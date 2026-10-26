"""Tests ของ ToastManager + ReminderDialog — Tk จริง ไม่ mock Tk (patch เฉพาะ winsound / เวลา "ตอนนี้" / animation flag)

root ถูก map ไว้แต่ alpha=0; test ที่ต้องการ root ซ่อน/ย่อ จะ withdraw/iconify แล้วคืนสภาพใน tearDown
"""

import os
import sys
import time
import tkinter as tk
import unicodedata
import unittest
from datetime import datetime
from tkinter import ttk
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.core.models import Note  # noqa: E402
from src.ui import reminder_dialog as dialog_mod  # noqa: E402
from src.ui import strings, toast as toast_mod, win11  # noqa: E402
from src.ui.reminder_dialog import ReminderDialog  # noqa: E402
from src.ui.strings import t  # noqa: E402
from src.ui.theme import Theme  # noqa: E402
from src.ui.toast import ToastManager, wrap_clamp  # noqa: E402
from src.ui.widgets import px  # noqa: E402

FIXED_NOW = datetime(2026, 10, 26, 11, 13, 42)


class FakeSettings:
    def __init__(self, **kw) -> None:
        self.data = {"theme": "light", "font_size": "normal", "sound": True, **kw}
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
    root.geometry("500x400+60+60")
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
    end = time.monotonic() + seconds
    root.update()
    while time.monotonic() < end:
        root.update()
        time.sleep(0.005)


def alive(widget: tk.Misc) -> bool:
    try:
        return bool(widget.winfo_exists())
    except tk.TclError:
        return False


class UiCase(unittest.TestCase):
    """ปิด animation (ผลลัพธ์ทันที) + คืนสถานะ root/settings/ภาษาทุกครั้ง"""

    animations = False

    def setUp(self) -> None:
        patcher = mock.patch.object(win11, "animations_enabled", return_value=self.animations)
        patcher.start()
        self.addCleanup(patcher.stop)
        strings.set_language("th")
        settings.data["sound"] = False
        settings.data["theme"] = "light"
        theme.refresh()
        self._dialogs: list[ReminderDialog] = []
        self.mgr = ToastManager(root, theme, settings)

    def tearDown(self) -> None:
        self.mgr.close_all()
        for d in self._dialogs:
            d.close()
        root.deiconify()
        root.update()
        strings.set_language("th")

    def reminder(self, note_id="n1", title="ประชุมทีม", content="", when="2026-10-26 11:00", **cbs):
        calls = {k: [] for k in ("done", "snooze", "open", "dismiss")}
        self.mgr.show_reminder(
            {"id": note_id, "title": title, "content": content, "reminder_datetime": when},
            on_done=lambda: calls["done"].append(1),
            on_snooze=lambda w: calls["snooze"].append(w),
            on_open=lambda: calls["open"].append(1),
            on_dismiss=lambda: calls["dismiss"].append(1))
        return calls

    def toast_for(self, key):
        return next(tt for tt in self.mgr.toasts if tt.key == key)

    def dialog(self, note=None, on_save=None, **kw) -> tuple[ReminderDialog, list]:
        saved: list = []
        note = note or Note(id="n1", title="ซื้อของ", **kw)
        d = ReminderDialog(root, note, theme, on_save or (lambda when, rep: saved.append((when, rep))))
        self._dialogs.append(d)
        pump()
        return d, saved


# ================================================================== helper
class WrapClampTest(UiCase):
    def test_limits_lines_adds_ellipsis_and_fits_width(self) -> None:
        font = theme.font("body")
        text = "สวัสดีครับ นี่คือข้อความภาษาไทยที่ยาวมากๆ " * 8
        out = wrap_clamp(text, font, 200, 3)
        lines = out.split("\n")
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[-1].endswith("…"))
        for ln in lines:
            self.assertLessEqual(font.measure(ln), 200 + 1, ln)

    def test_never_starts_line_with_combining_mark_or_ends_with_leading_vowel(self) -> None:
        font = theme.font("body")
        out = wrap_clamp("เมื่อวานนี้ที่ไปประชุมกับลูกค้าเรื่องโครงการใหม่ที่ต้องส่งมอบภายในไตรมาสนี้" * 2, font, 120, 8)
        for ln in out.split("\n"):
            self.assertNotIn(unicodedata.category(ln[0]), ("Mn", "Me"), ln)
            self.assertNotIn(ln.rstrip("…")[-1:], tuple("เแโใไ"), ln)

    def test_blank_lines_dropped_and_short_text_untouched(self) -> None:
        self.assertEqual(wrap_clamp("a\n\n  \nb", theme.font("body"), 300, 3), "a\nb")
        self.assertEqual(wrap_clamp("", theme.font("body"), 300, 3), "")


