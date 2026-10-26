"""Tests ของ UI foundation (strings / theme / win11 / icons / widgets) — ใช้ Tk จริง ไม่ mock

root ถูก map ไว้แต่ alpha=0 (มองไม่เห็น): การทดสอบ <Configure>/ขนาด widget ต้องการหน้าต่างที่ map แล้ว
ส่วนฟีเจอร์ที่ต้องรอ timer ใช้ root.update() ร่วมกับ seconds สั้น ๆ
"""

import os
import sys
import time
import tkinter as tk
import unittest
from tkinter import ttk

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.ui import icons, strings, win11  # noqa: E402
from src.ui.theme import FONT_SIZES, NOTE_COLORS, Theme, contrast  # noqa: E402
from src.ui.widgets import (IconButton, PlaceholderEntry, RoundedFrame, SettingsCard, Tooltip, UndoBar,  # noqa: E402
                            fade_in, fade_out, is_pointer_inside, px, slide_y)

TOKENS = ["bg", "surface", "card", "card_hover", "stroke", "stroke_strong", "text", "text_secondary",
          "text_disabled", "accent", "on_accent", "subtle_hover", "subtle_pressed", "critical", "caution", "success"]


class FakeSettings:
    def __init__(self, **kw) -> None:
        self.data = {"theme": "light", "font_size": "normal", **kw}
        self._subs = []

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value, save=True) -> None:
        if self.data.get(key) != value:
            self.data[key] = value
            for cb in list(self._subs):
                cb(key, value)

    def subscribe(self, cb) -> None:
        self._subs.append(cb)


root: tk.Tk
settings: FakeSettings
theme: Theme


def setUpModule() -> None:
    global root, settings, theme
    root = tk.Tk()
    root.geometry("500x400+0+0")
    root.attributes("-alpha", 0.0)
    settings = FakeSettings()
    theme = Theme(root, settings)
    root.update()


def tearDownModule() -> None:
    try:
        root.destroy()
    except tk.TclError:
        pass


def pump(seconds: float = 0.0) -> None:
    """รัน event loop (และรอ seconds) — เพื่อให้ after/Configure ทำงาน"""
    end = time.monotonic() + seconds
    root.update()
    while time.monotonic() < end:
        root.update()
        time.sleep(0.005)


class StringsTest(unittest.TestCase):
    def tearDown(self) -> None:
        strings.set_language("th")

    def test_missing_key_returns_key(self) -> None:
        self.assertEqual(strings.t("no.such.key"), "no.such.key")

    def test_language_switch(self) -> None:
        strings.set_language("th")
        self.assertEqual(strings.t("board.empty_title"), "ยังไม่มีโน้ต")
        strings.set_language("en")
        self.assertEqual(strings.get_language(), "en")
        self.assertEqual(strings.t("board.empty_title"), "No notes yet")

    def test_invalid_language_ignored(self) -> None:
        strings.set_language("fr")
        self.assertEqual(strings.get_language(), "th")

    def test_format_kwargs(self) -> None:
        self.assertEqual(strings.t("board.tab_active", n=4), "งานที่ทำอยู่ (4)")
        strings.set_language("en")
        self.assertEqual(strings.t("settings.about", version="3.0.0", author="X"), "QuickNote 3.0.0 · by X")

    def test_bad_format_does_not_crash(self) -> None:
        self.assertIn("{n}", strings.t("board.tab_active", wrong=1))

    def test_same_key_set_and_nonempty(self) -> None:
        th, en = strings.STRINGS["th"], strings.STRINGS["en"]
        self.assertEqual(set(th), set(en))
        self.assertTrue(all(th.values()) and all(en.values()))

    def test_same_placeholders_in_both_languages(self) -> None:
        import re
        for k in strings.STRINGS["th"]:
            self.assertEqual(sorted(re.findall(r"\{(\w+)\}", strings.STRINGS["th"][k])),
                             sorted(re.findall(r"\{(\w+)\}", strings.STRINGS["en"][k])), k)


