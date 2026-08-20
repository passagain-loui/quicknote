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
            completed_at TIMESTAMP
        )
    """)

    conn.commit()
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
    """อ่านโน้ตตามสถานะ (active/completed)"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT * FROM notes WHERE status = ? ORDER BY created_at DESC", (status,))
    notes = [dict(row) for row in c.fetchall()]

    conn.close()
    return notes


def update_note(note_id: str, title: Optional[str] = None,
                content: Optional[str] = None, status: Optional[str] = None,
                collapsed: Optional[bool] = None) -> None:
    """อัปเดตโน้ต — ส่งแค่ฟิลด์ที่เปลี่ยน"""
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


if __name__ == "__main__":
    init_db()
    print(f"[OK] Database initialized at {DB_FILE}")