# ================================================================== toast
class ToastShowTest(UiCase):
    def test_maps_while_root_withdrawn(self) -> None:
        """C6: toast ต้องขึ้นแม้ root ถูกซ่อน (ไม่ transient)"""
        root.withdraw()
        pump()
        self.reminder()
        pump(0.1)
        win = self.toast_for("n1").win
        self.assertFalse(root.winfo_viewable())
        self.assertTrue(win.winfo_viewable())
        self.assertEqual(win.state(), "normal")
        self.assertEqual(win.wm_transient(), "")
        self.assertTrue(win.overrideredirect())
        self.assertTrue(win.attributes("-topmost"))

    def test_maps_while_root_iconified(self) -> None:
        root.iconify()
        pump()
        self.reminder()
        pump(0.1)
        self.assertTrue(self.toast_for("n1").win.winfo_viewable())

    def test_contents(self) -> None:
        self.reminder(title="ประชุมทีม Marketing", content="บรรทัด 1\n\nบรรทัด 2\nบรรทัด 3\nบรรทัด 4",
                      when="2026-10-26 14:30")
        tt = self.toast_for("n1")
        self.assertEqual(tt.caption_lbl.cget("text"), "QuickNote · 14:30")
        self.assertEqual(tt.title_lbl.cget("text"), "ประชุมทีม Marketing")
        body = tt.text_lbl.cget("text").split("\n")
        self.assertEqual(len(body), 3)
        self.assertTrue(body[-1].endswith("…"))
        self.assertEqual([b.cget("text") for b in tt.buttons],
                         [t("toast.done"), t("toast.snooze") + "  ▾", t("toast.open")])
        pump(0.05)
        self.assertEqual(tt.win.winfo_width(), px(root, 364))

    def test_buttons_equal_width(self) -> None:
        self.reminder()
        pump(0.05)
        widths = [b.winfo_width() for b in self.toast_for("n1").buttons]
        self.assertLessEqual(max(widths) - min(widths), 1, widths)  # คลาดได้ 1px จากการปัดเศษ

    def test_empty_title_falls_back(self) -> None:
        self.reminder(title="  ")
        self.assertEqual(self.toast_for("n1").title_lbl.cget("text"), t("common.untitled"))


class ToastActionsTest(UiCase):
    def test_close_button_dismisses_once(self) -> None:
        calls = self.reminder()
        tt = self.toast_for("n1")
        win = tt.win
        tt.close_btn.invoke()
        tt.dismiss()  # ซ้ำต้องไม่ยิงอีก
        self.assertEqual(calls["dismiss"], [1])
        self.assertEqual(self.mgr.toasts, ())
        pump(0.05)
        self.assertFalse(alive(win))

    def test_escape_key_dismisses_once(self) -> None:
        calls = self.reminder()
        win = self.toast_for("n1").win
        win.focus_force()
        pump(0.05)
        win.event_generate("<Escape>")
        pump(0.05)
        self.assertEqual(calls["dismiss"], [1])
        self.assertEqual(self.mgr.toasts, ())

    def test_done_open_buttons_call_only_their_callback_and_close(self) -> None:
        for idx, name in ((0, "done"), (2, "open")):
            with self.subTest(name):
                calls = self.reminder(note_id=f"x{idx}")
                tt = self.toast_for(f"x{idx}")
                win = tt.win
                tt.buttons[idx].invoke()
                self.assertEqual(calls[name], [1])
                self.assertEqual([len(v) for k, v in calls.items() if k != name], [0, 0, 0])
                self.assertNotIn(tt, self.mgr.toasts)
                pump(0.05)
                self.assertFalse(alive(win))

    def test_snooze_menu_when_strings(self) -> None:
        expected = ["2026-10-26 11:18", "2026-10-26 11:28", "2026-10-26 12:13", "2026-10-27 09:00"]
        with mock.patch.object(toast_mod, "_now", return_value=FIXED_NOW):
            for i, want in enumerate(expected):
                calls = self.reminder(note_id=f"s{i}")
                tt = self.toast_for(f"s{i}")
                self.assertEqual(tt.menu.index("end"), 3)
                self.assertEqual([tt.menu.entrycget(j, "label") for j in range(4)],
                                 [t("toast.snooze_5"), t("toast.snooze_15"), t("toast.snooze_60"),
                                  t("toast.snooze_tomorrow")])
                tt.menu.invoke(i)
                self.assertEqual(calls["snooze"], [want])
                self.assertEqual(calls["done"] + calls["open"] + calls["dismiss"], [])
                self.assertNotIn(tt, self.mgr.toasts)

    def test_snooze_time_computed_at_click_not_at_show(self) -> None:
        with mock.patch.object(toast_mod, "_now", return_value=FIXED_NOW):
            calls = self.reminder()
        later = datetime(2026, 10, 26, 13, 0, 5)
        with mock.patch.object(toast_mod, "_now", return_value=later):
            self.toast_for("n1").menu.invoke(0)
        self.assertEqual(calls["snooze"], ["2026-10-26 13:05"])

    def test_callback_exception_still_closes_toast(self) -> None:
        self.mgr.show_reminder({"id": "e", "title": "x"}, on_done=lambda: 1 / 0, on_snooze=lambda w: None,
                               on_open=lambda: None, on_dismiss=lambda: None)
        tt = self.toast_for("e")
        with self.assertLogs("src.ui.toast", level="ERROR"):
            tt.buttons[0].invoke()
        self.assertEqual(self.mgr.toasts, ())