class ThemeTest(unittest.TestCase):
    def tearDown(self) -> None:
        settings.set("theme", "light")
        settings.set("font_size", "normal")

    def test_tokens_light_and_dark(self) -> None:
        for mode in ("light", "dark"):
            settings.set("theme", mode)
            self.assertEqual(theme.mode, mode)
            for tok in TOKENS:
                v = theme.c(tok)
                self.assertRegex(v, r"^#[0-9A-Fa-f]{6}$", f"{mode}/{tok}")
            self.assertGreaterEqual(contrast(theme.c("text"), theme.c("bg")), 4.5)
            self.assertGreaterEqual(contrast(theme.c("text_secondary"), theme.c("card")), 4.5)
            self.assertGreaterEqual(contrast(theme.c("accent"), theme.c("bg")), 3.0)

    def test_unknown_token_does_not_raise(self) -> None:
        self.assertTrue(theme.c("nope"))

    def test_mode_change_notifies_subscribers(self) -> None:
        hits = []
        unsub = theme.subscribe(lambda: hits.append(theme.mode))
        settings.set("theme", "dark")
        settings.set("theme", "light")
        unsub()
        settings.set("theme", "dark")
        self.assertEqual(hits, ["dark", "light"])

    def test_refresh_idempotent(self) -> None:
        settings.set("theme", "dark")
        self.assertFalse(theme.refresh())

    def test_system_mode_resolves_to_light_or_dark(self) -> None:
        settings.set("theme", "system")
        self.assertIn(theme.mode, ("light", "dark"))

    def test_note_colors(self) -> None:
        for mode in ("light", "dark"):
            settings.set("theme", mode)
            for c in NOTE_COLORS:
                self.assertRegex(theme.note_bg(c), r"^#[0-9A-Fa-f]{6}$")
                self.assertRegex(theme.note_dot(c), r"^#[0-9A-Fa-f]{6}$")
                self.assertRegex(theme.note_hover(c), r"^#[0-9A-Fa-f]{6}$")
            self.assertEqual(theme.note_bg("none"), theme.c("card"))
            self.assertEqual(theme.note_bg("garbage"), theme.c("card"))
            # ข้อความต้องอ่านออกบนสีโน้ตทุกสี
            for c in NOTE_COLORS:
                self.assertGreaterEqual(contrast(theme.c("text"), theme.note_bg(c)), 4.5, f"{mode}/{c}")
                self.assertGreaterEqual(contrast(theme.c("text_secondary"), theme.note_bg(c)), 4.5, f"{mode}/{c}")

    def test_font_size_changes(self) -> None:
        settings.set("font_size", "normal")
        base = theme.font("body").cget("size")
        self.assertEqual(base, FONT_SIZES["normal"]["body"])
        settings.set("font_size", "large")
        self.assertEqual(theme.font("body").cget("size"), FONT_SIZES["large"]["body"])
        self.assertGreater(theme.font("body").cget("size"), base)
        theme.set_font_size("small")
        self.assertEqual(theme.font("caption").cget("size"), FONT_SIZES["small"]["caption"])
        theme.set_font_size("bogus")  # ค่าผิด → normal
        self.assertEqual(theme.font("body").cget("size"), FONT_SIZES["normal"]["body"])

    def test_all_font_styles_exist(self) -> None:
        for name in ("caption", "body", "body_strong", "subtitle", "title", "icon10", "icon12", "icon14", "icon32"):
            self.assertIsNotNone(theme.font(name).actual("family"))
        self.assertIn(theme.font("icon12").actual("family"), ("Segoe Fluent Icons", "Segoe MDL2 Assets"))

    def test_ttk_styles_present(self) -> None:
        st = ttk.Style(root)
        for name in ("Accent.TButton", "Subtle.TButton", "Link.TButton", "Placeholder.TEntry", "Switch.TCheckbutton"):
            self.assertTrue(st.layout(name), name)
            ttk.Button(root, style=name).destroy() if "Button" in name else None
        for mode in ("light", "dark"):  # style ต้องอยู่รอดหลังสลับธีม (config ต่อ theme)
            settings.set("theme", mode)
            self.assertEqual(st.lookup("Placeholder.TEntry", "foreground"), theme.c("text_disabled"))
            self.assertEqual(st.lookup("Link.TButton", "foreground"), theme.c("accent"))
            self.assertEqual(st.lookup(".", "background"), theme.c("bg"))

    def test_variant_style_background(self) -> None:
        name = theme.ttk_style("Switch.TCheckbutton", "card")
        self.assertEqual(name, "Card.Switch.TCheckbutton")
        settings.set("theme", "dark")
        self.assertEqual(ttk.Style(root).lookup(name, "background"), theme.c("card"))

    def test_apply_window(self) -> None:
        top = tk.Toplevel(root)
        top.withdraw()
        theme.apply_window(top)
        self.assertEqual(top.cget("bg"), theme.c("bg"))
        top.destroy()

    def test_no_global_palette_clobber(self) -> None:
        """สลับธีมแล้วสีของ tk widget ที่เรากำหนดเองต้องไม่ถูก sv-ttk (tk_setPalette) เขียนทับ"""
        fr = tk.Frame(root, bg="#123456")
        fr.pack()
        settings.set("theme", "dark")
        pump(0.05)
        self.assertEqual(fr.cget("bg").lower(), "#123456")
        fr.destroy()


