"""Test export.py + models.py"""

import unittest

from src.core import export
from src.core.constants import APP_ID, APP_VERSION, MIN_ALPHA
from src.core.models import Note
from tests.v3.core_base import CoreTestCase, db


class ConstantsTests(unittest.TestCase):
    def test_values(self):
        self.assertEqual(APP_VERSION, "3.0.0")
        self.assertEqual(MIN_ALPHA, 0.3)
        self.assertEqual(APP_ID, "PassagainP.QuickNote")


class ModelTests(unittest.TestCase):
    def test_from_dict_reads_collapsed_truthfully_h4(self):
        self.assertFalse(Note.from_dict({"id": "a", "title": "t", "collapsed": 0}).collapsed)
        self.assertTrue(Note.from_dict({"id": "a", "title": "t", "collapsed": 1}).collapsed)

    def test_new_fields_defaults_and_values(self):
        n = Note.from_dict({"id": "a", "title": "t"})
        self.assertEqual((n.color, n.reminder_repeat, n.deleted_at), ("none", "none", None))
        n = Note.from_dict({"id": "a", "title": "t", "color": "pink",
                            "reminder_repeat": "weekly", "deleted_at": "2026-01-01T00:00:00"})
        self.assertEqual((n.color, n.reminder_repeat, n.deleted_at), ("pink", "weekly", "2026-01-01T00:00:00"))

    def test_invalid_enums_fall_back(self):
        n = Note.from_dict({"id": "a", "title": "t", "color": "red",
                            "reminder_repeat": "hourly", "priority": "urgent", "status": "zzz"})
        self.assertEqual((n.color, n.reminder_repeat, n.priority, n.status),
                         ("none", "none", "none", "active"))

    def test_roundtrip_from_db_row(self):
        n = Note(id="x", title="t", color="blue", is_pinned=True)
        self.assertEqual(Note.from_dict(n.to_dict()), n)


class ExportTests(CoreTestCase):
    def test_export_markdown_th(self):
        a = db.create_note("งานแรก", "รายละเอียด\nบรรทัดสอง")
        db.update_fields(a, priority="high", is_pinned=True)
        db.set_reminder(a, "2030-01-01 09:00", "daily")
        b = db.create_note("เสร็จแล้ว")
        db.set_status(b, "completed")
        out = self.tmp / "o.md"
        self.assertTrue(export.export_markdown(str(out), "th"))
        text = out.read_text(encoding="utf-8")
        self.assertIn("## งานแรก", text)
        self.assertIn("- [ ] งานแรก", text)
        self.assertIn("- [x] เสร็จแล้ว", text)
        self.assertIn("รายละเอียด\nบรรทัดสอง", text)
        self.assertIn("เตือน: 2030-01-01 09:00 (ทุกวัน)", text)
        self.assertIn("ความสำคัญ: high", text)
        self.assertLess(text.index("งานแรก"), text.index("เสร็จแล้ว"))  # active ก่อน completed
        self.assertFalse(out.with_name("o.md.tmp").exists())

    def test_export_markdown_en_and_excludes_deleted(self):
        a = db.create_note("Keep")
        gone = db.create_note("Gone")
        db.soft_delete(gone)
        out = self.tmp / "o.md"
        self.assertTrue(export.export_markdown(str(out), "en"))
        text = out.read_text(encoding="utf-8")
        self.assertIn("Exported", text)
        self.assertIn("## Keep", text)
        self.assertNotIn("Gone", text)

    def test_export_empty_title(self):
        db.create_note("")
        out = self.tmp / "o.md"
        self.assertTrue(export.export_markdown(str(out), "en"))
        self.assertIn("(untitled)", out.read_text(encoding="utf-8"))

    def test_export_bad_path_returns_false(self):
        self.assertFalse(export.export_markdown(str(self.tmp / "no_such_dir" / "x.md"), "th"))


if __name__ == "__main__":
    unittest.main()