class ToastStackTest(UiCase):
    def geometry(self, tt):
        return tt.win.winfo_x(), tt.win.winfo_y(), tt.win.winfo_width(), tt.win.winfo_height()

    def test_three_toasts_stack_upward_inside_work_area(self) -> None:
        for n in "abc":
            self.reminder(note_id=n, content="x\ny" if n == "b" else "")
        pump(0.1)
        left, top, right, bottom = win11.get_work_area(root)
        margin, gap = px(root, 12), px(root, 8)
        a, b, c = (self.geometry(self.toast_for(n)) for n in "abc")
        for x, y, w, h in (a, b, c):
            self.assertGreaterEqual(x, left)
            self.assertGreaterEqual(y, top)
            self.assertLessEqual(x + w, right - margin)
            self.assertLessEqual(y + h, bottom - margin)
        self.assertEqual(a[0] + a[2], right - margin)
        self.assertEqual(a[1] + a[3], bottom - margin)  # อันแรกชิดล่าง
        self.assertEqual(b[1] + b[3] + gap, a[1])
        self.assertEqual(c[1] + c[3] + gap, b[1])

    def test_restack_after_closing_middle(self) -> None:
        for n in "abc":
            self.reminder(note_id=n)
        pump(0.1)
        a_before = self.geometry(self.toast_for("a"))
        self.toast_for("b").dismiss()
        pump(0.1)
        a, c = self.geometry(self.toast_for("a")), self.geometry(self.toast_for("c"))
        self.assertEqual(a, a_before)
        self.assertEqual(c[1] + c[3] + px(root, 8), a[1])

    def test_restack_animated_converges(self) -> None:
        """เปิด animation จริง: ปิดอันกลางแล้วอันบนต้องเลื่อนลงมาจบที่ตำแหน่งเป้าหมาย"""
        with mock.patch.object(win11, "animations_enabled", return_value=True):
            for n in "abc":
                self.reminder(note_id=n)
            pump(0.5)
            self.toast_for("b").dismiss()
            pump(0.5)
            a, c = self.geometry(self.toast_for("a")), self.geometry(self.toast_for("c"))
            self.assertEqual(c[1] + c[3] + px(root, 8), a[1])
            self.assertAlmostEqual(float(self.toast_for("c").win.attributes("-alpha")), 1.0, places=2)

    def test_same_note_twice_keeps_one_toast_and_replaces(self) -> None:
        first = self.reminder(note_id="dup", title="เดิม")
        old_win = self.toast_for("dup").win
        second = self.reminder(note_id="dup", title="ใหม่")
        self.assertEqual(len(self.mgr.toasts), 1)
        self.assertEqual(self.toast_for("dup").title_lbl.cget("text"), "ใหม่")
        self.assertFalse(alive(old_win))
        self.toast_for("dup").dismiss()
        self.assertEqual((first["dismiss"], second["dismiss"]), ([], [1]))  # toast เก่าถูกแทนที่เงียบ ๆ

    def test_replacement_keeps_slot(self) -> None:
        for n in "abc":
            self.reminder(note_id=n)
        self.reminder(note_id="b", title="ใหม่")
        self.assertEqual([tt.key for tt in self.mgr.toasts], ["a", "b", "c"])

    def test_close_for_is_silent_and_targeted(self) -> None:
        a = self.reminder(note_id="a")
        b = self.reminder(note_id="b")
        self.mgr.close_for("a")
        self.mgr.close_for("nope")
        self.mgr.close_for("")
        self.assertEqual([tt.key for tt in self.mgr.toasts], ["b"])
        self.assertEqual(a, {"done": [], "snooze": [], "open": [], "dismiss": []})
        self.assertEqual(b["dismiss"], [])


