"""QuickNote v3 theme — Windows 11 (Fluent) tokens, fonts, ธีมระบบ, ttk styles (DESIGN_SPEC 2.1–2.6)

เขียนใหม่ทั้งไฟล์ (v2 เป็น macOS pastel) — UI เก่าที่ import THEMES/PASTEL_PALETTE จะพังโดยตั้งใจ
"""

from __future__ import annotations

import logging
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk
from typing import Callable

from . import win11

try:  # sv-ttk คือ ttk theme สไตล์ Win11; ถ้าไม่มีแอปยังเปิดได้ (ใช้ธีม ttk มาตรฐาน)
    import sv_ttk
except Exception:  # pragma: no cover
    sv_ttk = None

log = logging.getLogger(__name__)

# ---------------------------------------------------------------- tokens (spec 2.1)
LIGHT = {
    "bg": "#F3F3F3", "surface": "#FBFBFB", "card": "#FFFFFF", "card_hover": "#F9F9F9",
    "stroke": "#E5E5E5", "stroke_strong": "#C8C8C8",
    "text": "#1A1A1A", "text_secondary": "#5F5F5F", "text_disabled": "#A0A0A0",
    "accent": "#005FB8", "on_accent": "#FFFFFF",
    "subtle_hover": "#EDEDED", "subtle_pressed": "#E3E3E3",
    "critical": "#C42B1C", "caution": "#9D5D00", "success": "#0F7B0F",
}
DARK = {
    "bg": "#202020", "surface": "#2B2B2B", "card": "#2D2D2D", "card_hover": "#323232",
    "stroke": "#3A3A3A", "stroke_strong": "#555555",
    "text": "#FFFFFF", "text_secondary": "#C5C5C5", "text_disabled": "#787878",
    "accent": "#60CDFF", "on_accent": "#000000",
    "subtle_hover": "#3A3A3A", "subtle_pressed": "#333333",
    "critical": "#FF99A4", "caution": "#FCE100", "success": "#6CCB5F",
}
# ค่า accent เริ่มต้นของ Windows (ถ้าผู้ใช้ไม่ได้เปลี่ยนสี) → ใช้ค่าตาม spec ตรง ๆ
_WINDOWS_STOCK_ACCENT = "#0078D4"

# ---------------------------------------------------------------- สีโน้ต (spec 2.2)
NOTE_COLORS = ("none", "yellow", "green", "pink", "purple", "blue", "gray")
_NOTE_BG = {
    "light": {"yellow": "#FFF7D1", "green": "#E4F9E0", "pink": "#FFE4F1",
              "purple": "#F2E6FF", "blue": "#E2F1FF", "gray": "#F3F2F1"},
    "dark": {"yellow": "#4A4528", "green": "#2F4A2C", "pink": "#4F2E3D",
             "purple": "#3E3350", "blue": "#2A3C4F", "gray": "#3A3A3A"},
}
_NOTE_DOT = {"yellow": "#E8C33B", "green": "#6BC75C", "pink": "#EB7BB0",
             "purple": "#A87FE0", "blue": "#5DA9E9", "gray": "#8A8886"}

# ---------------------------------------------------------------- fonts (spec 2.3)
FONT_SIZES = {  # (pt) ตามระดับ "ขนาดตัวอักษร" ใน Settings
    "small": {"caption": 8, "body": 9, "subtitle": 13, "title": 16},
    "normal": {"caption": 9, "body": 10, "subtitle": 14, "title": 18},
    "large": {"caption": 11, "body": 12, "subtitle": 16, "title": 20},
}
_ICON_PT = {"icon10": 10, "icon12": 12, "icon14": 14, "icon32": 32}  # ไอคอนไม่ scale ตาม font_size (ปุ่มขนาดตายตัว)
_FALLBACK_TOKEN = "#FF00FF"  # token สะกดผิด → สีชมพูจัดให้เห็นตอน dev แทนที่จะ crash ตอนวาด