class IconsTest(unittest.TestCase):
    def test_every_icon_is_single_private_use_char(self) -> None:
        for name, ch in icons.ICONS.items():
            self.assertEqual(len(ch), 1, name)
            self.assertTrue(0xE000 <= ord(ch) <= 0xF8FF, name)

    def test_required_names(self) -> None:
        for n in ("add", "search", "settings", "pin", "unpin", "topmost", "more", "clock", "calendar", "delete",
                  "cancel", "circle", "completed", "check", "chevron_down", "chevron_right", "flag", "color", "undo"):
            self.assertIn(n, icons.ICONS)

    def test_glyphs_exist_in_both_icon_fonts(self) -> None:
        try:
            from fontTools.ttLib import TTFont
        except ImportError:
            self.skipTest("fonttools ไม่ได้ติดตั้ง")
        fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
        for fname in ("SegoeIcons.ttf", "segmdl2.ttf"):
            path = os.path.join(fonts, fname)
            if not os.path.exists(path):
                continue
            cmap = TTFont(path).getBestCmap()
            for name, ch in icons.ICONS.items():
                self.assertIn(ord(ch), cmap, f"{name} missing in {fname}")

    def test_glyph_unknown_name(self) -> None:
        self.assertEqual(icons.glyph("zzz"), "")


class Win11Test(unittest.TestCase):
    def test_functions_never_raise(self) -> None:
        win11.apply_titlebar(root, True, "#202020")
        win11.apply_titlebar(root, False, None)
        win11.apply_titlebar(root, False, "not-a-color")
        win11.apply_titlebar(None, True)       # type: ignore[arg-type]
        win11.apply_titlebar(object(), True)   # type: ignore[arg-type]
        acc = win11.get_accent_color()
        self.assertTrue(acc is None or (acc.startswith("#") and len(acc) == 7))
        self.assertIsInstance(win11.is_system_dark(), bool)
        self.assertIsInstance(win11.is_high_contrast(), bool)
        self.assertIsInstance(win11.animations_enabled(), bool)
        self.assertIn(win11.icon_font_family(), ("Segoe Fluent Icons", "Segoe MDL2 Assets"))
        win11.set_app_user_model_id("PassagainP.QuickNote.Test")
        win11.set_app_user_model_id(None)  # type: ignore[arg-type]

    def test_work_area_is_sane(self) -> None:
        l, t, r, b = win11.get_work_area(root)
        self.assertGreater(r - l, 300)
        self.assertGreater(b - t, 300)
        top = tk.Toplevel(root)
        top.withdraw()
        self.assertEqual(len(win11.get_work_area(top)), 4)  # หน้าต่างซ่อนอยู่ก็ต้องตอบได้
        top.destroy()
        self.assertEqual(len(win11.get_work_area(None)), 4)  # type: ignore[arg-type]

    def test_titlebar_hwnd_resolves(self) -> None:
        if sys.platform != "win32":
            self.skipTest("Windows only")
        self.assertTrue(win11._frame_hwnd(root))


