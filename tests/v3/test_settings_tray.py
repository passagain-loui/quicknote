"""Tests ของหน้าต่าง Settings + System tray — Tk จริง, DB/settings/Startup เป็น temp ทั้งหมด

ไม่แตะ ~/.quicknote หรือโฟลเดอร์ Startup จริง; patch เฉพาะ dialog ของ OS (filedialog/messagebox/os.startfile)
และ pystray.Icon.run (ไม่ให้ไอคอนไปโผล่ในถาดของผู้ใช้จริง)
"""

import copy
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pystray  # noqa: E402

from src.core import database as db  # noqa: E402
from src.platform.hotkey import parse_hotkey  # noqa: E402
from src.core import settings as settings_mod  # noqa: E402
from src.core.constants import MIN_ALPHA  # noqa: E402
from src.platform import autostart, tray as tray_mod  # noqa: E402
from src.ui import settings_window as sw  # noqa: E402
from src.ui import strings  # noqa: E402
from src.ui.theme import Theme  # noqa: E402

root: tk.Tk


def setUpModule() -> None:
    global root
    root = tk.Tk()
    root.geometry("380x500+0+0")
    root.attributes("-alpha", 0.0)
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


class SettingsTestCase(unittest.TestCase):
    """DB + settings.json + โฟลเดอร์ Startup ชั่วคราวต่อ test, สร้าง SettingsWindow ให้ทุกครั้ง"""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="qn_test_settings_"))
        self._old_env = os.environ.get("DB_PATH")
        self._old_app_dir, self._old_file = db.APP_DIR, settings_mod.SETTINGS_FILE
        os.environ["DB_PATH"] = str(self.tmp / "notes.db")
        db.APP_DIR = self.tmp
        settings_mod.SETTINGS_FILE = self.tmp / "settings.json"
        db.init_db()

        self.startup = self.tmp / "Startup"
        patcher = mock.patch.object(autostart, "get_startup_dir", return_value=self.startup)
        patcher.start()
        self.addCleanup(patcher.stop)

        strings.set_language("th")
        self.settings = settings_mod.Settings()
        self.settings.set("theme", "light")
        self.theme = Theme(root, self.settings)
        self.actions = sw.SettingsActions(mock.Mock(), mock.Mock(), mock.Mock(), mock.Mock())
        self.closed: list[int] = []
        self.win: sw.SettingsWindow | None = None

    def tearDown(self) -> None:
        if self.win is not None:
            self.win._close()
        strings.set_language("th")
        pump()
        if self._old_env is None:
            os.environ.pop("DB_PATH", None)
        else:
            os.environ["DB_PATH"] = self._old_env
        db.APP_DIR, settings_mod.SETTINGS_FILE = self._old_app_dir, self._old_file
        shutil.rmtree(self.tmp, ignore_errors=True)

    def open(self, actions: sw.SettingsActions | None = None) -> sw.SettingsWindow:
        self.win = sw.SettingsWindow(root, self.settings, self.theme, actions or self.actions,
                                     lambda: self.closed.append(1))
        pump(0.05)
        return self.win

    def saved(self) -> dict:
        with open(settings_mod.SETTINGS_FILE, encoding="utf-8") as f:
            return json.load(f)

    def pick(self, key: str, label: str) -> None:
        """เลือกค่าใน combobox เหมือนผู้ใช้ (ตั้งข้อความ + ยิง <<ComboboxSelected>>)"""
        combo = self.win.controls[key]
        combo.set(label)
        combo.event_generate("<<ComboboxSelected>>")
        pump(0.05)

    def label_texts(self, widget=None) -> list[str]:
        widget = widget or self.win.win
        out = []
        for w in widget.winfo_children():
            if isinstance(w, tk.Label) and w.cget("text"):
                out.append(w.cget("text"))
            out += self.label_texts(w)
        return out


