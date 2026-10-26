"""Tests ของ ReminderScheduler — Tk จริง + DB ชั่วคราว (C2: after-handle เดียว, due/missed, mark_ringing ก่อน callback)"""

import gc
import tkinter as tk
import time
from datetime import datetime, timedelta

from src.core import database as db
from src.core.reminders import FMT
from src.ui.scheduler import ReminderScheduler
from tests.v3.core_base import CoreTestCase


def at(delta_min: float) -> str:
    return (datetime.now() + timedelta(minutes=delta_min)).strftime(FMT)


root: tk.Tk


def setUpModule() -> None:
    global root
    root = tk.Tk()  # ตัวเดียวต่อโมดูล (ดูเหตุผลใน board_base)
    root.withdraw()


def tearDownModule() -> None:
    root.destroy()
    gc.collect()


class SchedulerTest(CoreTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.root = root
        self.due: list[list[dict]] = []
        self.missed: list[list[dict]] = []
        self.ringing_in_callback: list[int] = []

    def tearDown(self) -> None:
        for job in self.root.tk.splitlist(self.root.tk.call("after", "info")):
            self.root.tk.call("after", "cancel", job)
        super().tearDown()

    def make_scheduler(self, interval_ms: int = 5000) -> ReminderScheduler:
        def on_due(rows):
            self.ringing_in_callback.extend(db.get_note(r["id"])["reminder_triggered"] for r in rows)
            self.due.append(rows)

        return ReminderScheduler(self.root, on_due, lambda rows: self.missed.append(rows), interval_ms)

    def pending_scheduler_jobs(self) -> int:
        n = 0
        for job in self.root.tk.splitlist(self.root.tk.call("after", "info")):
            script = str(self.root.tk.call("after", "info", job)[0])
            if "_on_timer" in script:
                n += 1
        return n

    def test_c2_many_check_now_keep_single_chain(self) -> None:
        sch = self.make_scheduler(interval_ms=40)
        ticks: list[int] = []
        sch.on_tick(lambda: ticks.append(1))
        sch.start()
        for _ in range(15):
            sch.check_now()
        self.assertEqual(self.pending_scheduler_jobs(), 1)
        t_end = time.monotonic() + 0.5
        while time.monotonic() < t_end:
            self.root.update()
            time.sleep(0.005)
        self.assertEqual(self.pending_scheduler_jobs(), 1)
        # 16 ครั้งตรง ๆ + ~12 รอบจากเวลา 0.5s/40ms — ไม่ใช่ทวีคูณ
        self.assertLess(len(ticks), 16 + 25)
        sch.stop()
        self.assertEqual(self.pending_scheduler_jobs(), 0)

    def test_check_now_without_start_does_not_schedule(self) -> None:
        sch = self.make_scheduler()
        sch.check_now()
        self.assertEqual(self.pending_scheduler_jobs(), 0)

    def test_due_vs_missed_split(self) -> None:
        late = db.create_note("late")
        db.set_reminder(late, at(-5))
        way_late = db.create_note("way late")
        db.set_reminder(way_late, at(-61 - 120))
        future = db.create_note("future")
        db.set_reminder(future, at(30))
        sch = self.make_scheduler()
        sch.check_now()
        self.assertEqual([[r["id"] for r in rows] for rows in self.due], [[late]])
        self.assertEqual([[r["id"] for r in rows] for rows in self.missed], [[way_late]])
        # due → กำลังดัง ; missed → ทำให้ไม่ดัง (ครั้งเดียว = ล้าง datetime) ; future ไม่ถูกแตะ
        self.assertEqual(db.get_note(late)["reminder_triggered"], 1)
        self.assertIsNone(db.get_note(way_late)["reminder_datetime"])
        self.assertEqual(db.get_note(way_late)["reminder_triggered"], 0)
        self.assertEqual(db.get_note(future)["reminder_triggered"], 0)

    def test_mark_ringing_before_callback_and_not_refired(self) -> None:
        nid = db.create_note("x")
        db.set_reminder(nid, at(-1))
        sch = self.make_scheduler()
        sch.check_now()
        self.assertEqual(self.ringing_in_callback, [1])
        sch.check_now()  # ดังแล้วไม่ดังซ้ำ
        self.assertEqual(len(self.due), 1)

    def test_missed_repeating_advances_instead_of_clearing(self) -> None:
        nid = db.create_note("daily")
        db.set_reminder(nid, at(-60 * 5), "daily")
        sch = self.make_scheduler()
        sch.check_now()
        self.assertEqual(len(self.missed), 1)
        row = db.get_note(nid)
        self.assertGreater(row["reminder_datetime"], datetime.now().strftime(FMT))
        self.assertEqual(row["reminder_triggered"], 0)

    def test_failing_callback_does_not_kill_loop(self) -> None:
        nid = db.create_note("x")
        db.set_reminder(nid, at(-1))

        def boom(_rows):
            raise RuntimeError("boom")

        sch = ReminderScheduler(self.root, boom, lambda r: None, 40)
        sch.start()
        self.assertEqual(self.pending_scheduler_jobs(), 1)  # reschedule แม้ callback พัง
        sch.stop()