class IconButtonTest(unittest.TestCase):
    def make(self, **kw) -> IconButton:
        calls = kw.pop("calls", [])
        b = IconButton(root, theme, icons.ICONS["add"], command=kw.pop("command", lambda: calls.append(1)),
                       tooltip="เพิ่ม", **kw)
        b.pack()
        pump()
        return b

    def click(self, b: IconButton) -> None:
        b.event_generate("<Enter>")
        b.event_generate("<ButtonPress-1>", x=0, y=0)
        b.event_generate("<ButtonRelease-1>", x=0, y=0)
        pump()

    def test_construct_and_destroy(self) -> None:
        b = self.make()
        self.assertGreaterEqual(b.winfo_reqwidth(), px(root, 32) - 1)
        b.destroy()
        pump()

    def test_click_invokes_command(self) -> None:
        calls = []
        b = self.make(calls=calls)
        self.click(b)
        self.assertEqual(calls, [1])
        b.destroy()

    def test_release_outside_does_not_invoke(self) -> None:
        calls = []
        b = self.make(calls=calls)
        b.event_generate("<ButtonPress-1>", x=0, y=0)
        b.event_generate("<ButtonRelease-1>", x=-50, y=-50)
        pump()
        self.assertEqual(calls, [])
        b.destroy()

    def test_toggle_passes_state(self) -> None:
        states = []
        b = IconButton(root, theme, icons.ICONS["topmost"], command=lambda s: states.append(s), toggle=True)
        b.pack()
        pump()
        self.assertFalse(b.active)
        self.click(b)
        self.click(b)
        self.assertEqual(states, [True, False])
        b.set_active(True)
        b.event_generate("<Leave>")
        self.assertTrue(b.active)
        self.assertEqual(b.cget("bg"), theme.c("accent"))  # toggle เปิด = พื้น accent
        self.assertEqual(b.cget("fg"), theme.c("on_accent"))
        b.destroy()

    def test_toggle_command_without_argument(self) -> None:
        calls = []
        b = IconButton(root, theme, icons.ICONS["topmost"], command=lambda: calls.append(1), toggle=True)
        b.pack()
        pump()
        self.click(b)
        self.assertEqual(calls, [1])
        self.assertTrue(b.active)
        b.destroy()

    def test_keyboard_activation(self) -> None:
        calls = []
        b = self.make(calls=calls)
        b.focus_force()
        pump()
        b.event_generate("<space>")
        b.event_generate("<Return>")
        pump()
        self.assertEqual(len(calls), 2)
        b.destroy()

    def test_disabled_ignores_click(self) -> None:
        calls = []
        b = self.make(calls=calls)
        b.set_enabled(False)
        self.click(b)
        self.assertEqual(calls, [])
        self.assertEqual(b.cget("fg"), theme.c("text_disabled"))
        b.destroy()

    def test_hover_color_and_focus_ring(self) -> None:
        b = self.make()
        base = b.cget("bg")
        b.event_generate("<Enter>")
        self.assertEqual(b.cget("bg"), theme.c("subtle_hover"))
        b.event_generate("<Leave>")
        self.assertEqual(b.cget("bg"), base)
        self.assertEqual(int(b.cget("highlightthickness")), 2)
        self.assertEqual(b.cget("highlightcolor"), theme.c("accent"))
        self.assertTrue(int(b.cget("takefocus")))
        b.destroy()

    def test_follows_theme_change(self) -> None:
        holder = tk.Frame(root, bg=theme.c("bg"))
        holder.pack()
        b = IconButton(holder, theme, icons.ICONS["add"], command=lambda: None)
        b.pack()
        settings.set("theme", "dark")
        holder.configure(bg=theme.c("bg"))
        pump(0.05)
        self.assertEqual(b.cget("fg"), theme.c("text"))
        self.assertEqual(b.cget("bg"), theme.c("bg"))
        settings.set("theme", "light")
        holder.destroy()
        pump(0.05)  # subscriber ของปุ่มที่ถูกทำลายต้องไม่ทำให้ crash