# ============================================================ controls → settings
class ControlsTest(SettingsTestCase):
    def test_builds_all_controls_without_google(self) -> None:
        win = self.open()
        for key in ("theme", "language", "alpha", "font_size", "compact", "autostart", "always_on_top",
                    "close_to_tray", "hotkey_new_note", "hotkey_toggle_show", "sound", "snooze_default_minutes",
                    "auto_backup", "backup", "restore", "export", "open_folder"):
            self.assertIn(key, win.controls, key)
        texts = " ".join(self.label_texts())
        self.assertNotIn("Google", texts)
        self.assertIn(strings.t("settings.about", version=sw.APP_VERSION, author=sw.APP_AUTHOR), texts)
        self.assertEqual(win.win.title(), "ตั้งค่า")

    def test_switches_write_settings_and_persist(self) -> None:
        win = self.open()
        for key in ("compact", "always_on_top", "close_to_tray", "sound", "auto_backup"):
            before = self.settings.get(key)
            win.controls[key].invoke()
            self.assertEqual(self.settings.get(key), (not before), key)
            self.assertEqual(self.saved()[key], not before, key)  # บันทึกลงดิสก์ทันที ไม่ต้องกดปุ่ม
            win.controls[key].invoke()
            self.assertEqual(self.settings.get(key), before, key)

    def test_comboboxes_write_settings(self) -> None:
        win = self.open()
        self.pick("theme", "มืด")
        self.assertEqual(self.settings.get("theme"), "dark")
        self.assertEqual(self.theme.mode, "dark")
        self.pick("theme", "ตามระบบ")
        self.assertEqual(self.settings.get("theme"), "system")
        self.pick("theme", "สว่าง")
        self.pick("font_size", "ใหญ่")
        self.assertEqual(self.settings.get("font_size"), "large")
        self.pick("snooze_default_minutes", "15 นาที")
        self.assertEqual(self.settings.get("snooze_default_minutes"), 15)
        self.pick("snooze_default_minutes", "1 ชั่วโมง")
        self.assertEqual(self.settings.get("snooze_default_minutes"), 60)
        self.assertEqual(str(win.controls["theme"].cget("state")), "readonly")
        self.assertEqual(self.saved()["snooze_default_minutes"], 60)

    def test_odd_stored_values_do_not_crash(self) -> None:
        self.settings.data["snooze_default_minutes"] = 7  # ค่านอกรายการ (ไฟล์ถูกแก้มือ)
        self.settings.data["alpha"] = "oops"
        win = self.open()
        self.assertEqual(win.controls["snooze_default_minutes"].get(), "5 นาที")
        self.assertEqual(win.controls["alpha_label"].cget("text"), "100%")

    def test_alpha_slider_clamps_and_debounces_save(self) -> None:
        win = self.open()
        slider = win.controls["alpha"]
        slider.move_to(50)
        self.assertAlmostEqual(self.settings.get("alpha"), 0.5)
        self.assertEqual(win.controls["alpha_label"].cget("text"), "50%")
        self.assertFalse(settings_mod.SETTINGS_FILE.exists() and self.saved().get("alpha") == 0.5)  # ยังไม่ fsync ระหว่างลาก
        win._flush_alpha()
        self.assertAlmostEqual(self.saved()["alpha"], 0.5)

        slider.move_to(2)  # ต่ำกว่าขั้นต่ำ → clamp (M11: UI กับ settings ต้องตรงกัน)
        self.assertEqual(slider.get(), round(MIN_ALPHA * 100))
        self.assertAlmostEqual(self.settings.get("alpha"), MIN_ALPHA)
        self.assertEqual(win.controls["alpha_label"].cget("text"), "30%")
        slider.move_to(500)
        self.assertEqual(slider.get(), 100)
        self.assertEqual(self.settings.get("alpha"), 1.0)

    def test_alpha_slider_mouse_and_keys(self) -> None:
        win = self.open()
        slider = win.controls["alpha"]
        win.win.update()
        slider.event_generate("<ButtonPress-1>", x=0, y=5)  # ปลายซ้ายสุด
        self.assertAlmostEqual(self.settings.get("alpha"), MIN_ALPHA)
        slider.event_generate("<Right>")
        self.assertAlmostEqual(self.settings.get("alpha"), MIN_ALPHA + 0.01)
        slider.event_generate("<End>")
        self.assertEqual(self.settings.get("alpha"), 1.0)

    def test_alpha_pending_save_flushed_on_close(self) -> None:
        win = self.open()
        win.controls["alpha"].move_to(60)
        win._close()
        self.assertAlmostEqual(self.saved()["alpha"], 0.6)

    def test_language_switch_relabels_window_live(self) -> None:
        win = self.open()
        self.pick("language", "English")
        self.assertEqual(self.settings.get("language"), "en")
        self.assertEqual(strings.get_language(), "en")
        self.assertEqual(win.win.title(), "Settings")
        texts = self.label_texts()
        self.assertIn("Appearance", texts)
        self.assertIn("Window opacity", texts)
        self.assertEqual(win.controls["language"].get(), "English")
        self.assertEqual(win.controls["snooze_default_minutes"].get(), "5 min")
        self.pick("language", "ไทย")
        self.assertIn("ลักษณะ", self.label_texts())

    def test_external_setting_changes_sync_controls(self) -> None:
        win = self.open()
        self.settings.set("always_on_top", False)
        self.assertFalse(win.controls["always_on_top"].instate(["selected"]))
        self.settings.set("alpha", 0.5)
        self.assertEqual(win.controls["alpha_label"].cget("text"), "50%")
        self.settings.set("snooze_default_minutes", 30)
        self.assertEqual(win.controls["snooze_default_minutes"].get(), "30 นาที")
        self.settings.set("hotkeys", {"new_note": "<ctrl>+<alt>+j", "toggle_show": "<ctrl>+<alt>+s"})
        self.assertEqual(win._recorders["new_note"].button.cget("text"), "Ctrl+Alt+J")

    def test_theme_change_recolors_open_window(self) -> None:
        win = self.open()
        self.settings.set("theme", "dark")
        pump(0.1)
        self.assertEqual(win._canvas.cget("bg"), self.theme.c("bg"))
        self.assertEqual(win._inner.cget("bg"), self.theme.c("bg"))
        card = next(w for w in win._inner.winfo_children() if isinstance(w, sw.SettingsCard))
        self.assertEqual(card.body.cget("bg"), self.theme.c("card"))
        self.assertEqual(card._rf.cget("bg"), self.theme.c("bg"))  # กล่องหลังมุมโค้งต้องเป็นสีพื้นใหม่ (ไม่ใช่ขอบขาวในธีมมืด)

    def test_page_scrolls_with_wheel(self) -> None:
        win = self.open()
        win.win.geometry("520x300")
        pump(0.1)
        self.assertEqual(win._canvas.yview()[0], 0.0)
        win._canvas.event_generate("<MouseWheel>", delta=-120)
        self.assertGreater(win._canvas.yview()[0], 0.0)

    def test_combobox_wheel_scrolls_page_not_value(self) -> None:
        win = self.open()
        win.win.geometry("520x300")
        pump(0.1)
        combo = win.controls["theme"]
        before = combo.get()
        combo.event_generate("<MouseWheel>", delta=-120)
        self.assertEqual(combo.get(), before)
        self.assertEqual(self.settings.get("theme"), "light")


