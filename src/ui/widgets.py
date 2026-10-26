"""Custom widgets ของ QuickNote v3 — IconButton, Tooltip, PlaceholderEntry, RoundedFrame, UndoBar, SettingsCard + animation helpers

ทุก widget อ่านสีจาก Theme token (ไม่ hardcode) และตอบ apply_theme() เมื่อธีมเปลี่ยน
"""

from __future__ import annotations

import inspect
import time
import tkinter as tk
from tkinter import ttk
from typing import Callable

from . import win11
from .strings import t
from .theme import Theme, blend, current_theme


# ---------------------------------------------------------------- helpers
def px(widget: tk.Misc, n: float) -> int:
    """ขนาด 'px ที่ DPI 96' → พิกเซลจริง (Tk ไม่ scale ตัวเลขพิกเซลให้เอง เมื่อ DPI > 100%)"""
    try:
        return max(1, round(n * widget.winfo_fpixels("1i") / 96.0))
    except tk.TclError:
        return int(n)


def _parent_bg(parent: tk.Misc, fallback: str) -> str:
    """พื้นหลังของ parent ที่เป็น tk widget (ttk ไม่มี bg ให้อ่าน → ใช้ fallback)"""
    for opt in ("bg", "background"):
        try:
            return str(parent.cget(opt))
        except (tk.TclError, AttributeError):
            continue
    return fallback


def _resolve_color(theme: Theme, spec: str) -> str:
    """spec เป็น hex/ชื่อสีระบบ → ใช้ตรง ๆ, นอกนั้นถือเป็นชื่อ token"""
    if spec.startswith("#") or spec.startswith("System"):
        return spec
    return theme.c(spec)


def _accepts_arg(fn: Callable) -> bool:
    try:
        for p in inspect.signature(fn).parameters.values():
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD, p.VAR_POSITIONAL):
                return True
    except (TypeError, ValueError):
        pass
    return False


def is_pointer_inside(widget: tk.Misc) -> bool:
    """เมาส์อยู่ใน widget (หรือลูกหลานของมัน) ไหม — ใช้แทน <Leave> ของ frame ที่ยิงตอนเมาส์ย้ายไปลูก (hover กระพริบ)"""
    try:
        x, y = widget.winfo_pointerxy()
        w = widget.winfo_containing(x, y)
    except (tk.TclError, KeyError):
        return False  # KeyError: Tk คืนชื่อ popdown ของ combobox ที่ map เป็น widget ไม่ได้
    while w is not None:
        if w == widget:
            return True
        w = getattr(w, "master", None)
    return False


# ---------------------------------------------------------------- Tooltip
class Tooltip:
    """tooltip หน่วง 500ms — แสดงตอน hover และตอน keyboard focus, ซ่อนเมื่อออก/คลิก"""

    def __init__(self, widget: tk.Misc, text: str | Callable[[], str], delay_ms: int = 500,
                 theme: Theme | None = None) -> None:
        self.widget = widget
        self._text = text
        self.delay_ms = delay_ms
        self._theme = theme
        self._job: str | None = None
        self._tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<FocusIn>", self._schedule, add="+")
        for ev in ("<Leave>", "<ButtonPress>", "<FocusOut>", "<Destroy>", "<Unmap>"):
            widget.bind(ev, self.hide, add="+")

    def set_text(self, text: str | Callable[[], str]) -> None:
        self._text = text

    def _current_text(self) -> str:
        try:
            return self._text() if callable(self._text) else str(self._text)
        except Exception:
            return ""

    def _schedule(self, _e=None) -> None:
        self._cancel()
        try:
            self._job = self.widget.after(self.delay_ms, self._due)
        except tk.TclError:
            self._job = None

    def _cancel(self) -> None:
        if self._job is not None:
            try:
                self.widget.after_cancel(self._job)
            except (tk.TclError, ValueError):
                pass
            self._job = None

    def _due(self) -> None:
        self._job = None
        # ระหว่างรอ เมาส์อาจออกไปแล้ว (Leave ถูกกลืน) → แสดงเฉพาะตอนที่ยังอยู่บน widget หรือ widget มี focus
        try:
            if is_pointer_inside(self.widget) or self.widget.focus_get() == self.widget:
                self.show()
        except (tk.TclError, KeyError):
            pass

    def show(self) -> None:
        self.hide()
        text = self._current_text()
        theme = self._theme or current_theme()
        if not text or theme is None:
            return
        try:
            tip = tk.Toplevel(self.widget)
            tip.withdraw()
            tip.overrideredirect(True)
            tip.attributes("-topmost", True)
            tip.configure(bg=theme.c("stroke_strong"))  # พื้น Toplevel = สีขอบ 1px (Label ข้างในเว้น 1px)
            tk.Label(tip, text=text, font=theme.font("caption"), bg=theme.c("surface"), fg=theme.c("text"),
                     padx=8, pady=4, justify="left", wraplength=px(self.widget, 320)).pack(padx=1, pady=1)
            tip.update_idletasks()
            w, h = tip.winfo_reqwidth(), tip.winfo_reqheight()
            left, top, right, bottom = win11.get_work_area(self.widget.winfo_toplevel())
            x = max(left, min(self.widget.winfo_rootx(), right - w - 4))
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + px(self.widget, 6)
            if y + h > bottom:  # ไม่พอข้างล่าง → ขึ้นไปอยู่เหนือ widget
                y = self.widget.winfo_rooty() - h - px(self.widget, 6)
            tip.geometry(f"+{x}+{max(top, y)}")
            tip.deiconify()
            self._tip = tip
        except tk.TclError:
            self._tip = None

    def hide(self, _e=None) -> None:
        self._cancel()
        if self._tip is not None:
            try:
                self._tip.destroy()
            except tk.TclError:
                pass
            self._tip = None