# ---------------------------------------------------------------- color utils
def _is_hex(c: str) -> bool:
    return isinstance(c, str) and len(c) == 7 and c.startswith("#")


def _rgb(c: str) -> tuple[int, int, int]:
    return int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)


def _hex(r: float, g: float, b: float) -> str:
    return "#%02X%02X%02X" % (max(0, min(255, round(r))), max(0, min(255, round(g))), max(0, min(255, round(b))))


def blend(a: str, b: str, t: float) -> str:
    """ผสมสี a→b ที่สัดส่วน t (0..1) — ถ้าเป็นชื่อสีระบบ (high contrast) คืน a ตามเดิม"""
    if not (_is_hex(a) and _is_hex(b)):
        return a
    (r1, g1, b1), (r2, g2, b2) = _rgb(a), _rgb(b)
    return _hex(r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t)


def luminance(c: str) -> float:
    def ch(v: int) -> float:
        s = v / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4
    r, g, b = _rgb(c)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _derive_accent(system: str | None, dark: bool) -> str:
    """accent ที่อ่านออกในโหมดนั้น — registry ให้ค่าเดียว ต้องปรับเองให้ contrast ≥ 4.5:1"""
    default = DARK["accent"] if dark else LIGHT["accent"]
    if not system or not _is_hex(system) or system.upper() == _WINDOWS_STOCK_ACCENT:
        return default
    ref = DARK["bg"] if dark else "#FFFFFF"
    col = system
    for _ in range(30):
        if contrast(col, ref) >= 4.5:
            break
        col = blend(col, "#FFFFFF" if dark else "#000000", 0.08)
    return col