# ============================================================ hotkey recorder
def key_event(keycode: int, keysym: str = "??", state: int = 0) -> SimpleNamespace:
    return SimpleNamespace(keycode=keycode, keysym=keysym, state=state)


CTRL_ALT = sw._STATE_CTRL | sw._STATE_ALT


class HotkeyTest(SettingsTestCase):
    def test_pure_conversion(self) -> None:
        self.assertEqual(sw.key_token(78, "??"), "n")                # VK ไม่ใช่ keysym (แป้นภาษาไทยก็ได้ n)
        self.assertEqual(sw.key_token(0x35, "5"), "5")
        self.assertEqual(sw.key_token(0x74, "F5"), "<f5>")
        self.assertEqual(sw.key_token(0x20, "space"), "<space>")
        self.assertEqual(sw.key_token(0xBC, "comma"), ",")
        self.assertIsNone(sw.key_token(0x1B, "Escape"))
        self.assertEqual(sw.modifiers_from_state(CTRL_ALT | 0x8), {"ctrl", "alt"})  # 0x8 = NumLock ต้องไม่นับ
        self.assertEqual(sw.compose_hotkey({"alt", "shift", "ctrl"}, "n"), "<ctrl>+<alt>+<shift>+n")
        self.assertEqual(sw.format_hotkey("<ctrl>+<alt>+n"), "Ctrl+Alt+N")
        self.assertEqual(sw.format_hotkey("<cmd>+<f5>"), "Win+F5")
        self.assertEqual(sw.format_hotkey("<ctrl>+<page_up>"), "Ctrl+PageUp")

    def test_generated_combos_are_valid_for_register_hotkey(self) -> None:
        # ตัวลงทะเบียนจริงคือ Win32 RegisterHotKey (platform/hotkey.py) ไม่ใช่ pynput แล้ว
        for mods, code, sym in (({"ctrl", "alt"}, 78, "n"), ({"cmd", "shift"}, 0x74, "F5"), ({"ctrl"}, 0x20, "space"),
                                ({"alt"}, 0xBC, "comma")):
            combo = sw.compose_hotkey(mods, sw.key_token(code, sym))
            mod_flags, vk = parse_hotkey(combo)  # ไม่ raise = ลงทะเบียนได้
            self.assertTrue(mod_flags and vk, combo)

    def start(self, name: str = "new_note") -> sw._HotkeyRecorder:
        win = self.open()
        rec = win._recorders[name]
        rec.button.invoke()
        return rec

    def test_click_enters_recording_mode(self) -> None:
        rec = self.start()
        self.assertTrue(rec.recording)
        self.assertEqual(rec.button.cget("text"), strings.t("settings.hotkey.recording"))

    def test_records_combo_into_new_dict(self) -> None:
        rec = self.start()
        spy = mock.Mock()
        self.settings.subscribe(spy)
        old = self.settings.get("hotkeys")
        self.assertEqual(rec._on_press(key_event(0x4B, "??", CTRL_ALT)), "break")  # Ctrl+Alt+K
        hk = self.settings.get("hotkeys")
        self.assertEqual(hk["new_note"], "<ctrl>+<alt>+k")
        self.assertEqual(hk["toggle_show"], old["toggle_show"])
        self.assertIsNot(hk, old)
        spy.assert_called_once()                                        # listener รู้ว่าต้อง restart hotkey
        self.assertEqual(spy.call_args.args[0], "hotkeys")
        self.assertFalse(rec.recording)
        self.assertEqual(rec.button.cget("text"), "Ctrl+Alt+K")
        self.assertEqual(self.saved()["hotkeys"]["new_note"], "<ctrl>+<alt>+k")

    def test_real_key_event_reaches_recorder(self) -> None:
        rec = self.start()
        rec.button.focus_force()
        pump(0.05)
        rec.button.event_generate("<KeyPress>", keycode=0x4B, state=CTRL_ALT)
        pump(0.05)
        self.assertEqual(self.settings.get("hotkeys")["new_note"], "<ctrl>+<alt>+k")

    def test_modifier_keys_tracked_without_state_bits(self) -> None:
        rec = self.start()
        rec._on_press(key_event(0x5B, "Super_L"))      # Win ไม่มีบิตใน state ของ Tk → ต้องจำเองจาก KeyPress
        self.assertIn("Win", rec.button.cget("text"))
        rec._on_press(key_event(0x4E, "n"))
        self.assertEqual(self.settings.get("hotkeys")["new_note"], "<cmd>+n")

    def test_no_modifier_rejected_and_keeps_recording(self) -> None:
        rec = self.start()
        before = copy.deepcopy(self.settings.get("hotkeys"))
        rec._on_press(key_event(0x4E, "n", 0))
        self.assertEqual(self.settings.get("hotkeys"), before)
        self.assertTrue(rec.recording)
        self.assertEqual(rec.error.cget("text"), strings.t("settings.hotkey.invalid"))
        self.assertEqual(rec.error.winfo_manager(), "grid")
        rec._on_press(key_event(0x4E, "n", sw._STATE_SHIFT))   # Shift อย่างเดียวก็ไม่พอ
        self.assertEqual(self.settings.get("hotkeys"), before)
        rec._on_press(key_event(0x4E, "n", sw._STATE_CTRL))    # ลองใหม่แล้วผ่าน
        self.assertEqual(self.settings.get("hotkeys")["new_note"], "<ctrl>+n")
        self.assertEqual(rec.error.winfo_manager(), "")

    def test_duplicate_of_other_hotkey_rejected(self) -> None:
        rec = self.start()
        before = copy.deepcopy(self.settings.get("hotkeys"))
        rec._on_press(key_event(0x53, "s", CTRL_ALT))  # Ctrl+Alt+S = คีย์แสดง/ซ่อนอยู่แล้ว
        self.assertEqual(self.settings.get("hotkeys"), before)
        self.assertEqual(rec.error.cget("text"), strings.t("settings.hotkey.duplicate"))

    def test_escape_cancels(self) -> None:
        rec = self.start()
        before = copy.deepcopy(self.settings.get("hotkeys"))
        self.assertEqual(rec._on_press(key_event(0x1B, "Escape")), "break")
        self.assertFalse(rec.recording)
        self.assertEqual(rec.button.cget("text"), "Ctrl+Alt+N")
        self.assertEqual(self.settings.get("hotkeys"), before)
        self.assertEqual(self.closed, [])  # Esc ตอนอัดคีย์ต้องไม่ปิดหน้าต่าง

    def test_focus_loss_cancels(self) -> None:
        rec = self.start()
        rec.cancel()
        self.assertFalse(rec.recording)

    def test_keys_ignored_when_not_recording(self) -> None:
        win = self.open()
        rec = win._recorders["toggle_show"]
        self.assertIsNone(rec._on_press(key_event(0x4B, "k", CTRL_ALT)))  # ไม่ใช่ "break" → Space/Enter ของปุ่มทำงานปกติ
        self.assertEqual(self.settings.get("hotkeys")["toggle_show"], "<ctrl>+<alt>+s")