# ---------------------------------------------------------------- IconButton
class IconButton(tk.Label):
    """ปุ่มไอคอน (tk.Label + ฟอนต์ไอคอน) — hover/pressed/focus ring ตาม token, toggle ได้

    command: ปุ่มปกติเรียก command() ; toggle=True จะพลิกสถานะก่อนแล้วเรียก command(state) ถ้า command รับ
    argument (ไม่รับก็เรียก command() แล้วอ่าน .active เอง)
    """

    def __init__(self, parent: tk.Misc, theme: Theme, icon: str, command: Callable | None = None,
                 tooltip: str | Callable[[], str] = "", size: int = 32, toggle: bool = False,
                 fg_token: str = "text", font_style: str | None = None, base_bg: str | None = None) -> None:
        self._theme = theme
        self._command = command
        self._toggle = toggle
        self._fg_token = fg_token
        self._size = size
        self._active = False
        self._enabled = True
        self._hover = False
        self._pressed = False
        self._base_override = base_bg
        self._hl = 2  # ความหนา focus ring (spec 2.5)
        # ภาพโปร่งใส 1x1 ทำให้ width/height ของ Label นับเป็นพิกเซลแทนจำนวนตัวอักษร
        self._pixel = tk.PhotoImage(master=parent, width=1, height=1)
        side = px(parent, size) - 2 * self._hl
        font = theme.font(font_style or ("icon12" if size >= 32 else "icon10"))
        base = base_bg or _parent_bg(parent, theme.c("bg"))
        super().__init__(parent, text=icon, font=font, image=self._pixel, compound="center",
                         width=side, height=side, bd=0, padx=0, pady=0, takefocus=True,
                         highlightthickness=self._hl, highlightbackground=base,
                         highlightcolor=theme.c("accent"), bg=base, fg=theme.c(fg_token))
        self._tooltip = Tooltip(self, tooltip, theme=theme) if tooltip else None
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<space>", self._on_key)
        self.bind("<Return>", self._on_key)
        self.bind("<Destroy>", self._on_destroy)
        self._unsub = theme.subscribe(self._on_theme)
        self._paint()

    # --- public API
    @property
    def active(self) -> bool:
        return self._active

    def set_active(self, active: bool) -> None:
        self._active = bool(active)
        self._paint()

    def set_icon(self, icon: str) -> None:
        self.configure(text=icon)

    def set_command(self, command: Callable | None) -> None:
        self._command = command

    def set_tooltip(self, text: str | Callable[[], str]) -> None:
        if self._tooltip is None:
            self._tooltip = Tooltip(self, text, theme=self._theme)
        else:
            self._tooltip.set_text(text)

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        self.configure(takefocus=self._enabled)
        self._paint()

    def set_base_bg(self, color: str | None) -> None:
        """พื้นหลังที่ปุ่ม "กลืน" (เช่นสีการ์ด) — None = อ่านจาก parent ทุกครั้ง"""
        self._base_override = color
        self._paint()

    def apply_theme(self) -> None:
        try:
            self.configure(highlightcolor=self._theme.c("accent"))
        except tk.TclError:
            return
        self._paint()

    def invoke(self) -> None:
        if not self._enabled:
            return
        if self._toggle:
            self._active = not self._active
            self._paint()
        cmd = self._command
        if cmd is None:
            return
        if self._toggle and _accepts_arg(cmd):
            cmd(self._active)
        else:
            cmd()

    # --- internals
    def _base(self) -> str:
        return self._base_override or _parent_bg(self.master, self._theme.c("bg"))

    def _paint(self) -> None:
        th = self._theme
        base = self._base()
        if not self._enabled:
            bg, fg = base, th.c("text_disabled")
        elif self._active:
            bg = th.c("accent")
            if self._pressed:
                bg = blend(bg, "#000000", 0.15)
            elif self._hover:
                bg = blend(bg, "#FFFFFF" if th.mode == "dark" else "#000000", 0.08)
            fg = th.c("on_accent")
        elif self._pressed:
            bg, fg = th.c("subtle_pressed"), th.c(self._fg_token)
        elif self._hover:
            bg, fg = th.c("subtle_hover"), th.c(self._fg_token)
        else:
            bg, fg = base, th.c(self._fg_token)
        try:
            # ring ใช้ highlightbackground = base เพื่อ "มองไม่เห็น" ตอนไม่มี focus
            self.configure(bg=bg, fg=fg, highlightbackground=base)
        except tk.TclError:
            pass

    def _on_enter(self, _e) -> None:
        self._hover = True
        self._paint()

    def _on_leave(self, _e) -> None:
        self._hover = False
        self._pressed = False
        self._paint()

    def _on_press(self, _e) -> None:
        if self._enabled:
            self._pressed = True
            self._paint()

    def _on_release(self, e) -> None:
        was = self._pressed
        self._pressed = False
        self._paint()
        # คลิกที่นับ = ปล่อยเมาส์ขณะยังอยู่บนปุ่ม (เหมือนปุ่ม Windows ทั่วไป)
        if was and 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height():
            self.invoke()

    def _on_key(self, _e) -> str:
        self.invoke()
        return "break"

    def _on_theme(self) -> None:
        # พื้นของ parent อาจยังไม่ถูกเปลี่ยนในรอบเดียวกัน → รอ idle ค่อยอ่านใหม่
        try:
            self.after_idle(self.apply_theme)
        except tk.TclError:
            pass

    def _on_destroy(self, e) -> None:
        if e.widget is self:
            self._unsub()


