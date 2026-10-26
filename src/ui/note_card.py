"""NoteCard — การ์ดโน้ต v3 (DESIGN_SPEC 4.x, สัญญา ARCHITECTURE ข้อ 5)

โครงภายในคงที่เสมอ: header → content → chip row (ทุกครั้งที่เปลี่ยนโหมด pack_forget แล้ว pack ใหม่ตามลำดับ
แก้ V4) การ์ดไม่เขียน DB เอง: ทุกการเปลี่ยนแปลงออกทาง CardCallbacks ให้ Board เป็นเจ้าของข้อมูล
เนื้อหา/หัวข้อบันทึกผ่าน on_save เท่านั้น (debounce 500ms + flush ตอนพับ/ทำลาย/ปิดแอป — C7/C8)
"""

from __future__ import annotations

import logging
import tkinter as tk
import tkinter.font as tkfont
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from ..core.models import Note
from ..core.reminders import format_reminder
from .icons import ICONS
from .strings import get_language, t
from .theme import Theme, blend
from .widgets import IconButton, RoundedFrame, Tooltip, _animate, is_pointer_inside, px

log = logging.getLogger("quicknote.card")

SAVE_DEBOUNCE_MS = 500
SAVED_CAPTION_MS = 1500

# ขนาดทั้งหมดเป็น "px ที่ 96 DPI" แล้วคูณด้วย px() ตอนใช้
PAD_X = 9          # + inset ของ RoundedFrame (3) ≈ 12px จากขอบการ์ดตามสเปก
PAD_Y = 3
CARD_GAP_Y = 4     # pady ของการ์ดแต่ละใบใน list (รวม 8px ระหว่างใบ)
CHECK_SIZE = 26
BTN_SIZE = 26
INDENT = CHECK_SIZE + 8   # เนื้อหา/chip ชิดแนวเดียวกับหัวข้อ

_GLYPH_RING = ICONS["circle"]
_GLYPH_DONE = ICONS["completed"]
_GLYPH_HOVER = ""   # ring + check (มีทั้ง Fluent และ MDL2) ใช้เป็น "check จาง" ตอน hover

PRIORITY_TOKEN = {"high": "critical", "medium": "caution", "low": "accent"}
_LEADING_VOWELS = "เแโใไ"

# ปุ่มลัดระดับแอปที่ Entry/Text ชน (Ctrl+T สลับตัวอักษร, Ctrl+F/N/P ขยับ cursor ฯลฯ) → ส่งต่อเป็น virtual event
GLOBAL_SHORTCUTS = {
    "<Control-n>": "<<QN-NewNote>>",
    "<Control-f>": "<<QN-Search>>",
    "<Control-t>": "<<QN-Topmost>>",
    "<Control-Key-1>": "<<QN-TabActive>>",
    "<Control-Key-2>": "<<QN-TabCompleted>>",
}


def forward_shortcuts(widget: tk.Misc) -> None:
    """กัน class binding ของ Entry/Text (emacs-style) แย่งปุ่มลัดของแอป แล้วส่งให้ Board จัดการ"""
    for seq, virtual in GLOBAL_SHORTCUTS.items():
        widget.bind(seq, lambda e, v=virtual: (e.widget.event_generate(v), "break")[1])


def ellipsize(text: str, font: tkfont.Font, max_px: int) -> str:
    """ตัดข้อความให้พอดีความกว้างด้วย font.measure แล้วต่อ … (ไม่ตัดกลางกลุ่มอักษรไทย)"""
    if max_px <= 0:
        return ""
    if font.measure(text) <= max_px:
        return text
    lo, hi = 0, len(text)
    while lo < hi:  # หา n มากสุดที่ text[:n]+"…" ยังพอดี
        mid = (lo + hi + 1) // 2
        if font.measure(text[:mid] + "…") <= max_px:
            lo = mid
        else:
            hi = mid - 1
    n = lo
    # ตัวถัดไปเป็นสระบน/วรรณยุกต์ (Mn) หรือตัวสุดท้ายเป็นสระหน้า → ถอยกลับ ไม่งั้นเครื่องหมายลอยโดดเดี่ยว
    while n > 0 and (unicodedata.category(text[n]) == "Mn" or text[n - 1] in _LEADING_VOWELS):
        n -= 1
    return text[:n].rstrip() + "…"


def _done_font(theme: Theme, base_style: str) -> tkfont.Font:
    """font ขีดฆ่าสำหรับงานที่เสร็จ — แคชบน theme และ sync กับ font ฐานทุกครั้งที่ขอ (ขนาดตัวอักษรเปลี่ยนได้)"""
    cache = theme.__dict__.setdefault("_qn_done_fonts", {})
    font = cache.get(base_style)
    if font is None:
        font = cache[base_style] = tkfont.Font(root=theme.root)
    spec = dict(theme.font(base_style).actual())
    spec["overstrike"] = True
    font.configure(**spec)
    return font


def _first_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def _fixed(widget: tk.Misc) -> tk.Misc:
    """ติดป้ายว่า widget นี้มีสีของตัวเอง (chip/input) — _paint ของการ์ดต้องไม่ทาสีการ์ดทับ"""
    widget._qn_fixed = True  # type: ignore[attr-defined]
    return widget


