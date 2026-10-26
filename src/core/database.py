"""SQLite3 database for QuickNote v3 — โครงสร้างตาราง + API ตามสัญญา docs/v3/ARCHITECTURE.md ข้อ 2

กฎ: ทุก write อยู่ใต้ DB_WRITE_LOCK, ทุก connection ปิดใน finally,
เวลาทั้งหมดเป็น local-time string (ห้ามใช้ datetime('now') ของ SQLite เพราะเป็น UTC)
"""

import logging
import os
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from .reminders import FMT, next_occurrence

log = logging.getLogger("quicknote.db")

APP_DIR = Path.home() / ".quicknote"
DB_WRITE_LOCK = threading.Lock()  # scheduler thread / main thread / tray เขียนพร้อมกันได้

# คีย์ที่ update_fields ยอมรับ (H6: เขียนเฉพาะที่ส่งมา ไม่ยุ่ง reminder/status)
_UPDATABLE = {"title", "content", "collapsed", "priority", "color", "is_pinned"}
_PRIORITIES = ("none", "low", "medium", "high")
_COLORS = ("none", "yellow", "green", "pink", "purple", "blue", "gray")
_REPEATS = ("none", "daily", "weekdays", "weekly")

_BACKUP_NAME = re.compile(r"^notes_\d{8}\.db$")


def get_app_dir() -> Path:
    """โฟลเดอร์ข้อมูลของแอป — env QUICKNOTE_HOME ชนะ (อ่านตอนเรียก) เพื่อรันแอปจริงเทสโดยไม่แตะ ~/.quicknote"""
    home = os.environ.get("QUICKNOTE_HOME")
    return Path(home) if home else APP_DIR


def _get_db_file() -> str:
    """path ของ DB — อ่าน env DB_PATH ตอนเรียก เพื่อให้ test แยก DB ได้ (รองรับ ':memory:')"""
    db_path = os.environ.get("DB_PATH")
    if db_path:
        return db_path
    return str(get_app_dir() / "notes.db")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _get_db_connection() -> sqlite3.Connection:
    """connection ใหม่แบบ WAL (reader ไม่บล็อก writer) — ผู้เรียกต้อง close เอง"""
    db_file = _get_db_file()
    if db_file == ":memory:":
        # shared cache ทำให้ :memory: อยู่ข้าม connection ได้ (ใช้ใน test)
        conn = sqlite3.connect("file::memory:?cache=shared", uri=True,
                               timeout=20.0, check_same_thread=False)
    else:
        conn = sqlite3.connect(db_file, timeout=20.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


@contextmanager
def _read() -> Iterator[sqlite3.Connection]:
    conn = _get_db_connection()
    try:
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        conn.close()


@contextmanager
def _write() -> Iterator[sqlite3.Connection]:
    """lock → connection → commit (rollback เมื่อพลาด) → close เสมอ"""
    with DB_WRITE_LOCK:
        conn = _get_db_connection()
        try:
            conn.row_factory = sqlite3.Row
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


# ---------------------------------------------------------------- schema

def init_db() -> None:
    """สร้างโฟลเดอร์ + ตาราง + migrate + ล้างโน้ตที่ soft-delete ค้าง + ซ่อมเวลาเตือนเพี้ยน"""
    db_file = _get_db_file()
    if db_file != ":memory:":
        Path(db_file).parent.mkdir(parents=True, exist_ok=True)

    with _write() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT DEFAULT '',
                status TEXT DEFAULT 'active' CHECK(status IN ('active', 'completed')),
                collapsed BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                priority TEXT DEFAULT 'none' CHECK(priority IN ('none', 'low', 'medium', 'high')),
                reminder_datetime TEXT,
                reminder_triggered BOOLEAN DEFAULT 0,
                is_pinned BOOLEAN DEFAULT 0,
                last_dismissed_at TIMESTAMP,
                color TEXT DEFAULT 'none',
                reminder_repeat TEXT DEFAULT 'none',
                deleted_at TEXT
            )
        """)

    _migrate_db_schema()
    purge_deleted()
    _sanitize_reminders()


def _migrate_db_schema() -> None:
    """เพิ่มคอลัมน์ที่ DB เก่าไม่มี — idempotent (ทำซ้ำกี่ครั้งก็ไม่พัง)"""
    wanted = {
        "priority": "TEXT DEFAULT 'none'",
        "reminder_datetime": "TEXT",
        "reminder_triggered": "BOOLEAN DEFAULT 0",
        "is_pinned": "BOOLEAN DEFAULT 0",
        "last_dismissed_at": "TIMESTAMP",
        "color": "TEXT DEFAULT 'none'",
        "reminder_repeat": "TEXT DEFAULT 'none'",
        "deleted_at": "TEXT",
    }
    with _write() as conn:  # L8: connection ปิดใน finally ของ _write เสมอ
        columns = {row[1] for row in conn.execute("PRAGMA table_info(notes)")}
        for name, ddl in wanted.items():
            if name not in columns:
                conn.execute(f"ALTER TABLE notes ADD COLUMN {name} {ddl}")
        # อัปเกรดจาก v2.x ครั้งแรก (ยังไม่มีคอลัมน์ color): v2 ไม่เคยบันทึก collapsed จริง
        # จึงพับทุกใบไว้ก่อน ไม่งั้นเปิดมาจะกางพร้อมกันหลายใบ ขัดกฎ "กางทีละใบ"
        if "color" not in columns:
            conn.execute("UPDATE notes SET collapsed = 1")


def _sanitize_reminders() -> None:
    """ล้าง reminder_datetime ที่ไม่ใช่ 'YYYY-MM-DD HH:MM' (กัน scheduler เทียบ string เพี้ยน)"""
    with _write() as conn:
        rows = conn.execute(
            "SELECT id, reminder_datetime FROM notes WHERE reminder_datetime IS NOT NULL").fetchall()
        for row in rows:
            try:
                datetime.strptime(str(row["reminder_datetime"]), FMT)
            except ValueError:
                log.warning("clearing corrupt reminder on %s: %r", row["id"], row["reminder_datetime"])
                conn.execute(
                    "UPDATE notes SET reminder_datetime = NULL, reminder_triggered = 0 WHERE id = ?",
                    (row["id"],))


# ---------------------------------------------------------------- read

# M4: ไม่มี reminder_datetime ในลำดับ — กฎคือ pinned → กำลังดัง → priority → ใหม่สุด
# rowid DESC เป็น tiebreak เพราะ created_at ละเอียดแค่วินาที
_ORDER_BY = """
    ORDER BY COALESCE(is_pinned, 0) DESC,
             CASE WHEN reminder_triggered = 1 AND reminder_datetime IS NOT NULL THEN 0 ELSE 1 END,
             CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 ELSE 3 END,
             created_at DESC,
             rowid DESC