class Theme:
    """ศูนย์รวมสี/ฟอนต์/ttk style — สร้างครั้งเดียวต่อ root"""

    def __init__(self, root: tk.Misc, settings) -> None:
        self.root = root
        self.settings = settings
        self.mode = "light"
        self.high_contrast = False
        self._tokens: dict[str, str] = dict(LIGHT)
        self._subs: list[Callable[[], None]] = []
        self._variants: set[tuple[str, str]] = set()
        self._fonts: dict[str, tkfont.Font] = {}
        self._font_size = "normal"
        self._sys_accent: str | None = None
        self._applied_key: tuple | None = None

        self._pick_families()
        self._font_size = self._setting("font_size", "normal")
        if self._font_size not in FONT_SIZES:
            self._font_size = "normal"
        self._build_fonts()
        self._apply(self._resolve(), notify=False)
        # ฟังการเปลี่ยนค่าใน Settings เอง ผู้เรียกจึงไม่ต้องจำว่าต้อง refresh/set_font_size
        sub = getattr(settings, "subscribe", None)
        if callable(sub):
            try:
                sub(self._on_setting)
            except Exception:
                pass
        _set_current(self)

    # ------------------------------------------------------------ settings
    def _setting(self, key: str, default):
        try:
            v = self.settings.get(key, default)
        except TypeError:
            v = self.settings.get(key)
        except Exception:
            v = None
        return default if v is None else v

    def _on_setting(self, key: str, value) -> None:
        try:
            if key == "theme":
                self.refresh()
            elif key == "font_size":
                self.set_font_size(str(value))
        except tk.TclError:
            pass  # root ถูกทำลายระหว่างปิดแอป

    # ------------------------------------------------------------ resolve
    def _resolve(self) -> tuple:
        """อ่านสถานะที่มีผลต่อสีทั้งหมด → tuple เพื่อเทียบว่าเปลี่ยนไหม"""
        hc = win11.is_high_contrast()
        pref = str(self._setting("theme", "system")).lower()
        if hc:
            try:
                r, g, b = (v // 257 for v in self.root.winfo_rgb("SystemWindow"))
                dark = luminance(_hex(r, g, b)) < 0.4
            except tk.TclError:
                dark = False
        elif pref == "dark":
            dark = True
        elif pref == "light":
            dark = False
        else:
            dark = win11.is_system_dark()
        return ("dark" if dark else "light", hc, win11.get_accent_color())

    def refresh(self) -> bool:
        """อ่านธีม/accent/high-contrast ใหม่ — True ถ้ามีอะไรเปลี่ยน (เรียกทุก tick ของ scheduler ได้)"""
        state = self._resolve()
        if state == self._applied_key:
            return False
        self._apply(state, notify=True)
        return True

    def _apply(self, state: tuple, notify: bool) -> None:
        mode, hc, sys_accent = state
        self._applied_key = state
        self.mode, self.high_contrast, self._sys_accent = mode, hc, sys_accent
        dark = mode == "dark"
        t = dict(DARK if dark else LIGHT)
        # ไม่ใช้ accent ของระบบ: ปุ่ม Accent/Switch/Scale ของ sv_ttk เป็น sprite สีฟ้าตายตัว
        # ถ้าวิดเจ็ตของเราตามสีระบบ จะเห็นฟ้าสองเฉดปนกัน — ความสม่ำเสมอสำคัญกว่า
        t["accent"] = DARK["accent"] if dark else LIGHT["accent"]
        if hc:
            t.update({k: "SystemWindow" for k in ("bg", "surface", "card", "card_hover")})
            t.update({k: "SystemWindowText" for k in ("stroke", "stroke_strong", "text", "text_secondary",
                                                       "critical", "caution", "success")})
            t.update(text_disabled="SystemGrayText", accent="SystemHighlight", on_accent="SystemHighlightText",
                     subtle_hover="SystemHighlight", subtle_pressed="SystemHighlight")
        self._tokens = t
        self._apply_ttk()
        try:
            self.root.configure(bg=t["bg"])
        except tk.TclError:
            pass
        if notify:
            for cb in list(self._subs):
                try:
                    cb()
                except tk.TclError:
                    pass
                except Exception:
                    log.exception("theme subscriber failed")

    # ------------------------------------------------------------ tokens
    def c(self, token: str) -> str:
        try:
            return self._tokens[token]
        except KeyError:
            log.warning("unknown theme token: %s", token)
            return _FALLBACK_TOKEN

    def note_bg(self, color: str) -> str:
        if color in (None, "", "none") or color not in _NOTE_DOT:
            return self.c("card")
        if self.high_contrast:
            return self.c("card")
        return _NOTE_BG[self.mode][color]

    def note_dot(self, color: str) -> str:
        if color not in _NOTE_DOT:
            return self.c("stroke_strong")
        return self.c("accent") if self.high_contrast else _NOTE_DOT[color]

    def note_hover(self, color: str) -> str:
        """สีการ์ดตอน hover: ไม่มีสี → card_hover, มีสี → เข้มขึ้น/สว่างขึ้นเล็กน้อย (spec 4.6)"""
        if color not in _NOTE_DOT or self.high_contrast:
            return self.c("card_hover")
        return blend(self.note_bg(color), "#FFFFFF" if self.mode == "dark" else "#000000", 0.04)

    def subscribe(self, cb: Callable[[], None]) -> Callable[[], None]:
        """แจ้งเมื่อ mode/accent/font เปลี่ยน — คืนฟังก์ชัน unsubscribe (widget ที่ถูกทำลายต้องเรียก)"""
        self._subs.append(cb)

        def unsubscribe() -> None:
            try:
                self._subs.remove(cb)
            except ValueError:
                pass
        return unsubscribe

    # ------------------------------------------------------------ fonts
    def _pick_families(self) -> None:
        try:
            fams = set(tkfont.families(self.root))
        except tk.TclError:
            fams = set()
        if "Segoe UI Variable Text" in fams:
            self._fam, self._fam_strong, self._strong_weight = (
                "Segoe UI Variable Text",
                "Segoe UI Variable Text Semibold" if "Segoe UI Variable Text Semibold" in fams else "Segoe UI Variable Text",
                "normal" if "Segoe UI Variable Text Semibold" in fams else "bold")
        else:
            self._fam = "Segoe UI"
            has_sb = "Segoe UI Semibold" in fams
            self._fam_strong = "Segoe UI Semibold" if has_sb else "Segoe UI"
            self._strong_weight = "normal" if has_sb else "bold"
        self._icon_family = win11.icon_font_family()
        if self._icon_family not in fams and fams:
            self._icon_family = "Segoe MDL2 Assets" if "Segoe MDL2 Assets" in fams else self._icon_family

    def _font_spec(self) -> dict[str, tuple[str, int, str]]:
        s = FONT_SIZES[self._font_size]
        return {
            "caption": (self._fam, s["caption"], "normal"),
            "body": (self._fam, s["body"], "normal"),
            "body_strong": (self._fam_strong, s["body"], self._strong_weight),
            "subtitle": (self._fam_strong, s["subtitle"], self._strong_weight),
            "title": (self._fam_strong, s["title"], self._strong_weight),
        }

    def _build_fonts(self) -> None:
        for name, (fam, size, weight) in self._font_spec().items():
            self._fonts[name] = tkfont.Font(root=self.root, family=fam, size=size, weight=weight)
        for name, pt in _ICON_PT.items():
            self._fonts[name] = tkfont.Font(root=self.root, family=self._icon_family, size=pt)

    def font(self, style: str) -> tkfont.Font:
        return self._fonts.get(style) or self._fonts["body"]

    def set_font_size(self, size: str) -> None:
        """เปลี่ยนขนาดฟอนต์ทั้งแอปด้วย configure ใน Font object เดิม (widget ที่ใช้อยู่อัปเดตเอง)"""
        if size not in FONT_SIZES:
            size = "normal"
        if size == self._font_size:
            return
        self._font_size = size
        for name, (fam, sz, weight) in self._font_spec().items():
            self._fonts[name].configure(family=fam, size=sz, weight=weight)
        self._sync_named_fonts()
        for cb in list(self._subs):
            try:
                cb()
            except tk.TclError:
                pass
            except Exception:
                log.exception("theme subscriber failed")

    def _sync_named_fonts(self) -> None:
        """ให้ ttk widget (sv-ttk + Tk default fonts) ใช้ฟอนต์ตระกูลเดียวกับ custom widget"""
        spec = self._font_spec()
        mapping = {
            "SunValleyCaptionFont": "caption", "SunValleyBodyFont": "body", "SunValleyBodyStrongFont": "body_strong",
            "SunValleyBodyLargeFont": "subtitle", "SunValleySubtitleFont": "subtitle", "SunValleyTitleFont": "title",
            "TkDefaultFont": "body", "TkTextFont": "body", "TkMenuFont": "body", "TkHeadingFont": "body_strong",
            "TkCaptionFont": "body_strong", "TkSmallCaptionFont": "caption", "TkTooltipFont": "caption",
        }
        for fname, style in mapping.items():
            fam, size, weight = spec[style]
            try:
                tkfont.nametofont(fname, root=self.root).configure(family=fam, size=size, weight=weight)
            except tk.TclError:
                pass  # ฟอนต์ชื่อนี้ไม่มีใน Tk/sv-ttk เวอร์ชันนี้

    # ------------------------------------------------------------ ttk
    def _apply_ttk(self) -> None:
        st = ttk.Style(self.root)
        if sv_ttk is not None:
            try:
                sv_ttk.set_theme(self.mode, self.root)
            except Exception:
                log.exception("sv_ttk.set_theme failed")
        self._sync_named_fonts()
        c = self.c
        self._configure_base()

        # Subtle.TButton: โปร่งใส มีพื้นเฉพาะตอน hover (ยืม layout ของ Toolbutton จาก sv-ttk)
        try:
            st.layout("Subtle.TButton", st.layout("Toolbutton"))
        except tk.TclError:
            pass
        st.configure("Subtle.TButton", padding=(8, 2, 8, 3), anchor="center", foreground=c("text"))
        st.map("Subtle.TButton", foreground=[("disabled", c("text_disabled"))])

        # Link.TButton: ปุ่มข้อความสี accent ไม่มีพื้น (เช่น "เลิกทำ", "ล้างการค้นหา", "ลบการแจ้งเตือน")
        st.layout("Link.TButton", [("Link.focus", {"children": [("Link.padding", {"children": [
            ("Link.label", {"side": "left", "expand": 1})]})]})])
        st.configure("Link.TButton", padding=(4, 2), anchor="center", foreground=c("accent"))
        st.map("Link.TButton", foreground=[("disabled", c("text_disabled")), ("pressed", c("text_secondary")),
                                           ("active", blend(c("accent"), c("text"), 0.3))])

        # Placeholder.TEntry: ข้อความจางตอนยังไม่มีค่า (sv-ttk map foreground ตอน hover ไว้ ต้อง override ด้วย)
        dis = c("text_disabled")
        st.configure("Placeholder.TEntry", foreground=dis)
        st.map("Placeholder.TEntry", foreground=[("disabled", dis), ("pressed", dis), ("active", dis)])

        for base, on in sorted(self._variants):
            self._configure_variant(st, base, on)

    def _configure_base(self) -> None:
        """style "." ของ ttk จาก token ของเราทั้งหมด

        sv-ttk ตั้งค่า "." เองใน proc configure_colors (ผูกกับ <<ThemeChanged>>) และเรียก tk_setPalette
        ซึ่งเขียนทับสีของ "ทุก tk widget" ในแอป (ทดสอบแล้ว) และแย่งตั้ง "." กับเราจนวนไม่รู้จบ
        → ทำให้ proc นั้นเป็น no-op แล้วตั้งเองที่นี่ (ต้อง eval หลัง sv.tcl ถูก source)
        """
        c = self.c
        try:
            self.root.tk.eval("proc configure_colors {} {}")
            st = ttk.Style(self.root)
            st.configure(".", background=c("bg"), foreground=c("text"), troughcolor=c("bg"),
                         focuscolor=c("accent"), selectbackground=c("accent"), selectforeground=c("on_accent"),
                         insertwidth=1, insertcolor=c("text"), fieldbackground=c("bg"),
                         font="SunValleyBodyFont", borderwidth=0, relief="flat")
            st.map(".", foreground=[("disabled", c("text_disabled"))])
            self.root.configure(bg=c("bg"))
        except tk.TclError:
            pass

    def ttk_style(self, base: str, on: str = "card") -> str:
        """style ของ ttk widget ที่พื้นหลังตรงกับ token `on` (เช่น Switch บน SettingsCard สี card)

        ttk วาดพื้นหลังโปร่งของรูป sprite ด้วยสี style "." (= bg) → วางบนพื้นอื่นจะเห็นกรอบเทา
        คืนชื่อ style ใหม่เช่น "Card.Switch.TCheckbutton" (สืบทอดหน้าตาจาก base ครบ)
        """
        self._variants.add((base, on))
        self._configure_variant(ttk.Style(self.root), base, on)
        return f"{on.capitalize()}.{base}"

    def _configure_variant(self, st: ttk.Style, base: str, on: str) -> None:
        st.configure(f"{on.capitalize()}.{base}", background=self.c(on))

    # ------------------------------------------------------------ window
    def apply_window(self, window) -> None:
        """พื้นหลัง + titlebar (มืด/สว่าง + สี caption กลืนกับ bg) ให้หน้าต่าง/dialog ใด ๆ"""
        try:
            window.configure(bg=self.c("bg"))
        except tk.TclError:
            return
        win11.apply_titlebar(window, self.mode == "dark", None if self.high_contrast else self.c("bg"))


# ---------------------------------------------------------------- current theme (ให้ Tooltip ฯลฯ หยิบใช้เมื่อไม่ได้ส่ง theme มา)
_current: Theme | None = None


def _set_current(theme: Theme) -> None:
    global _current
    _current = theme


def current_theme() -> Theme | None:
    return _current
