"""SQLite3 database for QuickNote — ดูแลโครงสร้างดาตาเบสและฟังก์ชันพื้นฐาน"""

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional


APP_DIR = Path.home() / ".quicknote"
DB_FILE = APP_DIR / "notes.db"


def init_db() -> None:
    """สร้างโฟลเดอร์แอป + ตาราง notes ถ้ายังไม่มี"""
    APP_DIR.mkdir(exist_ok=True)

    conn = sqlite3.connect(DB_FILE)
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
            is_pinned BOOLEAN DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()
    _migrate_db_schema()  # v1.3.0: ensure old DB gets new columns
    sanitize_reminders()  # v2.2.2: clean corrupted reminder times on startup


def _migrate_db_schema() -> None:
    """ตรวจและเพิ่มคอลัมน์ใหม่สำหรับ v1.3.0+ (priority, reminders, pinning)"""
    conn = sqlite3.connect(DB_FILE)
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

        conn.commit()
    except sqlite3.OperationalError as e:
        # ถ้า constraint ขัดแย้ง ให้ rollback ซ้ำ ไม่ต้องทำลายฐานข้อมูล
        conn.rollback()
    finally:
        conn.close()


def create_note(title: str, content: str = "") -> str:
    """เพิ่มโน้ตใหม่ — คืนค่า id"""
    note_id = uuid.uuid4().hex
    conn = sqlite3.connect(DB_FILE)
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
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT * FROM notes ORDER BY created_at DESC")
    notes = [dict(row) for row in c.fetchall()]

    conn.close()
    return notes


def get_notes_by_status(status: str) -> list[dict]:
    """อ่านโน้ตตามสถานะ (active/completed) — v2.8.2: Absolute sort by newest triggered reminder"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # v2.8.2: Sort by reminder_triggered DESC, then by reminder_datetime DESC (newest triggered on top)
    # Then pinned, priority, created_at for stable secondary ordering
    c.execute("""
        SELECT * FROM notes
        WHERE status = ?
        ORDER BY reminder_triggered DESC,
                 reminder_datetime DESC,
                 is_pinned DESC,
                 CASE priority
                   WHEN 'high' THEN 0
                   WHEN 'medium' THEN 1
                   WHEN 'low' THEN 2
                   ELSE 3
                 END,
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
                clear_reminder: bool = False) -> None:
    """อัปเดตโน้ต — ส่งแค่ฟิลด์ที่เปลี่ยน (v2.8.3: added clear_reminder flag)"""
    conn = sqlite3.connect(DB_FILE)
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
    if clear_reminder:
        updates.append("reminder_datetime = NULL")
        updates.append("reminder_triggered = 0")
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

    if updates:
        params.append(note_id)
        sql = "UPDATE notes SET " + ", ".join(updates) + " WHERE id = ?"
        c.execute(sql, params)
        conn.commit()

    conn.close()


def update_note_status_only(note_id: str, status: str,
                           reminder_triggered: Optional[bool] = None) -> None:
    """อัปเดตสถานะของโน้ตเท่านั้น (v1.3.9: prevent title/content corruption on status change)"""
    conn = sqlite3.connect(DB_FILE)
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
    """ลบโน้ต"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.commit()
    conn.close()


def get_note(note_id: str) -> Optional[dict]:
    """อ่านโน้ตเดียว"""
    conn = sqlite3.connect(DB_FILE)
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
        conn = sqlite3.connect(DB_FILE)
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
        conn = sqlite3.connect(DB_FILE)
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
            conn = sqlite3.connect(DB_FILE)
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