# ============================================================ autostart
class AutostartTest(SettingsTestCase):
    link = "QuickNote.lnk"

    def test_switch_creates_and_removes_real_shortcut(self) -> None:
        win = self.open()
        sw_ = win.controls["autostart"]
        self.assertFalse(sw_.instate(["selected"]))
        with mock.patch.object(sw.messagebox, "showerror") as err:
            sw_.invoke()
            self.assertTrue((self.startup / self.link).exists())
            self.assertTrue(sw_.instate(["selected"]))
            sw_.invoke()
            self.assertFalse((self.startup / self.link).exists())
            self.assertFalse(sw_.instate(["selected"]))
            err.assert_not_called()

    def test_initial_state_reads_disk_truth(self) -> None:
        self.startup.mkdir(parents=True)
        (self.startup / self.link).write_bytes(b"x")
        win = self.open()
        self.assertTrue(win.controls["autostart"].instate(["selected"]))

    def test_failure_reverts_switch_and_shows_error(self) -> None:
        win = self.open()
        with mock.patch.object(sw, "enable_autostart", return_value=False), \
                mock.patch.object(sw.messagebox, "showerror") as err:
            win.controls["autostart"].invoke()
        self.assertFalse(win.controls["autostart"].instate(["selected"]))
        err.assert_called_once()
        self.assertEqual(err.call_args.kwargs["parent"], win.win)
        self.assertEqual(err.call_args.args[1], strings.t("settings.autostart.error"))

    def test_disable_failure_reverts_to_on(self) -> None:
        self.startup.mkdir(parents=True)
        (self.startup / self.link).write_bytes(b"x")
        win = self.open()
        with mock.patch.object(sw, "disable_autostart", return_value=False), \
                mock.patch.object(sw.messagebox, "showerror") as err:
            win.controls["autostart"].invoke()
        self.assertTrue(win.controls["autostart"].instate(["selected"]))
        err.assert_called_once()

    def test_autostart_module_launch_target_is_quoted(self) -> None:
        with mock.patch.object(autostart.sys, "frozen", False, create=True):
            exe, args, workdir = autostart._launch_target()
        self.assertTrue(args.startswith('"') and args.endswith('main.py"'))
        self.assertTrue(Path(workdir).is_dir())
        self.assertTrue(Path(exe).exists())

    def test_disable_when_absent_is_success(self) -> None:
        self.assertTrue(autostart.disable_autostart())


