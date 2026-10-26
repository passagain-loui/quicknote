"""Integration ของ main.py — Tk + Board + DB + settings จริง บน temp (ปลอมเฉพาะ pynput/pystray)

ครอบคลุม: C3 (quit ทางเดียว + บันทึก settings/geometry) · C8 (flush ก่อนออก) · ปิดหน้าต่างแล้วไม่หาย (close vs tray) ·
restart hotkey · single instance (L9) · อัปเกรดจาก v2 (สำรอง DB) · QUICKNOTE_HOME · --selftest
"""

import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

import main as app_main
from src.core import database as db
from src.core import settings as settings_mod
from src.core.reminders import format_dt
from src.ui.strings import t
from tests.v3.board_base import BoardTestCase, start_shared_root, stop_shared_root
from tests.v3.core_base import ROOT, CoreTestCase


def setUpModule() -> None:
    start_shared_root()


def tearDownModule() -> None:
    stop_shared_root()


class FakeTray:
    """แทน TrayIcon จริง (pystray) — นับการเรียกที่ main.py ต้องทำ"""

    def __init__(self, running: bool = True) -> None:
        self.is_running = running
        self.stopped = 0
        self.tooltip_updates = 0
        self.menu_updates = 0

    def stop(self) -> None:
        self.stopped += 1

    def update_tooltip(self) -> None:
        self.tooltip_updates += 1

    def update_menu_language(self) -> None:
        self.menu_updates += 1


class FakeListener:
    """แทน pynput listener — เก็บ config ที่ถูกลงทะเบียนและจำนวนครั้งที่ถูก stop"""

    def __init__(self, config: dict, on_hotkey) -> None:
        self.config = config
        self.on_hotkey = on_hotkey
        self.stopped = 0

    def stop(self) -> None:
        self.stopped += 1


class HotkeyFactory:
    def __init__(self) -> None:
        self.created: list[FakeListener] = []
        self.reject: set[str] = set()   # combo ของ new_note ที่จะทำให้ลงทะเบียนล้มเหลว

    def __call__(self, config: dict, on_hotkey):
        if config.get("new_note") in self.reject:
            return None
        listener = FakeListener(dict(config), on_hotkey)
        self.created.append(listener)
        return listener