class TooltipTest(unittest.TestCase):
    def test_show_hide_and_callable_text(self) -> None:
        lbl = tk.Label(root, text="x")
        lbl.pack()
        pump()
        state = {"t": "หนึ่ง"}
        tip = Tooltip(lbl, lambda: state["t"], delay_ms=10)
        tip.show()
        self.assertIsNotNone(tip._tip)
        tip.hide()
        self.assertIsNone(tip._tip)
        state["t"] = "สอง"
        tip.show()
        self.assertEqual(tip._tip.winfo_children()[0].cget("text"), "สอง")  # ตามภาษา/ข้อความ ณ ตอนแสดง
        lbl.destroy()  # tooltip ต้องหายไปพร้อม widget
        pump()
        self.assertIsNone(tip._tip)

    def test_empty_text_not_shown(self) -> None:
        lbl = tk.Label(root, text="x")
        lbl.pack()
        tip = Tooltip(lbl, "")
        tip.show()
        self.assertIsNone(tip._tip)
        lbl.destroy()


class PlaceholderEntryTest(unittest.TestCase):
    def test_get_value_empty_while_placeholder(self) -> None:
        e = PlaceholderEntry(root, "ค้นหา")
        e.pack()
        pump()
        self.assertTrue(e.showing_placeholder)
        self.assertEqual(e.get_value(), "")
        self.assertEqual(e.get(), "ค้นหา")           # ข้อความที่มองเห็น
        self.assertEqual(str(e.cget("style")), "Placeholder.TEntry")
        e.destroy()

    def test_focus_clears_and_blur_restores(self) -> None:
        e = PlaceholderEntry(root, "ค้นหา")
        e.pack()
        e.focus_force()
        pump()
        e.event_generate("<FocusIn>")
        self.assertFalse(e.showing_placeholder)
        self.assertEqual(e.get(), "")
        self.assertEqual(str(e.cget("style")), "TEntry")
        e.insert(0, "นม")
        self.assertEqual(e.get_value(), "นม")
        e.delete(0, "end")
        e.event_generate("<FocusOut>")
        root.focus_force()
        pump()
        self.assertTrue(e.showing_placeholder)
        e.destroy()

    def test_set_value_and_clear(self) -> None:
        e = PlaceholderEntry(root, "ph")
        e.pack()
        e.set_value("hello")
        self.assertEqual(e.get_value(), "hello")
        self.assertFalse(e.showing_placeholder)
        e.clear()
        pump()
        self.assertEqual(e.get_value(), "")
        e.destroy()

    def test_textvariable_never_sees_placeholder(self) -> None:
        var = tk.StringVar(master=root)
        seen = []
        var.trace_add("write", lambda *_: seen.append(var.get()))
        e = PlaceholderEntry(root, "ค้นหา", textvariable=var)
        e.pack()
        pump()
        self.assertTrue(e.showing_placeholder)
        self.assertEqual(var.get(), "")
        e.set_value("abc")
        self.assertEqual(var.get(), "abc")
        var.set("xyz")  # เขียนจากภายนอก → ช่องต้องตาม
        self.assertEqual(e.get_value(), "xyz")
        self.assertNotIn("ค้นหา", seen)
        e.destroy()
        var.set("after destroy")  # trace ถูกถอดแล้ว ต้องไม่ error

    def test_set_placeholder_text(self) -> None:
        e = PlaceholderEntry(root, "a")
        e.pack()
        pump()
        e.set_placeholder("b")
        self.assertEqual(e.get(), "b")
        self.assertEqual(e.get_value(), "")
        e.destroy()