# ---------------------------------------------------------------- PlaceholderEntry
class PlaceholderEntry(ttk.Entry):
    """ttk.Entry ที่แสดงข้อความจางเมื่อว่างและไม่มี focus

    เก็บ StringVar ภายในแยกจาก textvariable ที่ผู้ใช้ส่งมา — ตัวแปรของผู้ใช้จะไม่เคยเห็นข้อความ placeholder
    (ถ้าใช้ตัวแปรเดียวกัน trace ของ search/debounce จะยิงตอนเราใส่/ลบ placeholder)
    """

    def __init__(self, parent: tk.Misc, placeholder: str, textvariable: tk.StringVar | None = None,
                 style: str = "TEntry", placeholder_style: str = "Placeholder.TEntry", **kw) -> None:
        self._var = tk.StringVar(master=parent)
        self._ext = textvariable
        self._placeholder = placeholder
        self._base_style = style
        self._ph_style = placeholder_style
        self._showing = False
        self._syncing = False
        self._traces: list[tuple[tk.Variable, str, str]] = []
        super().__init__(parent, textvariable=self._var, style=style, **kw)
        if self._ext is not None:
            self._var.set(self._ext.get())
            self._traces.append((self._var, "write", self._var.trace_add("write", self._int_changed)))
            self._traces.append((self._ext, "write", self._ext.trace_add("write", self._ext_changed)))
        self.bind("<FocusIn>", self._on_focus_in, add="+")
        self.bind("<FocusOut>", self._on_focus_out, add="+")
        self.bind("<Destroy>", self._on_destroy, add="+")
        self._refresh()

    # --- public API
    def get_value(self) -> str:
        return "" if self._showing else self._var.get()

    def set_value(self, text: str) -> None:
        self._showing = False
        self.configure(style=self._base_style)
        self._var.set(text)
        self._refresh()

    def clear(self) -> None:
        self.set_value("")

    def set_placeholder(self, text: str) -> None:
        self._placeholder = text
        if self._showing:
            self._write_internal(text)

    @property
    def showing_placeholder(self) -> bool:
        return self._showing

    # --- internals
    def _write_internal(self, text: str) -> None:
        self._syncing = True  # ไม่ให้ placeholder รั่วไปที่ตัวแปรของผู้ใช้
        try:
            self._var.set(text)
        finally:
            self._syncing = False

    def _refresh(self) -> None:
        """ว่างและไม่มี focus → โชว์ placeholder; ไม่ว่าง → ข้อความจริง"""
        try:
            focused = self.focus_get() == self
        except (tk.TclError, KeyError):
            focused = False
        if not self._showing and not self._var.get() and not focused:
            self._showing = True
            self.configure(style=self._ph_style)
            self._write_internal(self._placeholder)

    def _on_focus_in(self, _e) -> None:
        if self._showing:
            self._showing = False
            self.configure(style=self._base_style)
            self._write_internal("")

    def _on_focus_out(self, _e) -> None:
        self._refresh()

    def _int_changed(self, *_a) -> None:
        if self._ext is not None and not self._syncing and not self._showing:
            self._syncing = True
            try:
                if self._ext.get() != self._var.get():
                    self._ext.set(self._var.get())
            finally:
                self._syncing = False

    def _ext_changed(self, *_a) -> None:
        if self._ext is not None and not self._syncing and self._ext.get() != self.get_value():
            self.set_value(self._ext.get())

    def _on_destroy(self, e) -> None:
        if e.widget is self:
            for var, mode, name in self._traces:
                try:
                    var.trace_remove(mode, name)
                except (tk.TclError, ValueError):
                    pass
            self._traces.clear()