# ============================================================ close / lifecycle
class LifecycleTest(SettingsTestCase):
    def test_on_close_fires_once_and_listeners_released(self) -> None:
        win = self.open()
        win._close()
        win._close()
        self.assertEqual(self.closed, [1])
        self.assertNotIn(win._on_theme, self.theme._subs)
        with self.assertNoLogs("quicknote.settings"):  # listener ที่ค้างต้องไม่แตะ widget ที่ถูกทำลาย (Settings.set กลืน exception ไว้แค่ log)
            self.settings.set("compact", True)
            self.settings.set("language", "en")
            self.settings.set("alpha", 0.5)
            self.settings.set("theme", "dark")
            self.settings.set("hotkeys", {"new_note": "<ctrl>+<alt>+q"})
        pump(0.1)
        self.assertFalse(win.win.winfo_exists())
        strings.set_language("th")

    def test_wm_delete_window_runs_cleanup(self) -> None:
        win = self.open()
        root.tk.call(win.win.protocol("WM_DELETE_WINDOW"))
        self.assertEqual(self.closed, [1])
        self.assertFalse(win.win.winfo_exists())

    def test_external_destroy_still_notifies_once(self) -> None:
        win = self.open()
        win.win.destroy()
        pump(0.05)
        self.assertEqual(self.closed, [1])
        win._close()
        self.assertEqual(self.closed, [1])

    def test_close_does_not_unbind_app_wide_bindings(self) -> None:
        root.bind_all("<<QnTest>>", lambda e: None)
        try:
            win = self.open()
            win._close()
            self.assertTrue(root.bind_all("<<QnTest>>"))  # M13: ห้ามล้าง binding ทั้งแอป
        finally:
            root.unbind_all("<<QnTest>>")

    def test_transient_when_root_viewable_and_lift_when_root_hidden(self) -> None:
        win = self.open()
        self.assertEqual(str(win.win.wm_transient()), str(root))
        self.assertNotEqual(win.win.attributes("-topmost"), 1)
        root.withdraw()
        try:
            win.lift()
            pump(0.05)
            self.assertEqual(win.win.state(), "normal")
        finally:
            root.deiconify()
            root.attributes("-alpha", 0.0)
            pump(0.05)

    def test_window_fits_work_area(self) -> None:
        win = self.open()
        left, top, right, bottom = sw.win11.get_work_area(root)
        self.assertLessEqual(win.win.winfo_height(), bottom - top)
        self.assertLessEqual(win.win.winfo_width(), right - left)


