"""Tests ของ src/platform/hotkey.py — parser ล้วน + RegisterHotKey จริง (ไม่ฉีดคีย์เข้าระบบ)

ใช้คีย์ Ctrl+Alt+Shift+F23/F22 ที่แทบไม่มีโปรแกรมไหนจอง และจำลอง WM_HOTKEY ด้วย PostThreadMessage
แทนการกดคีย์จริง เพื่อไม่รบกวนแอปที่ผู้ใช้กำลังใช้อยู่ (การกดคีย์จริงพิสูจน์ใน tools/smoke_v3.py)
"""

import ctypes
import threading
import unittest

from src.platform import hotkey

COMBO_A = "<ctrl>+<alt>+<shift>+<f23>"
COMBO_B = "<ctrl>+<alt>+<shift>+<f22>"


class ParseTest(unittest.TestCase):
    def test_default_hotkeys(self) -> None:
        self.assertEqual(hotkey.parse_hotkey("<ctrl>+<alt>+n"), (0x2 | 0x1, ord("N")))
        self.assertEqual(hotkey.parse_hotkey("<ctrl>+<alt>+s"), (0x2 | 0x1, ord("S")))

    def test_tokens_written_by_settings_window(self) -> None:
        self.assertEqual(hotkey.parse_hotkey("<ctrl>+<alt>+<shift>+<f12>"), (0x2 | 0x1 | 0x4, 0x7B))
        self.assertEqual(hotkey.parse_hotkey("<cmd>+5"), (0x8, ord("5")))
        self.assertEqual(hotkey.parse_hotkey("<ctrl>+<page_up>"), (0x2, 0x21))
        self.assertEqual(hotkey.parse_hotkey("<alt>+<space>"), (0x1, 0x20))
        self.assertEqual(hotkey.parse_hotkey("<ctrl>+;"), (0x2, 0xBA))

    def test_invalid_combos_raise(self) -> None:
        for bad in ("", "n", "<ctrl>", "<shift>+n", "<ctrl>+<alt>", "<ctrl>+nn", "<ctrl>+<nope>", "<ctrl>+a+b",
                    "<ctrl>+<f25>"):
            with self.subTest(bad), self.assertRaises(ValueError):
                hotkey.parse_hotkey(bad)

    def test_key_is_layout_independent(self) -> None:
        """รหัสต้องมาจาก vk ไม่ใช่ตัวอักษร — เป็นเหตุผลที่เลิกใช้ pynput (แป้นไทยทำให้ Ctrl+Alt+N ไม่ทำงาน)"""
        self.assertEqual(hotkey.parse_hotkey("<ctrl>+<alt>+n")[1], 0x4E)


class ListenerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.started: list[hotkey.HotkeyListener] = []
        self.addCleanup(lambda: [l.stop() for l in self.started])

    def start(self, config: dict, on_hotkey=lambda name: None):
        listener = hotkey.start_hotkey_listener(config, on_hotkey)
        if listener is not None:
            self.started.append(listener)
        return listener

    def test_register_dispatch_and_stop(self) -> None:
        got: list[tuple[str, str]] = []
        fired = threading.Event()

        def on_hotkey(name: str) -> None:
            got.append((name, threading.current_thread().name))
            fired.set()

        listener = self.start({"new_note": COMBO_A, "toggle_show": COMBO_B}, on_hotkey)
        self.assertIsNotNone(listener)
        # WM_HOTKEY id 2 = รายการที่สอง (toggle_show) — ส่งตรงเข้า message queue ของ thread listener
        ctypes.WinDLL("user32").PostThreadMessageW(listener._thread_id, 0x0312, 2, 0)
        self.assertTrue(fired.wait(2))
        self.assertEqual(got, [("toggle_show", "qn-hotkeys")])   # callback รันบน thread ของ listener ไม่ใช่ main

        listener.stop()
        listener.stop()                                           # เรียกซ้ำได้
        again = self.start({"new_note": COMBO_A})                  # ปล่อยคีย์แล้ว → ลงทะเบียนใหม่ได้
        self.assertIsNotNone(again)

    def test_conflict_with_other_registration_returns_none(self) -> None:
        first = self.start({"new_note": COMBO_A})
        self.assertIsNotNone(first)
        with self.assertLogs("quicknote.hotkey", "WARNING"):
            self.assertIsNone(self.start({"new_note": COMBO_A}))   # ถูกจองแล้ว → บอกผู้เรียกได้ (msg.hotkey_failed)

    def test_partial_registration_is_rolled_back(self) -> None:
        first = self.start({"new_note": COMBO_B})
        self.assertIsNotNone(first)
        with self.assertLogs("quicknote.hotkey", "WARNING"):
            self.assertIsNone(self.start({"a": COMBO_A, "b": COMBO_B}))   # a สำเร็จ b ล้มเหลว
        self.assertIsNotNone(self.start({"a": COMBO_A}))                   # a ต้องไม่ค้างจองอยู่

    def test_invalid_combo_returns_none(self) -> None:
        with self.assertLogs("quicknote.hotkey", "WARNING"):
            self.assertIsNone(self.start({"new_note": "n"}))

    def test_callback_exception_does_not_kill_listener(self) -> None:
        calls: list[str] = []
        done = threading.Event()

        def on_hotkey(name: str) -> None:
            calls.append(name)
            if len(calls) == 1:
                raise RuntimeError("boom")
            done.set()

        listener = self.start({"new_note": COMBO_A}, on_hotkey)
        user32 = ctypes.WinDLL("user32")
        with self.assertLogs("quicknote.hotkey", "ERROR"):
            user32.PostThreadMessageW(listener._thread_id, 0x0312, 1, 0)
            user32.PostThreadMessageW(listener._thread_id, 0x0312, 1, 0)
            self.assertTrue(done.wait(2))


if __name__ == "__main__":
    unittest.main()