class AppTestCase(BoardTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.hotkeys = HotkeyFactory()
        self.app = app_main.App(self.root, self.settings, self.theme, self.toasts, self.board,
                                hotkey_factory=self.hotkeys)

    def loop(self, action=None, timeout_ms: int = 800) -> bool:
        """รัน mainloop จริง (thread อื่นเรียก root.after ได้เฉพาะตอนนี้) — คืน True ถ้า root.quit() ถูกเรียกก่อน timeout

        Tk เคลียร์ flag ของ quit ทุกครั้งที่เข้า mainloop จึงต้องรัน action "ข้างใน" loop ไม่ใช่ก่อนเข้า
        """
        timed_out: list[bool] = []
        if action is not None:
            self.root.after(0, action)
        job = self.root.after(timeout_ms, lambda: (timed_out.append(True), self.root.quit()))
        self.root.mainloop()
        try:
            self.root.after_cancel(job)
        except tk.TclError:
            pass
        return not timed_out

    def saved(self) -> dict:
        with open(settings_mod._settings_file(), encoding="utf-8") as f:
            return json.load(f)


class QuitPathTest(AppTestCase):
    def test_quit_saves_settings_geometry_and_flushes_pending_title(self) -> None:
        nid = db.create_note("old", collapsed=False)
        self.board._load_notes()
        self.card(nid)._title_var.set("typed just before quit")  # debounce 500ms ยังไม่ทันยิง
        self.settings.set("alpha", 0.7, save=False)               # C3: ค่าที่ยังไม่เคยถูกเขียนลงดิสก์
        self.pump()
        geometry = self.board.get_persistable_geometry()

        self.assertTrue(self.loop(self.app.quit_app))

        self.assertEqual(db.get_note(nid)["title"], "typed just before quit")
        self.assertEqual(self.saved()["alpha"], 0.7)
        self.assertEqual(self.saved()["geometry"], geometry)
        self.assertIn(("close_all",), self.toasts.calls)

    def test_quit_is_idempotent(self) -> None:
        with mock.patch.object(self.settings, "save", wraps=self.settings.save) as save:
            self.assertTrue(self.loop(lambda: (self.app.quit_app(), self.app.quit_app())))
        self.assertEqual(save.call_count, 1)

    def test_quit_purges_pending_delete(self) -> None:
        nid = db.create_note("to delete")
        self.board._load_notes()
        self.board._on_delete(nid)             # soft-delete + แถบ Undo กำลังนับถอยหลัง
        self.assertIsNotNone(db.get_note(nid))
        self.assertTrue(self.loop(self.app.quit_app))
        self.assertIsNone(db.get_note(nid))    # ปิดแอประหว่างรอ Undo = ลบจริงทุกครั้ง ไม่ขึ้นกับจังหวะ

    def test_one_failing_step_does_not_skip_the_rest(self) -> None:
        with mock.patch.object(self.board, "flush_all_cards", side_effect=RuntimeError("boom")), \
                self.assertLogs("quicknote.main", "ERROR"):
            self.assertTrue(self.loop(self.app.quit_app))   # ขั้นหนึ่งพัง ต้องยังออกได้
        self.assertEqual(self.saved()["geometry"], self.board.get_persistable_geometry())

    def test_shutdown_stops_everything_and_still_persists(self) -> None:
        tray = FakeTray()
        self.app.tray = tray
        self.app.start_hotkeys()
        listener = self.app.hotkeys
        nid = db.create_note("x", collapsed=False)
        self.board._load_notes()
        self.card(nid)._title_var.set("saved by shutdown")
        self.pump()
        # root ใช้ร่วมทั้งโมดูล จึงไม่ destroy จริง — ตรวจส่วนที่เหลือของ shutdown
        with mock.patch.object(self.root, "destroy"):
            self.app.shutdown()
        self.assertEqual(db.get_note(nid)["title"], "saved by shutdown")   # exception หลุด mainloop ก็ยังเซฟ
        self.assertEqual(tray.stopped, 1)
        self.assertEqual(listener.stopped, 1)
        self.assertIsNone(self.app.hotkeys)


class CloseRequestTest(AppTestCase):
    def test_close_without_tray_quits(self) -> None:
        self.app.tray = None
        self.assertTrue(self.loop(self.app.on_close_request))
        self.assertEqual(self.root.state(), "normal")

    def test_close_with_tray_hides_and_shows_hint_once(self) -> None:
        self.app.tray = FakeTray(running=True)
        self.assertFalse(self.settings.get("tray_hint_shown"))
        self.assertFalse(self.loop(self.app.on_close_request, 200))   # ซ่อน ไม่ใช่ออก
        self.assertEqual(self.root.state(), "withdrawn")
        self.assertEqual([c for c in self.toasts.calls if c[0] == "show_info"], [("show_info", t("toast.tray_hint"))])
        self.assertTrue(self.settings.get("tray_hint_shown"))
        self.assertTrue(self.saved()["tray_hint_shown"])

        self.board.show()
        self.assertFalse(self.loop(self.app.on_close_request, 200))
        self.assertEqual(self.root.state(), "withdrawn")
        self.assertEqual(len([c for c in self.toasts.calls if c[0] == "show_info"]), 1)   # ครั้งที่สองไม่โชว์ซ้ำ
        self.board.show()

    def test_close_with_tray_dead_quits_even_when_close_to_tray_is_on(self) -> None:
        self.app.tray = FakeTray(running=False)   # pystray เริ่มไม่ขึ้น → ห้ามซ่อนจนหน้าต่างหาย
        self.assertTrue(self.loop(self.app.on_close_request))

    def test_close_to_tray_off_quits_even_if_tray_runs(self) -> None:
        self.settings.set("close_to_tray", False)
        self.app.tray = FakeTray(running=True)
        self.assertTrue(self.loop(self.app.on_close_request))

    def test_wm_delete_window_is_routed_to_app(self) -> None:
        self.app.tray = None
        self.assertTrue(self.loop(lambda: self.root.tk.call(self.root.protocol("WM_DELETE_WINDOW"))))   # เหมือนผู้ใช้กด ✕
        self.assertIs(self.board.on_quit.__self__, self.app)

    def test_escape_without_tray_minimizes_instead_of_stranding_window(self) -> None:
        self.app.tray = None
        self.board._on_escape()
        self.assertEqual(self.root.state(), "iconic")   # ยังเรียกกลับจาก taskbar ได้
        self.root.deiconify()

    def test_escape_with_tray_hides(self) -> None:
        self.app.tray = FakeTray(running=True)
        self.board._on_escape()
        self.assertEqual(self.root.state(), "withdrawn")
        self.board.show()


class CanHideHookTest(BoardTestCase):
    def test_default_hides(self) -> None:
        self.board.hide()
        self.assertEqual(self.root.state(), "withdrawn")
        self.board.show()

    def test_can_hide_false_iconifies_and_flushes(self) -> None:
        nid = db.create_note("t", collapsed=False)
        self.board._load_notes()
        self.card(nid)._title_var.set("kept")
        self.board.can_hide = lambda: False
        self.board.hide()
        self.assertEqual(self.root.state(), "iconic")
        self.assertEqual(db.get_note(nid)["title"], "kept")
        self.root.deiconify()


class HotkeyRestartTest(AppTestCase):
    def test_start_registers_current_settings(self) -> None:
        self.assertTrue(self.app.start_hotkeys())
        self.assertEqual(self.hotkeys.created[-1].config, self.settings.get("hotkeys"))

    def test_changing_hotkeys_restarts_listener_with_new_dict(self) -> None:
        self.app.start_hotkeys()
        first = self.app.hotkeys
        new = {"new_note": "<ctrl>+<alt>+j", "toggle_show": "<ctrl>+<alt>+s"}
        self.settings.set("hotkeys", new)
        self.assertEqual(first.stopped, 1)
        self.assertIsNot(self.app.hotkeys, first)
        self.assertEqual(self.app.hotkeys.config, new)

    def test_registration_failure_warns_and_restores_previous(self) -> None:
        self.app.start_hotkeys()
        old = dict(self.settings.get("hotkeys"))
        self.hotkeys.reject.add("<ctrl>+<alt>+q")
        with mock.patch.object(app_main.messagebox, "showwarning") as warn:
            self.settings.set("hotkeys", {"new_note": "<ctrl>+<alt>+q", "toggle_show": "<ctrl>+<alt>+s"})
        warn.assert_called_once()
        self.assertEqual(warn.call_args.args[1], t("msg.hotkey_failed"))
        self.assertEqual(self.settings.get("hotkeys"), old)    # คืนค่าที่ใช้ได้
        self.assertEqual(self.app.hotkeys.config, old)         # และคีย์ลัดเดิมยังทำงาน

    def test_hotkey_actions_run_on_main_thread_via_after(self) -> None:
        self.app.start_hotkeys()
        listener = self.app.hotkeys
        self.board.hide()
        # เหมือน pynput: เรียกจาก thread อื่นขณะ mainloop ทำงาน
        self.loop(lambda: threading.Thread(target=listener.on_hotkey, args=("new_note",)).start(), 400)
        self.assertTrue(self.board._is_visible())
        self.assertIs(self.root.focus_get(), self.board._qa)


class SettingsListenersTest(AppTestCase):
    def test_language_change_updates_tray_menu(self) -> None:
        tray = FakeTray()
        self.app.tray = tray
        self.settings.set("language", "en")
        self.assertEqual(tray.menu_updates, 1)
        self.assertGreaterEqual(tray.tooltip_updates, 1)

    def test_tooltip_shows_next_reminder_and_tick_updates_only_on_change(self) -> None:
        tray = FakeTray()
        self.app.tray = tray
        self.assertEqual(self.app.tray_tooltip(), t("tray.tooltip"))
        nid = db.create_note("meeting")
        db.set_reminder(nid, format_dt(datetime.now() + timedelta(hours=2)))
        self.assertNotEqual(self.app.tray_tooltip(), t("tray.tooltip"))
        self.app._on_tick()
        self.app._on_tick()
        self.assertEqual(tray.tooltip_updates, 1)

    def test_scheduler_tick_hook_is_registered(self) -> None:
        tray = FakeTray()
        self.app.tray = tray
        db.set_reminder(db.create_note("soon"), format_dt(datetime.now() + timedelta(hours=1)))
        self.board.scheduler.check_now()
        self.board.scheduler.stop()
        self.assertEqual(tray.tooltip_updates, 1)


class TrayWiringTest(AppTestCase):
    def start_with_fake(self) -> dict:
        captured: dict = {}

        def fake_start(**kw):
            captured.update(kw)
            return FakeTray()

        self.app.setup_tray(start=fake_start)
        return captured

    def test_tray_callbacks_marshal_to_main_thread(self) -> None:
        cb = self.start_with_fake()
        self.board.hide()
        self.loop(lambda: threading.Thread(target=cb["on_new_note"]).start(), 400)   # เหมือน thread ของ pystray
        self.assertTrue(self.board._is_visible())

    def test_tray_settings_uses_boards_single_open_settings(self) -> None:
        cb = self.start_with_fake()
        with mock.patch.object(self.board, "open_settings") as opener:
            cb["on_settings"]()
            self.pump()
        opener.assert_called_once_with()   # H1: ไม่มี singleton ชุดที่สอง

    def test_tray_quit_goes_through_quit_app(self) -> None:
        cb = self.start_with_fake()
        self.assertTrue(self.loop(lambda: threading.Thread(target=cb["on_quit"]).start()))
        self.assertTrue(self.app._quitting)

    def test_tray_start_failure_leaves_app_usable(self) -> None:
        def broken(**_kw):
            raise OSError("no shell tray")
        with self.assertLogs("quicknote.main", "ERROR"):
            self.app.setup_tray(start=broken)
        self.assertIsNone(self.app.tray)
        self.assertFalse(self.app.tray_running())
        self.assertFalse(self.board.can_hide())

    def test_second_launch_signal_shows_window(self) -> None:
        single = app_main.SingleInstance("Local\\QuickNote.Test.Signal", 0)
        self.addCleanup(single.release)
        self.assertTrue(single.start_listener(lambda: self.app.ui(self.app.show_main)))
        self.board.hide()
        self.loop(lambda: threading.Thread(
            target=lambda: app_main.SingleInstance("unused", single.port).signal_existing()).start(), 600)
        self.assertTrue(self.board._is_visible())


class SingleInstanceTest(unittest.TestCase):
    NAME = "Local\\QuickNote.Test.Mutex.%d" % os.getpid()

    def test_mutex_detects_second_instance(self) -> None:
        first = app_main.SingleInstance(self.NAME, 0)
        second = app_main.SingleInstance(self.NAME, 0)
        self.addCleanup(first.release)
        self.addCleanup(second.release)
        self.assertTrue(first.acquire())
        self.assertFalse(second.acquire())
        first.release()
        self.assertTrue(second.acquire())   # instance แรกปิดแล้ว → เปิดใหม่ได้

    def test_port_taken_does_not_prevent_running(self) -> None:
        blocker = socket.socket()
        blocker.bind(("127.0.0.1", 0))
        blocker.listen(1)
        self.addCleanup(blocker.close)
        si = app_main.SingleInstance(self.NAME + ".port", blocker.getsockname()[1])
        self.addCleanup(si.release)
        self.assertTrue(si.acquire())                           # mutex ว่าง = เปิดได้
        with self.assertLogs("quicknote.main", "WARNING"):
            self.assertFalse(si.start_listener(lambda: None))   # bind ไม่ได้ → log ไม่ crash ไม่ออกเงียบ ๆ

    def test_signal_with_nobody_listening_returns_false(self) -> None:
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        with self.assertLogs("quicknote.main", "WARNING"):
            self.assertFalse(app_main.SingleInstance("unused", port).signal_existing())


class UpgradeBackupTest(CoreTestCase):
    def make_v2_db(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            Path(str(self.db_path) + suffix).unlink(missing_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""CREATE TABLE notes (id TEXT PRIMARY KEY, title TEXT NOT NULL, content TEXT DEFAULT '',
            status TEXT DEFAULT 'active', collapsed BOOLEAN DEFAULT 0, created_at TIMESTAMP,
            completed_at TIMESTAMP, priority TEXT DEFAULT 'none', reminder_datetime TEXT,
            reminder_triggered BOOLEAN DEFAULT 0, is_pinned BOOLEAN DEFAULT 0, last_dismissed_at TIMESTAMP)""")
        conn.execute("INSERT INTO notes (id, title, content, created_at) "
                     "VALUES ('a', 'งานเก่า', 'รายละเอียด', '2026-01-01T10:00:00')")
        conn.commit()
        conn.close()

    def test_pre_v3_db_is_backed_up_once_and_data_survives_migration(self) -> None:
        self.make_v2_db()
        backup = app_main.backup_pre_v3_db()
        self.assertEqual(Path(backup), self.tmp / "backups" / "notes_pre_v3.db")
        saved = sqlite3.connect(backup)
        try:
            cols = {r[1] for r in saved.execute("PRAGMA table_info(notes)")}
            self.assertNotIn("color", cols)                                  # ต้นฉบับก่อน migrate
            self.assertEqual(saved.execute("SELECT title FROM notes").fetchall(), [("งานเก่า",)])
        finally:
            saved.close()

        db.init_db()                                                         # migrate DB จริง
        self.assertEqual(db.get_note("a")["title"], "งานเก่า")
        self.assertIsNone(app_main.backup_pre_v3_db())                       # ตอนนี้เป็น v3 แล้ว ไม่ทำซ้ำ

    def test_existing_backup_is_never_overwritten(self) -> None:
        self.make_v2_db()
        first = app_main.backup_pre_v3_db()
        before = Path(first).stat().st_mtime_ns
        # ย้อน DB กลับเป็น v2 อีกครั้ง — ยังต้องไม่ทับสำเนาเดิม
        self.make_v2_db()
        self.assertIsNone(app_main.backup_pre_v3_db())
        self.assertEqual(Path(first).stat().st_mtime_ns, before)

    def test_v3_and_missing_db_are_left_alone(self) -> None:
        self.assertIsNone(app_main.backup_pre_v3_db())                       # setUp สร้าง DB v3 ไว้แล้ว
        for suffix in ("", "-wal", "-shm"):
            Path(str(self.db_path) + suffix).unlink(missing_ok=True)
        self.assertIsNone(app_main.backup_pre_v3_db())
        self.assertFalse((self.tmp / "backups").exists())


class QuickNoteHomeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.saved_env = {k: os.environ.pop(k, None) for k in ("DB_PATH", "QUICKNOTE_HOME")}
        self.home = Path(tempfile.mkdtemp(prefix="qn_test_home_"))
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)

    def tearDown(self) -> None:
        for k, v in self.saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_env_redirects_db_and_settings(self) -> None:
        os.environ["QUICKNOTE_HOME"] = str(self.home)
        self.assertEqual(db.get_app_dir(), self.home)
        self.assertEqual(Path(db._get_db_file()), self.home / "notes.db")
        s = settings_mod.Settings()
        s.set("alpha", 0.55)
        self.assertEqual(json.loads((self.home / "settings.json").read_text(encoding="utf-8"))["alpha"], 0.55)
        s2 = settings_mod.Settings()
        s2.load()
        self.assertEqual(s2.get("alpha"), 0.55)

    def test_db_path_still_wins_over_home(self) -> None:
        os.environ["DB_PATH"], os.environ["QUICKNOTE_HOME"] = "X:/db.sqlite", str(self.home)
        self.assertEqual(db._get_db_file(), "X:/db.sqlite")


class FreshProcessGeometryTest(unittest.TestCase):
    """C4: ตำแหน่งที่บันทึกไว้ต้องถูกคืนใน process ใหม่ — เทสที่ใช้ root ร่วมกันจับไม่ได้เพราะ root map ไปแล้ว

    บั๊กจริง: iconbitmap + -topmost ก่อน map ครั้งแรกทำให้ Tk 9 ทิ้ง +x+y แล้ว Windows วางหน้าต่างแบบ cascade
    """

    SCRIPT = """
import ctypes, sys
ctypes.windll.shcore.SetProcessDpiAwareness(2)
sys.path.insert(0, sys.argv[1])
import tkinter as tk
from src.core import database as db
from src.core.settings import Settings
from src.ui.theme import Theme
from src.ui.board import Board
from tests.v3.board_base import FakeToasts
db.init_db()
s = Settings(); s.load()
root = tk.Tk()
b = Board(root, s, Theme(root, s), FakeToasts())
root.update()
print(b.get_persistable_geometry())
b.scheduler.stop(); root.destroy()
"""

    def test_saved_position_is_restored_in_a_new_process(self) -> None:
        home = Path(tempfile.mkdtemp(prefix="qn_test_geo_"))
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        (home / "settings.json").write_text(json.dumps({"geometry": "353x394+210+140"}), encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if k != "DB_PATH"}
        env["QUICKNOTE_HOME"] = str(home)
        for _ in range(2):   # อาการเดิมสุ่มตำแหน่งทุกครั้ง — ตรวจซ้ำเพื่อไม่ให้ผ่านเพราะบังเอิญ
            proc = subprocess.run([sys.executable, "-c", self.SCRIPT, str(ROOT)], cwd=ROOT, env=env,
                                  capture_output=True, timeout=30)
            out = proc.stdout.decode("utf-8", "replace").strip()
            self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
            self.assertEqual(out, "353x394+210+140")


class SelfTestProcessTest(unittest.TestCase):
    def test_selftest_exits_zero_within_30s(self) -> None:
        env = {k: v for k, v in os.environ.items() if k not in ("DB_PATH", "QUICKNOTE_HOME")}
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run([sys.executable, str(ROOT / "main.py"), "--selftest"], cwd=ROOT, env=env,
                              capture_output=True, timeout=30)
        out = proc.stdout.decode("utf-8", "replace") + proc.stderr.decode("utf-8", "replace")
        self.assertEqual(proc.returncode, 0, out)


if __name__ == "__main__":
    unittest.main()
