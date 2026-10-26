"""หน้าต่างตั้งค่า (สไตล์ Windows 11 Settings) — DESIGN_SPEC ข้อ 7, ARCHITECTURE ข้อ 6

- ทั้งหน้าเลื่อนได้ (Canvas + ttk.Scrollbar) ไม่มีแท็บ ไม่มีปุ่ม Save/Close
- ทุก control เรียก settings.set(...) ทันที (บันทึก + แจ้ง listener) ส่วนผู้ฟัง (board/theme/main) เป็นคน apply ผล
- เปลี่ยนภาษา/ธีมแล้วหน้าต่างนี้ปรับตามเอง (ภาษา = สร้างหน้าใหม่, ธีม = ย้อมสีใหม่)
"""

from __future__ import annotations

import logging
import os
import sys
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from ..core import database
from ..core.constants import APP_AUTHOR, APP_VERSION, MIN_ALPHA
from ..core.export import export_markdown
from ..platform.autostart import disable_autostart, enable_autostart, is_autostart_enabled
from . import win11
from .strings import get_language, set_language, t
from .theme import Theme
from .widgets import SettingsCard, px

log = logging.getLogger(__name__)

_ALPHA_SAVE_DELAY_MS = 400  # ลาก slider แล้วไม่ fsync ทุกพิกเซล — รอให้นิ่งก่อนค่อยเขียนดิสก์
_SNOOZE_CHOICES = (5, 10, 15, 30, 60)
_OPEN: "SettingsWindow | None" = None  # หน้าต่างที่เปิดอยู่ (singleton ทั้งแอป — H1) ให้ dialog ของ actions หาแม่เจอ


# ============================================================ hotkey capture (ฟังก์ชันล้วน ทดสอบได้ไม่ต้องมี Tk)
_MOD_KEYSYMS = {
    "Control_L": "ctrl", "Control_R": "ctrl", "Alt_L": "alt", "Alt_R": "alt",
    "Shift_L": "shift", "Shift_R": "shift", "Super_L": "cmd", "Super_R": "cmd", "Win_L": "cmd", "Win_R": "cmd",
}
_MOD_ORDER = ("ctrl", "alt", "shift", "cmd")
_IGNORED_KEYSYMS = {"Caps_Lock", "Num_Lock", "Scroll_Lock", "Meta_L", "Meta_R", "Multi_key"}
_STATE_CTRL, _STATE_SHIFT, _STATE_ALT = 0x4, 0x1, 0x20000  # บิต state ของ Tk บน Windows (ตรวจกับ keybd_event จริงแล้ว)
_NAMED_KEYS = {
    "space": "<space>", "Return": "<enter>", "Tab": "<tab>", "BackSpace": "<backspace>", "Delete": "<delete>",
    "Insert": "<insert>", "Home": "<home>", "End": "<end>", "Prior": "<page_up>", "Next": "<page_down>",
    "Left": "<left>", "Right": "<right>", "Up": "<up>", "Down": "<down>",
}
# VK ของแป้นเครื่องหมาย (OEM) → ตัวอักษรที่ pynput เข้าใจ ("+" ใช้ไม่ได้เพราะเป็นตัวคั่นของ combo)
_OEM_KEYS = {0xBA: ";", 0xBB: "=", 0xBC: ",", 0xBD: "-", 0xBE: ".", 0xBF: "/", 0xC0: "`",
             0xDB: "[", 0xDC: "\\", 0xDD: "]", 0xDE: "'"}


def key_token(keycode: int, keysym: str) -> str | None:
    """แป้นที่ไม่ใช่ modifier → token แบบ pynput (None = แป้นที่ไม่รองรับ)

    ใช้ virtual-key code ไม่ใช่ keysym: ตอนกด Ctrl+Alt Windows ถือเป็น AltGr และแป้นภาษาไทยจะให้ keysym เป็นตัวอักษรไทย
    (ทดสอบแล้ว: Ctrl+Alt+N ได้ keysym '??' แต่ keycode=78 เสมอ)
    """
    if 0x41 <= keycode <= 0x5A:
        return chr(keycode).lower()
    if 0x30 <= keycode <= 0x39:
        return chr(keycode)
    if 0x70 <= keycode <= 0x87:
        return f"<f{keycode - 0x6F}>"
    if keycode in _OEM_KEYS:
        return _OEM_KEYS[keycode]
    return _NAMED_KEYS.get(keysym)


def modifiers_from_state(state: int) -> set[str]:
    mods = set()
    if state & _STATE_CTRL:
        mods.add("ctrl")
    if state & _STATE_ALT:
        mods.add("alt")
    if state & _STATE_SHIFT:
        mods.add("shift")
    return mods


def compose_hotkey(mods: set[str], token: str) -> str:
    """{'alt','ctrl'}, 'n' → '<ctrl>+<alt>+n' (เรียง modifier คงที่ ค่าที่เทียบกันได้)"""
    return "+".join([f"<{m}>" for m in _MOD_ORDER if m in mods] + [token])