@dataclass
class CardCallbacks:
    on_toggle_complete: Callable[[str], None]
    on_save: Callable[[str, dict], None]          # (note_id, {"title":..., "content":..., "collapsed":...}) เฉพาะที่เปลี่ยน
    on_request_expand: Callable[[str], None]      # board พับใบอื่นก่อน แล้วเรียก card.expand()
    on_reminder: Callable[[str], None]            # เปิด ReminderDialog
    on_clear_reminder: Callable[[str], None]
    on_pin: Callable[[str, bool], None]
    on_priority: Callable[[str, str], None]
    on_color: Callable[[str, str], None]
    on_delete: Callable[[str], None]
    on_alarm_done: Callable[[str], None]          # chip "เสร็จแล้ว" ตอน alarm ดัง
    on_alarm_snooze: Callable[[str], None]        # chip "เลื่อน N นาที"


class _CircleButton(tk.Label):
    """วงกลม complete: ring → (hover) check จาง → completed สี accent"""

    def __init__(self, parent: tk.Misc, theme: Theme, command: Callable[[], None]) -> None:
        self._theme = theme
        self._command = command
        self._done = False
        self._hover = False
        self._base = theme.c("card")
        self._pixel = tk.PhotoImage(master=parent, width=1, height=1)  # ทำให้ width/height นับเป็น px
        side = px(parent, CHECK_SIZE) - 4
        super().__init__(parent, text=_GLYPH_RING, font=theme.font("icon14"), image=self._pixel,
                         compound="center", width=side, height=side, bd=0, padx=0, pady=0,
                         takefocus=True, highlightthickness=2, highlightcolor=theme.c("accent"),
                         cursor="hand2")
        self.bind("<Enter>", self._on_enter, add="+")
        self.bind("<Leave>", self._on_leave, add="+")
        self.bind("<ButtonRelease-1>", self._on_release, add="+")
        self.bind("<space>", self._on_key)
        self.bind("<Return>", self._on_key)
        self.paint()

    def set_done(self, done: bool) -> None:
        self._done = done
        self.paint()

    def set_base(self, bg: str) -> None:
        self._base = bg
        self.paint()

    def paint(self) -> None:
        th = self._theme
        if self._done:
            glyph, fg = _GLYPH_DONE, th.c("accent")
        elif self._hover:
            glyph, fg = _GLYPH_HOVER, blend(th.c("text_secondary"), self._base, 0.35)
        else:
            glyph, fg = _GLYPH_RING, th.c("text_secondary")
        try:
            self.configure(text=glyph, fg=fg, bg=self._base, highlightbackground=self._base,
                           highlightcolor=th.c("accent"), font=th.font("icon14"))
        except tk.TclError:
            pass

    def _on_enter(self, _e) -> None:
        self._hover = True
        self.paint()

    def _on_leave(self, _e) -> None:
        self._hover = False
        self.paint()

    def _on_release(self, e) -> None:
        if 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height():
            self._command()

    def _on_key(self, _e) -> str:
        self._command()
        return "break"


