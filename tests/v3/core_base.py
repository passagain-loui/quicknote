"""Base สำหรับ test ของ core — DB/settings จริงบน temp dir ไม่แตะ ~/.quicknote"""

import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core import database as db  # noqa: E402
from src.core import settings as settings_mod  # noqa: E402


class CoreTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="qn_test_core_"))
        # เก็บค่าเดิมไว้คืนใน tearDown (module-level state ต้องไม่รั่วข้าม test)
        self._old_env = os.environ.get("DB_PATH")
        self._old_app_dir = db.APP_DIR
        self._old_settings_file = settings_mod.SETTINGS_FILE
        self.db_path = self.tmp / "notes.db"
        os.environ["DB_PATH"] = str(self.db_path)
        db.APP_DIR = self.tmp
        settings_mod.SETTINGS_FILE = self.tmp / "settings.json"
        db.init_db()

    def tearDown(self):
        if self._old_env is None:
            os.environ.pop("DB_PATH", None)
        else:
            os.environ["DB_PATH"] = self._old_env
        db.APP_DIR = self._old_app_dir
        settings_mod.SETTINGS_FILE = self._old_settings_file
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- helpers ---
    def raw(self, sql: str, params=()):
        """รัน SQL ตรง ๆ (สำหรับตั้งค่า fixture เช่น created_at)"""
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(sql, params)
            conn.commit()
            return cur.fetchall()
        finally:
            conn.close()

    def make(self, title="t", created="2026-01-01T10:00:00", **fields) -> str:
        nid = db.create_note(title)
        self.raw("UPDATE notes SET created_at = ? WHERE id = ?", (created, nid))
        if fields:
            db.update_fields(nid, **fields)
        return nid

    def ids(self, status="active"):
        return [n["id"] for n in db.get_notes_by_status(status)]