class ToastMissedInfoTest(UiCase):
    def test_missed_lists_titles_and_view_callback(self) -> None:
        viewed = []
        notes = [{"title": f"งาน {i}"} for i in range(7)]
        self.mgr.show_missed(notes, lambda: viewed.append(1))
        self.assertEqual(len(self.mgr.toasts), 1)
        tt = self.mgr.toasts[0]
        self.assertEqual(tt.title_lbl.cget("text"), t("toast.missed", n=7))
        lines = tt.text_lbl.cget("text").split("\n")
        self.assertEqual(lines[:5], [f"• งาน {i}" for i in range(5)])
        self.assertEqual(lines[5], t("toast.missed_more", n=2))
        self.assertEqual(len(tt.buttons), 1)
        tt.buttons[0].invoke()
        self.assertEqual(viewed, [1])
        self.assertEqual(self.mgr.toasts, ())

    def test_missed_close_button_does_not_call_view_and_second_replaces(self) -> None:
        viewed = []
        self.mgr.show_missed([{"title": "a"}], lambda: viewed.append(1))
        self.mgr.show_missed([{"title": "a"}, {"title": "b"}], lambda: viewed.append(2))
        self.assertEqual(len(self.mgr.toasts), 1)
        self.assertEqual(self.mgr.toasts[0].title_lbl.cget("text"), t("toast.missed", n=2))
        self.mgr.toasts[0].close_btn.invoke()
        self.assertEqual(viewed, [])
        self.assertEqual(self.mgr.toasts, ())

    def test_missed_empty_list_shows_nothing(self) -> None:
        self.mgr.show_missed([], lambda: None)
        self.assertEqual(self.mgr.toasts, ())

    def test_info_auto_closes(self) -> None:
        self.mgr.show_info("QuickNote ยังทำงานอยู่ในถาด", seconds=0.2)
        self.assertEqual(len(self.mgr.toasts), 1)
        win = self.mgr.toasts[0].win
        self.assertEqual(self.mgr.toasts[0].text_lbl.cget("text"), "QuickNote ยังทำงานอยู่ในถาด")
        pump(0.1)
        self.assertEqual(len(self.mgr.toasts), 1)
        pump(0.4)
        self.assertEqual(self.mgr.toasts, ())
        self.assertFalse(alive(win))

    def test_info_toasts_do_not_replace_each_other_and_x_closes(self) -> None:
        self.mgr.show_info("a", seconds=30)
        self.mgr.show_info("b", seconds=30)
        self.assertEqual(len(self.mgr.toasts), 2)
        self.mgr.toasts[0].close_btn.invoke()
        self.assertEqual(len(self.mgr.toasts), 1)

    def test_info_survives_when_root_withdrawn(self) -> None:
        root.withdraw()
        self.mgr.show_info("hint", seconds=30)
        pump(0.1)
        self.assertTrue(self.mgr.toasts[0].win.winfo_viewable())


class ToastSoundTest(UiCase):
    def test_sound_disabled_never_calls_winsound(self) -> None:
        settings.data["sound"] = False
        with mock.patch.object(toast_mod, "winsound") as ws:
            self.reminder()
            self.mgr.show_missed([{"title": "x"}], lambda: None)
        ws.PlaySound.assert_not_called()

    def test_sound_enabled_plays_reminder_alias_async(self) -> None:
        settings.data["sound"] = True
        with mock.patch.object(toast_mod, "winsound") as ws:
            ws.SND_ALIAS, ws.SND_ASYNC, ws.SND_NODEFAULT = 1, 2, 4
            self.reminder()
        ws.PlaySound.assert_called_once_with("Notification.Reminder", 7)

    def test_falls_back_to_system_notification_then_silent(self) -> None:
        settings.data["sound"] = True
        with mock.patch.object(toast_mod, "winsound") as ws:
            ws.PlaySound.side_effect = [RuntimeError("no alias"), None]
            self.reminder()
            self.assertEqual([c.args[0] for c in ws.PlaySound.call_args_list],
                             ["Notification.Reminder", "SystemNotification"])
        with mock.patch.object(toast_mod, "winsound") as ws:
            ws.PlaySound.side_effect = RuntimeError("nothing works")
            self.reminder(note_id="other")  # ต้องไม่ raise
        self.assertEqual(len(self.mgr.toasts), 2)

    def test_info_toast_is_silent(self) -> None:
        settings.data["sound"] = True
        with mock.patch.object(toast_mod, "winsound") as ws:
            self.mgr.show_info("x")
        ws.PlaySound.assert_not_called()


