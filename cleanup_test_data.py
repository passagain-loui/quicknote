#!/usr/bin/env python3
"""Cleanup script to remove test data from production database

Removes all Notes with titles containing test keywords from ~/.quicknote/notes.db
to ensure E2E test data doesn't pollute production environment.
"""

import sqlite3
from pathlib import Path

DB_FILE = Path.home() / ".quicknote" / "notes.db"

def cleanup_test_data():
    """Remove test data from production database"""
    if not DB_FILE.exists():
        print(f"[INFO] No production database found at {DB_FILE}")
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        # Get all notes with test keywords in title
        test_keywords = ['Test', 'test', '292', '291', '290', 'Alarm', 'alarm']

        total_deleted = 0
        for keyword in test_keywords:
            c.execute("SELECT COUNT(*) FROM notes WHERE title LIKE ?", (f"%{keyword}%",))
            count = c.fetchone()[0]
            if count > 0:
                c.execute("DELETE FROM notes WHERE title LIKE ?", (f"%{keyword}%",))
                total_deleted += count
                print(f"[CLEANUP] Deleted {count} notes with '{keyword}' in title")

        if total_deleted > 0:
            conn.commit()
            print(f"[OK] Successfully deleted {total_deleted} test notes from production DB")
        else:
            print(f"[INFO] No test data found in production DB")

        conn.close()

    except Exception as e:
        print(f"[ERROR] Failed to cleanup test data: {e}")

if __name__ == "__main__":
    cleanup_test_data()
