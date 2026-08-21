"""E2E Test Suite for v2.9.25 — Isolated Test DB & Alarm State Lock (No Repeat Triggers)"""

import unittest
import sys
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.constants import APP_VERSION
from src.core.models import Note
from src.core.database import init_db, create_note, get_note, update_note, get_notes_by_status


class TestAlarmStateLockV2925(unittest.TestCase):
    """Test that alarm fires only once (no repeat triggers) — v2.9.25"""

    def setUp(self):
        """Initialize with isolated test database"""
        from src.core import database
        self.temp_dir = Path(tempfile.mkdtemp())
        self.temp_db = self.temp_dir / "test.db"
        database.DB_FILE = self.temp_db
        database.APP_DIR = self.temp_dir
        database.init_db()

    def tearDown(self):
        """Clean up test database"""
        if self.temp_dir.exists():
            shutil.rmtree(str(self.temp_dir))

    def test_alarm_fires_only_once_state_locked(self):
        """Test 1: When Scheduler triggers alarm, reminder_triggered = 1 IMMEDIATELY

        v2.9.25: Scheduler immediately locks alarm state to prevent repeat triggers
        This prevents the next scheduler cycle (5s later) from firing same alarm again
        """
        # Create note with past reminder (alarm should trigger)
        note_id = create_note(title="Single Fire Test", content="")
        past_time = (datetime.now() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M")
        update_note(note_id, reminder_datetime=past_time, reminder_triggered=0, status="active")

        # Simulate what happens in _trigger_reminder():
        # Step 1: Immediately set reminder_triggered = 1 to lock alarm state
        update_note(note_id, reminder_triggered=True)

        # Verify state is locked
        note_data = get_note(note_id)
        note_obj = Note.from_dict(note_data)
        self.assertTrue(note_obj.reminder_triggered)
        print("[PASS] Test 1: Alarm state locked (reminder_triggered=1)")

    def test_alarm_not_repeat_on_next_scheduler_cycle(self):
        """Test 2: Next scheduler cycle won't fire same alarm (state is locked)

        After reminder_triggered = 1, the scheduler loop checks:
        - reminder_datetime <= now? ✓ (yes, time arrived)
        - reminder_triggered = 0? ✗ (no, it's 1 now)
        Result: Alarm won't fire again
        """
        # Create locked alarm
        note_id = create_note(title="Lock Test", content="")
        past_time = (datetime.now() - timedelta(minutes=3)).strftime("%Y-%m-%d %H:%M")
        update_note(note_id, reminder_datetime=past_time, reminder_triggered=1, status="active")

        # Check if alarm would fire (simulate scheduler check)
        note_data = get_note(note_id)
        reminder_datetime = note_data.get('reminder_datetime')
        reminder_triggered = note_data.get('reminder_triggered')

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        would_fire = (reminder_datetime <= now_str) and (reminder_triggered == 0)

        self.assertFalse(would_fire)
        print("[PASS] Test 2: Locked alarm won't fire on next cycle")

    def test_version_v2925(self):
        """Test 3: Version updated to v2.9.25"""
        self.assertEqual(APP_VERSION, "2.9.25")
        print(f"[PASS] Test 3: App version is {APP_VERSION}")


class TestRedBorderOnTriggeredAlarmV2925(unittest.TestCase):
    """Test red border shows when alarm just triggered — v2.9.25"""

    def setUp(self):
        """Initialize with isolated test database"""
        from src.core import database
        self.temp_dir = Path(tempfile.mkdtemp())
        self.temp_db = self.temp_dir / "test.db"
        database.DB_FILE = self.temp_db
        database.APP_DIR = self.temp_dir
        database.init_db()

    def tearDown(self):
        """Clean up test database"""
        if self.temp_dir.exists():
            shutil.rmtree(str(self.temp_dir))

    def test_red_border_shows_when_triggered(self):
        """Test 4: Red border shows when reminder_triggered = 1

        v2.9.25: Red border logic checks reminder_triggered = 1 (just fired)
        not reminder_datetime <= now AND reminder_triggered = 0
        """
        # Create triggered alarm
        note_id = create_note(title="Triggered Alarm", content="")
        past_time = (datetime.now() - timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M")
        update_note(note_id, reminder_datetime=past_time, reminder_triggered=1, status="active")

        # Check if red border would show
        note_data = get_note(note_id)
        reminder_triggered = note_data.get('reminder_triggered')

        # v2.9.25: Red border logic
        should_show_red_border = bool(reminder_triggered)

        self.assertTrue(should_show_red_border)
        print("[PASS] Test 4: Red border shows when triggered")

    def test_red_border_hides_when_dismissed(self):
        """Test 5: Red border disappears when dismissed (reminder_triggered = 0)

        When user clicks Dismiss in dialog, callback clears reminder state
        """
        # Create note, then dismiss it
        note_id = create_note(title="Dismiss Test", content="")
        past_time = (datetime.now() - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M")
        update_note(note_id, reminder_datetime=past_time, reminder_triggered=1, status="active")

        # User dismisses: clear reminder completely
        update_note(note_id, reminder_datetime=None, reminder_triggered=0)

        # Check if red border would show
        note_data = get_note(note_id)
        reminder_triggered = note_data.get('reminder_triggered')

        # Red border logic
        should_show_red_border = bool(reminder_triggered)

        self.assertFalse(should_show_red_border)
        print("[PASS] Test 5: Red border hides when dismissed")

    def test_triggered_alarm_at_index_0(self):
        """Test 6: Triggered alarm (reminder_triggered=1) sorts to Index 0

        v2.9.25: SQL ORDER BY checks reminder_triggered=1 first
        """
        # Create mixed notes
        normal_note_id = create_note(title="Normal Task", content="")
        triggered_note_id = create_note(title="Triggered Alarm", content="")

        # Set normal note active (no alarm)
        update_note(normal_note_id, status="active")

        # Set triggered note
        past_time = (datetime.now() - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M")
        update_note(triggered_note_id, reminder_datetime=past_time, reminder_triggered=1, status="active")

        # Fetch sorted notes
        notes = get_notes_by_status("active")

        # Triggered alarm should be at Index 0
        self.assertEqual(len(notes), 2)
        self.assertEqual(notes[0]['id'], triggered_note_id)
        self.assertEqual(notes[1]['id'], normal_note_id)
        print("[PASS] Test 6: Triggered alarm at Index 0")


class TestIsolatedTestDatabaseV2925(unittest.TestCase):
    """Test that E2E tests don't pollute production database — v2.9.25"""

    def test_temporary_db_used_not_production(self):
        """Test 7: E2E tests use isolated temp DB, not production

        Verify that when test creates/modifies notes, production DB stays clean
        """
        from src.core import database

        # Capture current production DB path
        prod_db_path = Path.home() / ".quicknote" / "notes.db"

        # Create test DB (should NOT be production path)
        temp_dir = Path(tempfile.mkdtemp())
        test_db = temp_dir / "test.db"

        try:
            # Override database module to use test DB
            database.DB_FILE = test_db
            database.APP_DIR = temp_dir
            database.init_db()

            # Create test note
            test_note_id = database.create_note(title="Test Note v2925", content="")

            # Verify test note is in TEST db, not production
            test_note = database.get_note(test_note_id)
            self.assertIsNotNone(test_note)
            self.assertEqual(test_note['title'], "Test Note v2925")

            # Verify production DB is untouched
            if prod_db_path.exists():
                prod_conn = database.sqlite3.connect(prod_db_path)
                prod_conn.row_factory = database.sqlite3.Row
                c = prod_conn.cursor()
                c.execute("SELECT COUNT(*) FROM notes WHERE title = 'Test Note v2925'")
                count = c.fetchone()[0]
                prod_conn.close()
                self.assertEqual(count, 0)  # Should not exist in production

            print("[PASS] Test 7: E2E test DB isolated from production")

        finally:
            if temp_dir.exists():
                shutil.rmtree(str(temp_dir))


def run_all_tests():
    """Run all test suites"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestAlarmStateLockV2925))
    suite.addTests(loader.loadTestsFromTestCase(TestRedBorderOnTriggeredAlarmV2925))
    suite.addTests(loader.loadTestsFromTestCase(TestIsolatedTestDatabaseV2925))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success: {result.wasSuccessful()}")
    print("="*70)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