class ToastThemeTest(UiCase):
    def test_recolours_on_theme_change_and_unsubscribes_on_close(self) -> None:
        subs = len(theme._subs)
        self.reminder()
        tt = self.toast_for("n1")
        self.assertEqual(len(theme._subs), subs + 1 + 1)  # toast + ปุ่ม ✕
        light_surface = theme.c("surface")
        self.assertEqual(tt.body.cget("bg"), light_surface)
        settings.set("theme", "dark")
        pump(0.1)
        self.assertEqual(theme.mode, "dark")
        self.assertEqual(tt.body.cget("bg"), theme.c("surface"))
        self.assertNotEqual(theme.c("surface"), light_surface)
        self.assertEqual(tt.win.cget("bg"), theme.c("stroke"))
        self.assertEqual(tt.title_lbl.cget("fg"), theme.c("text"))
        tt.dismiss()
        pump(0.05)
        self.assertEqual(len(theme._subs), subs)

    def test_english_strings(self) -> None:
        strings.set_language("en")
        self.reminder()
        self.assertEqual([b.cget("text") for b in self.toast_for("n1").buttons], ["Done", "Snooze  ▾", "Open"])


class ToastAnimationTest(UiCase):
    animations = True

    def test_enter_animation_ends_opaque_at_target(self) -> None:
        self.reminder()
        tt = self.toast_for("n1")
        pump(0.5)
        left, top, right, bottom = win11.get_work_area(root)
        self.assertAlmostEqual(float(tt.win.attributes("-alpha")), 1.0, places=2)
        self.assertEqual(tt.win.winfo_y() + tt.win.winfo_height(), bottom - px(root, 12))

    def test_exit_fades_then_destroys(self) -> None:
        self.reminder()
        pump(0.4)
        win = self.toast_for("n1").win
        self.toast_for("n1").dismiss()
        self.assertTrue(alive(win))  # กำลัง fade
        pump(0.4)
        self.assertFalse(alive(win))


# ================================================================== dialog
class DialogPrefillTest(UiCase):
    def test_prefill_existing_reminder(self) -> None:
        d, _ = self.dialog(Note(id="n", title="ซื้อของ", reminder_datetime="2030-05-17 14:35",
                                reminder_repeat="weekly"))
        self.assertEqual((d.date_var.get(), d.hour_var.get(), d.minute_var.get()), ("17/05/2030", "14", "35"))
        self.assertEqual(d.repeat, "weekly")
        self.assertEqual(d.repeat_var.get(), t("reminder.repeat.weekly"))
        self.assertTrue(d.is_valid)
        self.assertIsNotNone(d.delete_btn)
        self.assertEqual(d.message, "")

    def test_default_is_next_full_hour(self) -> None:
        with mock.patch.object(dialog_mod, "_now", return_value=FIXED_NOW):
            d, _ = self.dialog()
        self.assertEqual((d.date_var.get(), d.hour_var.get(), d.minute_var.get()), ("26/10/2026", "12", "00"))
        self.assertEqual(d.repeat, "none")
        self.assertIsNone(d.delete_btn)

    def test_default_rolls_over_midnight(self) -> None:
        with mock.patch.object(dialog_mod, "_now", return_value=datetime(2026, 10, 26, 23, 30)):
            d, _ = self.dialog()
        self.assertEqual((d.date_var.get(), d.hour_var.get(), d.minute_var.get()), ("27/10/2026", "00", "00"))

    def test_corrupt_stored_value_falls_back_to_default(self) -> None:
        with mock.patch.object(dialog_mod, "_now", return_value=FIXED_NOW):
            d, _ = self.dialog(Note(id="n", title="x", reminder_datetime="garbage", reminder_repeat="bogus"))
        self.assertEqual(d.hour_var.get(), "12")
        self.assertEqual(d.repeat, "none")

    def test_title_shown_and_window_title(self) -> None:
        d, _ = self.dialog(Note(id="n", title="ประชุมทีม Marketing"))
        self.assertEqual(d._note_lbl.cget("text"), "ประชุมทีม Marketing")
        self.assertEqual(d.top.title(), t("reminder.title"))

    def test_calendar_uses_theme_colours_not_hardcoded(self) -> None:
        d, _ = self.dialog()
        self.assertEqual(d.date_entry.cget("selectbackground"), theme.c("accent"))
        self.assertEqual(d.date_entry.cget("headersbackground"), theme.c("surface"))
        self.assertNotIn("darkblue", str(d.date_entry.cget("background")).lower())


