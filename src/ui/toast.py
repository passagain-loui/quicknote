"""Toast แจ้งเตือนมุมขวาล่าง (in-app, DESIGN_SPEC 6.2) — ToastManager

กติกาที่ห้ามพลาด:
- ห้าม transient (C6): transient จะ "ตาม state ของ root" ถ้า root ถูก withdraw/ย่อ toast จะหายไปด้วย
  ทั้งที่นั่นคือตอนที่ต้องการแจ้งเตือนที่สุด → ใช้ overrideredirect + -topmost อย่างเดียว
- toast ไม่แตะ DB: เรียกแต่ callback ที่ได้รับมา (board/scheduler เป็นคนเขียน DB)
- ✕ / Esc = on_dismiss เสมอ (H7) ไม่งั้นโน้ตค้างสถานะ "กำลังดัง" ถาวร
"""

from __future__ import annotations

import logging
import unicodedata
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import ttk
from typing import Callable

from ..core import reminders
from . import win11
from .icons import glyph
from .strings import t
from .widgets import IconButton, fade_in, fade_out, px, slide_y

try:  # winsound มีเฉพาะ Windows; platform อื่นแค่ไม่มีเสียง
    import winsound
except ImportError:  # pragma: no cover
    winsound = None

log = logging.getLogger(__name__)

_WIDTH = 364      # px ที่ 96 DPI (spec 6.2)
_MARGIN = 12      # ห่างขอบ work area
_GAP = 8          # ห่างระหว่าง toast ที่ซ้อนกัน
_PAD = 16         # padding ในตัว toast
_SLIDE = 16       # ระยะ slide ตอนเข้า
_MISSED_KEY = "__missed__"
_MISSED_MAX_TITLES = 5
ICON_FILE = Path(__file__).resolve().parents[2] / "assets" / "icon.ico"

# สระนำของไทย: ห้ามค้างท้ายบรรทัด (จะลอยแยกจากพยัญชนะที่ตามมา)
_THAI_LEADING_VOWELS = "เแโใไ"


def _now() -> datetime:
    """แยกเป็นฟังก์ชันเพื่อให้ test ตรึงเวลาได้โดยไม่ต้อง mock datetime ทั้งโมดูล"""
    return datetime.now()


# ---------------------------------------------------------------- ตัดข้อความ
def wrap_clamp(text: str, font, width: int, max_lines: int) -> str:
    """ตัดบรรทัดเองตามความกว้างพิกเซล แล้วจำกัดไม่เกิน max_lines (ต่อท้าย … ถ้าถูกตัด)

    ทำเองเพราะ Label ไม่มี "จำกัดจำนวนบรรทัดหลัง wrap" และภาษาไทยไม่มีช่องว่างให้ตัดคำ
    — ตัดที่ช่องว่างล่าสุดถ้ามี ไม่งั้นตัดตรงขอบ แต่ไม่แยกวรรณยุกต์/สระบน-ล่างออกจากพยัญชนะ
    """
    width = max(width, 20)
    lines: list[str] = []
    for para in text[:600].splitlines():
        para = para.strip()
        if not para:
            continue
        cur = ""
        for ch in para:
            if unicodedata.category(ch) in ("Mn", "Me"):
                cur += ch  # เครื่องหมายผสม: กว้าง 0 ต้องติดพยัญชนะเดิมเสมอ
                continue
            if font.measure(cur + ch) <= width:
                cur += ch
                continue
            sp = cur.rfind(" ")
            if sp > 0:
                lines.append(cur[:sp])
                cur = cur[sp + 1:] + ch
            elif cur and cur[-1] in _THAI_LEADING_VOWELS:
                lines.append(cur[:-1])
                cur = cur[-1] + ch
            else:
                lines.append(cur)
                cur = ch
        if cur:
            lines.append(cur)
    if not lines:
        return ""
    cut = len(lines) > max_lines
    lines = lines[:max_lines]
    if cut:
        last = lines[-1]
        while last and font.measure(last + "…") > width:
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"
    return "\n".join(lines)


