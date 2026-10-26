"""Board — หน้าต่างหลักของ QuickNote v3 (DESIGN_SPEC 3.x/9, สัญญา ARCHITECTURE ข้อ 5)

หลักการ:
  - native window frame (ไม่ overrideredirect) — drag/resize/Snap/taskbar เป็นของ Windows
  - ลำดับการ์ดมาจาก SQL เท่านั้น: _load_notes() ถอดการ์ดทุกใบแล้ว pack ใหม่ตามลำดับ DB (แก้ C5)
    ไม่มี repack_card_to_top() / band-aid ใด ๆ
  - Board เป็นเจ้าของการเขียน DB ทั้งหมดของ UI (การ์ดแค่เรียก callback) และเป็นเจ้าของ flow ของ alarm
"""

from __future__ import annotations

import logging
import re
import sys
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Callable

from ..core import database as db
from ..core.models import Note
from ..core.reminders import format_dt, format_reminder
from . import strings
from .icons import ICONS
from .note_card import GLOBAL_SHORTCUTS, CARD_GAP_Y, CardCallbacks, NoteCard, ellipsize, forward_shortcuts
from .scheduler import ReminderScheduler
from .strings import t
from .theme import Theme
from .widgets import IconButton, PlaceholderEntry, Tooltip, UndoBar, px

if TYPE_CHECKING:  # ToastManager ถูกเขียนโดย module อื่น — ใช้เป็น type เท่านั้น
    from .toast import ToastManager

log = logging.getLogger("quicknote.board")

MIN_W, MIN_H = 300, 360          # px ที่ 96 DPI
REFRESH_DEBOUNCE_MS = 150
SEARCH_DEBOUNCE_MS = 150
TOPMOST_REAPPLY_MS = 3000
_GEO_RE = re.compile(r"(\d+)x(\d+)([+-])(-?\d+)([+-])(-?\d+)")


# ---------------------------------------------------------------- geometry helpers (pure → ทดสอบได้)
def parse_geometry(geometry: str) -> tuple[int, int, int, int] | None:
    """'WxH+X+Y' → (w, h, x, y); รูปแบบผิด → None  (Tk คืนตำแหน่งติดลบเป็น '+-8')"""
    m = _GEO_RE.fullmatch(str(geometry or "").strip())
    if not m:
        return None
    w, h, sx, x, sy, y = m.groups()
    return int(w), int(h), int(x) * (1 if sx == "+" else -1), int(y) * (1 if sy == "+" else -1)


def clamp_geometry(geometry: str, vx: int, vy: int, vw: int, vh: int, min_w: int, min_h: int,
                   fallback: str = "380x600+120+120") -> str:
    """บีบหน้าต่างให้อยู่ใน virtual screen ทั้งใบ (C4) — จอที่เคยใช้ถูกถอด/เปลี่ยนความละเอียดแล้วหน้าต่างไม่หลุดนอกจอ"""
    parsed = parse_geometry(geometry) or parse_geometry(fallback)
    w, h, x, y = parsed  # type: ignore[misc]
    w = max(min_w, min(w, vw))
    h = max(min_h, min(h, vh))
    x = max(vx, min(x, vx + vw - w))
    y = max(vy, min(y, vy + vh - h))
    return f"{w}x{h}+{x}+{y}"


def _icon_path() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base / "assets" / "icon.ico"


