"""Test reminders.py — next_occurrence / format_reminder / quick_times"""

import unittest
from datetime import datetime

from src.core.reminders import format_reminder, next_occurrence, quick_times


class NextOccurrenceTests(unittest.TestCase):
    def test_none_returns_same(self):
        self.assertEqual(next_occurrence("2026-10-30 09:00", "none"), "2026-10-30 09:00")

    def test_daily(self):
        now = datetime(2026, 10, 30, 9, 0, 30)
        self.assertEqual(next_occurrence("2026-10-30 09:00", "daily", now), "2026-10-31 09:00")

    def test_daily_skips_missed_cycles(self):
        now = datetime(2026, 11, 5, 8, 0)
        self.assertEqual(next_occurrence("2026-10-30 09:00", "daily", now), "2026-11-05 09:00")
        now = datetime(2026, 11, 5, 10, 0)
        self.assertEqual(next_occurrence("2026-10-30 09:00", "daily", now), "2026-11-06 09:00")

    def test_weekdays_friday_to_monday(self):
        # 2026-10-30 เป็นวันศุกร์
        now = datetime(2026, 10, 30, 9, 1)
        self.assertEqual(datetime(2026, 10, 30).weekday(), 4)
        self.assertEqual(next_occurrence("2026-10-30 09:00", "weekdays", now), "2026-11-02 09:00")

    def test_weekdays_mid_week(self):
        now = datetime(2026, 10, 28, 9, 1)  # พุธ
        self.assertEqual(next_occurrence("2026-10-28 09:00", "weekdays", now), "2026-10-29 09:00")

    def test_weekdays_missed_over_weekend(self):
        now = datetime(2026, 10, 31, 12, 0)  # เสาร์
        self.assertEqual(next_occurrence("2026-10-28 09:00", "weekdays", now), "2026-11-02 09:00")

    def test_weekly(self):
        now = datetime(2026, 10, 30, 9, 1)
        self.assertEqual(next_occurrence("2026-10-30 09:00", "weekly", now), "2026-11-06 09:00")

    def test_weekly_skips_missed_cycles_and_keeps_weekday(self):
        now = datetime(2026, 11, 20, 12, 0)  # ศุกร์
        self.assertEqual(next_occurrence("2026-10-02 09:00", "weekly", now), "2026-11-27 09:00")
        now = datetime(2026, 11, 18, 12, 0)  # พุธ → ศุกร์ถัดไป
        self.assertEqual(next_occurrence("2026-10-02 09:00", "weekly", now), "2026-11-20 09:00")

    def test_result_is_after_original_even_if_early(self):
        # dismiss ก่อนถึงเวลา (when ในอนาคต) ต้องไม่ได้ค่าเดิมกลับ
        now = datetime(2026, 10, 1, 8, 0)
        self.assertEqual(next_occurrence("2026-10-30 09:00", "daily", now), "2026-10-31 09:00")

    def test_default_now_is_in_future(self):
        out = next_occurrence("2020-01-01 09:00", "daily")
        self.assertGreater(datetime.strptime(out, "%Y-%m-%d %H:%M"), datetime.now())


class FormatReminderTests(unittest.TestCase):
    NOW = datetime(2026, 10, 30, 12, 0)  # ศุกร์

    def test_today(self):
        self.assertEqual(format_reminder("2026-10-30 14:30", self.NOW, "th"), ("วันนี้ 14:30", False))
        self.assertEqual(format_reminder("2026-10-30 14:30", self.NOW, "en"), ("Today 14:30", False))

    def test_tomorrow(self):
        self.assertEqual(format_reminder("2026-10-31 09:00", self.NOW, "th"), ("พรุ่งนี้ 09:00", False))
        self.assertEqual(format_reminder("2026-10-31 09:00", self.NOW, "en"), ("Tomorrow 09:00", False))

    def test_other_day(self):
        self.assertEqual(format_reminder("2026-11-06 14:30", self.NOW, "th"), ("ศ. 6 พ.ย. 14:30", False))
        self.assertEqual(format_reminder("2026-11-06 14:30", self.NOW, "en"), ("Fri 6 Nov 14:30", False))
        self.assertEqual(format_reminder("2026-11-04 08:05", self.NOW, "th")[0], "พ. 4 พ.ย. 08:05")
        self.assertEqual(format_reminder("2026-11-05 08:05", self.NOW, "th")[0], "พฤ. 5 พ.ย. 08:05")
        self.assertEqual(format_reminder("2026-11-08 08:05", self.NOW, "th")[0], "อา. 8 พ.ย. 08:05")

    def test_overdue(self):
        self.assertEqual(format_reminder("2026-10-30 09:15", self.NOW, "th"), ("เลยกำหนด 09:15", True))
        self.assertEqual(format_reminder("2026-10-30 09:15", self.NOW, "en"), ("Overdue 09:15", True))

    def test_overdue_other_day_adds_date(self):
        text, overdue = format_reminder("2026-10-28 09:15", self.NOW, "th")
        self.assertTrue(overdue)
        self.assertEqual(text, "เลยกำหนด พ. 28 ต.ค. 09:15")

    def test_exact_minute_is_not_overdue(self):
        self.assertFalse(format_reminder("2026-10-30 12:00", self.NOW, "th")[1])

    def test_invalid_does_not_crash(self):
        self.assertEqual(format_reminder("junk", self.NOW, "th"), ("junk", False))


class QuickTimesTests(unittest.TestCase):
    def test_morning(self):
        q = quick_times(datetime(2026, 10, 30, 9, 7, 42))
        self.assertEqual(q, {"in15m": "2026-10-30 09:22", "in1h": "2026-10-30 10:07",
                             "this_evening": "2026-10-30 17:00", "tomorrow_9": "2026-10-31 09:00"})

    def test_after_17_has_no_evening(self):
        q = quick_times(datetime(2026, 10, 30, 17, 0, 1))
        self.assertIsNone(q["this_evening"])
        self.assertEqual(q["tomorrow_9"], "2026-10-31 09:00")

    def test_crossing_midnight(self):
        q = quick_times(datetime(2026, 10, 31, 23, 50))
        self.assertEqual(q["in15m"], "2026-11-01 00:05")
        self.assertEqual(q["tomorrow_9"], "2026-11-01 09:00")


if __name__ == "__main__":
    unittest.main()
