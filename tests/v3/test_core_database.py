"""Test database.py v3 — API, sort order, reminder lifecycle, soft delete, migration"""

import sqlite3
import unittest
from datetime import datetime, timedelta

from tests.v3.core_base import CoreTestCase, db


class UpdateFieldsTests(CoreTestCase):
    def test_priority_is_persisted_c1(self):
        nid = self.make("a")
        db.update_fields(nid, priority="high")
        self.assertEqual(db.get_note(nid)["priority"], "high")

    def test_only_given_keys_written_h6(self):
        nid = self.make("a")
        db.set_reminder(nid, "2030-01-01 09:00", "daily")
        db.mark_ringing(nid)
        db.update_fields(nid, title="new")
        n = db.get_note(nid)
        self.assertEqual(n["title"], "new")
        self.assertEqual(n["reminder_datetime"], "2030-01-01 09:00")
        self.assertEqual(n["reminder_repeat"], "daily")
        self.assertEqual(n["reminder_triggered"], 1)
        self.assertEqual(n["status"], "active")

    def test_disallowed_key_raises(self):
        nid = self.make("a")
        for bad in ("status", "reminder_datetime", "id", "deleted_at"):
            with self.assertRaises(ValueError):
                db.update_fields(nid, **{bad: "x"})

    def test_invalid_enum_values_raise(self):
        nid = self.make("a")
        with self.assertRaises(ValueError):
            db.update_fields(nid, priority="urgent")
        with self.assertRaises(ValueError):
            db.update_fields(nid, color="red")

    def test_bool_fields_and_color(self):
        nid = self.make("a")
        db.update_fields(nid, collapsed=False, is_pinned=True, color="pink")
        n = db.get_note(nid)
        self.assertEqual((n["collapsed"], n["is_pinned"], n["color"]), (0, 1, "pink"))

    def test_create_note_defaults_collapsed_and_local_timestamp(self):
        before = datetime.now().replace(microsecond=0)
        nid = db.create_note("x")
        n = db.get_note(nid)
        self.assertEqual(n["collapsed"], 1)
        created = datetime.fromisoformat(n["created_at"])
        self.assertLessEqual(before, created)
        self.assertLess(created - before, timedelta(seconds=5))  # local time ไม่ใช่ UTC
        self.assertEqual(n["color"], "none")
        self.assertEqual(n["reminder_repeat"], "none")
        self.assertIsNone(n["deleted_at"])
        self.assertEqual(db.get_note(db.create_note("y", collapsed=False))["collapsed"], 0)


class SortOrderTests(CoreTestCase):
    def test_pinned_first(self):
        old_pinned = self.make("old", created="2026-01-01T00:00:00", is_pinned=True)
        new = self.make("new", created="2026-02-01T00:00:00", priority="high")
        self.assertEqual(self.ids(), [old_pinned, new])

    def test_ringing_before_priority_but_after_pinned(self):
        high = self.make("high", priority="high")
        ringing = self.make("ring")
        db.set_reminder(ringing, "2026-01-01 09:00")
        db.mark_ringing(ringing)
        pinned = self.make("pin", is_pinned=True)
        self.assertEqual(self.ids(), [pinned, ringing, high])

    def test_triggered_without_datetime_is_not_ringing(self):
        a = self.make("a", created="2026-01-01T00:00:00")
        b = self.make("b", created="2026-01-02T00:00:00")
        # สถานะค้าง: triggered=1 แต่ไม่มี datetime ต้องไม่ถือว่าดัง
        self.raw("UPDATE notes SET reminder_triggered = 1 WHERE id = ?", (a,))
        self.assertEqual(self.ids(), [b, a])

    def test_priority_order_then_created_desc(self):
        none_new = self.make("n", created="2026-03-01T00:00:00")
        low = self.make("l", created="2026-01-01T00:00:00", priority="low")
        med = self.make("m", created="2026-01-02T00:00:00", priority="medium")
        high = self.make("h", created="2026-01-03T00:00:00", priority="high")
        none_old = self.make("n2", created="2026-02-01T00:00:00")
        self.assertEqual(self.ids(), [high, med, low, none_new, none_old])

    def test_null_reminders_do_not_jump_ahead_m4(self):
        # โน้ตมี reminder (ยังไม่ดัง) ไม่ถูกจัดให้ต่ำกว่าโน้ตที่ไม่มี reminder เพราะ NULL
        with_rem = self.make("rem", created="2026-01-02T00:00:00", priority="medium")
        db.set_reminder(with_rem, "2030-01-01 09:00")
        plain = self.make("plain", created="2026-01-03T00:00:00")
        self.assertEqual(self.ids(), [with_rem, plain])

    def test_same_second_tiebreak_is_newest_first(self):
        a = db.create_note("a")
        b = db.create_note("b")
        self.raw("UPDATE notes SET created_at = '2026-01-01T00:00:00'")
        self.assertEqual(self.ids(), [b, a])

    def test_status_filter(self):
        a = self.make("a")
        b = self.make("b")
        db.set_status(b, "completed")
        self.assertEqual(self.ids("active"), [a])
        self.assertEqual(self.ids("completed"), [b])


