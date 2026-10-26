"""Base สำหรับ test ของหน้าต่างหลัก — Tk จริง + Board จริง + DB/settings ชั่วคราว (ไม่ mock Tk)

root ถูก map ไว้แต่ alpha=0 (มองไม่เห็น): การทดสอบขนาด/<Configure> ต้องการหน้าต่างที่ map แล้ว
ใช้ Tk root ตัวเดียวต่อโมดูลเทส (setUpModule) — สร้าง/ทำลาย Tk หลายสิบตัวติดกันทำให้ Tk 9 + sv-ttk
crash แบบสุ่มตอนโหลดธีม (เจอจริง) ส่วน Board/Settings ใหม่ทุกเทสเพื่อแยกสถานะ
toast เป็น fake ที่เก็บการเรียกไว้ เพราะ ToastManager จริงเป็นของ module อื่น
"""

import gc
import time
import tkinter as tk

from src.core import settings as settings_mod
from src.ui import strings
from src.ui.board import Board
from src.ui.theme import Theme
from tests.v3.core_base import CoreTestCase


class FakeToasts:
    """ToastManager จำลอง — เก็บ callback ไว้ให้เทสกดแทนผู้ใช้"""

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.reminders: list[dict] = []
        self.missed_view = None

    def show_reminder(self, note, on_done, on_snooze, on_open, on_dismiss) -> None:
        self.calls.append(("show_reminder", note["id"]))
        self.reminders.append({"note": note, "on_done": on_done, "on_snooze": on_snooze,
                               "on_open": on_open, "on_dismiss": on_dismiss})

    def show_missed(self, notes, on_view) -> None:
        self.calls.append(("show_missed", [n["id"] for n in notes]))
        self.missed_view = on_view

    def show_info(self, message, seconds=6) -> None:
        self.calls.append(("show_info", message))

    def close_for(self, note_id) -> None:
        self.calls.append(("close_for", note_id))

    def close_all(self) -> None:
        self.calls.append(("close_all",))

    def closed(self) -> list[str]:
        return [c[1] for c in self.calls if c[0] == "close_for"]


class _Shared:
    root: tk.Tk
    settings: settings_mod.Settings
    theme: Theme
    listener_baseline: int


def start_shared_root() -> None:
    """เรียกจาก setUpModule"""
    _Shared.root = tk.Tk()
    _Shared.settings = settings_mod.Settings()
    _Shared.theme = Theme(_Shared.root, _Shared.settings)
    _Shared.listener_baseline = len(_Shared.settings._listeners)  # listener ของ Theme — ห้ามตัดทิ้ง
    _Shared.root.update()


def stop_shared_root() -> None:
    """เรียกจาก tearDownModule"""
    try:
        _Shared.root.destroy()
    except tk.TclError:
        pass
    gc.collect()


_VIRTUAL = ("<<QN-NewNote>>", "<<QN-Search>>", "<<QN-Topmost>>", "<<QN-TabActive>>", "<<QN-TabCompleted>>")


class BoardTestCase(CoreTestCase):
    def setUp(self) -> None:
        super().setUp()  # DB_PATH / SETTINGS_FILE ชั่วคราวต่อเทส
        strings.set_language("th")
        self.errors: list[BaseException] = []
        self.root = _Shared.root
        self.root.report_callback_exception = lambda exc, val, tb: self.errors.append(val)
        self.settings = _Shared.settings
        self.settings.load()  # ไฟล์ใหม่ไม่มี → DEFAULTS
        self.theme = _Shared.theme
        self.theme.set_font_size("normal")
        self.settings.set("theme", "light", save=False)
        self.theme.refresh()
        self.root.deiconify()
        self.toasts = FakeToasts()
        self.board = Board(self.root, self.settings, self.theme, self.toasts)
        self.root.attributes("-alpha", 0.0)
        self.board.scheduler.stop()  # เทสสั่ง check_now เองเพื่อควบคุมจังหวะ
        self.pump()

    def tearDown(self) -> None:
        root = self.root
        try:
            self.board.flush_all_cards()
            self.board.scheduler.stop()
            self.board._unsub_theme()
            del self.settings._listeners[_Shared.listener_baseline:]
            for seq in ("<Unmap>", "<Destroy>", "<MouseWheel>", "<Escape>", "<Up>", "<Down>", *_VIRTUAL):
                root.tk.call("bind", root._w, seq, "")  # unbind ของ tkinter ล้มเมื่อ command ถูกลบไปก่อนแล้ว
            # ทำลาย widget ก่อน (ให้มันลบ command ของ after ตัวเอง) แล้วค่อยยกเลิก after ที่เหลือระดับ Tcl
            # (after_cancel ผ่าน root จะลบ command ที่ widget อื่นเป็นเจ้าของ แล้ว destroy ของ widget นั้นพัง)
            for child in root.winfo_children():
                child.destroy()
            for job in root.tk.splitlist(root.tk.call("after", "info")):
                root.tk.call("after", "cancel", job)
            root.update()
        except tk.TclError:
            import traceback
            traceback.print_exc()
        strings.set_language("th")
        super().tearDown()
        self.assertEqual(self.errors, [], "exception ใน Tk callback")

    def pump(self, seconds: float = 0.0) -> None:
        end = time.monotonic() + seconds
        self.root.update()
        while time.monotonic() < end:
            self.root.update()
            time.sleep(0.005)
        self.root.update()

    # --- helpers
    def card(self, note_id: str):
        return self.board.note_cards[note_id]

    def pack_order(self) -> list[str]:
        """id ของการ์ดตามลำดับ pack จริงบนจอ"""
        by_widget = {c: nid for nid, c in self.board.note_cards.items()}
        return [by_widget[w] for w in self.board._inner.pack_slaves() if w in by_widget]
