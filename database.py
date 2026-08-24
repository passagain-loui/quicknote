import sqlite3

class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect('notes.db', check_same_thread=False, isolation_level=None)
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.execute('PRAGMA busy_timeout=5000')
        self.cursor = self.conn.cursor()

    def save_note(self, note):
        self.cursor.execute('INSERT INTO notes (content) VALUES (?)', (note,))
        self.conn.commit()

    def close(self):
        self.conn.close()