class StatusTests(CoreTestCase):
    def test_completed_sets_and_active_clears_completed_at_m5(self):
        nid = self.make("a")
        db.set_status(nid, "completed")
        self.assertTrue(db.get_note(nid)["completed_at"])
        db.set_status(nid, "active")
        n = db.get_note(nid)
        self.assertEqual(n["status"], "active")
        self.assertIsNone(n["completed_at"])

    def test_invalid_status_raises(self):
        with self.assertRaises(ValueError):
            db.set_status(self.make("a"), "done")

    def test_title_and_content_untouched_by_status(self):
        nid = db.create_note("หัวข้อไทย", "เนื้อหา")
        db.set_status(nid, "completed")
        n = db.get_note(nid)
        self.assertEqual((n["title"], n["content"]), ("หัวข้อไทย", "เนื้อหา"))

    def test_count_by_status(self):
        self.make("a")
        self.make("b")
        c = self.make("c")
        db.set_status(c, "completed")
        self.assertEqual(db.count_by_status(), {"active": 2, "completed": 1})


class ReminderLifecycleTests(CoreTestCase):
    def test_set_reminder_resets_triggered_and_clear(self):
        nid = self.make("a")
        db.set_reminder(nid, "2026-01-01 09:00", "weekly")
        db.mark_ringing(nid)
        db.set_reminder(nid, "2026-01-02 09:00", "daily")
        n = db.get_note(nid)
        self.assertEqual((n["reminder_datetime"], n["reminder_repeat"], n["reminder_triggered"]),
                         ("2026-01-02 09:00", "daily", 0))
        db.set_reminder(nid, None)
        n = db.get_note(nid)
        self.assertEqual((n["reminder_datetime"], n["reminder_repeat"], n["reminder_triggered"]),
                         (None, "none", 0))

    def test_invalid_inputs_raise(self):
        nid = self.make("a")
        with self.assertRaises(ValueError):
            db.set_reminder(nid, "tomorrow")
        with self.assertRaises(ValueError):
            db.set_reminder(nid, "2026-01-01 09:00", "monthly")

    def test_lifecycle_once(self):
        nid = self.make("a")
        db.set_reminder(nid, "2026-01-01 09:00")
        self.assertEqual([n["id"] for n in db.get_due_reminders("2026-01-01 09:00")], [nid])
        db.mark_ringing(nid)
        self.assertEqual(db.get_due_reminders("2026-01-01 09:05"), [])  # ดังแล้วไม่ถูกหยิบซ้ำ
        self.assertEqual(db.get_note(nid)["reminder_datetime"], "2026-01-01 09:00")  # คงไว้
        db.dismiss_reminder(nid)
        n = db.get_note(nid)
        self.assertIsNone(n["reminder_datetime"])
        self.assertEqual(n["reminder_triggered"], 0)

    def test_dismiss_repeat_advances(self):
        nid = self.make("a")
        db.set_reminder(nid, "2020-01-01 09:00", "daily")
        db.mark_ringing(nid)
        db.dismiss_reminder(nid)
        n = db.get_note(nid)
        self.assertEqual(n["reminder_triggered"], 0)
        self.assertEqual(n["reminder_repeat"], "daily")
        nxt = datetime.strptime(n["reminder_datetime"], "%Y-%m-%d %H:%M")
        self.assertGreater(nxt, datetime.now())
        self.assertEqual((nxt.hour, nxt.minute), (9, 0))
        self.assertLessEqual(nxt - datetime.now(), timedelta(days=1, minutes=1))

    def test_dismiss_missing_note_is_noop(self):
        db.dismiss_reminder("nope")

    def test_snooze_keeps_repeat(self):
        nid = self.make("a")
        db.set_reminder(nid, "2026-01-01 09:00", "weekdays")
        db.mark_ringing(nid)
        db.snooze_reminder(nid, "2026-01-01 09:05")
        n = db.get_note(nid)
        self.assertEqual((n["reminder_datetime"], n["reminder_triggered"], n["reminder_repeat"]),
                         ("2026-01-01 09:05", 0, "weekdays"))
        self.assertEqual(db.get_due_reminders("2026-01-01 09:04"), [])
        self.assertEqual(len(db.get_due_reminders("2026-01-01 09:05")), 1)

    def test_due_excludes_completed_deleted_triggered_and_no_reminder(self):
        due = self.make("due")
        comp = self.make("comp")
        dele = self.make("dele")
        ring = self.make("ring")
        self.make("none")
        future = self.make("future")
        for n in (due, comp, dele, ring):
            db.set_reminder(n, "2026-01-01 09:00")
        db.set_reminder(future, "2026-01-01 10:00")
        db.set_status(comp, "completed")
        db.soft_delete(dele)
        db.mark_ringing(ring)
        got = [n["id"] for n in db.get_due_reminders("2026-01-01 09:30")]
        self.assertEqual(got, [due])

    def test_get_next_reminder(self):
        self.assertIsNone(db.get_next_reminder())
        soon = self.make("soon")
        later = self.make("later")
        past = self.make("past")
        now = datetime.now()
        db.set_reminder(later, (now + timedelta(hours=5)).strftime("%Y-%m-%d %H:%M"))
        db.set_reminder(soon, (now + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M"))
        db.set_reminder(past, (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M"))
        nxt = db.get_next_reminder()
        self.assertEqual(nxt["id"], soon)
        self.assertEqual(set(nxt), {"id", "title", "reminder_datetime"})


class SoftDeleteTests(CoreTestCase):
    def test_soft_delete_hides_and_undo_restores(self):
        a = self.make("a")
        b = self.make("b")
        db.soft_delete(a)
        self.assertEqual(self.ids(), [b])
        self.assertEqual(db.count_by_status()["active"], 1)
        self.assertIsNotNone(db.get_note(a)["deleted_at"])  # ยังอยู่ใน DB (undo ได้)
        db.undo_delete(a)
        self.assertEqual(set(self.ids()), {a, b})
        self.assertEqual(db.count_by_status()["active"], 2)

    def test_purge_removes_only_deleted(self):
        a = self.make("a")
        b = self.make("b")
        db.soft_delete(a)
        db.purge_deleted()
        self.assertIsNone(db.get_note(a))
        self.assertIsNotNone(db.get_note(b))

    def test_init_db_purges_deleted(self):
        a = self.make("a")
        db.soft_delete(a)
        db.init_db()
        self.assertIsNone(db.get_note(a))

    def test_delete_all_completed(self):
        a = self.make("a")
        b = self.make("b")
        c = self.make("c")
        db.set_status(b, "completed")
        db.set_status(c, "completed")
        self.assertEqual(db.delete_all_completed(), 2)
        self.assertEqual(self.ids("completed"), [])
        self.assertEqual(self.ids(), [a])


class SchemaTests(CoreTestCase):
    def test_sanitize_clears_corrupt_reminder(self):
        a = self.make("a")
        self.raw("UPDATE notes SET reminder_datetime = 'garbage' WHERE id = ?", (a,))
        db.init_db()
        self.assertIsNone(db.get_note(a)["reminder_datetime"])

    def test_migration_from_v2946_schema(self):
        # สร้าง DB ตามสคีมา v2.9.46 (ไม่มี color/reminder_repeat/deleted_at) ใน path ใหม่
        import os
        old_path = self.tmp / "old.db"
        conn = sqlite3.connect(old_path)
        conn.execute("""
            CREATE TABLE notes (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, content TEXT DEFAULT '',
                status TEXT DEFAULT 'active' CHECK(status IN ('active', 'completed')),
                collapsed BOOLEAN DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                priority TEXT DEFAULT 'none' CHECK(priority IN ('none', 'low', 'medium', 'high')),
                reminder_datetime TEXT, reminder_triggered BOOLEAN DEFAULT 0,
                is_pinned BOOLEAN DEFAULT 0, last_dismissed_at TIMESTAMP)
        """)
        conn.execute("INSERT INTO notes (id, title, content, priority, is_pinned, reminder_datetime) "
                     "VALUES ('old1', 'โน้ตเก่า', 'เนื้อหา', 'high', 1, '2030-05-05 08:00')")
        conn.commit()
        conn.close()

        os.environ["DB_PATH"] = str(old_path)
        db.init_db()
        db.init_db()  # idempotent
        cols = {r[1] for r in self.raw_on(old_path, "PRAGMA table_info(notes)")}
        self.assertTrue({"color", "reminder_repeat", "deleted_at"} <= cols)
        n = db.get_note("old1")
        self.assertEqual((n["title"], n["content"], n["priority"], n["is_pinned"]),
                         ("โน้ตเก่า", "เนื้อหา", "high", 1))
        self.assertEqual((n["color"], n["reminder_repeat"], n["deleted_at"]), ("none", "none", None))
        self.assertEqual(n["reminder_datetime"], "2030-05-05 08:00")
        self.assertEqual(self.ids(), ["old1"])

    @staticmethod
    def raw_on(path, sql):
        conn = sqlite3.connect(path)
        try:
            return conn.execute(sql).fetchall()
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