# ---------------------------------------------------------------- RoundedFrame
class RoundedFrame(tk.Canvas):
    """กรอบมุมโค้ง = Canvas วาด polygon smooth + frame เนื้อหา (.body) ที่ฝังด้วย create_window

    - ความสูงตามเนื้อหา (.body) ส่วนความกว้างตาม geometry manager (pack fill="x")
    - redraw ด้วย coords() ของ item เดิม ไม่สร้างใหม่ → เบาพอสำหรับการ์ด ~100 ใบ
    - .body ถูกเว้นขอบ `inset` px เพื่อไม่ให้มุมสี่เหลี่ยมของ frame ทับเส้นโค้ง
    - bg/border = ชื่อ token ("card", "stroke") หรือ hex
    """

    def __init__(self, parent: tk.Misc, theme: Theme, radius: int = 8, bg: str = "card",
                 border: str = "stroke", border_width: int = 1, parent_bg: str | None = None, **kw) -> None:
        self._theme = theme
        self.radius = radius
        self._bg_spec = bg
        self._border_spec = border
        self._bw = border_width
        self._parent_bg_override = parent_bg
        self.inset = border_width + int(radius * 0.3)
        super().__init__(parent, bg=parent_bg or _parent_bg(parent, theme.c("bg")),
                         highlightthickness=0, bd=0, width=1, height=1, **kw)
        self._shape = self.create_polygon(0, 0, 0, 0, 0, 0, smooth=True,
                                          fill=_resolve_color(theme, bg), outline=_resolve_color(theme, border),
                                          width=border_width)
        self.body = tk.Frame(self, bg=_resolve_color(theme, bg), bd=0, highlightthickness=0)
        # ใช้ place แทน create_window: window item จะไม่ถูกวาด/resize ถ้าอยู่นอกพื้นที่ canvas ที่ยังสูง 1px
        # ทำให้ไม่เคยมี <Configure> มาบอกความสูงเนื้อหา (ไก่กับไข่) — place จัดขนาดตามที่ body ขอเสมอ
        self.body.place(x=self.inset, y=self.inset, relwidth=1.0, width=-2 * self.inset)
        self._cw = self._ch = 0
        self.bind("<Configure>", self._on_configure)
        self.body.bind("<Configure>", self._on_body_configure)

    # --- public API
    def set_colors(self, bg: str | None = None, border: str | None = None, width: int | None = None) -> None:
        if bg is not None:
            self._bg_spec = bg
        if border is not None:
            self._border_spec = border
        if width is not None:
            self._bw = width
        fill = _resolve_color(self._theme, self._bg_spec)
        self.itemconfigure(self._shape, fill=fill, outline=_resolve_color(self._theme, self._border_spec),
                           width=self._bw)
        self.body.configure(bg=fill)
        self._redraw()

    def set_parent_bg(self, color: str) -> None:
        self._parent_bg_override = color
        self.configure(bg=color)

    def apply_theme(self) -> None:
        """re-resolve token → สีใหม่ (เรียกหลัง Theme เปลี่ยน; สี hex ที่ส่งมาตรง ๆ ไม่เปลี่ยน)"""
        self.configure(bg=self._parent_bg_override or _parent_bg(self.master, self._theme.c("bg")))
        self.set_colors()

    # --- internals
    def _on_configure(self, e) -> None:
        if e.width != self._cw or e.height != self._ch:
            self._cw, self._ch = e.width, e.height
            self._redraw()

    def _on_body_configure(self, _e) -> None:
        h = self.body.winfo_reqheight() + 2 * self.inset
        if int(self.cget("height")) != h:
            self.configure(height=h)

    def _redraw(self) -> None:
        w, h = self._cw, self._ch
        if w < 2 or h < 2:
            return
        r = max(1, min(self.radius, h // 2, w // 2))
        # เส้นขอบกว้าง bw วาดคร่อมพิกัด → ขยับเข้า bw/2 กันโดน canvas ตัด
        o = self._bw / 2.0
        x1, y1, x2, y2 = o, o, w - 1 - o + 0.5, h - 1 - o + 0.5
        pts = [x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y1 + r,
               x2, y2 - r, x2, y2 - r, x2, y2, x2 - r, y2, x2 - r, y2, x1 + r, y2, x1 + r, y2,
               x1, y2, x1, y2 - r, x1, y2 - r, x1, y1 + r, x1, y1 + r, x1, y1]
        self.coords(self._shape, *pts)


# ---------------------------------------------------------------- UndoBar
class UndoBar(tk.Frame):
    """แถบ "<ข้อความ> · เลิกทำ" ที่ล่างหน้าต่าง (ไม่ใช่ Toplevel)

    - show() แล้ว pack เองด้วย pack_options (ใส่ before=widget ได้ถ้าต้องอยู่เหนือ status bar)
    - แถบใหม่มาแทนแถบเก่า → เรียก on_expire ของอันเก่า "ทันที" (ลบจริง/ยืนยันก่อนค่อยโชว์อันใหม่)
    - flush() ใช้ตอนปิดแอป เพื่อให้ on_expire ที่ค้างอยู่ถูกเรียกก่อน
    """

    def __init__(self, parent: tk.Misc, theme: Theme, pack_options: dict | None = None) -> None:
        self._theme = theme
        self._pack = pack_options or {"side": "bottom", "fill": "x", "padx": 12, "pady": (0, 8)}
        super().__init__(parent, bd=0, highlightthickness=1, bg=theme.c("surface"),
                         highlightbackground=theme.c("stroke_strong"))
        self._msg = tk.Label(self, font=theme.font("body"), bg=theme.c("surface"), fg=theme.c("text"), anchor="w")
        self._msg.pack(side="left", fill="x", expand=True, padx=(12, 8), pady=8)
        self._btn = ttk.Button(self, text=t("undo.action"), style=theme.ttk_style("Link.TButton", "surface"),
                               command=self._on_undo_click, takefocus=True)
        self._btn.pack(side="right", padx=(0, 8), pady=4)
        self._job: str | None = None
        self._on_undo: Callable | None = None
        self._on_expire: Callable | None = None
        self._visible = False
        self._unsub = theme.subscribe(self._on_theme)
        self.bind("<Destroy>", self._on_destroy)

    @property
    def is_active(self) -> bool:
        return self._visible

    def show(self, message: str, on_undo: Callable[[], None], on_expire: Callable[[], None] | None = None,
             seconds: float = 5) -> None:
        self.flush()  # แถบเก่าที่ค้าง → จบเดี๋ยวนี้ (เรียก on_expire)
        self._on_undo, self._on_expire = on_undo, on_expire
        self._msg.configure(text=message)
        self._btn.configure(text=t("undo.action"))
        self.pack(**self._pack)
        self._visible = True
        self._job = self.after(int(seconds * 1000), self._expire)

    def hide(self) -> None:
        """ซ่อนโดยไม่เรียก callback ใด ๆ"""
        self._cancel()
        self._on_undo = self._on_expire = None
        self._visible = False
        try:
            self.pack_forget()
        except tk.TclError:
            pass

    def flush(self) -> None:
        """ถ้ามีแถบค้างอยู่ → จบทันทีและเรียก on_expire"""
        if self._visible:
            self._expire()

    def apply_theme(self) -> None:
        th = self._theme
        try:
            self.configure(bg=th.c("surface"), highlightbackground=th.c("stroke_strong"))
            self._msg.configure(bg=th.c("surface"), fg=th.c("text"))
            self._btn.configure(style=th.ttk_style("Link.TButton", "surface"))
        except tk.TclError:
            pass

    def _cancel(self) -> None:
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except (tk.TclError, ValueError):
                pass
            self._job = None

    def _expire(self) -> None:
        cb = self._on_expire
        self.hide()
        if cb:
            cb()

    def _on_undo_click(self) -> None:
        cb = self._on_undo
        self.hide()
        if cb:
            cb()

    def _on_theme(self) -> None:
        try:
            self.after_idle(self.apply_theme)
        except tk.TclError:
            pass

    def _on_destroy(self, e) -> None:
        if e.widget is self:
            self._unsub()


# ---------------------------------------------------------------- SettingsCard
class SettingsCard(tk.Frame):
    """การ์ดกลุ่มการตั้งค่าแบบ Windows 11 — แถว ≥56px, padding 16px, เส้นคั่น 1px, ชื่อ+คำอธิบายซ้าย control ขวา"""

    MIN_ROW = 56
    PAD = 16

    def __init__(self, parent: tk.Misc, theme: Theme) -> None:
        self._theme = theme
        super().__init__(parent, bd=0, highlightthickness=0, bg=_parent_bg(parent, theme.c("bg")))
        self._rf = RoundedFrame(self, theme, radius=8, bg="card", border="stroke")
        self._rf.pack(fill="x")
        self.body = self._rf.body
        self._rows: list[tuple[tk.Frame, tk.Label, tk.Label | None]] = []
        self._dividers: list[tk.Frame] = []
        self._unsub = theme.subscribe(self._on_theme)
        self.bind("<Destroy>", self._on_destroy)

    def ttk_style(self, base: str) -> str:
        """style ttk ที่พื้นหลังเป็นสี card (ใช้ในโรงงาน control: Switch, Combobox ฯลฯ)"""
        return self._theme.ttk_style(base, "card")

    def add_row(self, title: str, description: str | None,
                control_factory: Callable[[tk.Widget], tk.Widget]) -> tk.Widget:
        th = self._theme
        card = th.c("card")
        if self._rows:
            div = tk.Frame(self.body, height=1, bd=0, highlightthickness=0, bg=th.c("stroke"))
            div.pack(fill="x", padx=px(self, 1))
            self._dividers.append(div)
        row = tk.Frame(self.body, bg=card, bd=0, highlightthickness=0)
        row.pack(fill="x")
        row.grid_columnconfigure(0, weight=1)
        row.grid_rowconfigure(0, minsize=px(self, self.MIN_ROW))
        left = tk.Frame(row, bg=card)
        left.grid(row=0, column=0, sticky="w", padx=(px(self, self.PAD), px(self, 8)), pady=px(self, 8))
        title_lbl = tk.Label(left, text=title, font=th.font("body"), bg=card, fg=th.c("text"), anchor="w",
                             justify="left")
        title_lbl.pack(anchor="w")
        desc_lbl = None
        if description:
            desc_lbl = tk.Label(left, text=description, font=th.font("caption"), bg=card,
                                fg=th.c("text_secondary"), anchor="w", justify="left")
            desc_lbl.pack(anchor="w")
        control = control_factory(row)
        control.grid(row=0, column=1, sticky="e", padx=(px(self, 8), px(self, self.PAD)))
        self._rows.append((row, title_lbl, desc_lbl))

        def rewrap(_e=None, row=row, control=control, desc=desc_lbl, title=title_lbl) -> None:
            # คำอธิบายยาวต้องตัดบรรทัดไม่ให้ดัน control ออกนอกการ์ด
            try:
                room = row.winfo_width() - control.winfo_reqwidth() - px(self, 2 * self.PAD + 16)
                if room > 80:
                    title.configure(wraplength=room)
                    if desc is not None:
                        desc.configure(wraplength=room)
            except tk.TclError:
                pass
        row.bind("<Configure>", rewrap, add="+")
        return control

    def apply_theme(self) -> None:
        th = self._theme
        try:
            self.configure(bg=_parent_bg(self.master, th.c("bg")))
            self._rf.apply_theme()
            for row, title, desc in self._rows:
                row.configure(bg=th.c("card"))
                row.winfo_children()[0].configure(bg=th.c("card"))  # left frame
                title.configure(bg=th.c("card"), fg=th.c("text"))
                if desc is not None:
                    desc.configure(bg=th.c("card"), fg=th.c("text_secondary"))
            for d in self._dividers:
                d.configure(bg=th.c("stroke"))
        except tk.TclError:
            pass

    def _on_theme(self) -> None:
        try:
            self.after_idle(self.apply_theme)
        except tk.TclError:
            pass

    def _on_destroy(self, e) -> None:
        if e.widget is self:
            self._unsub()


# ---------------------------------------------------------------- animation (after-based, ปลอดภัยถ้า window ถูกทำลาย)
def _ease_out(p: float) -> float:
    return 1 - (1 - p) ** 3


def _animate(window: tk.Misc, key: str, ms: int, step: Callable[[float], None],
             then: Callable[[], None] | None) -> None:
    """วนเฟรมละ ~16ms ด้วย after; เรียก step(0..1); ยกเลิกงานเดิมของ key เดียวกัน; จบแล้วเรียก then"""
    jobs: dict = window.__dict__.setdefault("_qn_anim_jobs", {})
    old = jobs.pop(key, None)
    if old is not None:
        try:
            window.after_cancel(old)
        except (tk.TclError, ValueError):
            pass
    if ms <= 0 or not win11.animations_enabled():
        try:
            step(1.0)
        except tk.TclError:
            return
        if then:
            then()
        return
    t0 = time.monotonic()

    def tick() -> None:
        jobs.pop(key, None)
        try:
            if not window.winfo_exists():
                return
            p = min(1.0, (time.monotonic() - t0) * 1000.0 / ms)
            step(_ease_out(p))
            if p >= 1.0:
                if then:
                    then()
                return
            jobs[key] = window.after(16, tick)
        except tk.TclError:
            return  # window ถูกทำลายกลางแอนิเมชัน — เงียบ ๆ ไม่ต้องทำต่อ

    tick()


def fade_in(window: tk.Misc, ms: int = 150, to: float = 1.0, then: Callable[[], None] | None = None) -> None:
    """alpha 0 → to (เรียกก่อน/พร้อม deiconify)"""
    try:
        window.attributes("-alpha", 0.0)
    except tk.TclError:
        return
    _animate(window, "fade", ms, lambda p: window.attributes("-alpha", to * p), then)


def fade_out(window: tk.Misc, ms: int = 100, then: Callable[[], None] | None = None) -> None:
    """alpha ปัจจุบัน → 0 แล้วเรียก then (ปกติคือ destroy)"""
    try:
        start = float(window.attributes("-alpha"))
    except (tk.TclError, ValueError):
        start = 1.0
    _animate(window, "fade", ms, lambda p: window.attributes("-alpha", start * (1 - p)), then)


def slide_y(window: tk.Misc, dy: int, ms: int = 150, then: Callable[[], None] | None = None) -> None:
    """เลื่อน Toplevel จากตำแหน่งปัจจุบันไป +dy px (ลบ = ขึ้น) — slide-in: วางต่ำกว่าเป้า 16px แล้วเรียก slide_y(w, -16)"""
    try:
        x0, y0 = window.winfo_x(), window.winfo_y()
    except tk.TclError:
        return
    _animate(window, "slide", ms, lambda p: window.geometry(f"+{x0}+{round(y0 + dy * p)}"), then)