class DialogQuickButtonsTest(UiCase):
    def fields(self, d):
        return d.date_var.get(), d.hour_var.get(), d.minute_var.get()

    def test_quick_buttons_fill_fields(self) -> None:
        with mock.patch.object(dialog_mod, "_now", return_value=FIXED_NOW):
            d, _ = self.dialog()
            d.quick_buttons["in15m"].invoke()
            self.assertEqual(self.fields(d), ("26/10/2026", "11", "28"))
            d.quick_buttons["in1h"].invoke()
            self.assertEqual(self.fields(d), ("26/10/2026", "12", "13"))
            d.quick_buttons["this_evening"].invoke()
            self.assertEqual(self.fields(d), ("26/10/2026", "17", "00"))
            d.quick_buttons["tomorrow_9"].invoke()
            self.assertEqual(self.fields(d), ("27/10/2026", "09", "00"))
        self.assertTrue(d.is_valid)

    def test_evening_disabled_after_17(self) -> None:
        with mock.patch.object(dialog_mod, "_now", return_value=datetime(2026, 10, 26, 18, 0)):
            d, _ = self.dialog()
            self.assertTrue(d.quick_buttons["this_evening"].instate(["disabled"]))
            self.assertFalse(d.quick_buttons["tomorrow_9"].instate(["disabled"]))
            before = self.fields(d)
            d.quick_buttons["this_evening"].invoke()  # disabled → ไม่มีผล
            self.assertEqual(self.fields(d), before)

    def test_quick_button_clears_error(self) -> None:
        d, _ = self.dialog()
        d.minute_var.set("99")
        self.assertFalse(d.is_valid)
        d.quick_buttons["in1h"].invoke()
        self.assertTrue(d.is_valid)
        self.assertTrue(d.save_btn.instate(["!disabled"]))


class DialogValidationTest(UiCase):
    def test_invalid_minute_disables_save_and_shows_error(self) -> None:
        with mock.patch.object(dialog_mod, "_now", return_value=FIXED_NOW):
            d, saved = self.dialog()
            d.minute_var.set("99")
            self.assertTrue(d.save_btn.instate(["disabled"]))
            self.assertEqual(d.message, t("reminder.err_minute"))
            d.save()
            d.top.event_generate("<Return>")
            pump(0.05)
            self.assertEqual(saved, [])
            self.assertTrue(alive(d.top))
            d.minute_var.set("30")
            self.assertTrue(d.save_btn.instate(["!disabled"]))
            self.assertEqual(d.message, "")

    def test_each_field_reports_its_own_error(self) -> None:
        d, _ = self.dialog()
        cases = [("hour_var", "24", "reminder.err_hour"), ("hour_var", "ab", "reminder.err_hour"),
                 ("hour_var", "-1", "reminder.err_hour"), ("hour_var", "", "reminder.err_hour"),
                 ("minute_var", "60", "reminder.err_minute"), ("minute_var", "x1", "reminder.err_minute"),
                 ("date_var", "32/13/2026", "reminder.err_date"), ("date_var", "hello", "reminder.err_date"),
                 ("date_var", "01/01/0001", "reminder.err_date")]
        for var, text, key in cases:
            with self.subTest(var=var, text=text):
                d.quick_buttons["in1h"].invoke()  # รีเซ็ตให้ถูกต้องก่อน
                getattr(d, var).set(text)
                self.assertFalse(d.is_valid)
                self.assertEqual(d.message, t(key))
                self.assertTrue(d.save_btn.instate(["disabled"]))

    def test_validates_while_typing_in_spinbox(self) -> None:
        """M7: ตรวจทุกครั้งที่ค่าเปลี่ยน ไม่ใช่ตอนกดบันทึก — พิมพ์ลงช่องจริง"""
        d, _ = self.dialog()
        d.minute_spin.delete(0, "end")
        d.minute_spin.insert(0, "77")
        self.assertEqual(d.message, t("reminder.err_minute"))
        d.minute_spin.delete(0, "end")
        d.minute_spin.insert(0, "7")  # พิมพ์เลขอะไรก็ได้ 0–59 (ไม่ต้องเป็นขั้นละ 5)
        self.assertTrue(d.is_valid)

    def test_past_time_warns_but_still_saves(self) -> None:
        with mock.patch.object(dialog_mod, "_now", return_value=FIXED_NOW):
            d, saved = self.dialog()
            d.set_when(datetime(2026, 10, 26, 9, 0))
            self.assertTrue(d.is_valid)
            self.assertTrue(d.is_past)
            self.assertEqual(d.message, t("reminder.past_warning"))
            self.assertNotEqual(d._msg_icon.cget("text"), "")
            self.assertTrue(d.save_btn.instate(["!disabled"]))
            d.save()
        self.assertEqual(saved, [("2026-10-26 09:00", "none")])

    def test_future_time_has_no_message(self) -> None:
        with mock.patch.object(dialog_mod, "_now", return_value=FIXED_NOW):
            d, _ = self.dialog()
            self.assertEqual(d.message, "")
            self.assertEqual(d._msg_icon.cget("text"), "")
            self.assertFalse(d.is_past)