class RoundedFrameTest(unittest.TestCase):
    def test_redraw_on_resize_and_height_follows_content(self) -> None:
        rf = RoundedFrame(root, theme, radius=8)
        rf.pack(fill="x")
        lbl = tk.Label(rf.body, text="เนื้อหา", bg=theme.c("card"))
        lbl.pack(padx=12, pady=10)
        pump(0.05)
        self.assertGreater(rf.winfo_width(), 100)
        self.assertEqual(rf.winfo_height(), lbl.winfo_reqheight() + 20 + 2 * rf.inset)
        c1 = rf.coords(rf._shape)
        root.geometry("350x400+0+0")
        pump(0.05)
        c2 = rf.coords(rf._shape)
        self.assertNotEqual(c1, c2)           # ขอบ polygon ถูกวาดใหม่ตามความกว้างใหม่
        self.assertAlmostEqual(max(c2[0::2]), rf.winfo_width() - 1, delta=2)
        lbl.configure(text="ยาว\nหลาย\nบรรทัด")
        pump(0.05)
        self.assertEqual(rf.winfo_height(), lbl.winfo_reqheight() + 20 + 2 * rf.inset)
        root.geometry("500x400+0+0")
        pump()
        rf.destroy()

    def test_set_colors_and_theme(self) -> None:
        rf = RoundedFrame(root, theme)
        rf.pack(fill="x")
        rf.set_colors(bg="#FFF7D1", border="critical", width=2)
        self.assertEqual(rf.itemcget(rf._shape, "fill"), "#FFF7D1")
        self.assertEqual(rf.itemcget(rf._shape, "outline"), theme.c("critical"))
        self.assertEqual(rf.itemcget(rf._shape, "width"), "2.0")
        self.assertEqual(rf.body.cget("bg"), "#FFF7D1")
        rf.set_colors(bg="card", border="stroke", width=1)
        settings.set("theme", "dark")
        rf.apply_theme()
        self.assertEqual(rf.itemcget(rf._shape, "fill"), theme.c("card"))
        self.assertEqual(rf.cget("bg"), theme.c("bg"))
        settings.set("theme", "light")
        rf.destroy()

    def test_many_cards_are_cheap(self) -> None:
        holder = tk.Frame(root)
        holder.pack(fill="both", expand=True)
        t0 = time.monotonic()
        cards = [RoundedFrame(holder, theme) for _ in range(100)]
        for c in cards:
            c.pack(fill="x", pady=2)
            tk.Label(c.body, text="x").pack()
        pump()
        self.assertLess(time.monotonic() - t0, 5.0)
        holder.destroy()


class UndoBarTest(unittest.TestCase):
    def make(self) -> UndoBar:
        bar = UndoBar(root, theme)
        pump()
        return bar

    def test_undo_click_calls_on_undo_only(self) -> None:
        bar = self.make()
        log = []
        bar.show("ลบโน้ตแล้ว", on_undo=lambda: log.append("undo"), on_expire=lambda: log.append("expire"))
        self.assertTrue(bar.is_active)
        pump()
        self.assertEqual(bar.winfo_manager(), "pack")
        bar._btn.invoke()
        pump(0.05)
        self.assertEqual(log, ["undo"])
        self.assertFalse(bar.is_active)
        self.assertEqual(bar.winfo_manager(), "")
        bar.destroy()

    def test_expire_after_timeout(self) -> None:
        bar = self.make()
        log = []
        bar.show("x", on_undo=lambda: log.append("undo"), on_expire=lambda: log.append("expire"), seconds=0.1)
        pump(0.05)
        self.assertEqual(log, [])
        pump(0.2)
        self.assertEqual(log, ["expire"])
        self.assertFalse(bar.is_active)
        bar.destroy()

    def test_replacing_bar_expires_previous_immediately(self) -> None:
        bar = self.make()
        log = []
        bar.show("a", on_undo=lambda: log.append("undo-a"), on_expire=lambda: log.append("expire-a"), seconds=10)
        bar.show("b", on_undo=lambda: log.append("undo-b"), on_expire=lambda: log.append("expire-b"), seconds=0.1)
        self.assertEqual(log, ["expire-a"])
        self.assertEqual(bar._msg.cget("text"), "b")
        pump(0.25)
        self.assertEqual(log, ["expire-a", "expire-b"])
        bar.destroy()

    def test_flush_and_hide(self) -> None:
        bar = self.make()
        log = []
        bar.show("a", on_undo=lambda: None, on_expire=lambda: log.append("e"), seconds=10)
        bar.flush()
        self.assertEqual(log, ["e"])
        bar.show("b", on_undo=lambda: None, on_expire=lambda: log.append("e2"), seconds=10)
        bar.hide()  # hide เฉย ๆ ไม่เรียก callback
        pump(0.05)
        self.assertEqual(log, ["e"])
        bar.destroy()

    def test_destroy_with_pending_timer_is_safe(self) -> None:
        bar = self.make()
        bar.show("a", on_undo=lambda: None, on_expire=None, seconds=0.05)
        bar.destroy()
        pump(0.15)