def format_hotkey(combo: str) -> str:
    """'<ctrl>+<alt>+n' → 'Ctrl+Alt+N' สำหรับแสดงผล"""
    names = {"cmd": "Win"}
    parts = []
    for tok in combo.split("+"):
        if tok.startswith("<") and tok.endswith(">"):
            word = tok[1:-1]
            parts.append(names.get(word) or "".join(p.capitalize() for p in word.split("_")))
        else:
            parts.append(tok.upper())
    return "+".join(parts)


# ============================================================ actions
@dataclass
class SettingsActions:
    """การกระทำที่ main/board เป็นเจ้าของ — หน้า Settings แค่เรียก (ไม่รู้ว่า DB/dialog ทำงานอย่างไร)"""
    backup: Callable[[], None]
    restore: Callable[[], None]
    export_markdown: Callable[[], None]
    open_data_folder: Callable[[], None]


def _dialog_parent(root: tk.Misc) -> tk.Misc:
    """file/message dialog ต้องมีแม่เป็นหน้าต่างตั้งค่าที่เปิดอยู่ ไม่งั้นไปโผล่หลังมันเมื่อ root เป็น topmost"""
    win = _OPEN
    if win is not None and not win._closed:
        return win.win
    return root


def make_default_actions(root: tk.Misc, on_restored: Callable[[], None]) -> SettingsActions:
    """actions มาตรฐาน: สำรอง/กู้คืน/ส่งออก/เปิดโฟลเดอร์ — on_restored ถูกเรียกเฉพาะเมื่อกู้คืนสำเร็จ (C9: board ต้อง rebuild)"""
    app = t("app.name")

    def backup() -> None:
        parent = _dialog_parent(root)
        path = filedialog.asksaveasfilename(
            parent=parent, title=t("dialog.backup.title"), defaultextension=".db",
            initialfile=f"notes_backup_{datetime.now():%Y%m%d}.db",
            filetypes=[(t("dialog.filetype.db"), "*.db"), (t("dialog.filetype.all"), "*.*")])
        if not path:
            return
        if database.backup_database(path):
            messagebox.showinfo(app, t("msg.backup_ok"), parent=parent)
        else:
            messagebox.showerror(t("common.error_title"), t("msg.backup_fail"), parent=parent)

    def restore() -> None:
        parent = _dialog_parent(root)
        path = filedialog.askopenfilename(
            parent=parent, title=t("dialog.restore.pick"),
            filetypes=[(t("dialog.filetype.db"), "*.db"), (t("dialog.filetype.all"), "*.*")])
        if not path:
            return
        if not messagebox.askyesno(t("dialog.restore.title"), t("dialog.restore.body"), icon="warning", parent=parent):
            return
        if not database.restore_database(path):
            messagebox.showerror(t("common.error_title"), t("msg.restore_fail"), parent=parent)
            return
        try:
            on_restored()  # ข้อมูลใน DB เปลี่ยนใต้เท้า board แล้ว → ต้องสร้างการ์ดใหม่จาก DB
        except Exception:
            log.exception("on_restored failed")
        messagebox.showinfo(app, t("msg.restore_ok"), parent=parent)

    def export() -> None:
        parent = _dialog_parent(root)
        path = filedialog.asksaveasfilename(
            parent=parent, title=t("dialog.export.title"), defaultextension=".md",
            initialfile=f"notes_export_{datetime.now():%Y%m%d}.md",
            filetypes=[(t("dialog.filetype.md"), "*.md"), (t("dialog.filetype.all"), "*.*")])
        if not path:
            return
        if export_markdown(path, get_language()):
            messagebox.showinfo(app, t("msg.export_ok"), parent=parent)
        else:
            messagebox.showerror(t("common.error_title"), t("msg.export_fail"), parent=parent)

    def open_data_folder() -> None:
        live = database._get_db_file()
        folder = database.get_app_dir() if live == ":memory:" else Path(live).parent
        try:
            os.startfile(str(folder))
        except OSError:
            log.exception("cannot open data folder")
            messagebox.showerror(t("common.error_title"), t("msg.open_folder_fail"), parent=_dialog_parent(root))

    return SettingsActions(backup=backup, restore=restore, export_markdown=export, open_data_folder=open_data_folder)