class DialogSaveTest(UiCase):
    def test_save_passes_when_string_and_repeat(self) -> None:
        with mock.patch.object(dialog_mod, "_now", return_value=FIXED_NOW):
            d, saved = self.dialog()
            d.set_when(datetime(2026, 11, 3, 8, 5))
            d.set_repeat("weekdays")
            d.save()
        self.assertEqual(saved, [("2026-11-03 08:05", "weekdays")])
        self.assertFalse(alive(d.top))

    def test_repeat_chosen_from_combobox_display_text(self) -> None:
        d, saved = self.dialog()
        d.repeat_combo.set(t("reminder.repeat.daily"))
        self.assertEqual(d.repeat, "daily")
        d.save()
        self.assertEqual(saved[0][1], "daily")

    def test_delete_link_clears_reminder(self) -> None:
        d, saved = self.dialog(Note(id="n", title="x", reminder_datetime="2030-01-01 10:00", reminder_repeat="daily"))
        d.delete_btn.invoke()
        self.assertEqual(saved, [(None, "none")])
        self.assertFalse(alive(d.top))

    def test_spinbox_wraps_and_steps(self) -> None:
        d, _ = self.dialog()
        d.hour_var.set("23")
        d.hour_spin.event_generate("<<Increment>>")
        self.assertEqual(d.hour_var.get(), "00")
        d.minute_var.set("55")
        d.minute_spin.event_generate("<<Increment>>")
        self.assertEqual(d.minute_var.get(), "00")
        d.minute_spin.event_generate("<<Decrement>>")
        self.assertEqual(d.minute_var.get(), "55")
        d.minute_var.set("07")  # พิมพ์ค่าที่ไม่ใช่ขั้น 5 ได้ และยังถูกต้อง
        self.assertTrue(d.is_valid)


class DialogKeysTest(UiCase):
    def press(self, d, key: str) -> None:
        d.top.focus_force()
        pump(0.05)
        d.top.event_generate(key)
        pump(0.05)

    def test_enter_saves_when_valid(self) -> None:
        d, saved = self.dialog()
        d.set_when(datetime(2031, 1, 2, 3, 4))
        self.press(d, "<Return>")
        self.assertEqual(saved, [("2031-01-02 03:04", "none")])
        self.assertFalse(alive(d.top))

    def test_escape_cancels_without_saving(self) -> None:
        d, saved = self.dialog()
        self.press(d, "<Escape>")
        self.assertEqual(saved, [])
        self.assertFalse(alive(d.top))

    def test_enter_on_delete_link_deletes_instead_of_saving(self) -> None:
        d, saved = self.dialog(Note(id="n", title="x", reminder_datetime="2030-01-01 10:00"))
        d.delete_btn.focus_force()
        pump(0.05)
        d.top.event_generate("<Return>")
        pump(0.05)
        self.assertEqual(saved, [(None, "none")])

    def test_close_window_button_cancels(self) -> None:
        d, saved = self.dialog()
        d.top.tk.call(d.top.protocol("WM_DELETE_WINDOW"))  # = ผู้ใช้กด ✕ ที่ titlebar
        self.assertFalse(alive(d.top))
        self.assertEqual(saved, [])
        self.assertIsNone(root.grab_current())