class SettingsCardTest(unittest.TestCase):
    def test_rows_min_height_and_controls(self) -> None:
        card = SettingsCard(root, theme)
        card.pack(fill="x")
        made = []
        ctrl = card.add_row("ธีม", "เลือกโหมดสว่าง มืด หรือตามระบบ", lambda p: made.append(ttk.Combobox(p, values=["a"])) or made[-1])
        card.add_row("เล่นเสียง", None, lambda p: ttk.Checkbutton(p, style=card.ttk_style("Switch.TCheckbutton")))
        card.add_row("ที่สาม", "desc", lambda p: ttk.Button(p, text="ปุ่ม"))
        pump(0.1)
        self.assertIs(ctrl, made[0])
        rows = [r for r, _, _ in card._rows]
        self.assertEqual(len(rows), 3)
        for r in rows:
            self.assertGreaterEqual(r.winfo_height(), px(root, 56))
        self.assertEqual(len(card._dividers), 2)
        settings.set("theme", "dark")
        pump(0.1)
        self.assertEqual(rows[0].cget("bg"), theme.c("card"))
        settings.set("theme", "light")
        card.destroy()
        pump(0.05)


class AnimationTest(unittest.TestCase):
    def test_fade_and_slide_complete(self) -> None:
        top = tk.Toplevel(root)
        top.geometry("100x50+200+200")
        pump()
        done = []
        fade_in(top, ms=60, then=lambda: done.append("in"))
        pump(0.3)
        self.assertAlmostEqual(float(top.attributes("-alpha")), 1.0, places=2)
        y0 = top.winfo_y()
        slide_y(top, -16, ms=60, then=lambda: done.append("slide"))
        pump(0.3)
        self.assertEqual(top.winfo_y(), y0 - 16)
        fade_out(top, ms=60, then=lambda: done.append("out"))
        pump(0.3)
        self.assertEqual(done, ["in", "slide", "out"])
        top.destroy()

    def test_destroyed_window_midway_is_safe(self) -> None:
        top = tk.Toplevel(root)
        fade_in(top, ms=200)
        slide_y(top, 10, ms=200)
        top.destroy()
        pump(0.3)
        fade_out(top, ms=50)  # window ตายไปแล้ว ต้องไม่ raise

    def test_new_animation_cancels_old(self) -> None:
        top = tk.Toplevel(root)
        pump()
        fade_in(top, ms=1000)
        fade_out(top, ms=30)
        pump(0.2)
        self.assertLess(float(top.attributes("-alpha")), 0.05)
        top.destroy()


class HelpersTest(unittest.TestCase):
    def test_is_pointer_inside_returns_bool(self) -> None:
        f = tk.Frame(root, width=10, height=10)
        f.pack()
        pump()
        self.assertIsInstance(is_pointer_inside(f), bool)
        f.destroy()
        self.assertFalse(is_pointer_inside(f))  # widget ตายแล้วไม่ raise

    def test_px_scales(self) -> None:
        self.assertGreaterEqual(px(root, 32), 32 - 1)
        self.assertGreaterEqual(px(root, 0), 1)


if __name__ == "__main__":
    unittest.main()