# ============================================================ hotkey recorder
class _HotkeyRecorder:
    """ปุ่มแสดงคีย์ลัดปัจจุบัน — คลิกแล้ว "กดคีย์ลัด…" จับ combo ถัดไป, Esc/คลิกที่อื่น = ยกเลิก"""

    def __init__(self, parent: tk.Misc, owner: "SettingsWindow", card: SettingsCard, name: str) -> None:
        self.owner, self.name = owner, name
        self.recording = False
        self._held: set[str] = set()
        self._err_job: str | None = None
        self.frame = tk.Frame(parent, bd=0, highlightthickness=0)
        owner._track(self.frame, bg="card")
        self.button = ttk.Button(self.frame, width=18, style=card.ttk_style("TButton"), command=self.start)
        self.button.grid(row=0, column=0, sticky="e")
        self.error = tk.Label(self.frame, font=owner.theme.font("caption"), anchor="e", justify="right")
        owner._track(self.error, bg="card", fg="critical")
        self.error.grid(row=1, column=0, sticky="e")
        self.error.grid_remove()
        self.frame.grid_columnconfigure(0, weight=1)
        self.button.bind("<KeyPress>", self._on_press)
        self.button.bind("<KeyRelease>", self._on_release)
        self.button.bind("<FocusOut>", lambda _e: self.cancel())
        self.refresh()

    def refresh(self) -> None:
        combo = self.owner.settings.get("hotkeys", {}).get(self.name, "")
        self.button.configure(text=format_hotkey(combo) if combo else "—")

    def start(self) -> None:
        self.recording = True
        self._held.clear()
        self._clear_error()
        self.button.configure(text=t("settings.hotkey.recording"))
        self.button.focus_set()

    def cancel(self) -> None:
        if not self.recording:
            return
        self.recording = False
        self._held.clear()
        self._clear_error()
        try:
            self.refresh()
        except tk.TclError:
            pass  # หน้าต่างกำลังถูกทำลาย

    # --- keyboard
    def _on_press(self, e: tk.Event) -> str | None:
        if not self.recording:
            return None  # ไม่ได้อัดอยู่ → Space/Enter ทำงานตามปกติของปุ่ม
        if e.keysym == "Escape":
            self.cancel()
            return "break"
        group = _MOD_KEYSYMS.get(e.keysym)
        if group:
            self._held.add(group)
            self._preview()
            return "break"
        if e.keysym in _IGNORED_KEYSYMS:
            return "break"
        token = key_token(e.keycode, e.keysym)
        if token is not None:
            self._finish(modifiers_from_state(e.state) | self._held, token)
        return "break"

    def _on_release(self, e: tk.Event) -> str | None:
        if not self.recording:
            return None
        group = _MOD_KEYSYMS.get(e.keysym)
        if group:
            self._held.discard(group)
            self._preview()
        return "break"

    def _preview(self) -> None:
        """กด modifier ค้างอยู่ → แสดง "Ctrl+Alt+…" ให้เห็นว่าระบบรับแล้ว"""
        if self._held:
            self.button.configure(text="+".join(format_hotkey(f"<{m}>") for m in _MOD_ORDER if m in self._held) + "+…")
        else:
            self.button.configure(text=t("settings.hotkey.recording"))

    def _finish(self, mods: set[str], token: str) -> None:
        if not mods & {"ctrl", "alt", "cmd"}:
            # Shift อย่างเดียวไม่นับ: คีย์ลัดทั้งระบบที่ไม่มี Ctrl/Alt/Win จะแย่งการพิมพ์ปกติของทุกโปรแกรม
            self._show_error(t("settings.hotkey.invalid"))
            return
        combo = compose_hotkey(mods, token)
        others = {v for k, v in self.owner.settings.get("hotkeys", {}).items() if k != self.name}
        if combo in others:
            self._show_error(t("settings.hotkey.duplicate"))
            return
        self.recording = False
        self._held.clear()
        self._clear_error()
        self.owner._set_hotkey(self.name, combo)
        self.refresh()

    # --- error line
    def _show_error(self, message: str) -> None:
        self._clear_error()
        self.error.configure(text=message)
        self.error.grid()
        self._preview()
        self._err_job = self.frame.after(3000, self._clear_error)

    def _clear_error(self) -> None:
        if self._err_job is not None:
            try:
                self.frame.after_cancel(self._err_job)
            except (tk.TclError, ValueError):
                pass
            self._err_job = None
        try:
            self.error.grid_remove()
        except tk.TclError:
            pass


