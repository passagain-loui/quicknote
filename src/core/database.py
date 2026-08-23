"""SQLite3 database for QuickNote — ดูแลโครงสร้างดาตาเบสและฟังก์ชันพื้นฐาน"""

import sqlite3
import uuid
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional


APP_DIR = Path.home() / ".quicknote"
DB_FILE = APP_DIR / "notes.db"
DB_WRITE_LOCK = threading.Lock()  # v2.9.36: Thread-safe database writes


def _get_db_connection():
    """v2.9.36: Create SQLite connection with WAL mode + enhanced timeout for thread-safe access

    WAL (Write-Ahead Logging) allows multiple threads to read while one thread writes,
    preventing deadlocks between Background Scheduler Thread and Main GUI Thread.
    v2.9.36: Increased timeout to 20 seconds for better concurrent write handling
    """
    conn = sqlite3.connect(DB_FILE, timeout=20.0, check_same_thread=False)  # 20s timeout, thread-safe
    conn.execute("PRAGMA journal_mode=WAL;")        # Enable WAL mode
    conn.execute("PRAGMA synchronous=NORMAL;")       # Balance safety and performance
    conn.execute("PRAGMA busy_timeout=5000;")         # 5-second busy timeout
    return conn


def init_db() -> None:
    """v2.9.36: สร้างโฟลเดอร์แอป + ตาราง notes ถ้ายังไม่มี (thread-safe with lock)"""
    with DB_WRITE_LOCK:  # v2.9.36: Prevent concurrent initialization
        APP_DIR.mkdir(exist_ok=True)

        conn = _get_db_connection()  # v2.9.22: WAL-enabled connection
        c = conn.cursor()

        c.execute("""
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
                last_dismissed_at TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    _migrate_db_schema()  # v1.3.0: ensure old DB gets new columns
    sanitize_reminders()  # v2.2.2: clean corrupted reminder times on startup


def _migrate_db_schema() -> None:
    """v2.9.36: ตรวจและเพิ่มคอลัมน์ใหม่สำหรับ v1.3.0+ (priority, reminders, pinning) — thread-safe"""
    with DB_WRITE_LOCK:  # v2.9.36: Prevent concurrent schema changes
        conn = _get_db_connection()  # v2.9.22: WAL-enabled connection
        c = conn.cursor()

        try:
            # ตรวจว่าคอลัมน์มีอยู่หรือไม่
            c.execute("PRAGMA table_info(notes)")
            columns = {row[1] for row in c.fetchall()}

            # เพิ่มคอลัมน์ใหม่ถ้ายังไม่มี
            if "priority" not in columns:
                c.execute("ALTER TABLE notes ADD COLUMN priority TEXT DEFAULT 'none'")
            if "reminder_datetime" not in columns:
                c.execute("ALTER TABLE notes ADD COLUMN reminder_datetime TEXT")
            if "reminder_triggered" not in columns:
                c.execute("ALTER TABLE notes ADD COLUMN reminder_triggered BOOLEAN DEFAULT 0")
            if "is_pinned" not in columns:
                # v1.5.0: Add pinning support
                c.execute("ALTER TABLE notes ADD COLUMN is_pinned BOOLEAN DEFAULT 0")
            if "last_dismissed_at" not in columns:
                # v2.9.28: Track when note was last dismissed (for pinning at top)
                c.execute("ALTER TABLE notes ADD COLUMN last_dismissed_at TIMESTAMP")

            conn.commit()
        except sqlite3.OperationalError as e:
            # ถ้า constraint ขัดแย้ง ให้ rollback ซ้ำ ไม่ต้องทำลายฐานข้อมูล
            conn.rollback()
        finally:
            conn.close()


def create_note(title: str, content: str = "") -> str:
    """v2.9.36: เพิ่มโน้ตใหม่ — คืนค่า id (thread-safe with lock)"""
    with DB_WRITE_LOCK:  # v2.9.36: Prevent concurrent note creation
        note_id = uuid.uuid4().hex
        conn = _get_db_connection()  # v2.9.22: WAL-enabled connection
        c = conn.cursor()

        c.execute("""
            INSERT INTO notes (id, title, content, created_at)
            VALUES (?, ?, ?, ?)
        """, (note_id, title, content, datetime.now().isoformat()))

        conn.commit()
        conn.close()
        return note_id


def get_all_notes() -> list[dict]:
    """อ่านทุกโน้ต คืนเป็น list of dict"""
    conn = _get_db_connection()  # v2.9.22: WAL-enabled connection
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT * FROM notes ORDER BY created_at DESC")
    notes = [dict(row) for row in c.fetchall()]

    conn.close()
    return notes


def get_notes_by_status(status: str) -> list[dict]:
    """อ่านโน้ตตามสถานะ (active/completed) — v2.8.2: Absolute sort by newest triggered reminder"""
    conn = _get_db_connection()  # v2.9.22: WAL-enabled connection
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # v2.9.40: Pin persistence — PINNED NOTES ARE PRIMARY SORT (always appear at top)
    # v2.9.26: Secondary: Recently triggered alarms with datetime
    # v2.9.28: Tertiary: Recently dismissed notes stay at top (pinned to top for quick access)
    # Triggered alarm = reminder_triggered = 1 AND reminder_datetime IS NOT NULL
    c.execute("""
        SELECT * FROM notes
        WHERE status = ?
        ORDER BY
                 -- v2.9.40 PRIMARY: PINNED NOTES FIRST (all pinned notes above unpinned)
                 is_pinned DESC,
                 -- SECONDARY: Recently triggered alarms with datetime go next
                 -- v2.9.26: Must check both triggered=1 AND datetime is NOT NULL
                 CASE
                   WHEN reminder_triggered = 1 AND reminder_datetime IS NOT NULL
                   THEN 0  -- Just triggered with datetime: high priority
                   ELSE 1  -- Not triggered or datetime cleared: lower priority
                 END,
                 -- TERTIARY: Recently dismissed notes stay high (pinned to top for quick access)
                 -- Use last_dismissed_at timestamp (most recent first) for recently dismissed notes
                 CASE WHEN last_dismissed_at IS NOT NULL THEN 0 ELSE 1 END,
                 last_dismissed_at DESC,
                 -- QUATERNARY: by reminder time (soonest first)
                 reminder_datetime ASC,
                 -- QUINARY: priority
                 CASE priority
                   WHEN 'high' THEN 0
                   WHEN 'medium' THEN 1
                   WHEN 'low' THEN 2
                   ELSE 3
                 END,
                 -- FINAL: creation time (newest first)
                 created_at DESC
    """, (status,))
    notes = [dict(row) for row in c.fetchall()]

    conn.close()
    return notes


def update_note(note_id: str, title: Optional[str] = None,
                content: Optional[str] = None, status: Optional[str] = None,
                collapsed: Optional[bool] = None, priority: Optional[str] = None,
                reminder_datetime: Optional[str] = None,
                reminder_triggered: Optional[bool] = None,
                is_pinned: Optional[bool] = None,
                clear_reminder: bool = False,
                clear_reminder_datetime: bool = False,
                mark_dismissed: bool = False) -> None:  # v2.9.28: Mark note as recently dismissed
    """v2.9.36: อัปเดตโน้ต — ส่งแค่ฟิลด์ที่เปลี่ยน (thread-safe with lock)"""
    with DB_WRITE_LOCK:  # v2.9.36: Prevent concurrent note updates
        conn = _get_db_connection()  # v2.9.22: WAL-enabled connection
        c = conn.cursor()

        updates = []
        params = []

        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if content is not None:
            updates.append("content = ?")
            params.append(content)
        if status is not None:
            updates.append("status = ?")
            params.append(status)
            if status == "completed":
                updates.append("completed_at = ?")
                params.append(datetime.now().isoformat())
        if collapsed is not None:
            updates.append("collapsed = ?")
            params.append(collapsed)
        if priority is not None:
            updates.append("priority = ?")
            params.append(priority)
        # v2.8.3: Handle reminder_datetime clearing
        # v2.9.26: Added clear_reminder_datetime for selective clearing (keeps reminder_triggered state)
        if clear_reminder:
            updates.append("reminder_datetime = NULL")
            updates.append("reminder_triggered = 0")
        elif clear_reminder_datetime:
            updates.append("reminder_datetime = NULL")
        elif reminder_datetime is not None:
            updates.append("reminder_datetime = ?")
            params.append(reminder_datetime)
        if reminder_triggered is not None and not clear_reminder:
            updates.append("reminder_triggered = ?")
            params.append(reminder_triggered)
        if is_pinned is not None:
            # v1.5.0: Add pinning support
            updates.append("is_pinned = ?")
            params.append(is_pinned)

        # v2.9.28: Mark note as recently dismissed (for pinning at top of board)
        if mark_dismissed:
            updates.append("last_dismissed_at = ?")
            params.append(datetime.now().isoformat())

        if updates:
            params.append(note_id)
            sql = "UPDATE notes SET " + ", ".join(updates) + " WHERE id = ?"
            c.execute(sql, params)
            conn.commit()

        conn.close()


def update_note_status_only(note_id: str, status: str,
                           reminder_triggered: Optional[bool] = None) -> None:
    """v2.9.36: อัปเดตสถานะของโน้ตเท่านั้น (thread-safe with lock)"""
    with DB_WRITE_LOCK:  # v2.9.36: Prevent concurrent status updates
        conn = _get_db_connection()  # v2.9.22: WAL-enabled connection
        c = conn.cursor()

        updates = []
        params = []

        # Always update status
        updates.append("status = ?")
        params.append(status)

        if status == "completed":
            updates.append("completed_at = ?")
            params.append(datetime.now().isoformat())

        # Optional: update reminder_triggered
        if reminder_triggered is not None:
            updates.append("reminder_triggered = ?")
            params.append(reminder_triggered)

        if updates:
            params.append(note_id)
            sql = "UPDATE notes SET " + ", ".join(updates) + " WHERE id = ?"
            c.execute(sql, params)
            conn.commit()

        conn.close()


def delete_note(note_id: str) -> None:
    """v2.9.36: ลบโน้ต (thread-safe with lock)"""
    with DB_WRITE_LOCK:  # v2.9.36: Prevent concurrent note deletion
        conn = _get_db_connection()  # v2.9.22: WAL-enabled connection
        c = conn.cursor()
        c.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        conn.commit()
        conn.close()


def get_note(note_id: str) -> Optional[dict]:
    """อ่านโน้ตเดียว"""
    conn = _get_db_connection()  # v2.9.22: WAL-enabled connection
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
    row = c.fetchone()

    conn.close()
    return dict(row) if row else None


def get_next_due_reminder() -> Optional[str]:
    """v2.2.3: Get the next due reminder datetime for UI display

    Returns the earliest reminder_datetime that:
    - Has a value (not NULL)
    - Not yet triggered
    - Chronologically in the future (greater than current time)

    Format: "YYYY-MM-DD HH:MM" or None if no due reminders
    """
    try:
        from datetime import datetime
        conn = _get_db_connection()  # v2.9.22: WAL-enabled connection
        c = conn.cursor()

        # Get current time in ISO format (YYYY-MM-DD HH:MM)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Find earliest reminder that's not triggered and in the future
        c.execute("""
            SELECT MIN(reminder_datetime) FROM notes
            WHERE reminder_datetime IS NOT NULL
            AND reminder_triggered = 0
            AND reminder_datetime > ?
        """, (now_str,))

        result = c.fetchone()
        conn.close()

        if result and result[0]:
            return result[0]
        return None
    except Exception:
        return None


def sanitize_reminders() -> None:
    """v2.2.2: Clean corrupted reminder datetime values

    Fixes reminders with invalid format:
    - Length != 16 chars (YYYY-MM-DD HH:MM is exactly 16)
    - Format doesn't match YYYY-MM-DD HH:MM pattern

    Sets reminder_datetime = NULL for any corrupted values
    """
    try:
        conn = _get_db_connection()  # v2.9.22: WAL-enabled connection
        c = conn.cursor()

        # Get all reminders
        c.execute("SELECT id, reminder_datetime FROM notes WHERE reminder_datetime IS NOT NULL")
        rows = c.fetchall()

        cleaned = 0
        for row_id, reminder_str in rows:
            # Validate format: must be exactly "YYYY-MM-DD HH:MM" (16 chars)
            if not reminder_str or len(str(reminder_str)) != 16:
                # Invalid length — clear it
                c.execute("UPDATE notes SET reminder_datetime = NULL WHERE id = ?", (row_id,))
                cleaned += 1
                continue

            # Validate format: must parse as YYYY-MM-DD HH:MM
            try:
                datetime.strptime(str(reminder_str), "%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                # Invalid format — clear it
                c.execute("UPDATE notes SET reminder_datetime = NULL WHERE id = ?", (row_id,))
                cleaned += 1

        if cleaned > 0:
            conn.commit()
            print(f"[Sanitize] Cleaned {cleaned} corrupted reminder(s)")

        conn.close()
    except Exception as e:
        print(f"[Sanitize Error] {e}")


def backup_database(target_path: str) -> bool:
    """v2.4.0: Backup database to specified location

    Args:
        target_path: Full file path where backup should be saved (e.g., "C:/Users/user/Desktop/notes_backup.db")

    Returns:
        True if backup successful, False otherwise
    """
    try:
        import shutil
        # Ensure source database exists
        if not DB_FILE.exists():
            return False
        # Copy database file to target location
        shutil.copy2(str(DB_FILE), target_path)
        return True
    except Exception as e:
        print(f"[Backup Error] {e}")
        return False


def restore_database(backup_path: str) -> bool:
    """v2.4.0: Restore database from backup file

    Args:
        backup_path: Full file path of backup database to restore (e.g., "C:/Users/user/Desktop/notes_backup.db")

    Returns:
        True if restore successful, False otherwise
    """
    try:
        import shutil
        # Ensure backup file exists
        backup_file = Path(backup_path)
        if not backup_file.exists():
            return False

        # Close any open connections (safety measure)
        try:
            conn = _get_db_connection()  # v2.9.22: WAL-enabled connection
            conn.close()
        except Exception:
            pass

        # Restore by copying backup over current database
        shutil.copy2(str(backup_path), str(DB_FILE))

        # Verify database integrity (run migrations)
        init_db()
        return True
    except Exception as e:
        print(f"[Restore Error] {e}")
        return False


if __name__ == "__main__":
    init_db()
    print(f"[OK] Database initialized at {DB_FILE}")