class NoteCard(RoundedFrame):
    def __init__(self, parent: tk.Misc, note: Note, theme: Theme, callbacks: CardCallbacks,
                 compact: bool = False) -> None:
        super().__init__(parent, theme, radius=8, bg=theme.note_bg(note.color), border="stroke", border_width=1)
        self.th = theme
        self.note = note
        self.callbacks = callbacks
        self._compact = compact
        self._expanded = False
        self._hover = False
        self._focused = False
        self._menu_open = False
        self._removing = False
        self._saved = {"title": note.title, "content": note.content}
        self._save_job: str | None = None
        self._fit_w = 0
        self._chip_sig: tuple | None = None
        self._title_entry: tk.Entry | None = None
        self._title_wrap: tk.Frame | None = None
        self._title_ph: tk.Label | None = None
        self._title_trace: str | None = None
        self._text: tk.Text | None = None
        self._text_ph: tk.Label | None = None
        self._meta_full = ""
        self._meta_visible = False
        self._meta_overdue = False
        self._title_font = theme.font("body_strong")
        self._title_var = tk.StringVar(master=self)
        self._prio_var = tk.StringVar(master=self)
        self._color_var = tk.StringVar(master=self)
        self._menu = tk.Menu(self, tearoff=0)
        self._submenus: list[tk.Menu] = []

        self.configure(takefocus=True, highlightthickness=0)
        self._build()
        self._bind_card()
        self.refresh_from(note)

    # ================================================================ build
    def _build(self) -> None:
        th, body = self.th, self.body
        # --- header: [วงกลม][หัวข้อ/meta][pin] + ปุ่ม hover ลอยทับด้านขวา
        self._top = tk.Frame(body, bd=0, highlightthickness=0)
        self._top.pack(fill="x", padx=px(self, PAD_X), pady=px(self, PAD_Y))
        self._top.grid_columnconfigure(1, weight=1)
        self._top.grid_rowconfigure(0, minsize=px(self, BTN_SIZE))

        self._check = _CircleButton(self._top, th, self._toggle_complete)
        self._check.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, px(self, 6)))
        Tooltip(self._check, lambda: t("card.restore_tip" if self.note.status == "completed" else "card.complete_tip"),
                theme=th)

        self._col = tk.Frame(self._top, bd=0, highlightthickness=0)
        self._col.grid(row=0, column=1, rowspan=2, sticky="nsew")
        self._col.grid_columnconfigure(0, weight=1)
        self._col.grid_rowconfigure(0, minsize=px(self, BTN_SIZE))
        self._title = tk.Label(self._col, anchor="w", justify="left", bd=0, padx=0, pady=0)
        self._title.grid(row=0, column=0, sticky="we")
        self._meta = tk.Frame(self._col, bd=0, highlightthickness=0)
        self._meta.grid(row=1, column=0, sticky="we")
        self._m_icon = tk.Label(self._meta, bd=0, padx=0, pady=0)
        self._m_time = tk.Label(self._meta, bd=0, padx=0, pady=0)
        self._m_dot = tk.Label(self._meta, bd=0, padx=0, pady=0)
        self._m_prio = tk.Label(self._meta, bd=0, padx=0, pady=0)
        self._m_text = tk.Label(self._meta, bd=0, padx=0, pady=0, anchor="w")
        self._m_sep = [tk.Label(self._meta, bd=0, padx=0, pady=0, text=" · ") for _ in range(2)]

        self._pin = tk.Label(self._top, text=ICONS["pin"], bd=0, padx=0, pady=0)
        self._pin.grid(row=0, column=2, sticky="ne", padx=(px(self, 4), 0))

        self._actions = tk.Frame(self._top, bd=0, highlightthickness=0)
        self._clock = IconButton(self._actions, th, ICONS["clock"], lambda: self.callbacks.on_reminder(self.note.id),
                                 tooltip=lambda: t("card.reminder_tip"), size=BTN_SIZE, fg_token="text_secondary")
        self._more = IconButton(self._actions, th, ICONS["more"], self._popup_from_button,
                                tooltip=lambda: t("card.more_tip"), size=BTN_SIZE, fg_token="text_secondary")
        self._clock.pack(side="left")
        self._more.pack(side="left")

        # --- content (กางเท่านั้น) และ chip row
        self._content_wrap = tk.Frame(body, bd=0, highlightthickness=0)
        self._chips = tk.Frame(body, bd=0, highlightthickness=0)
        self._chip_row = tk.Frame(self._chips, bd=0, highlightthickness=0)
        self._chip_row.pack(side="left")
        self._saved_lbl = tk.Label(self._chips, bd=0, padx=0, pady=0)
        self._saved_lbl.pack(side="right", anchor="s")

        for w in (self._top, self._col, self._title, self._meta, self._m_icon, self._m_time, self._m_dot,
                  self._m_prio, self._m_text, self._m_sep[0], self._m_sep[1], self._pin, self.body, self):
            self._wire(w, click=True)
        for w in (self._check, self._actions, self._clock, self._more, self._content_wrap, self._chips,
                  self._chip_row, self._saved_lbl):
            self._wire(w)
        self._col.bind("<Configure>", self._on_col_configure)

    def _bind_card(self) -> None:
        self.bind("<FocusIn>", self._on_focus_in, add="+")
        self.bind("<FocusOut>", self._on_focus_out, add="+")
        self.bind("<Return>", lambda e: self._key_expand())
        self.bind("<space>", lambda e: self._key_complete())
        self.bind("<Control-Return>", lambda e: self._key_complete())
        self.bind("<Delete>", lambda e: self.callbacks.on_delete(self.note.id))
        self.bind("<Control-p>", lambda e: self._toggle_pin())
        self.bind("<Control-r>", lambda e: self.callbacks.on_reminder(self.note.id))
        self.bind("<Destroy>", self._on_destroy, add="+")

    def _wire(self, w: tk.Misc, click: bool = False) -> None:
        w.bind("<Enter>", self._on_enter, add="+")
        w.bind("<Leave>", self._on_leave, add="+")
        w.bind("<Button-3>", self._on_context, add="+")
        if click:
            w.bind("<Button-1>", self._on_click, add="+")

    # ================================================================ public API
    def refresh_from(self, note: Note) -> None:
        """sync ทุก widget จากข้อมูลล่าสุด (H5) — ช่องที่กำลังพิมพ์/มีค่าค้างไม่ถูกทับ"""
        self.note = note
        pending = self._save_job is not None
        # สถานะพับ/กางเป็นของ DB (H4): ไม่ตรงกับหน้าจอ → ปรับให้ตรงโดยไม่เขียนกลับ
        if note.collapsed and self._expanded:
            self.collapse(persist=False)
        elif not note.collapsed and not self._expanded:
            self.expand(focus=False, persist=False)
        if self._expanded and self._title_entry is not None and self._text is not None:
            if not pending:
                if self.focus_displayof() is not self._title_entry and self._title_var.get() != note.title:
                    self._title_var.set(note.title)
                if self.focus_displayof() is not self._text and self._text.get("1.0", "end-1c") != note.content:
                    self._set_text(note.content)
                self._saved = {"title": note.title, "content": note.content}
        else:
            self._saved = {"title": note.title, "content": note.content}
        self._render()

    def flush_pending(self) -> None:
        """C7/C8: ยกเลิก timer แล้วบันทึกค่าค้างจาก widget ทันที — เรียกก่อน hide/destroy/quit"""
        self._cancel_save()
        if not self._expanded:
            return
        changes = self._collect(revert_empty=True)
        if changes:
            self._emit(changes)

    def expand(self, focus: bool = True, persist: bool = True) -> None:
        if self._expanded:
            return
        self._expanded = True
        self._build_editor()
        if persist:
            self._emit({"collapsed": False})
        else:
            self.note.collapsed = False
        self._render()
        if focus and self._text is not None:
            self._text.focus_set()
            self._text.mark_set("insert", "end-1c")

    def collapse(self, persist: bool = True) -> None:
        if not self._expanded:
            return
        self._cancel_save()
        changes = self._collect(revert_empty=True)
        self._expanded = False
        if persist:
            changes["collapsed"] = True
        else:
            self.note.collapsed = True
        if changes:
            self._emit(changes)
        self._destroy_editor()
        self._render()

    def set_compact(self, compact: bool) -> None:
        if compact != self._compact:
            self._compact = compact
            self._render()

    def apply_theme(self) -> None:
        self._chip_sig = None  # chip ใช้สีตายตัวตอนสร้าง → สร้างใหม่ตามธีม
        self._render()
        if self._text is not None:
            self._style_inputs()

    def focus_card(self) -> None:
        self.focus_set()

    def focus_content(self) -> None:
        """โฟกัสช่องเนื้อหา (ใช้หลัง Shift+Enter สร้างโน้ตแล้วกาง)"""
        if self._text is not None:
            self._text.focus_set()
            self._text.mark_set("insert", "end-1c")

    @property
    def expanded(self) -> bool:
        return self._expanded

    @property
    def ringing(self) -> bool:
        return bool(self.note.reminder_triggered and self.note.reminder_datetime)

    def animate_out(self, then: Callable[[], None] | None = None) -> None:
        """complete/restore: หดความสูง + ช่องว่างจนหาย ~250ms (spec 4.1) แล้วค่อยให้ board โหลดรายการใหม่"""
        self._removing = True
        h0 = max(1, self.winfo_height())
        gap = px(self, CARD_GAP_Y)

        def step(p: float) -> None:
            self.configure(height=max(1, int(h0 * (1 - p))))
            self.pack_configure(pady=(int(gap * (1 - p)), int(gap * (1 - p))))

        _animate(self, "out", 250, step, then)

    # ================================================================ render
    def _render(self) -> None:
        """วาดทุกอย่างจาก self.note ใหม่ทั้งหมด (ถูกเรียกหลังข้อมูล/โหมด/ธีมเปลี่ยน)"""
        n, th = self.note, self.th
        done = n.status == "completed"
        self._check.set_done(done)
        self._title_font = _done_font(th, "body_strong") if done else th.font("body_strong")
        self._title.configure(font=self._title_font)
        if n.is_pinned:
            self._pin.grid()
        else:
            self._pin.grid_remove()
        self._update_meta()
        self._relayout()
        self._paint()
        self._fit_w = 0
        self._fit_texts()
        self._update_chips()
        self._place_actions()

    def _relayout(self) -> None:
        """header → content → chips เสมอ (V4) — ถอดทั้งหมดแล้ว pack ใหม่ตามลำดับ"""
        compact = self._compact and not self._expanded
        self._top.pack_configure(pady=px(self, 2 if compact else PAD_Y))
        self._top.grid_rowconfigure(0, minsize=px(self, BTN_SIZE if not compact else BTN_SIZE - 2))
        self._col.grid_rowconfigure(0, minsize=px(self, BTN_SIZE if not compact else BTN_SIZE - 2))
        indent = px(self, INDENT)
        self._content_wrap.pack_forget()
        self._chips.pack_forget()
        if self._expanded:
            self._title.grid_remove()
            self._meta.grid_remove()
            # กันช่องหัวข้อชนปุ่มที่ลอยทับ: เว้นความกว้างของ [นาฬิกา][⋯] + pin (ถ้ามี)
            reserve = BTN_SIZE * 2 + 8 + (22 if self.note.is_pinned else 0)
            self._title_wrap.grid(row=0, column=0, sticky="we", padx=(0, px(self, reserve)))
            self._content_wrap.pack(fill="x", padx=(indent, px(self, PAD_X)), pady=(0, px(self, 4)))
        else:
            if self._title_wrap is not None:
                self._title_wrap.grid_remove()
            self._title.grid()
            if self._meta_visible and not compact:
                self._meta.grid()
            else:
                self._meta.grid_remove()
        if self._chips_needed():
            self._chips.pack(fill="x", padx=(indent, px(self, PAD_X)), pady=(0, px(self, PAD_Y)))

    def _paint(self) -> None:
        th, n = self.th, self.note
        if self._expanded or self._removing:
            bg = th.note_bg(n.color)
        else:
            bg = th.note_hover(n.color) if self._hover else th.note_bg(n.color)
        if self.ringing:
            border, width = "critical", 2
        elif self._focused:
            border, width = "accent", 2
        else:
            border, width = "stroke", 1
        self.set_colors(bg=bg, border=border, width=width)
        self.set_parent_bg(th.c("bg"))
        self._check.set_base(bg)
        for w in self._walk(self.body):
            if isinstance(w, IconButton):
                w.set_base_bg(bg)
            elif isinstance(w, (tk.Frame, tk.Label)) and w is not self._check:
                w.configure(bg=bg)
        done = n.status == "completed"
        self._title.configure(fg=th.c("text_secondary" if done else "text"))
        self._pin.configure(font=th.font("icon10"), fg=th.c("text_secondary"))
        self._saved_lbl.configure(font=th.font("caption"), fg=th.c("text_secondary"))
        for lbl in (self._m_time, self._m_text, self._m_prio, *self._m_sep):
            lbl.configure(font=th.font("caption"), fg=th.c("text_secondary"))
        self._m_icon.configure(font=th.font("icon10"))
        self._m_dot.configure(font=th.font("caption"))
        self._paint_meta_colors()
        self._place_actions()

    def _walk(self, w: tk.Misc):
        for child in w.winfo_children():
            if getattr(child, "_qn_fixed", False):
                continue
            yield child
            yield from self._walk(child)

    # ---------------------------------------------------------------- meta line
    def _update_meta(self) -> None:
        n = self.note
        lang = get_language()
        for w in (self._m_icon, self._m_time, self._m_dot, self._m_prio, self._m_text, *self._m_sep):
            w.pack_forget()
        groups: list[list[tk.Label]] = []
        self._meta_overdue = False
        if n.status == "completed":
            when = self._format_completed(n.completed_at, lang)
            self._m_text.configure(text=t("card.completed_meta", when=when) if when else "")
            self._meta_full = self._m_text.cget("text")
            if self._meta_full:
                groups.append([self._m_text])
        else:
            if n.reminder_datetime:
                text, overdue = format_reminder(n.reminder_datetime, datetime.now(), lang)
                if self.ringing:
                    # ตอนกำลังดัง "เลยกำหนด" ฟังดูเหมือนพลาดไปแล้ว ทั้งที่เพิ่งถึงเวลา
                    text = t("card.ringing_at", hm=n.reminder_datetime[-5:])
                self._meta_overdue = overdue
                self._m_icon.configure(text=ICONS["repeat" if n.reminder_repeat != "none" else "clock"])
                self._m_time.configure(text=" " + text)
                groups.append([self._m_icon, self._m_time])
            if n.priority != "none":
                self._m_dot.configure(text="●")
                self._m_prio.configure(text=" " + t(f"priority.{n.priority}"))
                groups.append([self._m_dot, self._m_prio])
            self._meta_full = _first_line(n.content)
            self._m_text.configure(text=self._meta_full)
            if self._meta_full:
                groups.append([self._m_text])
        self._meta_visible = bool(groups)
        sep = 0
        for i, group in enumerate(groups):
            if i:
                self._m_sep[sep].pack(side="left")
                sep += 1
            for w in group:
                w.pack(side="left")

    def _paint_meta_colors(self) -> None:
        th, n = self.th, self.note
        crit = n.status == "active" and (self.ringing or self._meta_overdue)
        self._m_icon.configure(fg=th.c("critical" if crit else "text_secondary"))
        self._m_time.configure(fg=th.c("critical" if crit else "text_secondary"),
                               font=th.font("body_strong" if self.ringing else "caption"))
        self._m_dot.configure(fg=th.c(PRIORITY_TOKEN.get(n.priority, "text_secondary")))

    @staticmethod
    def _format_completed(stamp: str | None, lang: str) -> str:
        """'เสร็จเมื่อ' ใช้ format_reminder กับเวลาอดีตไม่ได้ (จะได้ "เลยกำหนด") → ประกอบวันเองจากวันที่"""
        if not stamp:
            return ""
        try:
            dt = datetime.fromisoformat(stamp)
        except ValueError:
            return ""
        today = datetime.now().date()
        hm = dt.strftime("%H:%M")
        if dt.date() == today:
            return t("card.when_today", hm=hm)
        if dt.date() == today - timedelta(days=1):
            return t("card.when_yesterday", hm=hm)
        return format_reminder(dt.strftime("%Y-%m-%d %H:%M"), datetime(1970, 1, 1), lang)[0]

    # ---------------------------------------------------------------- text fitting
    def _on_col_configure(self, e) -> None:
        if e.width != self._fit_w and e.width > 1:
            self._fit_w = e.width
            self._fit_texts()

    def _fit_texts(self) -> None:
        w = self._col.winfo_width()
        if w <= 1:
            return
        self._fit_w = w
        title = self.note.title or t("common.untitled")
        self._title.configure(text=ellipsize(title, self._title_font, w - 2))
        if self._meta_full and self._m_text.winfo_manager():
            used = sum(c.winfo_reqwidth() for c in self._meta.winfo_children()
                       if c is not self._m_text and c.winfo_manager())
            font = self.th.font("caption")
            self._m_text.configure(text=ellipsize(self._meta_full, font, w - used - px(self, 4)))

    # ---------------------------------------------------------------- hover buttons
    def _show_actions(self) -> bool:
        return self._hover or self._focused or self._expanded or self._menu_open

    def _place_actions(self) -> None:
        if not self._show_actions() or self._removing:
            self._actions.place_forget()
            return
        shift = px(self, 22) if self.note.is_pinned else 0
        self._actions.place(relx=1.0, x=-shift, y=0, anchor="ne")
        self._actions.lift()

    def _on_enter(self, _e=None) -> None:
        if not self._hover:
            self._hover = True
            self._paint()

    def _on_leave(self, _e=None) -> None:
        # <Leave> ยิงตอนเมาส์ย้ายเข้าลูกด้วย → เช็กตำแหน่งจริง ไม่งั้นปุ่มกระพริบ
        if self._hover and not self._menu_open and not is_pointer_inside(self):
            self._hover = False
            self._paint()

    def _on_focus_in(self, _e) -> None:
        self._sync_focus()

    def _on_focus_out(self, _e) -> None:
        self.after_idle(self._sync_focus)

    def _sync_focus(self) -> None:
        """focus ring เฉพาะตอนตัวการ์ดเองถือ focus (Tk ส่ง FocusIn มาให้ตัวแม่ตอนลูกได้ focus ด้วย)"""
        try:
            focused = self.focus_get() is self
        except (tk.TclError, KeyError):
            focused = False
        if focused != self._focused:
            self._focused = focused
            self._paint()

    # ================================================================ interaction
    def _on_click(self, _e=None) -> None:
        if self._removing:
            return
        if not self._expanded:
            self.focus_set()
            self.callbacks.on_request_expand(self.note.id)

    def _key_expand(self) -> str:
        if not self._expanded:
            self.callbacks.on_request_expand(self.note.id)
        return "break"

    def _key_complete(self) -> str:
        self._toggle_complete()
        return "break"

    def _toggle_complete(self) -> None:
        if self._removing:
            return
        # ตอบสนองทันที (วงกลมเปลี่ยนเป็นสถานะใหม่) ก่อน board จะเขียน DB และหดการ์ด
        self._check.set_done(self.note.status == "active")
        self.callbacks.on_toggle_complete(self.note.id)

    def _toggle_pin(self) -> None:
        self.callbacks.on_pin(self.note.id, not self.note.is_pinned)

    # ---------------------------------------------------------------- context menu
    def _popup_from_button(self) -> None:
        self._popup(self._more.winfo_rootx(), self._more.winfo_rooty() + self._more.winfo_height())

    def _on_context(self, e) -> str:
        self._popup(e.x_root, e.y_root)
        return "break"

    def _popup(self, x: int, y: int) -> None:
        self._build_menu()
        self._menu_open = True
        self._place_actions()
        try:
            self._menu.tk_popup(x, y)
        finally:
            self._menu.grab_release()
            self._menu_open = False
            if self.winfo_exists():
                self._hover = is_pointer_inside(self)
                self._paint()

    def _build_menu(self) -> None:
        n, cb, m = self.note, self.callbacks, self._menu
        m.delete(0, "end")
        for sub in self._submenus:
            sub.destroy()
        self._submenus = []
        done = n.status == "completed"
        m.add_command(label=t("card.menu.restore" if done else "card.menu.complete"),
                      accelerator="Ctrl+Enter", command=self._toggle_complete)
        m.add_command(label=t("card.menu.unpin" if n.is_pinned else "card.menu.pin"),
                      accelerator="Ctrl+P", command=self._toggle_pin)
        m.add_command(label=t("card.menu.reminder"), accelerator="Ctrl+R",
                      command=lambda: cb.on_reminder(n.id))
        m.add_cascade(label=t("card.menu.priority"), menu=self._radio_menu(
            self._prio_var, n.priority, ("high", "medium", "low", "none"), "priority",
            lambda v: cb.on_priority(n.id, v)))
        m.add_cascade(label=t("card.menu.color"), menu=self._radio_menu(
            self._color_var, n.color, ("none", "yellow", "green", "pink", "purple", "blue", "gray"), "color",
            lambda v: cb.on_color(n.id, v)))
        m.add_separator()
        m.add_command(label=t("card.menu.delete"), accelerator="Delete", command=lambda: cb.on_delete(n.id))

    def _radio_menu(self, var: tk.StringVar, current: str, values: tuple, key: str,
                    command: Callable[[str], None]) -> tk.Menu:
        sub = tk.Menu(self._menu, tearoff=0)
        var.set(current)
        for v in values:
            sub.add_radiobutton(label=t(f"{key}.{v}"), variable=var, value=v, command=lambda v=v: command(v))
        self._submenus.append(sub)
        return sub

    # ================================================================ chips
    def _chips_needed(self) -> bool:
        return self._expanded or (self.ringing and self.note.status == "active")

    def _snooze_minutes(self) -> int:
        try:
            return int(self.th.settings.get("snooze_default_minutes", 5))
        except Exception:
            return 5

    def _update_chips(self) -> None:
        n = self.note
        sig = (self._expanded, self.ringing, n.reminder_datetime, n.reminder_repeat, n.priority, n.status,
               self._snooze_minutes(), get_language(), self.th.mode, self._meta_overdue)
        if sig == self._chip_sig:
            return
        self._chip_sig = sig
        for child in self._chip_row.winfo_children():
            child.destroy()
        cb = self.callbacks
        if self.ringing and n.status == "active":
            self._chip(t("card.alarm_done"), lambda: cb.on_alarm_done(n.id), filled=True)
            self._chip(t("card.alarm_snooze", n=self._snooze_minutes()), lambda: cb.on_alarm_snooze(n.id))
        if self._expanded and n.status == "active":
            if n.reminder_datetime:
                text, overdue = format_reminder(n.reminder_datetime, datetime.now(), get_language())
                self._chip(text, lambda: cb.on_reminder(n.id),
                           icon=ICONS["repeat" if n.reminder_repeat != "none" else "clock"],
                           fg="critical" if overdue else "text",
                           on_clear=lambda: cb.on_clear_reminder(n.id))
            else:
                self._chip(t("card.chip.add_reminder"), lambda: cb.on_reminder(n.id), icon=ICONS["clock"],
                           fg="text_secondary")
            if n.priority != "none":
                self._chip(t(f"priority.{n.priority}"), self._popup_priority, dot=PRIORITY_TOKEN[n.priority],
                           caret=True)
            else:
                self._chip(t("card.menu.priority"), self._popup_priority, icon=ICONS["flag"],
                           fg="text_secondary", caret=True)
        self._saved_lbl.lift()
        self._relayout()

    def _popup_priority(self) -> None:
        n, cb = self.note, self.callbacks
        menu = tk.Menu(self, tearoff=0)
        var = tk.StringVar(master=self, value=n.priority)
        for v in ("high", "medium", "low", "none"):
            menu.add_radiobutton(label=t(f"priority.{v}"), variable=var, value=v,
                                 command=lambda v=v: cb.on_priority(n.id, v))
        self._menu_open = True
        try:
            menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            menu.grab_release()
            self._menu_open = False
            self.after(300, menu.destroy)  # รอให้ command ของรายการที่เลือกทำงานก่อนค่อยทำลาย

    def _chip(self, text: str, on_click: Callable[[], None], icon: str | None = None, fg: str = "text",
              on_clear: Callable[[], None] | None = None, filled: bool = False, dot: str | None = None,
              caret: bool = False) -> tk.Frame:
        th = self.th
        base = th.c("accent") if filled else th.c("surface")
        edge = th.c("accent") if filled else th.c("stroke_strong")
        text_fg = th.c("on_accent") if filled else th.c(fg)
        frame = _fixed(tk.Frame(self._chip_row, bg=base, bd=0, highlightthickness=1, highlightbackground=edge,
                                cursor="hand2"))
        frame.pack(side="left", padx=(0, px(self, 6)))
        parts: list[tk.Label] = []

        def label(txt: str, font: str, color: str, **kw) -> tk.Label:
            lb = tk.Label(frame, text=txt, font=th.font(font), bg=base, fg=color, bd=0, padx=0, pady=0, **kw)
            lb.pack(side="left")
            parts.append(lb)
            return lb

        pad = px(self, 6)
        if icon:
            label(icon, "icon10", th.c(fg if not filled else "on_accent")).pack_configure(padx=(pad, px(self, 4)))
        elif dot:
            label("●", "caption", th.c(dot)).pack_configure(padx=(pad, px(self, 3)))
        main = label(text, "caption", text_fg)
        main.pack_configure(padx=(pad if not (icon or dot) else 0, pad), pady=px(self, 3))
        if caret:
            label(ICONS["chevron_down"], "icon10", th.c("text_secondary")).pack_configure(padx=(0, pad))
        clear = None
        if on_clear is not None:
            clear = label(ICONS["cancel"], "icon10", th.c("text_secondary"))
            clear.pack_configure(padx=(0, pad))
            clear.configure(cursor="hand2")
            clear.bind("<Button-1>", lambda e: (on_clear(), "break")[1])
            Tooltip(clear, lambda: t("card.chip.reminder_clear_tip"), theme=th)

        hover = th.c("accent") if filled else th.c("subtle_hover")
        hover = blend(hover, "#000000", 0.12) if filled else hover

        def tint(color: str) -> None:
            try:
                frame.configure(bg=color)
                for p in parts:
                    p.configure(bg=color)
            except tk.TclError:
                pass

        for w in (frame, *parts):
            w.bind("<Enter>", lambda e: tint(hover), add="+")
            w.bind("<Leave>", lambda e: tint(base) if not is_pointer_inside(frame) else None, add="+")
            if w is not clear:
                w.bind("<Button-1>", lambda e: (on_click(), "break")[1], add="+")
            self._wire(w)
        return frame

    # ================================================================ editor (expanded)
    def _build_editor(self) -> None:
        th = self.th
        self._title_var.set(self.note.title)
        # ห่อ Entry ด้วย frame เพื่อให้ได้ padding ใน + ขอบ 1px (tk.Entry ไม่มี padx)
        self._title_wrap = _fixed(tk.Frame(self._col, bd=0, highlightthickness=1))
        self._title_entry = tk.Entry(self._title_wrap, textvariable=self._title_var, font=th.font("body_strong"),
                                     bd=0, relief="flat", highlightthickness=0)
        self._title_entry.pack(fill="x", padx=px(self, 6), pady=px(self, 3))
        self._title_ph = self._make_placeholder(self._title_entry, t("card.title_placeholder"), 0, 0)
        self._text = tk.Text(self._content_wrap, height=3, wrap="word", undo=True, bd=0, relief="flat",
                             padx=px(self, 6), pady=px(self, 4), highlightthickness=1, font=th.font("body"))
        self._text.pack(fill="x")
        self._text_ph = self._make_placeholder(self._text, t("card.content_placeholder"), px(self, 8), px(self, 5))
        self._set_text(self.note.content)
        self._style_inputs()

        self._title_trace = self._title_var.trace_add("write", self._on_title_var)
        self._text.bind("<<Modified>>", self._on_text_modified)
        self._text.bind("<Configure>", lambda e: self._fit_text_height())
        for w in (self._title_entry, self._text):
            forward_shortcuts(w)
            w.bind("<FocusIn>", self._on_input_focus, add="+")
            w.bind("<FocusOut>", self._on_input_blur, add="+")
            self._wire(w)
        self._wire(self._title_wrap)
        self._saved = {"title": self.note.title, "content": self.note.content}

    def _destroy_editor(self) -> None:
        if self._title_trace is not None:
            self._title_var.trace_remove("write", self._title_trace)
            self._title_trace = None
        for w in (self._title_wrap, self._text):
            if w is not None:
                w.destroy()
        self._title_wrap = self._text = self._title_entry = self._title_ph = self._text_ph = None

    def _style_inputs(self) -> None:
        th = self.th
        if self._title_entry is not None:
            self._title_entry.configure(bg=th.c("surface"), fg=th.c("text"), insertbackground=th.c("text"),
                                        selectbackground=th.c("accent"), selectforeground=th.c("on_accent"),
                                        font=th.font("body_strong"))
        if self._title_wrap is not None:
            self._title_wrap.configure(bg=th.c("surface"), highlightbackground=th.c("stroke_strong"),
                                       highlightcolor=th.c("accent"))
        if self._text is not None:
            self._text.configure(bg=th.c("surface"), fg=th.c("text"), insertbackground=th.c("text"),
                                 selectbackground=th.c("accent"), selectforeground=th.c("on_accent"),
                                 highlightbackground=th.c("stroke_strong"), highlightcolor=th.c("accent"),
                                 font=th.font("body"))
        for ph in (self._title_ph, self._text_ph):
            if ph is not None:
                ph.configure(bg=th.c("surface"), fg=th.c("text_disabled"), font=th.font("body"))

    def _make_placeholder(self, widget: tk.Misc, text: str, x: int, y: int) -> tk.Label:
        lb = _fixed(tk.Label(widget, text=text, anchor="w", bd=0, padx=0, pady=0, cursor="xterm"))
        lb.bind("<Button-1>", lambda e: widget.focus_set())
        lb._qn_xy = (x, y)  # type: ignore[attr-defined]
        return lb

    def _update_placeholders(self) -> None:
        if self._text is None:
            return
        pairs = ((self._title_ph, self._title_var.get()), (self._text_ph, self._text.get("1.0", "end-1c")))
        for ph, value in pairs:
            if ph is None:
                continue
            if value:
                ph.place_forget()
            else:
                x, y = ph._qn_xy
                ph.place(x=x, y=y)

    def _set_text(self, content: str) -> None:
        assert self._text is not None
        self._text.delete("1.0", "end")
        self._text.insert("1.0", content)
        self._text.edit_reset()
        self._text.edit_modified(False)
        self._fit_text_height()
        self._update_placeholders()

    def _fit_text_height(self) -> None:
        """สูงตามเนื้อหา 3–12 บรรทัด (นับบรรทัดที่ตัดคำแล้ว)"""
        if self._text is None:
            return
        try:
            res = self._text.count("1.0", "end-1c", "displaylines")
            n = int(res[0]) if res else 1
        except (tk.TclError, ValueError, TypeError):
            n = 3
        n = max(3, min(12, n))
        if int(self._text.cget("height")) != n:
            self._text.configure(height=n)

    # ---------------------------------------------------------------- save pipeline (C7/C8)
    def _on_title_var(self, *_a) -> None:
        self._update_placeholders()
        self._schedule_save()

    def _on_text_modified(self, _e=None) -> None:
        if self._text is None or not self._text.edit_modified():
            return
        self._text.edit_modified(False)
        self._fit_text_height()
        self._update_placeholders()
        self._schedule_save()

    def _on_input_focus(self, e) -> None:
        self._update_placeholders()

    def _on_input_blur(self, _e) -> None:
        # ออกจากช่อง = บันทึกทันที (รวมคืนค่าหัวข้อเดิมถ้าลบจนว่าง — M19)
        self.after_idle(self._blur_flush)

    def _blur_flush(self) -> None:
        try:
            if self.winfo_exists() and self._expanded:
                self.flush_pending()
                self._update_placeholders()
        except tk.TclError:
            pass

    def _schedule_save(self) -> None:
        self._cancel_save()
        self._save_job = self.after(SAVE_DEBOUNCE_MS, self._on_save_timer)

    def _cancel_save(self) -> None:
        if self._save_job is not None:
            try:
                self.after_cancel(self._save_job)
            except (tk.TclError, ValueError):
                pass
            self._save_job = None

    def _on_save_timer(self) -> None:
        self._save_job = None
        try:
            if not self.winfo_exists() or not self._expanded:
                return
            changes = self._collect(revert_empty=False)  # ระหว่างพิมพ์หัวข้อว่างชั่วคราวได้ ไม่ต้องคืนค่าเดิม
        except (tk.TclError, AttributeError):
            return
        if changes:
            self._emit(changes)

    def _collect(self, revert_empty: bool) -> dict:
        """อ่านค่าจาก widget เทียบกับค่าที่บันทึกล่าสุด → dict เฉพาะที่เปลี่ยน"""
        changes: dict = {}
        try:
            if self._title_entry is not None:
                title = self._title_var.get().strip()
                if not title:
                    if revert_empty:
                        self._title_var.set(self._saved["title"])
                elif title != self._saved["title"]:
                    changes["title"] = title
            if self._text is not None:
                content = self._text.get("1.0", "end-1c")
                if content != self._saved["content"]:
                    changes["content"] = content
        except tk.TclError:
            return {}
        return changes

    def _emit(self, changes: dict) -> None:
        for key in ("title", "content", "collapsed"):
            if key in changes:
                setattr(self.note, key, changes[key])
                if key in self._saved:
                    self._saved[key] = changes[key]
        try:
            self.callbacks.on_save(self.note.id, dict(changes))
        except Exception:
            log.exception("on_save failed for %s", self.note.id)
            return
        if ("title" in changes or "content" in changes) and self._expanded:
            self._show_saved()
            if "title" in changes:
                self._fit_w = 0
                self._fit_texts()

    def _show_saved(self) -> None:
        """caption "บันทึกแล้ว" จางหายใน 1.5 วินาที"""
        self._saved_lbl.configure(text=t("card.saved"))
        start, bg = self.th.c("text_secondary"), self._saved_lbl.cget("bg")

        def step(p: float) -> None:
            self._saved_lbl.configure(fg=blend(start, bg, p))

        def done() -> None:
            self._saved_lbl.configure(text="")

        _animate(self._saved_lbl, "saved", SAVED_CAPTION_MS, step, done)

    # ================================================================ misc
    def _on_destroy(self, e) -> None:
        if e.widget is self:
            self._cancel_save()