# ============================================================ slider
class _Slider(tk.Canvas):
    """สไลเดอร์แบบ Win11 (ราง + ส่วนเติมสี accent + ปุ่มกลม) วาดเอง

    ใช้แทน ttk.Scale เพราะ sprite ของ sv-ttk ฝังสีพื้นหลังของธีม sv เองไว้ในรูป (#1c1c1c/#fafafa)
    วางบน SettingsCard จึงเป็นกล่องสี่เหลี่ยมหลังสไลเดอร์ ซึ่งแก้ด้วย style option ไม่ได้
    """

    def __init__(self, parent: tk.Misc, theme: Theme, lo: int, hi: int, value: int,
                 command: Callable[[int], None], width: int = 130) -> None:
        self._theme, self._lo, self._hi, self._cmd = theme, lo, hi, command
        self._value = max(lo, min(hi, int(value)))
        self._pad = px(parent, 10)
        hl = 2
        super().__init__(parent, width=px(parent, width), height=px(parent, 28), bd=0, takefocus=True,
                         highlightthickness=hl)
        for ev, step in (("<Left>", -1), ("<Down>", -1), ("<Right>", 1), ("<Up>", 1), ("<Prior>", 10), ("<Next>", -10)):
            self.bind(ev, lambda _e, d=step: self._nudge(d))
        self.bind("<Home>", lambda _e: self.move_to(self._lo))
        self.bind("<End>", lambda _e: self.move_to(self._hi))
        self.bind("<ButtonPress-1>", self._on_mouse)
        self.bind("<B1-Motion>", self._on_mouse)
        for ev in ("<FocusIn>", "<FocusOut>", "<Configure>"):
            self.bind(ev, lambda _e: self.repaint(), add="+")
        self.repaint()

    def get(self) -> int:
        return self._value

    def set(self, value: float) -> None:
        """ตั้งค่าเฉพาะการแสดงผล (ไม่เรียก command) — ใช้ตอน sync จาก settings"""
        self._value = max(self._lo, min(self._hi, round(value)))
        self.repaint()

    def move_to(self, value: float) -> None:
        """ผู้ใช้ขยับ: clamp แล้วเรียก command เมื่อค่าเปลี่ยน"""
        before = self._value
        self.set(value)
        if self._value != before:
            self._cmd(self._value)

    def _nudge(self, delta: int) -> str:
        self.move_to(self._value + delta)
        return "break"

    def _on_mouse(self, e: tk.Event) -> None:
        self.focus_set()
        x0, x1 = self._pad, max(self._pad + 1, self.winfo_width() - self._pad)
        frac = max(0.0, min(1.0, (e.x - x0) / (x1 - x0)))
        self.move_to(self._lo + frac * (self._hi - self._lo))

    def repaint(self) -> None:
        th = self._theme
        try:
            self.configure(bg=th.c("card"), highlightbackground=th.c("card"), highlightcolor=th.c("accent"))
            self.delete("all")
            w, h = self.winfo_width(), self.winfo_height()
            if w < 2:
                return
            x0, x1, y = self._pad, w - self._pad, h / 2
            xv = x0 + (self._value - self._lo) / (self._hi - self._lo) * (x1 - x0)
            track = max(2, px(self, 4))
            self.create_line(x0, y, x1, y, width=track, fill=th.c("stroke_strong"), capstyle="round")
            self.create_line(x0, y, xv, y, width=track, fill=th.c("accent"), capstyle="round")
            outer, inner = px(self, 10), px(self, 6)
            self.create_oval(xv - outer, y - outer, xv + outer, y + outer, fill=th.c("surface"),
                             outline=th.c("stroke_strong"))
            self.create_oval(xv - inner, y - inner, xv + inner, y + inner, fill=th.c("accent"), outline="")
        except tk.TclError:
            pass  # กำลังถูกทำลาย