class Board:
    def __init__(self, root: tk.Tk, settings, theme: Theme, toasts: "ToastManager") -> None:
        self.root = root
        self.settings = settings
        self.theme = theme
        self.toasts = toasts
        self.on_quit: Callable[[], None] | None = None   # main.py ตั้ง
        # main.py ตั้งให้บอกว่าซ่อนได้ไหม (tray ต้องทำงานอยู่) — ไม่งั้นหน้าต่างที่ซ่อนจะไม่มีทางเรียกกลับ (M16)
        self.can_hide: Callable[[], bool] = lambda: True

        self.note_cards: dict[str, NoteCard] = {}
        self._order: list[str] = []          # id ตามลำดับ DB ของแท็บปัจจุบัน (ก่อนกรองด้วย search)
        self._tab = "active"
        self._refresh_job: str | None = None
        self._search_job: str | None = None
        self._topmost_job: str | None = None
        self._restore_top_job: str | None = None
        self._settings_win = None
        self._tracked: list[tuple[tk.Misc, dict[str, str]]] = []
        self._scroll_shown = False
        self._region_h = 0
        self._empty_mode = ""
        self._count_cache = {"active": 0, "completed": 0}

        self._callbacks = CardCallbacks(
            on_toggle_complete=self._on_toggle_complete, on_save=self._on_save,
            on_request_expand=self._on_request_expand, on_reminder=self._open_reminder,
            on_clear_reminder=self._on_clear_reminder, on_pin=self._on_pin, on_priority=self._on_priority,
            on_color=self._on_color, on_delete=self._on_delete, on_alarm_done=self._alarm_done,
            on_alarm_snooze=self._alarm_snooze_default)

        strings.set_language(str(settings.get("language", "th")))
        # subscribe ก่อนสร้าง widget: board recolor พื้นก่อน แล้ว widget ลูก (IconButton) ค่อย after_idle อ่านสีจาก parent
        self._unsub_theme = theme.subscribe(self._on_theme)
        settings.subscribe(self._on_setting)

        self._init_window()
        self._build_ui()
        self._bind_keys()
        self._load_notes()
        self.theme.apply_window(self.root)

        # เจ้าของ alarm flow คือ Board: scheduler → refresh + toast
        self.scheduler = ReminderScheduler(root, self._on_due, self._on_missed)
        self.scheduler.on_tick(self._on_tick)
        self.scheduler.start()
        self._topmost_job = root.after(TOPMOST_REAPPLY_MS, self._reapply_topmost)

    # ================================================================ window
    def _init_window(self) -> None:
        r, s = self.root, self.settings
        r.title(t("board.window_title"))
        try:
            r.iconbitmap(str(_icon_path()))
        except tk.TclError:
            pass  # ไม่มีไอคอน/ไม่ใช่ Windows — ใช้ไอคอน Tk ไปก่อน
        r.minsize(px(r, MIN_W), px(r, MIN_H))
        r.geometry(self._restore_geometry())
        # ต้อง flush ตรงนี้ก่อนตั้ง -alpha/-topmost: ถ้าสร้างหน้าต่างจริงพร้อมกันหมด (iconbitmap + topmost) Tk 9 บน Windows
        # ทิ้งตำแหน่งที่ขอไว้แล้วให้ Windows วางเองแบบ cascade (+32+32, +96+96 …) → ตำแหน่งที่บันทึกไว้ไม่ถูกคืน (C4)
        r.update_idletasks()
        r.attributes("-alpha", float(s.get("alpha", 1.0)))
        self._apply_topmost()
        r.protocol("WM_DELETE_WINDOW", self._on_close_request)
        r.bind("<Unmap>", self._on_unmap, add="+")
        r.bind("<Destroy>", self._on_root_destroy, add="+")

    def _scale(self) -> float:
        try:
            return self.root.winfo_fpixels("1i") / 96.0
        except tk.TclError:
            return 1.0

    def _restore_geometry(self) -> str:
        """geometry ใน settings เก็บขนาดเป็นหน่วย 96 DPI (ใช้ได้ทุกความละเอียด) ตำแหน่งเป็นพิกเซลจริง"""
        r, k = self.root, self._scale()
        parsed = parse_geometry(str(self.settings.get("geometry", ""))) or parse_geometry("380x600+120+120")
        w, h, x, y = parsed  # type: ignore[misc]
        try:
            vx, vy, vw, vh = r.winfo_vrootx(), r.winfo_vrooty(), r.winfo_vrootwidth(), r.winfo_vrootheight()
        except tk.TclError:
            vx, vy, vw, vh = 0, 0, 1920, 1080
        return clamp_geometry(f"{round(w * k)}x{round(h * k)}+{x}+{y}", vx, vy, vw, vh,
                              px(r, MIN_W), px(r, MIN_H))

    def get_persistable_geometry(self) -> str:
        """สตริงสำหรับ settings["geometry"] — ขนาดหน่วย 96 DPI + ตำแหน่งจริง"""
        parsed = parse_geometry(self.root.geometry())
        if parsed is None or parsed[0] <= 1:
            return str(self.settings.get("geometry", "380x600+120+120"))
        w, h, x, y = parsed
        k = self._scale()
        return f"{round(w / k)}x{round(h / k)}+{x}+{y}"

    def _apply_topmost(self) -> None:
        try:
            self.root.attributes("-topmost", bool(self.settings.get("always_on_top", True)))
        except tk.TclError:
            pass

    def _reapply_topmost(self) -> None:
        """กัน fullscreen app ดันเราลงล่าง — เฉพาะตอนผู้ใช้เปิด always_on_top และไม่มี dialog ของเราเปิดอยู่ (H2)"""
        if self._topmost_job is not None:  # chain เดียวเสมอ แม้มีคนเรียกตรง ๆ (แบบเดียวกับ C2)
            try:
                self.root.after_cancel(self._topmost_job)
            except (tk.TclError, ValueError):
                pass
            self._topmost_job = None
        try:
            if self.settings.get("always_on_top", True) and not self._has_open_toplevel():
                self.root.attributes("-topmost", True)
            self._topmost_job = self.root.after(TOPMOST_REAPPLY_MS, self._reapply_topmost)
        except tk.TclError:
            pass

    def _has_open_toplevel(self) -> bool:
        """Settings / Reminder / toast ที่กำลังแสดง — ห้ามดันหน้าต่างหลักขึ้นทับ"""
        try:
            return any(isinstance(w, tk.Toplevel) and w.winfo_viewable() for w in self.root.winfo_children())
        except tk.TclError:
            return False

    def _on_close_request(self) -> None:
        """ปุ่ม ✕ ของ Windows — main.py จะ override protocol นี้เพื่อรู้ว่า tray ทำงานอยู่หรือไม่"""
        if self.settings.get("close_to_tray", True):
            self.hide()
        elif self.on_quit is not None:
            self.on_quit()
        else:
            self.root.destroy()

    def _on_unmap(self, e) -> None:
        if e.widget is self.root:
            self.flush_all_cards()  # ย่อ/ซ่อน = จุดที่ข้อมูลค้างอาจหายถ้าแอปถูกปิดต่อ (C8)

    def _on_root_destroy(self, e) -> None:
        if e.widget is self.root:
            self.scheduler.stop()
            self._unsub_theme()

    # ================================================================ show / hide
    def show(self) -> None:
        r = self.root
        try:
            r.deiconify()
            r.lift()
            # ปลดล็อก foreground ของ Windows: topmost ชั่วคราวแล้วคืนค่าตาม settings
            r.attributes("-topmost", True)
            r.focus_force()
            if self._restore_top_job is not None:
                r.after_cancel(self._restore_top_job)
            self._restore_top_job = r.after(150, self._apply_topmost)
        except tk.TclError:
            pass

    def hide(self) -> None:
        self.flush_all_cards()
        try:
            if self.can_hide():
                self.root.withdraw()
            else:
                self.root.iconify()  # ไม่มี tray = ย่อลง taskbar แทน (ยังมีปุ่มบน taskbar ให้กดเรียกกลับ)
        except tk.TclError:
            pass

    def toggle_visibility(self) -> None:
        """M22: มองเห็นแต่ไม่มี focus (ถูกหน้าต่างอื่นบัง) → ดึงขึ้นมา ไม่ซ่อน"""
        try:
            visible = self.root.state() == "normal" and bool(self.root.winfo_viewable())
            focused = self.root.focus_displayof() is not None
        except tk.TclError:
            return
        if visible and focused:
            self.hide()
        else:
            self.show()

    def _is_visible(self) -> bool:
        try:
            return bool(self.root.winfo_viewable())
        except tk.TclError:
            return False

    def _ensure_visible(self) -> None:
        if not self._is_visible():
            self.show()

    # ================================================================ UI build
    def _track(self, widget: tk.Misc, **opts: str) -> tk.Misc:
        """ผูก widget กับ token สี เพื่อ recolor ตอนธีมเปลี่ยน"""
        self._tracked.append((widget, opts))
        widget.configure(**{k: self.theme.c(v) for k, v in opts.items()})
        return widget

    def _build_ui(self) -> None:
        # ลำดับ pack สำคัญ: toolbar → selector → quick-add → footer(ล่าง) → list(ขยาย)
        self._build_toolbar()
        self._build_selector()
        self._build_quick_add()
        self._build_footer()
        self._build_list()
        self._build_empty_state()

    def _build_toolbar(self) -> None:
        r, th = self.root, self.theme
        bar = tk.Frame(r, height=px(r, 48), bd=0, highlightthickness=0)
        bar.pack(side="top", fill="x")
        bar.pack_propagate(False)
        self._track(bar, bg="surface")
        self._toolbar = bar

        self._tb_settings = IconButton(bar, th, ICONS["settings"], self.open_settings,
                                       tooltip=lambda: t("board.settings_tip"))
        self._tb_settings.pack(side="right", padx=(px(r, 2), px(r, 12)))
        self._tb_topmost = IconButton(bar, th, ICONS["topmost"], self._on_topmost_toggle,
                                      tooltip=lambda: t("board.topmost_tip"), toggle=True)
        self._tb_topmost.set_active(bool(self.settings.get("always_on_top", True)))
        self._tb_topmost.pack(side="right", padx=px(r, 2))

        icon = tk.Label(bar, text=ICONS["search"], font=th.font("icon12"), bd=0)
        self._track(icon, bg="surface", fg="text_secondary")
        icon.pack(side="left", padx=(px(r, 14), px(r, 6)))
        self._search_var = tk.StringVar(master=r)
        self._search = PlaceholderEntry(bar, t("board.search_placeholder"), textvariable=self._search_var,
                                        style=th.ttk_style("TEntry", "surface"),
                                        placeholder_style=th.ttk_style("Placeholder.TEntry", "surface"))
        self._search.pack(side="left", fill="x", expand=True, pady=px(r, 8))
        self._search_clear = IconButton(bar, th, ICONS["cancel"], self._clear_search, size=28,
                                        tooltip=lambda: t("board.search_clear_tip"), fg_token="text_secondary")
        self._search_var.trace_add("write", self._on_search_changed)
        forward_shortcuts(self._search)
        self._search.bind("<Down>", lambda e: self._arrow_from_input(1))

    def _build_selector(self) -> None:
        r, th = self.root, self.theme
        bar = tk.Frame(r, bd=0, highlightthickness=0)
        bar.pack(side="top", fill="x", padx=px(r, 12), pady=(px(r, 4), 0))
        self._track(bar, bg="bg")
        self._selector = bar
        self._tabs: dict[str, tuple[tk.Label, tk.Frame]] = {}
        for key, tip in (("active", "board.tab_active_tip"), ("completed", "board.tab_completed_tip")):
            cell = tk.Frame(bar, bd=0, highlightthickness=0)
            self._track(cell, bg="bg")
            cell.pack(side="left", padx=(0, px(r, 18)))
            lbl = tk.Label(cell, bd=0, cursor="hand2", takefocus=True, highlightthickness=2, padx=px(r, 2))
            lbl.pack()
            underline = tk.Frame(cell, height=px(r, 3), width=px(r, 16), bd=0, highlightthickness=0)
            underline.pack(pady=(px(r, 1), 0))
            lbl.bind("<Button-1>", lambda e, k=key: self._select_tab(k))
            lbl.bind("<Return>", lambda e, k=key: self._select_tab(k))
            lbl.bind("<space>", lambda e, k=key: self._select_tab(k))
            Tooltip(lbl, (lambda tk_=tip: t(tk_)), theme=th)
            self._tabs[key] = (lbl, underline)
        self._paint_tabs()

    def _build_quick_add(self) -> None:
        r = self.root
        wrap = tk.Frame(r, bd=0, highlightthickness=0)
        wrap.pack(side="top", fill="x", padx=px(r, 12), pady=(px(r, 2), px(r, 4)))
        self._track(wrap, bg="bg")
        self._qa_wrap = wrap
        self._qa = PlaceholderEntry(wrap, t("board.quick_add_placeholder"))
        self._qa.pack(fill="x")
        self._qa.bind("<Return>", lambda e: self._quick_add(False))
        self._qa.bind("<Shift-Return>", lambda e: self._quick_add(True))
        self._qa.bind("<Down>", lambda e: self._arrow_from_input(1))
        forward_shortcuts(self._qa)

    def _build_footer(self) -> None:
        r, th = self.root, self.theme
        footer = tk.Frame(r, bd=0, highlightthickness=0)
        footer.pack(side="bottom", fill="x")
        self._track(footer, bg="bg")
        self._footer = footer
        self.undo_bar = UndoBar(footer, th, pack_options={
            "side": "top", "fill": "x", "padx": px(r, 12), "pady": (px(r, 4), px(r, 8))})
        status = tk.Frame(footer, height=px(r, 28), bd=0, highlightthickness=0)
        status.pack_propagate(False)
        self._track(status, bg="surface")
        self._status = status
        line = tk.Frame(status, height=1, bd=0, highlightthickness=0)
        self._track(line, bg="stroke")
        line.pack(side="top", fill="x")
        self._status_icon = tk.Label(status, text=ICONS["clock"], font=th.font("icon10"), bd=0)
        self._track(self._status_icon, bg="surface", fg="text_secondary")
        self._status_icon.pack(side="left", padx=(px(r, 12), px(r, 6)))
        self._status_text = tk.Label(status, font=th.font("caption"), bd=0, anchor="w")
        self._track(self._status_text, bg="surface", fg="text_secondary")
        self._status_text.pack(side="left", fill="x", expand=True)
        self._status_shown = False

    def _build_list(self) -> None:
        r = self.root
        wrap = tk.Frame(r, bd=0, highlightthickness=0)
        wrap.pack(side="top", fill="both", expand=True)
        self._track(wrap, bg="bg")
        self._list_wrap = wrap
        self._canvas = tk.Canvas(wrap, highlightthickness=0, bd=0, yscrollincrement=px(r, 20))
        self._track(self._canvas, bg="bg")
        self._canvas.pack(fill="both", expand=True)
        # scrollbar วางลอยทับขอบขวา (place) ไม่กินที่ → ความกว้างการ์ดไม่เปลี่ยนตอนแถบโผล่/หาย
        self._scroll = ttk.Scrollbar(wrap, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._on_yscroll)
        self._inner = tk.Frame(self._canvas, bd=0, highlightthickness=0)
        self._track(self._inner, bg="bg")
        self._win = self._canvas.create_window(0, 0, window=self._inner, anchor="nw")
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._inner.bind("<Configure>", self._on_inner_configure)

    def _build_empty_state(self) -> None:
        """empty state เป็น frame ตัวเดียวที่ pack/forget (แก้ M1/M2) ปรับข้อความตาม 3 กรณี"""
        th, r = self.theme, self.root
        f = tk.Frame(self._inner, bd=0, highlightthickness=0)
        self._track(f, bg="bg")
        self._empty = f
        self._empty_icon = tk.Label(f, text=ICONS["add"], font=th.font("icon32"), bd=0)
        self._track(self._empty_icon, bg="bg", fg="text_disabled")
        self._empty_icon.pack(pady=(0, px(r, 6)))
        self._empty_title = tk.Label(f, font=th.font("body_strong"), bd=0, wraplength=px(r, 280), justify="center")
        self._track(self._empty_title, bg="bg", fg="text")
        self._empty_title.pack()
        self._empty_hint = tk.Label(f, font=th.font("caption"), bd=0, wraplength=px(r, 280), justify="center")
        self._track(self._empty_hint, bg="bg", fg="text_secondary")
        self._empty_hint.pack(pady=(px(r, 2), 0))
        self._empty_link = ttk.Button(f, style=th.ttk_style("Link.TButton", "bg"), command=self._clear_search,
                                      takefocus=True)
        # ปุ่ม "ลบงานที่เสร็จแล้วทั้งหมด" ท้ายรายการแท็บ completed
        self._tail = tk.Frame(self._inner, bd=0, highlightthickness=0)
        self._track(self._tail, bg="bg")
        self._tail_btn = ttk.Button(self._tail, style=th.ttk_style("Link.TButton", "bg"),
                                    command=self._delete_all_completed, takefocus=True)
        self._tail_btn.pack(pady=px(r, 8))

    # ---------------------------------------------------------------- list scrolling
    def _on_canvas_configure(self, e) -> None:
        self._canvas.itemconfigure(self._win, width=e.width)
        self._update_scrollregion()

    def _on_inner_configure(self, _e) -> None:
        self._update_scrollregion()

    def _update_scrollregion(self) -> None:
        ch = self._canvas.winfo_height()
        self._region_h = max(self._inner.winfo_reqheight(), ch)
        self._canvas.configure(scrollregion=(0, 0, self._canvas.winfo_width(), self._region_h))

    def _on_yscroll(self, lo: str, hi: str) -> None:
        self._scroll.set(lo, hi)
        need = not (float(lo) <= 0.0 and float(hi) >= 1.0)
        if need != self._scroll_shown:
            self._scroll_shown = need
            if need:
                self._scroll.place(relx=1.0, rely=0.0, relheight=1.0, anchor="ne")
            else:
                self._scroll.place_forget()

    def _on_wheel(self, e) -> None:
        w = e.widget
        # Text ที่ล้นความสูงต้องเลื่อนเนื้อหาเอง (class binding ทำให้แล้ว) — ไม่เลื่อนรายการซ้อน
        if isinstance(w, tk.Text):
            try:
                if w.yview() != (0.0, 1.0):
                    return
            except tk.TclError:
                pass
        steps = max(1, abs(int(e.delta)) // 120) * 3
        self._canvas.yview_scroll(-steps if e.delta > 0 else steps, "units")

    def _scroll_into_view(self, note_id: str) -> None:
        card = self.note_cards.get(note_id)
        if card is None or not card.winfo_manager():
            return
        self.root.update_idletasks()
        self._update_scrollregion()
        gap = px(self.root, CARD_GAP_Y)
        y0, y1 = card.winfo_y() - gap, card.winfo_y() + card.winfo_height() + gap
        top = self._canvas.canvasy(0)
        view_h = self._canvas.winfo_height()
        total = max(1, self._region_h)
        if y0 < top:
            self._canvas.yview_moveto(max(0.0, y0 / total))
        elif y1 > top + view_h:
            self._canvas.yview_moveto(max(0.0, (y1 - view_h) / total))

    def _scroll_to_top(self) -> None:
        self._canvas.yview_moveto(0.0)

    # ================================================================ keyboard
    def _bind_keys(self) -> None:
        r = self.root
        actions = {
            "<<QN-NewNote>>": self.focus_quick_add, "<<QN-Search>>": self.focus_search,
            "<<QN-Topmost>>": self._toggle_topmost_key,
            "<<QN-TabActive>>": lambda: self._select_tab("active"),
            "<<QN-TabCompleted>>": lambda: self._select_tab("completed"),
        }
        for seq, virtual in GLOBAL_SHORTCUTS.items():
            r.event_add(virtual, seq)
        for virtual, fn in actions.items():
            r.bind(virtual, lambda e, fn=fn: (fn(), "break")[1])
        r.bind("<Escape>", self._on_escape)
        r.bind("<Up>", lambda e: self._on_arrow(-1))
        r.bind("<Down>", lambda e: self._on_arrow(1))
        # bind ที่ toplevel (ไม่ใช้ bind_all) → ไม่กวนเมาส์วีลของ Settings/dialog
        r.bind("<MouseWheel>", self._on_wheel, add="+")

    def _on_escape(self, _e=None):
        """Esc: ปิดเมนู (native จัดการเอง) → พับการ์ด → ล้างคำค้น → ซ่อนหน้าต่าง"""
        card = self._expanded_card()
        if card is not None:
            card.collapse()
            card.focus_card()
            return "break"
        if self._query():
            self._clear_search()
            return "break"
        self.hide()
        return "break"

    def _visible_cards(self) -> list[NoteCard]:
        return [self.note_cards[i] for i in self._order if i in self.note_cards and self.note_cards[i].winfo_manager()]

    def _on_arrow(self, delta: int):
        try:
            w = self.root.focus_lastfor()  # key event มาถึงเฉพาะตอนแอปมี focus จริง ซึ่งผลเท่า focus_get
        except (tk.TclError, KeyError):
            return None
        cards = self._visible_cards()
        if isinstance(w, NoteCard) and w in cards:
            i = cards.index(w) + delta
            if 0 <= i < len(cards):
                cards[i].focus_card()
                self._scroll_into_view(cards[i].note.id)
            return "break"
        return None

    def _arrow_from_input(self, delta: int):
        """↓ จากช่องค้นหา/quick-add ไปที่การ์ดใบแรก"""
        cards = self._visible_cards()
        if delta > 0 and cards:
            cards[0].focus_card()
            self._scroll_into_view(cards[0].note.id)
            return "break"
        return None

    def _toggle_topmost_key(self) -> None:
        self.settings.set("always_on_top", not bool(self.settings.get("always_on_top", True)))

    # ================================================================ public focus API
    def focus_quick_add(self) -> None:
        self._ensure_visible()
        if self._tab != "active":
            self._select_tab("active")
        self._qa.focus_set()

    def focus_search(self) -> None:
        self._ensure_visible()
        self._search.focus_set()
        self._search.select_range(0, "end")

    # ================================================================ tabs
    def _select_tab(self, tab: str) -> None:
        if tab == self._tab:
            return
        self.flush_all_cards()
        self._tab = tab
        if self._query():
            self._search_var.set("")  # H9: ล้างคำค้นตอนเปลี่ยนแท็บเท่านั้น (ไม่ใช่ใน _load_notes)
        self._paint_tabs()
        if tab == "active":
            self._qa_wrap.pack(side="top", fill="x", padx=px(self.root, 12),
                               pady=(px(self.root, 2), px(self.root, 4)), after=self._selector)
        else:
            self._qa_wrap.pack_forget()
        self._load_notes()
        self._scroll_to_top()

    def _paint_tabs(self) -> None:
        th = self.theme
        counts = self._count_cache
        for key, (lbl, bar) in self._tabs.items():
            sel = key == self._tab
            lbl.configure(text=t(f"board.tab_{key}", n=counts.get(key, 0)),
                          font=th.font("body_strong" if sel else "body"),
                          fg=th.c("text" if sel else "text_secondary"), bg=th.c("bg"),
                          highlightbackground=th.c("bg"), highlightcolor=th.c("accent"))
            bar.configure(bg=th.c("accent" if sel else "bg"))
            bar.master.configure(bg=th.c("bg"))

    def _update_counts(self) -> None:
        try:
            self._count_cache = db.count_by_status()
        except Exception:
            log.exception("count_by_status failed")
        self._paint_tabs()

    # ================================================================ search
    def _query(self) -> str:
        return self._search.get_value().strip().lower()

    def _on_search_changed(self, *_a) -> None:
        if self._search_var.get():
            if not self._search_clear.winfo_manager():
                self._search_clear.pack(side="right", padx=(0, px(self.root, 2)))
        else:
            self._search_clear.pack_forget()
        if self._search_job is not None:
            self.root.after_cancel(self._search_job)
        self._search_job = self.root.after(SEARCH_DEBOUNCE_MS, self._run_search)

    def _run_search(self) -> None:
        self._search_job = None
        self._apply_filter()
        self._scroll_to_top()

    def _clear_search(self) -> None:
        self._search.clear()
        self._search_var.set("")
        if self._search_job is not None:
            self.root.after_cancel(self._search_job)
            self._search_job = None
        self._apply_filter()

    # ================================================================ list refresh (C5 / H4 / H5 / H9)
    def refresh(self, immediate: bool = False) -> None:
        """debounce 150ms รวมคำขอที่ถี่ ๆ (alarm/dismiss/pin) เป็นการโหลดครั้งเดียว"""
        if immediate:
            self._load_notes()
        elif self._refresh_job is None:
            self._refresh_job = self.root.after(REFRESH_DEBOUNCE_MS, self._load_notes)

    def rebuild(self) -> None:
        """ทำลายการ์ดทั้งหมดโดยไม่ flush (ข้อมูลเก่าหลัง restore ต้องทิ้ง) แล้วโหลดใหม่"""
        self._cancel_refresh()
        for card in list(self.note_cards.values()):
            card.destroy()
        self.note_cards.clear()
        self.undo_bar.hide()  # callback ของแถบเก่าอ้างโน้ตที่ไม่มีแล้ว
        self._load_notes()

    def _cancel_refresh(self) -> None:
        if self._refresh_job is not None:
            try:
                self.root.after_cancel(self._refresh_job)
            except (tk.TclError, ValueError):
                pass
            self._refresh_job = None

    def _load_notes(self) -> None:
        self._cancel_refresh()
        try:
            rows = db.get_notes_by_status(self._tab)
        except Exception:
            log.exception("cannot load notes")
            return
        keep = {r["id"] for r in rows}
        for nid in [n for n in self.note_cards if n not in keep]:
            self._destroy_card(self.note_cards.pop(nid))
        for card in self.note_cards.values():  # ต้องถอดทั้งหมดก่อน pack ใหม่ ไม่งั้นลำดับไม่ขยับ (C5)
            card.pack_forget()

        compact = bool(self.settings.get("compact", False))
        self._order = []
        expanded_seen = False
        for row in rows:
            note = Note.from_dict(row)
            if not note.collapsed:  # กางทีละใบ: DB เก่า/restore อาจมีหลายใบ → เหลือใบแรก
                if expanded_seen:
                    note.collapsed = True
                    db.update_fields(note.id, collapsed=True)
                expanded_seen = True
            card = self.note_cards.get(note.id)
            if card is None:
                card = NoteCard(self._inner, note, self.theme, self._callbacks, compact=compact)
                self.note_cards[note.id] = card
            else:
                card.refresh_from(note)
            self._order.append(note.id)
        self._apply_filter()
        self._update_counts()
        self._update_status()

    def _destroy_card(self, card: NoteCard) -> None:
        try:
            card.flush_pending()
        except Exception:
            log.exception("flush before destroy failed")
        card.destroy()

    def _apply_filter(self) -> None:
        """pack เฉพาะการ์ดที่ตรงคำค้น ตามลำดับ DB — และจัด empty state / ปุ่มท้ายรายการ"""
        kw = self._query()
        for card in self.note_cards.values():
            card.pack_forget()
        self._empty.pack_forget()
        self._tail.pack_forget()
        shown = 0
        for nid in self._order:
            card = self.note_cards[nid]
            n = card.note
            if kw and kw not in n.title.lower() and kw not in n.content.lower():
                continue
            card.pack(fill="x", padx=px(self.root, 12), pady=px(self.root, CARD_GAP_Y))
            shown += 1
        if shown:
            if self._tab == "completed" and not kw:
                self._tail_btn.configure(text=t("board.delete_all_completed"))
                self._tail.pack(fill="x")
        else:
            self._show_empty(kw)
        self._canvas.after_idle(self._update_scrollregion)

    def _show_empty(self, kw: str) -> None:
        if kw:
            self._empty_mode = "search"
            self._empty_title.configure(text=t("board.empty_search", query=self._search.get_value().strip()))
            self._empty_hint.pack_forget()
            self._empty_link.configure(text=t("board.empty_search_clear"))
            self._empty_link.pack(pady=(px(self.root, 4), 0))
        else:
            self._empty_mode = self._tab
            self._empty_link.pack_forget()
            if self._tab == "active":
                self._empty_title.configure(text=t("board.empty_title"))
                self._empty_hint.configure(text=t("board.empty_hint"))
                self._empty_hint.pack(pady=(px(self.root, 2), 0))
            else:
                self._empty_title.configure(text=t("board.empty_completed"))
                self._empty_hint.pack_forget()
        self._empty.pack(pady=(px(self.root, 40), 0))

    def flush_all_cards(self) -> None:
        for card in list(self.note_cards.values()):
            try:
                card.flush_pending()
            except Exception:
                log.exception("flush failed for %s", card.note.id)

    def _expanded_card(self) -> NoteCard | None:
        return next((c for c in self.note_cards.values() if c.expanded), None)

    # ================================================================ card callbacks → DB
    def _on_save(self, note_id: str, changes: dict) -> None:
        fields = {k: v for k, v in changes.items() if k in ("title", "content", "collapsed")}
        if not fields:
            return
        try:
            db.update_fields(note_id, **fields)
        except Exception:
            log.exception("cannot save %s", note_id)

    def _on_request_expand(self, note_id: str) -> None:
        card = self.note_cards.get(note_id)
        if card is None:
            return
        for other in self.note_cards.values():
            if other is not card and other.expanded:
                other.collapse()  # flush ก่อนพับเสมอ
        card.expand()
        self.root.after_idle(lambda: self._scroll_into_view(note_id))

    def _on_toggle_complete(self, note_id: str) -> None:
        row = db.get_note(note_id)
        if row is None:
            return
        card = self.note_cards.get(note_id)
        if row["status"] == "active":
            db.set_status(note_id, "completed")
            if row["reminder_triggered"] and row["reminder_datetime"]:
                db.dismiss_reminder(note_id)  # กำลังดังอยู่แล้วเสร็จ → เลิกดัง ปิด toast
            self.toasts.close_for(note_id)
            message, target = t("undo.completed"), "active"
        else:
            db.set_status(note_id, "active")
            message, target = t("undo.restored"), "completed"
        self.undo_bar.show(message, on_undo=lambda: self._undo_status(note_id, target), on_expire=None)
        self._update_counts()
        if card is not None:
            card.animate_out(then=lambda: self._load_notes())
        else:
            self._load_notes()

    def _undo_status(self, note_id: str, status: str) -> None:
        db.set_status(note_id, status)
        self._load_notes()

    def _on_pin(self, note_id: str, pinned: bool) -> None:
        db.update_fields(note_id, is_pinned=pinned)
        self._load_notes()

    def _on_priority(self, note_id: str, priority: str) -> None:
        db.update_fields(note_id, priority=priority)
        self._load_notes()

    def _on_color(self, note_id: str, color: str) -> None:
        db.update_fields(note_id, color=color)
        self._load_notes()

    def _on_delete(self, note_id: str) -> None:
        card = self.note_cards.get(note_id)
        if card is not None:
            card.flush_pending()  # ให้ Undo คืนโน้ตพร้อมข้อความล่าสุด
        # แถบเก่าที่ค้างอยู่ต้องจบ (purge) "ก่อน" soft_delete ใบนี้ ไม่งั้น purge_deleted จะลบใบนี้ทิ้งไปด้วย
        self.undo_bar.flush()
        db.soft_delete(note_id)
        self.toasts.close_for(note_id)
        # H11: ซ่อนทันที + Undo 5 วินาที แล้วค่อยลบจริง
        self.undo_bar.show(t("undo.deleted"), on_undo=lambda: self._undo_delete(note_id),
                           on_expire=db.purge_deleted)
        self._load_notes()

    def _undo_delete(self, note_id: str) -> None:
        db.undo_delete(note_id)
        self._load_notes()

    def _on_clear_reminder(self, note_id: str) -> None:
        db.set_reminder(note_id, None)
        self.toasts.close_for(note_id)
        self._load_notes()

    def _delete_all_completed(self) -> None:
        n = self._count_cache.get("completed", 0)
        if n and messagebox.askyesno(t("dialog.delete_completed.title"),
                                     t("dialog.delete_completed.body", n=n), parent=self.root):
            db.delete_all_completed()
            self._load_notes()

    # ================================================================ quick add
    def _quick_add(self, expand: bool):
        title = self._qa.get_value().strip()
        if not title or self._tab != "active":
            return "break"  # ช่องว่าง + Enter = ไม่ทำอะไร
        if expand:
            prev = self._expanded_card()
            if prev is not None:
                prev.collapse()
        try:
            note_id = db.create_note(title, collapsed=not expand)
        except Exception:
            log.exception("cannot create note")
            return "break"
        self._qa.clear()
        if self._query():
            self._clear_search()  # โน้ตใหม่ไม่ตรงคำค้นจะถูกซ่อน ผู้ใช้จะนึกว่าไม่ได้สร้าง
        self._load_notes()
        self._scroll_into_view(note_id)
        if expand:
            card = self.note_cards.get(note_id)
            if card is not None:
                card.focus_content()
        return "break"

    # ================================================================ reminders / alarm flow
    def _open_reminder(self, note_id: str) -> None:
        row = db.get_note(note_id)
        if row is None:
            return
        from .reminder_dialog import ReminderDialog  # โหลดตอนใช้ — ไฟล์นี้เขียนโดย module อื่น
        ReminderDialog(self.root, Note.from_dict(row), self.theme,
                       lambda when, repeat: self._on_reminder_saved(note_id, when, repeat))

    def _on_reminder_saved(self, note_id: str, when: str | None, repeat: str) -> None:
        if when is None:
            db.set_reminder(note_id, None)
            self.toasts.close_for(note_id)
        else:
            db.set_reminder(note_id, when, repeat)
        self._load_notes()
        self.scheduler.check_now()  # เวลาที่ผ่านไปแล้ว = ดังทันที (spec 5)

    def _on_due(self, rows: list[dict]) -> None:
        self._load_notes()  # การ์ดเปลี่ยนเป็นสถานะดัง + ขึ้นลำดับตาม SQL ก่อนโชว์ toast
        for row in rows:
            nid = row["id"]
            self.toasts.show_reminder(
                row, on_done=lambda nid=nid: self._alarm_done(nid),
                on_snooze=lambda when, nid=nid: self._alarm_snooze(nid, when),
                on_open=lambda nid=nid: self.reveal_note(nid),
                on_dismiss=lambda nid=nid: self._alarm_dismiss(nid))
        if rows and self._is_visible():
            self._scroll_into_view(rows[0]["id"])

    def _on_missed(self, rows: list[dict]) -> None:
        self._load_notes()
        self.toasts.show_missed(rows, on_view=self.show)

    def _alarm_done(self, note_id: str) -> None:
        row = db.get_note(note_id)
        if row is None:
            return
        db.dismiss_reminder(note_id)  # ทำซ้ำ → เลื่อนรอบถัดไป, ครั้งเดียว → ล้าง
        if (row["reminder_repeat"] or "none") == "none":
            db.set_status(note_id, "completed")
        self.toasts.close_for(note_id)
        self._load_notes()

    def _alarm_snooze(self, note_id: str, when: str) -> None:
        db.snooze_reminder(note_id, when)
        self.toasts.close_for(note_id)
        self._load_notes()

    def _alarm_snooze_default(self, note_id: str) -> None:
        minutes = int(self.settings.get("snooze_default_minutes", 5))
        self._alarm_snooze(note_id, format_dt(datetime.now() + timedelta(minutes=minutes)))

    def _alarm_dismiss(self, note_id: str) -> None:
        db.dismiss_reminder(note_id)
        self.toasts.close_for(note_id)
        self._load_notes()

    def reveal_note(self, note_id: str) -> None:
        """toast "เปิด": แสดงหน้าต่าง + สลับแท็บถ้าจำเป็น + เลื่อน + กางการ์ด"""
        row = db.get_note(note_id)
        if row is None or row["deleted_at"]:
            return
        self.show()
        if row["status"] != self._tab:
            self._select_tab(row["status"])
        elif self._query():
            self._clear_search()
        self._load_notes()
        if note_id in self.note_cards:
            self._on_request_expand(note_id)
            self._scroll_into_view(note_id)

    # ================================================================ status bar
    def _update_status(self) -> None:
        try:
            nxt = db.get_next_reminder()
        except Exception:
            nxt = None
        if not nxt:
            if self._status_shown:
                self._status.pack_forget()
                self._status_shown = False
            return
        when, _ = format_reminder(nxt["reminder_datetime"], datetime.now(), strings.get_language())
        font = self.theme.font("caption")
        room = max(80, self.root.winfo_width() - px(self.root, 60) - font.measure(t("board.status_next", time=when, title="")))
        title = ellipsize(nxt["title"] or t("common.untitled"), font, room)
        self._status_text.configure(text=t("board.status_next", time=when, title=title))
        if not self._status_shown:
            self._status.pack(side="bottom", fill="x")
            self._status_shown = True

    def _on_tick(self) -> None:
        self.theme.refresh()  # ธีม/accent ของระบบเปลี่ยนระหว่างใช้งาน
        self._update_status()

    # ================================================================ settings window
    def open_settings(self) -> None:
        if self._settings_win is not None:
            try:
                self._settings_win.lift()
                return
            except tk.TclError:
                self._settings_win = None
        from .settings_window import SettingsWindow, make_default_actions
        actions = make_default_actions(self.root, on_restored=self.rebuild)
        self._settings_win = SettingsWindow(self.root, self.settings, self.theme, actions,
                                            on_close=self._settings_closed)

    def _settings_closed(self) -> None:
        self._settings_win = None

    def _on_topmost_toggle(self, state: bool) -> None:
        self.settings.set("always_on_top", bool(state))

    # ================================================================ live settings / theme
    def _on_setting(self, key: str, value) -> None:
        try:
            if not self.root.winfo_exists():
                return
            if key == "alpha":
                self.root.attributes("-alpha", float(value))
            elif key == "always_on_top":
                self._apply_topmost()
                self._tb_topmost.set_active(bool(value))
            elif key == "compact":
                for card in self.note_cards.values():
                    card.set_compact(bool(value))
            elif key == "language":
                self._on_language_changed(str(value))
            elif key == "snooze_default_minutes":
                for card in self.note_cards.values():
                    card.refresh_from(card.note)
        except tk.TclError:
            pass

    def _on_language_changed(self, lang: str) -> None:
        strings.set_language(lang)
        self.flush_all_cards()
        self._search.set_placeholder(t("board.search_placeholder"))
        self._qa.set_placeholder(t("board.quick_add_placeholder"))
        self.root.title(t("board.window_title"))
        self.rebuild()

    def _on_theme(self) -> None:
        th = self.theme
        for widget, opts in self._tracked:
            try:
                widget.configure(**{k: th.c(v) for k, v in opts.items()})
            except tk.TclError:
                pass
        self._paint_tabs()
        for card in self.note_cards.values():
            card.apply_theme()
        self.theme.apply_window(self.root)