class DialogModalTest(UiCase):
    def test_grab_held_while_open_and_released_on_save(self) -> None:
        d, _ = self.dialog()
        self.assertEqual(d.top.grab_status(), "local")
        d.save()
        self.assertIsNone(root.grab_current())

    def test_grab_released_on_cancel(self) -> None:
        d, _ = self.dialog()
        d.cancel()
        self.assertIsNone(root.grab_current())
        self.assertFalse(alive(d.top))

    def test_grab_released_when_on_save_raises(self) -> None:
        """M8: callback พัง → หน้าต่างหลักต้องไม่ติด grab"""
        def boom(when, repeat):
            raise RuntimeError("db locked")
        d, _ = self.dialog(on_save=boom)
        with self.assertLogs("src.ui.reminder_dialog", level="ERROR"), \
                mock.patch("tkinter.messagebox.showerror") as err:
            d.save()
        err.assert_called_once()  # ผู้ใช้ต้องเห็นว่าบันทึกไม่สำเร็จ
        self.assertIsNone(root.grab_current())
        self.assertFalse(alive(d.top))

    def test_grab_released_when_delete_callback_raises(self) -> None:
        def boom(when, repeat):
            raise RuntimeError("db locked")
        d, _ = self.dialog(Note(id="n", title="x", reminder_datetime="2030-01-01 10:00"), on_save=boom)
        with self.assertLogs("src.ui.reminder_dialog", level="ERROR"), \
                mock.patch("tkinter.messagebox.showerror"):
            d.delete_reminder()
        self.assertIsNone(root.grab_current())

    def test_close_is_idempotent_and_save_after_close_is_noop(self) -> None:
        d, saved = self.dialog()
        d.cancel()
        d.cancel()
        d.save()
        self.assertEqual(saved, [])

    def test_destroyed_with_root_child_cleans_theme_subscription(self) -> None:
        subs = len(theme._subs)
        d, _ = self.dialog()
        self.assertEqual(len(theme._subs), subs + 1)
        d.top.destroy()  # ถูกทำลายจากทางอื่น
        pump(0.05)
        self.assertEqual(len(theme._subs), subs)

    def test_transient_when_root_visible(self) -> None:
        d, _ = self.dialog()
        self.assertTrue(root.winfo_viewable())
        self.assertNotEqual(d.top.wm_transient(), "")

    def test_not_transient_when_root_withdrawn_and_still_visible(self) -> None:
        """C6 ฝั่ง dialog: root ซ่อนอยู่ dialog ต้องไม่ transient ไม่งั้นหายไปด้วย"""
        root.withdraw()
        pump()
        d, _ = self.dialog()
        pump(0.1)
        self.assertEqual(d.top.wm_transient(), "")
        self.assertTrue(d.top.winfo_viewable())
        self.assertTrue(d.top.attributes("-topmost"))
        d.cancel()
        self.assertIsNone(root.grab_current())

    def test_centered_over_root_and_inside_work_area(self) -> None:
        d, _ = self.dialog()
        left, top, right, bottom = win11.get_work_area(root)
        self.assertGreaterEqual(d.top.winfo_x(), left - 20)  # winfo_x รวมกรอบ native บางส่วน
        self.assertLessEqual(d.top.winfo_x() + d.top.winfo_width(), right + 20)
        self.assertLessEqual(d.top.winfo_y() + d.top.winfo_height(), bottom + 20)
        self.assertGreaterEqual(d.top.winfo_reqheight(), 1)

    def test_theme_change_updates_dialog(self) -> None:
        d, _ = self.dialog()
        settings.set("theme", "dark")
        pump(0.1)
        self.assertEqual(d.top.cget("bg"), theme.c("bg"))
        self.assertEqual(d.date_entry.cget("selectbackground"), theme.c("accent"))
        self.assertEqual(d._note_lbl.cget("fg"), theme.c("text_secondary"))

    def test_english_strings(self) -> None:
        strings.set_language("en")
        d, _ = self.dialog()
        self.assertEqual(d.top.title(), "Set reminder")
        self.assertEqual(d.repeat_var.get(), "Does not repeat")
        self.assertEqual(d.save_btn.cget("text"), "Save")
        self.assertIsInstance(d.repeat_combo, ttk.Combobox)


if __name__ == "__main__":
    unittest.main()