# ============================================================ actions
class ActionsTest(SettingsTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.restored = mock.Mock()
        self.act = sw.make_default_actions(root, self.restored)

    def note_titles(self) -> set[str]:
        return {n["title"] for n in db.get_notes_by_status("active")}

    def test_backup_creates_valid_sqlite_with_notes(self) -> None:
        db.create_note("alpha")
        db.create_note("beta")
        target = self.tmp / "out" / "b.db"
        win = self.open()
        target.parent.mkdir()
        with mock.patch.object(sw.filedialog, "asksaveasfilename", return_value=str(target)) as dlg, \
                mock.patch.object(sw.messagebox, "showinfo") as info:
            self.act.backup()
        self.assertTrue(target.is_file())
        conn = sqlite3.connect(target)
        try:
            self.assertEqual({r[0] for r in conn.execute("SELECT title FROM notes")}, {"alpha", "beta"})
        finally:
            conn.close()
        self.assertEqual(dlg.call_args.kwargs["parent"], win.win)  # dialog ต้องมีแม่เป็นหน้า Settings
        self.assertRegex(dlg.call_args.kwargs["initialfile"], r"^notes_backup_\d{8}\.db$")
        info.assert_called_once()
        self.assertEqual(info.call_args.kwargs["parent"], win.win)

    def test_backup_cancelled_does_nothing(self) -> None:
        with mock.patch.object(sw.filedialog, "asksaveasfilename", return_value=""), \
                mock.patch.object(sw.messagebox, "showinfo") as info, mock.patch.object(sw.messagebox, "showerror") as err:
            self.act.backup()
        info.assert_not_called()
        err.assert_not_called()

    def test_backup_failure_shows_error(self) -> None:
        with mock.patch.object(sw.filedialog, "asksaveasfilename", return_value=str(self.tmp / "x.db")), \
                mock.patch.object(sw.database, "backup_database", return_value=False), \
                mock.patch.object(sw.messagebox, "showerror") as err:
            self.act.backup()
        err.assert_called_once()
        self.assertEqual(err.call_args.args[1], strings.t("msg.backup_fail"))

    def make_backup(self) -> str:
        db.create_note("kept")
        path = str(self.tmp / "snap.db")
        self.assertTrue(db.backup_database(path))
        return path

    def test_restore_success_replaces_data_and_calls_on_restored(self) -> None:
        snap = self.make_backup()
        db.create_note("added later")
        self.assertEqual(self.note_titles(), {"kept", "added later"})
        with mock.patch.object(sw.filedialog, "askopenfilename", return_value=snap), \
                mock.patch.object(sw.messagebox, "askyesno", return_value=True) as ask, \
                mock.patch.object(sw.messagebox, "showinfo") as info:
            self.act.restore()
        self.assertEqual(self.note_titles(), {"kept"})
        self.restored.assert_called_once_with()
        ask.assert_called_once()
        info.assert_called_once()

    def test_restore_declined_changes_nothing(self) -> None:
        snap = self.make_backup()
        db.create_note("added later")
        with mock.patch.object(sw.filedialog, "askopenfilename", return_value=snap), \
                mock.patch.object(sw.messagebox, "askyesno", return_value=False):
            self.act.restore()
        self.assertEqual(self.note_titles(), {"kept", "added later"})
        self.restored.assert_not_called()

    def test_restore_cancelled_picker(self) -> None:
        with mock.patch.object(sw.filedialog, "askopenfilename", return_value=""), \
                mock.patch.object(sw.messagebox, "askyesno") as ask:
            self.act.restore()
        ask.assert_not_called()
        self.restored.assert_not_called()

    def test_restore_invalid_file_reports_error_and_skips_callback(self) -> None:
        db.create_note("mine")
        bad = self.tmp / "not_a_db.db"
        bad.write_text("this is not sqlite", encoding="utf-8")
        with mock.patch.object(sw.filedialog, "askopenfilename", return_value=str(bad)), \
                mock.patch.object(sw.messagebox, "askyesno", return_value=True), \
                mock.patch.object(sw.messagebox, "showerror") as err, mock.patch.object(sw.messagebox, "showinfo") as info:
            self.act.restore()
        self.restored.assert_not_called()
        info.assert_not_called()
        err.assert_called_once()
        self.assertEqual(err.call_args.args[1], strings.t("msg.restore_fail"))
        self.assertEqual(self.note_titles(), {"mine"})

    def test_restore_callback_failure_does_not_break_flow(self) -> None:
        snap = self.make_backup()
        self.restored.side_effect = RuntimeError("boom")
        with mock.patch.object(sw.filedialog, "askopenfilename", return_value=snap), \
                mock.patch.object(sw.messagebox, "askyesno", return_value=True), \
                mock.patch.object(sw.messagebox, "showinfo") as info, self.assertLogs("src.ui.settings_window", "ERROR"):
            self.act.restore()
        info.assert_called_once()

    def test_export_writes_markdown_in_current_language(self) -> None:
        db.create_note("ซื้อนม")
        target = self.tmp / "notes.md"
        with mock.patch.object(sw.filedialog, "asksaveasfilename", return_value=str(target)) as dlg, \
                mock.patch.object(sw.messagebox, "showinfo"):
            self.act.export_markdown()
        text = target.read_text(encoding="utf-8")
        self.assertIn("## ซื้อนม", text)
        self.assertRegex(dlg.call_args.kwargs["initialfile"], r"^notes_export_\d{8}\.md$")
        strings.set_language("en")
        target2 = self.tmp / "en.md"
        with mock.patch.object(sw.filedialog, "asksaveasfilename", return_value=str(target2)), \
                mock.patch.object(sw.messagebox, "showinfo"):
            self.act.export_markdown()
        self.assertIn("Exported", target2.read_text(encoding="utf-8"))

    def test_open_data_folder_targets_live_db_folder(self) -> None:
        with mock.patch.object(sw.os, "startfile") as start:
            self.act.open_data_folder()
        start.assert_called_once_with(str(self.tmp))

    def test_open_data_folder_failure_shows_error(self) -> None:
        with mock.patch.object(sw.os, "startfile", side_effect=OSError("nope")), \
                mock.patch.object(sw.messagebox, "showerror") as err, self.assertLogs("src.ui.settings_window", "ERROR"):
            self.act.open_data_folder()
        err.assert_called_once()

    def test_ui_buttons_call_injected_actions(self) -> None:
        win = self.open()
        for key, fn in (("backup", self.actions.backup), ("restore", self.actions.restore),
                        ("export", self.actions.export_markdown), ("open_folder", self.actions.open_data_folder)):
            win.controls[key].invoke()
            fn.assert_called_once_with()


# ============================================================ tray
class TrayTest(unittest.TestCase):
    def setUp(self) -> None:
        strings.set_language("th")
        self.cb = {n: mock.Mock() for n in ("toggle", "new", "settings", "quit")}
        self.tip = "QuickNote · แจ้งเตือนถัดไป 14:30"
        self.tray = tray_mod.TrayIcon(self.cb["toggle"], self.cb["new"], self.cb["settings"], self.cb["quit"],
                                      lambda: self.tip)
        tray_mod._ACTIVE = None
        self.addCleanup(setattr, tray_mod, "_ACTIVE", None)
        self.addCleanup(strings.set_language, "th")

    def items(self) -> list:
        return [i for i in self.tray.icon.menu.items if i is not pystray.Menu.SEPARATOR]

    def test_menu_in_both_languages(self) -> None:
        self.assertEqual([i.text for i in self.items()], ["แสดง QuickNote", "โน้ตใหม่", "ตั้งค่า", "ออก"])
        strings.set_language("en")
        self.tray.update_menu_language()  # ยังไม่ได้ run → ต้องไม่ raise
        self.assertEqual([i.text for i in self.items()], ["Show QuickNote", "New note", "Settings", "Quit"])
        seps = [i for i in self.tray.icon.menu.items if i is pystray.Menu.SEPARATOR]
        self.assertEqual(len(seps), 2)  # แสดง · โน้ตใหม่ ── ตั้งค่า ── ออก

    def test_menu_order_has_separators_in_place(self) -> None:
        kinds = ["sep" if i is pystray.Menu.SEPARATOR else "item" for i in self.tray.icon.menu.items]
        self.assertEqual(kinds, ["item", "item", "sep", "item", "sep", "item"])

    def test_only_toggle_is_default_item(self) -> None:
        items = self.items()
        self.assertTrue(items[0].default)       # คลิกซ้ายที่ไอคอน = toggle (M15)
        self.assertFalse(any(i.default for i in items[1:]))

    def test_callbacks_routed(self) -> None:
        for item, key in zip(self.items(), ("toggle", "new", "settings", "quit")):
            item(self.tray.icon)
            self.cb[key].assert_called_once_with()
        for key in ("toggle", "new", "settings", "quit"):
            self.assertEqual(self.cb[key].call_count, 1)

    def test_failing_callback_does_not_propagate(self) -> None:
        self.cb["toggle"].side_effect = RuntimeError("boom")
        with self.assertLogs("src.platform.tray", "ERROR"):
            self.items()[0](self.tray.icon)  # ถ้า raise จะฆ่า thread ของ pystray

    def test_tooltip_applied_and_truncated(self) -> None:
        self.assertEqual(self.tray.icon.title, self.tip)
        self.tip = "x" * 300
        self.tray.update_tooltip()
        self.assertEqual(len(self.tray.icon.title), 127)
        self.tip = "สั้น"
        self.tray.update_tooltip()
        self.assertEqual(self.tray.icon.title, "สั้น")

    def test_tooltip_callback_failure_falls_back(self) -> None:
        def boom() -> str:
            raise RuntimeError("db locked")
        tray = tray_mod.TrayIcon(mock.Mock(), mock.Mock(), mock.Mock(), mock.Mock(), boom)
        self.assertEqual(tray.icon.title, "QuickNote")
        empty = tray_mod.TrayIcon(mock.Mock(), mock.Mock(), mock.Mock(), mock.Mock(), lambda: "")
        self.assertEqual(empty.icon.title, "QuickNote")

    def test_run_is_idempotent_per_instance(self) -> None:
        with mock.patch.object(self.tray.icon, "run") as run:
            self.tray.run()
            self.tray.run()
        run.assert_called_once()

    def test_start_tray_thread_returns_single_icon(self) -> None:
        with mock.patch.object(pystray.Icon, "run") as run:
            first = tray_mod.start_tray_thread(*[self.cb[k] for k in ("toggle", "new", "settings", "quit")], lambda: "t")
            second = tray_mod.start_tray_thread(*[self.cb[k] for k in ("toggle", "new", "settings", "quit")], lambda: "t")
            for _ in range(100):
                if run.called:
                    break
                time.sleep(0.01)
        self.assertIs(first, second)
        run.assert_called_once()
        first.stop()
        with mock.patch.object(pystray.Icon, "run"):
            third = tray_mod.start_tray_thread(mock.Mock(), mock.Mock(), mock.Mock(), mock.Mock(), lambda: "t")
        self.assertIsNot(third, first)  # หลัง stop แล้วสร้างใหม่ได้

    def test_stop_is_safe_when_never_started(self) -> None:
        self.tray.stop()
        self.tray.stop()

    def test_icon_image_from_asset_and_fallback(self) -> None:
        img = tray_mod.load_icon_image()
        self.assertEqual(img.mode, "RGBA")
        self.assertIn(img.size[0], (16, 20, 24, 32, 48, 256))
        with mock.patch.object(tray_mod, "_asset", return_value=Path("Z:/no/such/icon.ico")):
            fallback = tray_mod.load_icon_image()
        self.assertEqual(fallback.size, (64, 64))

    def test_tray_module_never_touches_tk(self) -> None:
        source = Path(tray_mod.__file__).read_text(encoding="utf-8")
        self.assertNotIn("import tkinter", source)
        self.assertNotIn("from tkinter", source)


if __name__ == "__main__":
    unittest.main()