# ============================================================ window
class SettingsWindow:
    """singleton ทั้งแอปเป็นหน้าที่ของผู้เรียก (board.open_settings) — ที่นี่แค่ lift() ถ้าต้องการเรียกซ้ำ"""

    def __init__(self, root: tk.Tk, settings, theme: Theme, actions: SettingsActions,
                 on_close: Callable[[], None]) -> None:
        global _OPEN
        self.root, self.settings, self.theme, self.actions = root, settings, theme, actions
        self._on_close = on_close
        self._closed = False
        self._busy = False                         # กำลังอัปเดต control จาก/ไป settings → อย่าวนกลับ
        self._themed: list[tuple[tk.Widget, dict[str, str]]] = []
        self._syncers: dict[str, Callable[[], None]] = {}
        self.controls: dict[str, tk.Widget] = {}   # ชื่อ → widget (ให้ test และ debug เข้าถึง)
        self._recorders: dict[str, _HotkeyRecorder] = {}
        self._alpha_job: str | None = None
        self._alpha_dirty = False
        self._rebuild_job: str | None = None
        self._theme_job: str | None = None

        win = self.win = tk.Toplevel(root)
        win.withdraw()
        win.title(t("settings.title"))
        self._set_icon()
        # transient เฉพาะตอน root มองเห็น: ให้ติดอยู่เหนือหน้าต่างหลักที่ปักบนสุด แต่ถ้า root ถูก withdraw
        # (ซ่อนลงถาด) หน้าต่าง transient จะหายตามไปด้วย จึงต้องไม่ผูกตอนนั้น
        if self._root_viewable():
            win.transient(root)
        win.minsize(px(win, 420), px(win, 360))
        win.protocol("WM_DELETE_WINDOW", self._close)
        win.bind("<Escape>", lambda _e: self._close(), add="+")
        win.bind("<Destroy>", self._on_destroy, add="+")

        shell = self._shell = tk.Frame(win, bd=0, highlightthickness=0)
        shell.pack(fill="both", expand=True)
        shell.grid_rowconfigure(0, weight=1)
        shell.grid_columnconfigure(0, weight=1)
        self._canvas = tk.Canvas(shell, bd=0, highlightthickness=0, yscrollincrement=px(win, 20))
        self._scrollbar = ttk.Scrollbar(shell, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._scrollbar.set)
        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._scrollbar.grid(row=0, column=1, sticky="ns")
        self._inner = tk.Frame(self._canvas, bd=0, highlightthickness=0)
        self._inner_id = self._canvas.create_window(0, 0, window=self._inner, anchor="nw")
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfigure(self._inner_id, width=e.width))
        self._inner.bind("<Configure>", lambda _e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        win.bind("<MouseWheel>", self._on_wheel, add="+")
        win.bind("<FocusIn>", self._on_focus_in, add="+")

        self._unsub_theme = theme.subscribe(self._on_theme)
        settings.subscribe(self._on_setting)
        _OPEN = self

        self._paint_containers()  # ก่อนสร้างการ์ด: การ์ดอ่านสีพื้นจาก parent ตอนสร้าง (ไม่งั้นได้สีเทาของระบบ)
        self._build_page()
        self._place()
        win.deiconify()
        theme.apply_window(win)
        self._paint()
        win.lift()

    # ------------------------------------------------------------ public
    def lift(self) -> None:
        """เรียกซ้ำจาก board/tray เมื่อเปิดอยู่แล้ว — ดึงขึ้นหน้าสุดแม้ root จะซ่อนอยู่"""
        if self._closed:
            return
        try:
            if not self._root_viewable():
                self.win.transient("")  # transient กับ root ที่ซ่อนอยู่ = หน้าต่างนี้ถูกซ่อนด้วย
            if self.win.state() in ("iconic", "withdrawn"):
                self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
        except tk.TclError:
            pass

    # ------------------------------------------------------------ window helpers
    def _root_viewable(self) -> bool:
        try:
            return bool(self.root.winfo_viewable())
        except tk.TclError:
            return False

    def _set_icon(self) -> None:
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
        try:
            self.win.iconbitmap(str(base / "assets" / "icon.ico"))
        except tk.TclError:
            pass  # ไม่มีไอคอนก็เปิดได้ (ใช้ไอคอน Tk มาตรฐาน)

    def _place(self) -> None:
        """วางข้างหน้าต่างหลัก (ขวา → ซ้าย → กลางจอ) และไม่เกิน work area"""
        win = self.win
        left, top, right, bottom = win11.get_work_area(self.root)
        w = min(px(win, 520), right - left)
        h = min(px(win, 640), bottom - top)
        gap = px(win, 8)
        if self._root_viewable():
            rx, ry, rw = self.root.winfo_rootx(), self.root.winfo_rooty(), self.root.winfo_width()
            if rx + rw + gap + w <= right:
                x = rx + rw + gap
            elif rx - gap - w >= left:
                x = rx - gap - w
            else:
                x = left + (right - left - w) // 2
            y = ry - px(win, 32)
        else:
            x, y = left + (right - left - w) // 2, top + (bottom - top - h) // 2
        x = max(left, min(x, right - w))
        y = max(top, min(y, bottom - h))
        win.geometry(f"{w}x{h}+{x}+{y}")

    # ------------------------------------------------------------ scrolling
    def _on_wheel(self, e: tk.Event) -> str | None:
        if self._closed:
            return None
        self._canvas.yview_scroll(int(-e.delta / 120) * 3, "units")
        return "break"

    def _guard_wheel(self, widget: tk.Widget) -> None:
        """Combobox/Scale มี binding ล้อเมาส์ของตัวเอง (เปลี่ยนค่า!) → เลื่อนหน้าแทน ไม่ให้ค่าเปลี่ยนโดยไม่ตั้งใจ"""
        widget.bind("<MouseWheel>", self._on_wheel)

    def _on_focus_in(self, e: tk.Event) -> None:
        """Tab ไปถึง control ที่อยู่นอกจอ → เลื่อนให้เห็น (keyboard accessibility)"""
        w = e.widget
        try:
            if not str(w).startswith(str(self._inner) + "."):
                return
            top = w.winfo_rooty() - self._inner.winfo_rooty()
            bottom = top + w.winfo_height()
            total = max(1, self._inner.winfo_height())
            view_top = self._canvas.canvasy(0)
            view_h = self._canvas.winfo_height()
            margin = px(self.win, 24)
            if top - margin < view_top:
                self._canvas.yview_moveto(max(0, top - margin) / total)
            elif bottom + margin > view_top + view_h:
                self._canvas.yview_moveto((bottom + margin - view_h) / total)
        except tk.TclError:
            pass

    # ------------------------------------------------------------ theme
    def _track(self, widget: tk.Widget, **tokens: str) -> tk.Widget:
        """ผูก tk widget กับ token สี — ย้อมสีใหม่ตอนธีมเปลี่ยน (ttk/SettingsCard จัดการตัวเอง)"""
        self._themed.append((widget, tokens))
        widget.configure(**{opt: self.theme.c(tok) for opt, tok in tokens.items()})
        return widget

    def _paint_containers(self) -> None:
        for w in (self._shell, self._canvas, self._inner):
            w.configure(bg=self.theme.c("bg"))

    def _paint(self) -> None:
        th = self.theme
        for widget, tokens in self._themed:
            try:
                widget.configure(**{opt: th.c(tok) for opt, tok in tokens.items()})
            except tk.TclError:
                pass
        self._paint_containers()
        slider = self.controls.get("alpha")
        if isinstance(slider, _Slider):
            slider.repaint()

    def _on_theme(self) -> None:
        if self._closed:
            return
        # พื้นหลังของ container ต้องเปลี่ยน "ทันที": การ์ดตั้งค่าจะอ่านสีพื้นจาก parent ตอน apply_theme ของตัวเอง
        self._paint_containers()
        if self._theme_job is not None:
            return

        def apply() -> None:
            self._theme_job = None
            if self._closed:
                return
            try:
                self.theme.apply_window(self.win)
                self._paint()
            except tk.TclError:
                pass
        self._theme_job = self.win.after_idle(apply)

    # ------------------------------------------------------------ settings → window
    def _on_setting(self, key: str, value: object) -> None:
        """ค่าเปลี่ยนจากที่อื่น (Ctrl+T ในหน้าหลัก ฯลฯ) → control ในหน้านี้ต้องตาม"""
        if self._closed or self._busy:
            return
        if key == "language":
            set_language(str(value))
            self._schedule_rebuild()
            return
        sync = self._syncers.get(key)
        if sync is not None:
            self._busy = True
            try:
                sync()
            except tk.TclError:
                pass
            finally:
                self._busy = False

    def _commit(self, key: str, value: object, save: bool = True) -> None:
        """control → settings (บันทึก + แจ้ง listener) โดยไม่ให้ listener ของหน้านี้วนกลับมา"""
        self._busy = True
        try:
            self.settings.set(key, value, save=save)
        finally:
            self._busy = False

    def _set_hotkey(self, name: str, combo: str) -> None:
        # dict ใหม่ทุกครั้ง: set() เทียบค่าเดิมด้วย == จึงจะรู้ว่าเปลี่ยน (แก้ dict เดิมแล้วส่งกลับ = ไม่แจ้ง listener)
        hotkeys = dict(self.settings.get("hotkeys", {}))
        hotkeys[name] = combo
        self._commit("hotkeys", hotkeys)

    def _schedule_rebuild(self) -> None:
        if self._rebuild_job is None:
            # รอ idle: ผู้เรียกอาจเป็น <<ComboboxSelected>> ของ control ที่กำลังจะถูกทำลาย
            self._rebuild_job = self.win.after_idle(self._rebuild)

    def _rebuild(self) -> None:
        self._rebuild_job = None
        if self._closed:
            return
        top = self._canvas.yview()[0]
        self.win.title(t("settings.title"))
        self._build_page()
        self.win.update_idletasks()
        self._canvas.yview_moveto(top)

    # ------------------------------------------------------------ page
    def _build_page(self) -> None:
        for child in self._inner.winfo_children():
            child.destroy()
        self._themed.clear()
        self._syncers.clear()
        self.controls.clear()
        self._recorders.clear()
        th, win = self.theme, self.win
        pad = px(win, 24)

        title = tk.Label(self._inner, text=t("settings.title"), font=th.font("title"), anchor="w")
        self._track(title, bg="bg", fg="text")
        title.pack(fill="x", padx=pad, pady=(px(win, 16), 0))

        self._group(t("settings.group.appearance"), self._rows_appearance)
        self._group(t("settings.group.behavior"), self._rows_behavior)
        self._group(t("settings.group.notifications"), self._rows_notifications)
        self._group(t("settings.group.data"), self._rows_data)
        self._group(t("settings.group.about"), self._rows_about)
        spacer = tk.Frame(self._inner, height=px(win, 24), bd=0, highlightthickness=0)
        self._track(spacer, bg="bg")
        spacer.pack(fill="x")
        self._paint()

    def _group(self, heading: str, fill: Callable[[SettingsCard], None]) -> None:
        pad = px(self.win, 24)
        lbl = tk.Label(self._inner, text=heading, font=self.theme.font("body_strong"), anchor="w")
        self._track(lbl, bg="bg", fg="text")
        lbl.pack(fill="x", padx=pad, pady=(px(self.win, 20), px(self.win, 8)))
        card = SettingsCard(self._inner, self.theme)
        card.pack(fill="x", padx=pad)
        fill(card)

    # --- row builders
    def _add_switch(self, card: SettingsCard, name: str, title: str, desc: str | None, get: Callable[[], bool],
                    set_: Callable[[bool], None]) -> ttk.Checkbutton:
        var = tk.BooleanVar(master=self.win, value=bool(get()))

        def changed() -> None:
            if not self._busy:
                set_(var.get())

        cb = card.add_row(title, desc, lambda p: ttk.Checkbutton(
            p, variable=var, command=changed, style=card.ttk_style("Switch.TCheckbutton")))
        self.controls[name] = cb
        self._syncers[name] = lambda: var.set(bool(get()))
        return cb

    def _add_setting_switch(self, card: SettingsCard, key: str, title: str, desc: str | None) -> None:
        self._add_switch(card, key, t(title), t(desc) if desc else None, lambda: self.settings.get(key),
                         lambda v: self._commit(key, v))

    def _add_combo(self, card: SettingsCard, key: str, title: str, desc: str | None,
                   options: list[tuple[object, str]], width: int, on_pick: Callable[[object], None]) -> ttk.Combobox:
        """combobox readonly ที่ map ป้ายแสดงผล ↔ ค่าจริง (ไม่อ่านข้อความอิสระ — บทเรียน M10)"""
        var = tk.StringVar(master=self.win)

        def label_for(value: object) -> str:
            return next((lab for val, lab in options if val == value), options[0][1])

        def picked(_e=None) -> None:
            idx = combo.current()
            combo.selection_clear()  # readonly combobox ค้างไฮไลต์น้ำเงินหลังเลือก
            if self._busy or not 0 <= idx < len(options):
                return
            on_pick(options[idx][0])

        combo = card.add_row(title, desc, lambda p: ttk.Combobox(
            p, state="readonly", textvariable=var, values=[lab for _, lab in options], width=width,
            style=card.ttk_style("TCombobox")))
        var.set(label_for(self.settings.get(key)))
        combo.bind("<<ComboboxSelected>>", picked)
        self._guard_wheel(combo)
        self.controls[key] = combo
        self._syncers[key] = lambda: var.set(label_for(self.settings.get(key)))
        return combo

    def _rows_appearance(self, card: SettingsCard) -> None:
        self._add_combo(card, "theme", t("settings.theme"), t("settings.theme.desc"),
                        [(m, t(f"settings.theme.{m}")) for m in ("system", "light", "dark")], 14,
                        lambda v: self._commit("theme", v))
        self._add_combo(card, "language", t("settings.language"), t("settings.language.desc"),
                        [("th", t("settings.language.th")), ("en", t("settings.language.en"))], 14,
                        self._pick_language)
        self._add_alpha(card)
        self._add_combo(card, "font_size", t("settings.font_size"), t("settings.font_size.desc"),
                        [(m, t(f"settings.font_size.{m}")) for m in ("small", "normal", "large")], 14,
                        lambda v: self._commit("font_size", v))
        self._add_setting_switch(card, "compact", "settings.compact", "settings.compact.desc")

    def _rows_behavior(self, card: SettingsCard) -> None:
        self._add_autostart(card)
        self._add_setting_switch(card, "always_on_top", "settings.always_on_top", "settings.always_on_top.desc")
        self._add_setting_switch(card, "close_to_tray", "settings.close_to_tray", "settings.close_to_tray.desc")
        for name, title in (("new_note", "settings.hotkey_new"), ("toggle_show", "settings.hotkey_toggle")):
            rec = card.add_row(t(title), t("settings.hotkey.desc"),
                               lambda p, n=name: self._make_recorder(p, card, n))
            self.controls[f"hotkey_{name}"] = rec

    def _rows_notifications(self, card: SettingsCard) -> None:
        self._add_setting_switch(card, "sound", "settings.sound", "settings.sound.desc")
        options = [(m, t("settings.snooze.hour") if m == 60 else t("settings.snooze.minutes", n=m))
                   for m in _SNOOZE_CHOICES]
        self._add_combo(card, "snooze_default_minutes", t("settings.snooze"), t("settings.snooze.desc"),
                        options, 10, lambda v: self._commit("snooze_default_minutes", v))

    def _rows_data(self, card: SettingsCard) -> None:
        self._add_setting_switch(card, "auto_backup", "settings.auto_backup", "settings.auto_backup.desc")
        for name, title, desc, button, action in (
                ("backup", "settings.backup", "settings.backup.desc", "settings.backup.button", self.actions.backup),
                ("restore", "settings.restore", "settings.restore.desc", "settings.restore.button",
                 self.actions.restore),
                ("export", "settings.export", "settings.export.desc", "settings.export.button",
                 self.actions.export_markdown),
                ("open_folder", "settings.open_folder", None, "settings.open_folder.button",
                 self.actions.open_data_folder)):
            btn = card.add_row(t(title), t(desc) if desc else None, lambda p, b=button, a=action: ttk.Button(
                p, text=t(b), style=card.ttk_style("TButton"), command=a))
            self.controls[name] = btn

    def _rows_about(self, card: SettingsCard) -> None:
        text = t("settings.about", version=APP_VERSION, author=APP_AUTHOR)
        card.add_row(text, None, lambda p: self._track(tk.Frame(p, width=1, height=1, bd=0, highlightthickness=0),
                                                       bg="card"))

    # --- special rows
    def _pick_language(self, lang: object) -> None:
        set_language(str(lang))  # ก่อน settings.set: listener ของ board ที่ relabel ด้วย t() ต้องเห็นภาษาใหม่แล้ว
        self._commit("language", lang)
        self._schedule_rebuild()

    def _add_autostart(self, card: SettingsCard) -> None:
        var = tk.BooleanVar(master=self.win, value=is_autostart_enabled())

        def changed() -> None:
            want = var.get()
            ok = enable_autostart() if want else disable_autostart()
            actual = is_autostart_enabled()  # เชื่อสถานะจริงบนดิสก์ ไม่ใช่ค่าที่คืนมา
            if not ok or actual != want:
                var.set(actual)  # L13: คืนสวิตช์ให้ตรงความจริง + บอกผู้ใช้
                messagebox.showerror(t("common.error_title"), t("settings.autostart.error"), parent=self.win)

        self.controls["autostart"] = card.add_row(
            t("settings.autostart"), t("settings.autostart.desc"),
            lambda p: ttk.Checkbutton(p, variable=var, command=changed, style=card.ttk_style("Switch.TCheckbutton")))

    def _add_alpha(self, card: SettingsCard) -> None:
        parts: dict[str, tk.Widget] = {}
        current = self._alpha_percent()

        def build(p: tk.Widget) -> tk.Widget:
            frame = tk.Frame(p, bd=0, highlightthickness=0)
            self._track(frame, bg="card")
            label = tk.Label(frame, width=5, anchor="e", font=self.theme.font("body"))
            self._track(label, bg="card", fg="text_secondary")
            slider = _Slider(frame, self.theme, round(MIN_ALPHA * 100), 100, current, self._on_alpha)
            self._guard_wheel(slider)
            slider.pack(side="left")
            label.pack(side="left", padx=(px(self.win, 6), 0))
            parts.update(slider=slider, label=label)
            return frame

        card.add_row(t("settings.alpha"), t("settings.alpha.desc"), build)
        self.controls["alpha"] = parts["slider"]
        self.controls["alpha_label"] = parts["label"]

        def sync() -> None:
            value = self._alpha_percent()
            parts["slider"].set(value)
            parts["label"].configure(text=f"{value}%")
        self._syncers["alpha"] = sync
        sync()

    def _alpha_percent(self) -> int:
        try:
            return round(float(self.settings.get("alpha", 1.0)) * 100)
        except (TypeError, ValueError):
            return 100  # settings.data ถูกแก้มือเป็นค่าแปลก ๆ — อย่าให้หน้าต่างเปิดไม่ได้

    def _on_alpha(self, percent: int) -> None:
        """ลาก slider: ใช้ผลทันที (listener ของ board) แต่เลื่อนการเขียนดิสก์ไปจนนิ่ง"""
        self._commit("alpha", percent / 100, save=False)
        self.controls["alpha_label"].configure(text=f"{self._alpha_percent()}%")  # ค่าที่ผ่าน clamp แล้ว (ไม่ต่ำกว่า MIN_ALPHA)
        self._alpha_dirty = True
        if self._alpha_job is not None:
            self.win.after_cancel(self._alpha_job)
        self._alpha_job = self.win.after(_ALPHA_SAVE_DELAY_MS, self._flush_alpha)

    def _flush_alpha(self) -> None:
        self._alpha_job = None
        if self._alpha_dirty:
            self._alpha_dirty = False
            self.settings.save()

    def _make_recorder(self, parent: tk.Widget, card: SettingsCard, name: str) -> tk.Widget:
        rec = _HotkeyRecorder(parent, self, card, name)
        self._recorders[name] = rec
        self._syncers["hotkeys"] = lambda: [r.refresh() for r in self._recorders.values()]
        return rec.frame

    # ------------------------------------------------------------ close
    def _close(self) -> None:
        self._shutdown(destroy=True)

    def _on_destroy(self, e: tk.Event) -> None:
        if e.widget is self.win:
            self._shutdown(destroy=False)  # ถูกทำลายจากข้างนอก (ปิด root) — ยังต้อง cleanup + แจ้ง on_close

    def _shutdown(self, destroy: bool) -> None:
        """ปิดทางเดียว: ล้าง timer/listener, เขียน alpha ที่ค้าง, ทำลายหน้าต่าง, แจ้ง on_close ครั้งเดียว (M13: ไม่ unbind_all)"""
        global _OPEN
        if self._closed:
            return
        self._closed = True
        if _OPEN is self:
            _OPEN = None
        for job in (self._alpha_job, self._rebuild_job, self._theme_job):
            if job is not None:
                try:
                    self.win.after_cancel(job)
                except (tk.TclError, ValueError):
                    pass
        self._alpha_job = self._rebuild_job = self._theme_job = None
        if self._alpha_dirty:
            self._alpha_dirty = False
            self.settings.save()
        self._unsub_theme()
        unsubscribe = getattr(self.settings, "unsubscribe", None)  # Settings ปัจจุบันยังไม่มี → _closed กัน callback ทำงานแทน
        if callable(unsubscribe):
            unsubscribe(self._on_setting)
        if destroy:
            try:
                self.win.destroy()
            except tk.TclError:
                pass
        try:
            self._on_close()
        except Exception:
            log.exception("settings on_close failed")
