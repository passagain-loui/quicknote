"""ReminderScheduler — ตรวจ reminder ที่ถึงเวลาด้วย after-handle เดียว (แก้ C2 ที่ chain ทวีคูณ)

กติกา:
  - มี job ค้างได้ไม่เกิน 1 ตัวเสมอ: check_now() ยกเลิก job เดิมก่อนแล้วค่อยตั้งใหม่ ทางเดียวที่ตั้ง after
  - ห้ามใช้ thread (Tk UI thread safety) — ทุกอย่างรันบน main loop
  - due = เลยเวลาไม่เกิน MISSED_AFTER_MIN นาที → on_due ; เกินกว่านั้น (เครื่อง sleep/ปิดแอป) → on_missed รวมเป็นรายการเดียว
  - mark_ringing ก่อนเรียก callback เสมอ กันรอบถัดไปดังซ้ำถ้า callback ล้มเหลวกลางทาง
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import datetime
from typing import Callable

from ..core import database as db
from ..core.reminders import FMT, parse_dt

log = logging.getLogger("quicknote.scheduler")

MISSED_AFTER_MIN = 60


class ReminderScheduler:
    def __init__(self, root: tk.Misc, on_due: Callable[[list[dict]], None],
                 on_missed: Callable[[list[dict]], None], interval_ms: int = 5000) -> None:
        self.root = root
        self._on_due = on_due
        self._on_missed = on_missed
        self.interval_ms = interval_ms
        self._job: str | None = None
        self._running = False
        self._tick_hooks: list[Callable[[], None]] = []

    # ---------------------------------------------------------------- public API
    def start(self) -> None:
        """เริ่มวนตรวจ — ตรวจทันทีหนึ่งรอบเพื่อจับ alarm ที่พลาดระหว่างแอปปิดอยู่"""
        self._running = True
        self.check_now()

    def stop(self) -> None:
        self._running = False
        self._cancel()

    def on_tick(self, cb: Callable[[], None]) -> None:
        """hook ที่เรียกทุกรอบ (ธีมระบบ / status bar) — ใช้ loop เดียวกันแทนการตั้ง after เพิ่ม"""
        self._tick_hooks.append(cb)

    def check_now(self) -> None:
        """ตรวจเดี๋ยวนี้ แล้วเริ่มนับรอบใหม่ — job เดิมถูกยกเลิกก่อน จึงมี chain เดียวเสมอ"""
        self._cancel()
        try:
            self._check()
        except Exception:
            log.exception("reminder check failed")  # รอบหน้าต้องยังทำงาน ห้ามให้ loop ตาย
        self._run_hooks()
        if self._running:
            try:
                self._job = self.root.after(self.interval_ms, self._on_timer)
            except tk.TclError:
                self._job = None  # root ถูกทำลายระหว่างปิดแอป

    # ---------------------------------------------------------------- internals
    def _cancel(self) -> None:
        if self._job is not None:
            try:
                self.root.after_cancel(self._job)
            except (tk.TclError, ValueError):
                pass
            self._job = None

    def _on_timer(self) -> None:
        self._job = None
        self.check_now()

    def _run_hooks(self) -> None:
        for cb in list(self._tick_hooks):
            try:
                cb()
            except tk.TclError:
                pass
            except Exception:
                log.exception("scheduler tick hook failed")

    def _check(self) -> None:
        now = datetime.now()
        rows = db.get_due_reminders(now.strftime(FMT))
        if not rows:
            return
        due: list[dict] = []
        missed: list[dict] = []
        for row in rows:
            try:
                late_min = (now - parse_dt(row["reminder_datetime"])).total_seconds() / 60.0
            except (ValueError, TypeError):
                late_min = 0.0
            if late_min > MISSED_AFTER_MIN:
                # พลาด: ทำให้ไม่ดัง (ครั้งเดียว → ล้าง, ทำซ้ำ → ข้ามไปรอบถัดไป) แต่ยังส่งไปแจ้งใน toast
                db.dismiss_reminder(row["id"])
                missed.append(row)
            else:
                db.mark_ringing(row["id"])
                due.append(row)
        if due:
            self._on_due(due)
        if missed:
            self._on_missed(missed)