"""


def get_note(note_id: str) -> Optional[dict]:
    """อ่านโน้ตเดียว (รวมที่ soft-delete แล้ว เพื่อให้ undo ใช้ได้)"""
    with _read() as conn:
        row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        return dict(row) if row else None


def get_notes_by_status(status: str) -> list[dict]:
    with _read() as conn:
        rows = conn.execute(
            "SELECT * FROM notes WHERE status = ? AND deleted_at IS NULL" + _ORDER_BY, (status,))
        return [dict(r) for r in rows]


def count_by_status() -> dict[str, int]:
    counts = {"active": 0, "completed": 0}
    with _read() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM notes WHERE deleted_at IS NULL GROUP BY status")
        for r in rows:
            counts[r["status"]] = r["n"]
    return counts


def get_due_reminders(now: str) -> list[dict]:
    """reminder ที่ถึงเวลาแล้วและยังไม่ดัง — scheduler เรียกทุก 5 วินาที จึง query เฉพาะที่จำเป็น (L8)"""
    with _read() as conn:
        rows = conn.execute("""
            SELECT * FROM notes
            WHERE status = 'active' AND deleted_at IS NULL
              AND reminder_triggered = 0
              AND reminder_datetime IS NOT NULL AND reminder_datetime <= ?
            ORDER BY reminder_datetime ASC
        """, (now,))
        return [dict(r) for r in rows]


def get_next_reminder() -> Optional[dict]:
    """reminder อนาคตที่ใกล้ที่สุด (สำหรับ tooltip ถาด / status bar)"""
    now = datetime.now().strftime(FMT)
    with _read() as conn:
        row = conn.execute("""
            SELECT id, title, reminder_datetime FROM notes
            WHERE status = 'active' AND deleted_at IS NULL
              AND reminder_triggered = 0
              AND reminder_datetime IS NOT NULL AND reminder_datetime > ?
            ORDER BY reminder_datetime ASC LIMIT 1
        """, (now,)).fetchone()
        return dict(row) if row else None


# ---------------------------------------------------------------- write

def create_note(title: str, content: str = "", collapsed: bool = True) -> str:
    note_id = uuid.uuid4().hex
    with _write() as conn:
        conn.execute(
            "INSERT INTO notes (id, title, content, collapsed, created_at) VALUES (?, ?, ?, ?, ?)",
            (note_id, title, content, int(bool(collapsed)), _now()))
    return note_id


def update_fields(note_id: str, **fields) -> None:
    """เขียนเฉพาะ key ที่ส่งมา (C1/H6) — key นอกรายการ → ValueError"""
    bad = set(fields) - _UPDATABLE
    if bad:
        raise ValueError(f"update_fields: field not allowed: {sorted(bad)}")
    if not fields:
        return
    if "priority" in fields and fields["priority"] not in _PRIORITIES:
        raise ValueError(f"invalid priority: {fields['priority']!r}")
    if "color" in fields and fields["color"] not in _COLORS:
        raise ValueError(f"invalid color: {fields['color']!r}")
    values = {k: (int(bool(v)) if k in ("collapsed", "is_pinned") else v) for k, v in fields.items()}
    # ชื่อคอลัมน์มาจาก whitelist ด้านบนเท่านั้น จึงต่อ SQL ได้อย่างปลอดภัย
    sets = ", ".join(f"{k} = ?" for k in values)
    with _write() as conn:
        conn.execute(f"UPDATE notes SET {sets} WHERE id = ?", (*values.values(), note_id))


def set_status(note_id: str, status: str) -> None:
    """completed → ตั้ง completed_at; active → ล้าง (M5)"""
    if status not in ("active", "completed"):
        raise ValueError(f"invalid status: {status!r}")
    completed_at = _now() if status == "completed" else None
    with _write() as conn:
        conn.execute("UPDATE notes SET status = ?, completed_at = ? WHERE id = ?",
                     (status, completed_at, note_id))


def set_reminder(note_id: str, when: Optional[str], repeat: str = "none") -> None:
    """when=None → ล้างทั้ง datetime และ repeat; มีค่า → triggered=0 (ดังใหม่ได้)"""
    if when is None:
        sql, params = ("UPDATE notes SET reminder_datetime = NULL, reminder_repeat = 'none', "
                       "reminder_triggered = 0 WHERE id = ?"), (note_id,)
    else:
        datetime.strptime(when, FMT)  # ValueError ถ้ารูปแบบผิด — ดีกว่าเก็บค่าที่ scheduler เทียบไม่ได้
        if repeat not in _REPEATS:
            raise ValueError(f"invalid repeat: {repeat!r}")
        sql, params = ("UPDATE notes SET reminder_datetime = ?, reminder_repeat = ?, "
                       "reminder_triggered = 0 WHERE id = ?"), (when, repeat, note_id)
    with _write() as conn:
        conn.execute(sql, params)


def mark_ringing(note_id: str) -> None:
    """กำลังดัง — คง datetime ไว้เพื่อให้การ์ดแสดงและเรียงขึ้นบน"""
    with _write() as conn:
        conn.execute("UPDATE notes SET reminder_triggered = 1 WHERE id = ?", (note_id,))


def dismiss_reminder(note_id: str) -> None:
    """ปิดการเตือน: ครั้งเดียว → ล้าง datetime; ทำซ้ำ → เลื่อนไปรอบถัดไป"""
    with _write() as conn:
        row = conn.execute("SELECT reminder_datetime, reminder_repeat FROM notes WHERE id = ?",
                           (note_id,)).fetchone()
        if row is None:
            return
        repeat = row["reminder_repeat"] or "none"
        when = row["reminder_datetime"]
        if repeat == "none" or not when:
            conn.execute("UPDATE notes SET reminder_datetime = NULL, reminder_triggered = 0 "
                         "WHERE id = ?", (note_id,))
        else:
            conn.execute("UPDATE notes SET reminder_datetime = ?, reminder_triggered = 0 "
                         "WHERE id = ?", (next_occurrence(when, repeat), note_id))


def snooze_reminder(note_id: str, when: str) -> None:
    datetime.strptime(when, FMT)
    with _write() as conn:
        conn.execute("UPDATE notes SET reminder_datetime = ?, reminder_triggered = 0 WHERE id = ?",
                     (when, note_id))


def soft_delete(note_id: str) -> None:
    with _write() as conn:
        conn.execute("UPDATE notes SET deleted_at = ? WHERE id = ?", (_now(), note_id))


def undo_delete(note_id: str) -> None:
    with _write() as conn:
        conn.execute("UPDATE notes SET deleted_at = NULL WHERE id = ?", (note_id,))


def purge_deleted() -> None:
    """ลบจริงทุก row ที่ soft-delete (เรียกตอนเริ่มแอป — พ้นช่วง Undo แล้ว)"""
    with _write() as conn:
        conn.execute("DELETE FROM notes WHERE deleted_at IS NOT NULL")


def delete_all_completed() -> int:
    """ลบจริงโน้ตที่เสร็จแล้วทั้งหมด คืนจำนวนที่ถูกลบ"""
    with _write() as conn:
        return conn.execute("DELETE FROM notes WHERE status = 'completed'").rowcount


# ---------------------------------------------------------------- backup / restore

def backup_database(target_path: str) -> bool:
    """สำรองด้วย sqlite3 backup API — รวมข้อมูลที่ยังอยู่ใน WAL (C9; shutil.copy2 พลาดส่วนนี้)"""
    try:
        Path(target_path).parent.mkdir(parents=True, exist_ok=True)
        with DB_WRITE_LOCK:  # กันมี writer แทรกกลางการ copy
            src = _get_db_connection()
            try:
                dst = sqlite3.connect(target_path)
                try:
                    src.backup(dst)
                    # ให้ไฟล์สำรองเป็นไฟล์เดียวจบ (ไม่ต้องพก -wal/-shm ไปด้วย)
                    dst.execute("PRAGMA journal_mode=DELETE")
                finally:
                    dst.close()
            finally:
                src.close()
        return True
    except Exception as e:
        log.error("backup failed: %s", e)
        return False


def restore_database(backup_path: str) -> bool:
    """กู้คืน: ตรวจไฟล์ → เก็บ snapshot ก่อนกู้ → เขียนทับผ่าน backup API → init_db()

    คืน False และไม่แตะข้อมูลเดิมถ้าไฟล์ไม่ใช่ SQLite / ไม่ใช่ไฟล์ QuickNote
    """
    try:
        if not Path(backup_path).is_file():
            return False
        uri = Path(backup_path).resolve().as_uri() + "?mode=ro"
        src = sqlite3.connect(uri, uri=True)
        try:
            if src.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                return False
            cols = {r[1] for r in src.execute("PRAGMA table_info(notes)")}
            if not {"id", "title", "status"} <= cols:
                return False

            # กันพลาด: เก็บสำเนาข้อมูลปัจจุบันไว้ก่อนทับ
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            snapshot_dir = Path(_get_db_file()).parent if _get_db_file() != ":memory:" else get_app_dir()
            backup_database(str(snapshot_dir / f"notes_before_restore_{stamp}.db"))

            with DB_WRITE_LOCK:
                dst = _get_db_connection()
                try:
                    src.backup(dst)
                finally:
                    dst.close()
        finally:
            src.close()
        init_db()  # migrate คอลัมน์ให้ไฟล์ backup จากรุ่นเก่า
        return True
    except Exception as e:
        log.error("restore failed: %s", e)
        return False


def auto_backup(keep: int = 7) -> Optional[str]:
    """สำรองอัตโนมัติ APP_DIR/backups/notes_YYYYMMDD.db วันละครั้ง แล้วลบไฟล์เก่าเกิน keep

    คืน path ที่สร้างใหม่ หรือ None ถ้าวันนี้สำรองไปแล้ว/ล้มเหลว
    """
    folder = get_app_dir() / "backups"
    target = folder / f"notes_{datetime.now():%Y%m%d}.db"
    if target.exists():
        return None
    if not backup_database(str(target)):
        target.unlink(missing_ok=True)  # ไม่ทิ้งไฟล์ครึ่งๆ กลางๆ ที่จะทำให้วันนี้ไม่สำรองอีก
        return None

    # ชื่อมีวันที่เรียงตัวอักษร = เรียงตามเวลา
    old = sorted(p for p in folder.iterdir() if _BACKUP_NAME.match(p.name))
    for p in old[:max(0, len(old) - max(1, keep))]:
        try:
            p.unlink()
        except OSError as e:
            log.warning("cannot prune %s: %s", p, e)
    return str(target)


if __name__ == "__main__":
    init_db()
    print(f"[OK] Database initialized at {_get_db_file()}")