# ---------------------------------------------------------------- toast เดี่ยว
class _Toast:
    """หน้าต่าง toast หนึ่งอัน — manager เป็นคนจัดตำแหน่ง/ลำดับ

    buttons: [(ข้อความ, เป็นปุ่มหลักไหม, handler(button))] กว้างเท่ากันทุกปุ่ม
    """

    def __init__(self, mgr: "ToastManager", key: str, caption: str, title: str, body: str,
                 buttons: list[tuple[str, bool, Callable[[ttk.Button], None]]],
                 on_dismiss: Callable[[], None] | None, close_tip: str,
                 auto_seconds: float | None = None) -> None:
        self.mgr = mgr
        self.key = key
        self.on_dismiss = on_dismiss
        self.finished = False
        self.menu: tk.Menu | None = None
        self.spacer: tk.Frame | None = None
        self.buttons: list[ttk.Button] = []
        self._auto_job: str | None = None
        th, root = mgr.theme, mgr.root

        self.win = tk.Toplevel(root)
        self.win.withdraw()
        self.win.overrideredirect(True)  # ห้ามใช้ transient (C6)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=th.c("stroke"))  # พื้น Toplevel = ขอบ 1px (body เว้นขอบ 1px)
        win11.apply_titlebar(self.win, th.mode == "dark", None)  # ขอ DWM มุมโค้งให้ (Win10 ล้มเหลวเงียบ ๆ)

        self.width = px(root, _WIDTH)
        pad = px(root, _PAD)
        inner_w = self.width - 2 * pad - 2

        self.body = tk.Frame(self.win, bg=th.c("surface"), bd=0, highlightthickness=0)
        self.body.pack(fill="both", expand=True, padx=1, pady=1)

        # --- header: ไอคอนแอป + "QuickNote · 14:30" + ✕
        head = tk.Frame(self.body, bg=th.c("surface"))
        head.pack(fill="x", padx=(pad, px(root, 8)), pady=(px(root, 8), 0))
        self.head = head
        img = mgr.app_icon()
        if img is not None:
            self.icon_lbl = tk.Label(head, image=img, bg=th.c("surface"), bd=0)
        else:
            self.icon_lbl = tk.Label(head, text=glyph("clock"), font=th.font("icon10"),
                                     bg=th.c("surface"), fg=th.c("accent"), bd=0)
        self.icon_lbl.pack(side="left", padx=(0, px(root, 8)))
        self.caption_lbl = tk.Label(head, text=caption, font=th.font("caption"), bg=th.c("surface"),
                                    fg=th.c("text_secondary"), anchor="w")
        self.caption_lbl.pack(side="left", fill="x", expand=True)
        self.close_btn = IconButton(head, th, glyph("cancel"), command=self.dismiss, tooltip=close_tip,
                                    size=28, base_bg=th.c("surface"))
        self.close_btn.pack(side="right")

        # --- title + body
        self.title_lbl: tk.Label | None = None
        if title:  # toast แบบ info ไม่มีหัวข้อ
            self.title_lbl = tk.Label(self.body, text=wrap_clamp(title, th.font("body_strong"), inner_w, 2),
                                      font=th.font("body_strong"), bg=th.c("surface"), fg=th.c("text"),
                                      anchor="w", justify="left")
            self.title_lbl.pack(fill="x", padx=pad, pady=(px(root, 4), 0))
        self.text_lbl: tk.Label | None = None
        if body:
            self.text_lbl = tk.Label(self.body, text=body, font=th.font("body"), bg=th.c("surface"),
                                     fg=th.c("text_secondary"), anchor="w", justify="left")
            self.text_lbl.pack(fill="x", padx=pad, pady=(px(root, 4), 0))

        # --- ปุ่มกว้างเท่ากัน
        if buttons:
            row = tk.Frame(self.body, bg=th.c("surface"))
            half = px(root, 4)  # ช่องไฟระหว่างปุ่มแบ่งซ้าย/ขวาเท่ากัน → ทุกปุ่มกว้างเท่ากันจริง
            row.pack(fill="x", padx=pad - half, pady=(px(root, 14), px(root, 16)))
            self.btn_row = row
            for i, (label, primary, handler) in enumerate(buttons):
                row.grid_columnconfigure(i, weight=1, uniform="toast_btn")
                base = "Accent.TButton" if primary else "TButton"
                btn = ttk.Button(row, text=label, style=th.ttk_style(base, "surface"), takefocus=True)
                btn.configure(command=lambda b=btn, h=handler: h(b))
                btn.grid(row=0, column=i, sticky="ew", padx=half)
                self.buttons.append(btn)
        else:
            self.btn_row = None
            self.spacer = tk.Frame(self.body, height=px(root, 14), bg=th.c("surface"))
            self.spacer.pack()

        self.win.bind("<Escape>", lambda _e: self.dismiss())
        # ปุ่ม ttk ไม่รับ focus ตอนคลิก → Esc จะไม่ถึง toast ถ้าไม่ดึง focus มาเอง (overrideredirect ไม่ได้ focus เอง)
        self.win.bind("<ButtonPress-1>", lambda _e: self._grab_focus(), add="+")
        self._unsub = th.subscribe(self.apply_theme)

        self.win.update_idletasks()
        self.height = self.win.winfo_reqheight()
        if auto_seconds:
            self._auto_job = self.win.after(int(auto_seconds * 1000), self.close_silently)

    # --- โต้ตอบ
    def _grab_focus(self) -> None:
        try:
            self.win.focus_force()
        except tk.TclError:
            pass

    def dismiss(self) -> None:
        """✕ / Esc → on_dismiss ครั้งเดียว"""
        self.finish(self.on_dismiss)

    def finish(self, callback: Callable[[], None] | None) -> None:
        """เรียก callback (ครั้งเดียวต่อ toast) แล้วปิด — callback พังต้องไม่ทำให้ toast ค้างจอ"""
        if self.finished:
            return
        self.finished = True
        if callback is not None:
            try:
                callback()
            except Exception:
                log.exception("toast callback failed")
        self.mgr.remove(self)

    def close_silently(self) -> None:
        """ปิดโดยไม่เรียก callback (close_for / auto-hide / แทนที่ด้วย toast ใหม่ของโน้ตเดิม)"""
        if self.finished:
            return
        self.finished = True
        self.mgr.remove(self)

    def popup_menu(self, button: ttk.Button) -> None:
        """เมนู "เลื่อน" ใต้ปุ่ม — บน Windows tk_popup บล็อกจนเมนูปิด จึงต้องไม่มี state ค้างระหว่างนั้น"""
        if self.menu is None:
            return
        try:
            x = button.winfo_rootx()
            y = button.winfo_rooty() + button.winfo_height()
            self.menu.tk_popup(x, y)
        finally:
            try:
                self.menu.grab_release()
            except tk.TclError:
                pass

    # --- ธีม
    def apply_theme(self) -> None:
        th = self.mgr.theme
        try:
            self.win.configure(bg=th.c("stroke"))
            for w in (self.body, self.head, self.btn_row, self.spacer, self.icon_lbl, self.caption_lbl,
                      self.title_lbl, self.text_lbl):
                if w is not None:
                    w.configure(bg=th.c("surface"))
            self.caption_lbl.configure(fg=th.c("text_secondary"))
            if self.title_lbl is not None:
                self.title_lbl.configure(fg=th.c("text"))
            if self.text_lbl is not None:
                self.text_lbl.configure(fg=th.c("text_secondary"))
            if self.icon_lbl.cget("image") == "":
                self.icon_lbl.configure(fg=th.c("accent"))
            self.close_btn.set_base_bg(th.c("surface"))
            win11.apply_titlebar(self.win, th.mode == "dark", None)
        except tk.TclError:
            pass

    def destroy(self) -> None:
        self._unsub()
        if self._auto_job is not None:
            try:
                self.win.after_cancel(self._auto_job)
            except (tk.TclError, ValueError):
                pass
            self._auto_job = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass


# ---------------------------------------------------------------- manager
class ToastManager:
    """จัดการ toast ทั้งแอป: วางมุมขวาล่างของ work area ซ้อนขึ้นบน, ไม่ซ้ำต่อโน้ต, เสียงตาม settings"""

    def __init__(self, root: tk.Misc, theme, settings) -> None:
        self.root = root
        self.theme = theme
        self.settings = settings
        self._toasts: list[_Toast] = []  # เรียงจากล่างสุดขึ้นบน
        self._icon_img = None
        self._icon_tried = False

    # ------------------------------------------------------------ public
    @property
    def toasts(self) -> tuple[_Toast, ...]:
        return tuple(self._toasts)

    def show_reminder(self, note: dict, on_done: Callable[[], None], on_snooze: Callable[[str], None],
                      on_open: Callable[[], None], on_dismiss: Callable[[], None]) -> None:
        """toast แจ้งเตือนโน้ตหนึ่งอัน — โน้ตเดิมมี toast อยู่แล้วจะถูกแทนที่ (M21)"""
        note_id = str(note.get("id", ""))
        when = note.get("reminder_datetime")
        try:
            hm = reminders.parse_dt(when).strftime("%H:%M")
        except (TypeError, ValueError):
            hm = _now().strftime("%H:%M")
        th = self.theme
        inner_w = px(self.root, _WIDTH) - 2 * px(self.root, _PAD) - 2
        title = (note.get("title") or "").strip() or t("common.untitled")
        body = wrap_clamp(note.get("content") or "", th.font("body"), inner_w, 3)

        holder: dict[str, _Toast] = {}

        def snooze_handler(btn: ttk.Button) -> None:
            holder["toast"].popup_menu(btn)

        buttons = [
            (t("toast.done"), True, lambda _b: holder["toast"].finish(on_done)),
            (t("toast.snooze") + "  ▾", False, snooze_handler),
            (t("toast.open"), False, lambda _b: holder["toast"].finish(on_open)),
        ]
        toast = _Toast(self, note_id, t("toast.header", time=hm), title, body, buttons, on_dismiss,
                       t("toast.dismiss_tip"))
        holder["toast"] = toast
        toast.menu = self._build_snooze_menu(toast, on_snooze)
        self._add(toast)
        self._play_sound()

    def show_missed(self, notes: list[dict], on_view: Callable[[], None]) -> None:
        """toast เดียวสรุปการแจ้งเตือนที่พลาด (H8) — ไม่ว่าจะกี่รายการ (กัน alarm storm)"""
        if not notes:
            return
        th = self.theme
        inner_w = px(self.root, _WIDTH) - 2 * px(self.root, _PAD) - 2
        lines = []
        for n in notes[:_MISSED_MAX_TITLES]:
            title = (n.get("title") or "").strip() or t("common.untitled")
            lines.append(wrap_clamp("• " + title, th.font("body"), inner_w, 1))
        if len(notes) > _MISSED_MAX_TITLES:
            lines.append(t("toast.missed_more", n=len(notes) - _MISSED_MAX_TITLES))
        holder: dict[str, _Toast] = {}
        buttons = [(t("toast.missed_view"), True, lambda _b: holder["toast"].finish(on_view))]
        toast = _Toast(self, _MISSED_KEY, t("app.name"), t("toast.missed", n=len(notes)), "\n".join(lines),
                       buttons, None, t("common.close"))
        holder["toast"] = toast
        self._add(toast)
        self._play_sound()

    def show_info(self, message: str, seconds: float = 6) -> None:
        """ข้อความสั้น ๆ ที่หายเอง (เช่น hint "ยังทำงานอยู่ในถาด")"""
        th = self.theme
        inner_w = px(self.root, _WIDTH) - 2 * px(self.root, _PAD) - 2
        body = wrap_clamp(message, th.font("body"), inner_w, 4)
        toast = _Toast(self, "", t("app.name"), "", body, [], None, t("common.close"), auto_seconds=seconds)
        self._add(toast)

    def close_for(self, note_id: str) -> None:
        """ปิด toast ของโน้ตนี้โดยไม่เรียก callback (เช่น โน้ตถูก complete จากการ์ดแล้ว)"""
        if not note_id:
            return
        for toast in list(self._toasts):
            if toast.key == str(note_id):
                toast.close_silently()

    def close_all(self) -> None:
        """ปิดทุกอัน ไม่มี callback — ใช้ตอนปิดแอป"""
        for toast in list(self._toasts):
            toast.close_silently()

    # ------------------------------------------------------------ internals
    def app_icon(self):
        """ไอคอนแอป 16px (px-scaled) สำหรับ header; โหลดไม่ได้ → None (toast ใช้ glyph แทน)"""
        if not self._icon_tried:
            self._icon_tried = True
            try:
                from PIL import Image, ImageTk
                size = px(self.root, 16)
                with Image.open(ICON_FILE) as src:
                    img = src.convert("RGBA").resize((size, size), Image.LANCZOS)
                self._icon_img = ImageTk.PhotoImage(img, master=self.root)
            except Exception:
                log.debug("toast icon unavailable", exc_info=True)
                self._icon_img = None
        return self._icon_img

    def _build_snooze_menu(self, toast: _Toast, on_snooze: Callable[[str], None]) -> tk.Menu:
        menu = tk.Menu(toast.win, tearoff=False)
        for label_key, key in (("toast.snooze_5", "m5"), ("toast.snooze_15", "m15"),
                               ("toast.snooze_60", "h1"), ("toast.snooze_tomorrow", "tomorrow")):
            # คำนวณ "ตอนกด" ไม่ใช่ตอนสร้าง — toast อาจค้างอยู่นานก่อนผู้ใช้เลือก
            menu.add_command(label=t(label_key),
                             command=lambda k=key: toast.finish(lambda: on_snooze(self.snooze_time(k))))
        return menu

    @staticmethod
    def snooze_time(key: str, now: datetime | None = None) -> str:
        """when-string ("YYYY-MM-DD HH:MM") ของตัวเลือกเลื่อน: m5 | m15 | h1 | tomorrow"""
        now = now or _now()
        quick = reminders.quick_times(now)
        if key == "m5":
            return reminders.format_dt(now.replace(second=0, microsecond=0) + timedelta(minutes=5))
        return {"m15": quick["in15m"], "h1": quick["in1h"], "tomorrow": quick["tomorrow_9"]}[key]

    def _play_sound(self) -> None:
        if winsound is None or not self.settings.get("sound", True):
            return
        flags = winsound.SND_ALIAS | winsound.SND_ASYNC | winsound.SND_NODEFAULT
        for alias in ("Notification.Reminder", "SystemNotification"):
            try:
                winsound.PlaySound(alias, flags)
                return
            except Exception:
                continue  # alias ไม่มีในเครื่องนี้ → ลองตัวถัดไป; เสียงไม่ใช่เหตุให้แจ้งเตือนพัง

    def _layout(self) -> list[tuple[_Toast, int, int]]:
        """ตำแหน่งเป้าหมาย (x, y) ของทุก toast: ชิดมุมขวาล่างของ work area จอที่ root อยู่ ซ้อนขึ้นบน"""
        left, top, right, bottom = win11.get_work_area(self.root)
        margin, gap = px(self.root, _MARGIN), px(self.root, _GAP)
        out = []
        y_bottom = bottom - margin
        for toast in self._toasts:
            y = max(top, y_bottom - toast.height)
            out.append((toast, right - margin - toast.width, y))
            y_bottom = y_bottom - toast.height - gap
        return out

    def _add(self, toast: _Toast) -> None:
        # โน้ตเดิม/ข้อความสรุปเดิม → แทนที่ตำแหน่งเดิม (ไม่ซ้อนสองอัน)
        index = len(self._toasts)
        for i, old in enumerate(self._toasts):
            if toast.key and old.key == toast.key:  # key ว่าง = info ซ้ำได้
                index = i
                old.finished = True
                self._toasts.pop(i)
                old.destroy()
                break
        self._toasts.insert(index, toast)
        placed = {tt: (x, y) for tt, x, y in self._layout()}
        x, y = placed[toast]
        off = px(self.root, _SLIDE)
        toast.win.geometry(f"{toast.width}x{toast.height}+{x}+{y + off}")
        toast.win.deiconify()
        toast.win.update_idletasks()
        fade_in(toast.win, 150)
        slide_y(toast.win, -off, 150)
        self._restack(exclude=toast)

    def remove(self, toast: _Toast) -> None:
        """ถอด toast ออกจากลำดับทันที (ให้อันอื่นเลื่อนลงมาเลย) แล้วค่อย fade ตัวมันเองทิ้ง"""
        if toast in self._toasts:
            self._toasts.remove(toast)
        self._restack()
        win = toast.win
        try:
            if not win.winfo_exists():
                toast.destroy()
                return
            fade_out(win, 100, then=toast.destroy)
        except tk.TclError:
            toast.destroy()

    def _restack(self, exclude: _Toast | None = None) -> None:
        for toast, x, y in self._layout():
            if toast is exclude:
                continue
            try:
                dy = y - toast.win.winfo_y()
                if dy:
                    slide_y(toast.win, dy, 150)
            except tk.TclError:
                continue
