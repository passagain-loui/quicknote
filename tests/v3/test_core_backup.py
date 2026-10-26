"""Test backup / restore / auto_backup (C9)"""

import sqlite3
import unittest
from datetime import datetime, timedelta

from tests.v3.core_base import CoreTestCase, db


def _titles(path) -> list[str]:
    conn = sqlite3.connect(path)
    try:
        return [r[0] for r in conn.execute("SELECT title FROM notes ORDER BY title")]
    finally:
        conn.close()


class BackupTests(CoreTestCase):
    def test_backup_captures_write_still_in_wal(self):
        # เปิด connection ค้างไว้เพื่อกัน checkpoint อัตโนมัติ → ข้อมูลล่าสุดอยู่ใน -wal เท่านั้น
        holder = sqlite3.connect(self.db_path)
        holder.execute("PRAGMA journal_mode=WAL")
        holder.execute("BEGIN")
        holder.execute("SELECT count(*) FROM notes").fetchall()
        try:
            db.create_note("อยู่ใน WAL")
            wal = self.db_path.with_name(self.db_path.name + "-wal")
            self.assertTrue(wal.exists() and wal.stat().st_size > 0)
            target = self.tmp / "out" / "backup.db"
            self.assertTrue(db.backup_database(str(target)))
        finally:
            holder.close()
        self.assertEqual(_titles(target), ["อยู่ใน WAL"])

    def test_restore_non_sqlite_returns_false_and_keeps_data(self):
        db.create_note("keep")
        bogus = self.tmp / "bogus.db"
        bogus.write_bytes(b"this is definitely not a sqlite file" * 100)
        self.assertFalse(db.restore_database(str(bogus)))
        self.assertEqual([n["title"] for n in db.get_notes_by_status("active")], ["keep"])

    def test_restore_missing_file_returns_false(self):
        db.create_note("keep")
        self.assertFalse(db.restore_database(str(self.tmp / "nope.db")))
        self.assertEqual(len(db.get_notes_by_status("active")), 1)

    def test_restore_sqlite_without_notes_table_returns_false(self):
        other = self.tmp / "other.db"
        c = sqlite3.connect(other)
        c.execute("CREATE TABLE foo (x)")
        c.commit()
        c.close()
        db.create_note("keep")
        self.assertFalse(db.restore_database(str(other)))
        self.assertEqual(len(db.get_notes_by_status("active")), 1)

    def test_restore_valid_backup_replaces_data_and_snapshots(self):
        db.create_note("original")
        bak = self.tmp / "good.db"
        self.assertTrue(db.backup_database(str(bak)))
        db.create_note("added after backup")
        self.assertTrue(db.restore_database(str(bak)))
        self.assertEqual([n["title"] for n in db.get_notes_by_status("active")], ["original"])
        snaps = list(self.tmp.glob("notes_before_restore_*.db"))
        self.assertEqual(len(snaps), 1)
        self.assertEqual(_titles(snaps[0]), ["added after backup", "original"])

    def test_restore_old_schema_backup_is_migrated(self):
        old = self.tmp / "v2946.db"
        c = sqlite3.connect(old)
        c.execute("CREATE TABLE notes (id TEXT PRIMARY KEY, title TEXT NOT NULL, content TEXT, "
                  "status TEXT DEFAULT 'active', collapsed BOOLEAN DEFAULT 0, created_at TEXT, "
                  "completed_at TEXT, priority TEXT DEFAULT 'none', reminder_datetime TEXT, "
                  "reminder_triggered BOOLEAN DEFAULT 0, is_pinned BOOLEAN DEFAULT 0)")
        c.execute("INSERT INTO notes (id, title, status) VALUES ('o', 'เก่า', 'active')")
        c.commit()
        c.close()
        self.assertTrue(db.restore_database(str(old)))
        n = db.get_note("o")
        self.assertEqual((n["title"], n["color"], n["reminder_repeat"]), ("เก่า", "none", "none"))

    def test_data_usable_after_restore(self):
        bak = self.tmp / "b.db"
        db.backup_database(str(bak))
        db.restore_database(str(bak))
        nid = db.create_note("after")
        db.update_fields(nid, priority="low")
        self.assertEqual(db.get_note(nid)["priority"], "low")


class AutoBackupTests(CoreTestCase):
    def test_once_per_day(self):
        db.create_note("x")
        first = db.auto_backup()
        self.assertIsNotNone(first)
        self.assertEqual(first, str(self.tmp / "backups" / f"notes_{datetime.now():%Y%m%d}.db"))
        self.assertEqual(_titles(first), ["x"])
        self.assertIsNone(db.auto_backup())
        self.assertEqual(len(list((self.tmp / "backups").iterdir())), 1)

    def test_prunes_to_keep_newest(self):
        folder = self.tmp / "backups"
        folder.mkdir()
        today = datetime.now()
        for i in range(1, 10):
            (folder / f"notes_{today - timedelta(days=i):%Y%m%d}.db").write_bytes(b"x")
        (folder / "unrelated.txt").write_text("keep me")
        self.assertIsNotNone(db.auto_backup(keep=3))
        names = sorted(p.name for p in folder.iterdir())
        expect = sorted([f"notes_{today:%Y%m%d}.db"] +
                        [f"notes_{today - timedelta(days=i):%Y%m%d}.db" for i in (1, 2)] +
                        ["unrelated.txt"])
        self.assertEqual(names, expect)


if __name__ == "__main__":
    unittest.main()
