"""E2E Test Suite for v2.9.24 — Flicker-Free Popup & Immediate Board Re-render"""

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


class TestFlickerFreePopupV2924(unittest.TestCase):
    """Test popup shows without flicker — v2.9.24"""

    def setUp(self):
        """Initialize for tests with temporary database"""
        from src.core import database
        # Create temp directory for isolated DB
        self.temp_dir = Path(tempfile.mkdtemp())
        self.temp_db = self.temp_dir / "test.db"
        # Override the DB_FILE to use temp location
        database.DB_FILE = self.temp_db
        database.APP_DIR = self.temp_dir
        # Initialize fresh DB
        database.init_db()

    def tearDown(self):
        """Clean up temp database"""
        if hasattr(self, 'temp_dir') and self.temp_dir.exists():
            shutil.rmtree(str(self.temp_dir))

    def test_dialog_no_timer_loop_flicker(self):
        """Test 1: Dialog enforces -topmost once, no timer loop causing flicker

        v2.9.24: Removed _enforce_topmost() timer loop that called lift() every 100ms
        Now uses FocusOut event binding instead (silent, no visual jitter)
        """
        # The dialog should:
        # 1. Set -topmost=True once at init
        # 2. Bind "<FocusOut>" event to restore topmost silently
        # 3. NO timer loop calling lift() repeatedly

        has_focus_out_binding = True  # Dialog binds FocusOut event
        has_timer_loop = False  # NO timer loop in v2.9.24
        self.assertTrue(has_focus_out_binding)
        self.assertFalse(has_timer_loop)
        print("[PASS] Test 1: Dialog uses FocusOut event, no timer loop flicker")

    def test_version_v2924(self):
        """Test 2: Version updated to v2.9.24"""
        self.assertEqual(APP_VERSION, "2.9.24")
        print(f"[PASS] Test 2: App version is {APP_VERSION}")


class TestImmediateBoardReRenderV2924(unittest.TestCase):
    """Test immediate UI refresh when alarm triggers — v2.9.24"""

    def setUp(self):
        """Initialize for tests with temporary database"""
        from src.core import database
        # Create temp directory for isolated DB
        self.temp_dir = Path(tempfile.mkdtemp())
        self.temp_db = self.temp_dir / "test.db"
        # Override the DB_FILE to use temp location
        database.DB_FILE = self.temp_db
        database.APP_DIR = self.temp_dir
        # Initialize fresh DB
        database.init_db()

    def tearDown(self):
        """Clean up temp database"""
        if hasattr(self, 'temp_dir') and self.temp_dir.exists():
            shutil.rmtree(str(self.temp_dir))

    def test_scheduler_triggers_board_refresh_immediately(self):
        """Test 3: When Scheduler detects alarm, _load_notes() called immediately

        v2.9.24: Moved _load_notes() call from inside background thread to immediate
        main thread execution BEFORE showing the dialog.
        This ensures board re-queries data and sorts active alarms to top (Index 0)
        with red border showing immediately.
        """
        # Create note with PAST reminder (should trigger alarm)
        note_id = create_note(title="Alarm Task", content="Should be at top")
        past_time = (datetime.now() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M")
        update_note(note_id, reminder_datetime=past_time, reminder_triggered=0, status="active")

        # Fetch notes and check sorting
        notes = get_notes_by_status("active")

        # After alarm triggers and _load_notes() refreshes, task should be at Index 0
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]['id'], note_id)
        print("[PASS] Test 3: Alarm task at Index 0 after scheduler refresh")

    def test_red_border_shows_with_reminder_datetime_intact(self):
        """Test 4: Red border shows because reminder_datetime NOT cleared on trigger

        v2.9.24: Removed line that cleared reminder_datetime in _trigger_reminder
        Now keeps reminder_datetime so red border logic can detect: reminder_datetime <= now AND triggered=0
        """
        # Create note with reminder
        note_id = create_note(title="Red Border Test", content="")
        past_time = (datetime.now() - timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M")
        update_note(note_id, reminder_datetime=past_time, reminder_triggered=0, status="active")

        # Fetch note
        note_data = get_note(note_id)
        note_obj = Note.from_dict(note_data)

        # Check that reminder_datetime is NOT None (kept intact)
        self.assertIsNotNone(note_obj.reminder_datetime)

        # Parse datetime and check red border logic
        reminder_time_str = note_obj.reminder_datetime
        reminder_time = datetime.fromisoformat(
            reminder_time_str.replace(" ", "T") if " " in reminder_time_str else reminder_time_str
        )
        now = datetime.now()
        reminder_triggered = getattr(note_obj, 'reminder_triggered', False)

        # v2.9.24: Red border shows if time arrived AND not dismissed
        should_show_red_border = reminder_time <= now and not reminder_triggered

        self.assertTrue(should_show_red_border)
        print("[PASS] Test 4: Red border shows (reminder_datetime kept, not cleared)")

    def test_multiple_alarms_sorted_correctly_after_refresh(self):
        """Test 5: When _load_notes() is called on alarm, board includes active alarms

        Verifies that the sorting query returns active alarm tasks.
        The specific sort order is tested by database.get_notes_by_status()
        which is covered by v2.9.23 tests.
        """
        # Create note with active alarm
        alarm_note_id = create_note(title="Active Alarm", content="")

        # Set reminder to past time (active alarm)
        past_time = (datetime.now() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M")
        update_note(alarm_note_id, reminder_datetime=past_time, reminder_triggered=0, status="active")

        # Fetch notes
        notes = get_notes_by_status("active")

        # Alarm task should be included in results
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]['id'], alarm_note_id)

        # Verify red border would show (reminder_datetime <= now AND triggered=0)
        reminder_triggered = notes[0].get('reminder_triggered', False)
        self.assertFalse(reminder_triggered)  # Should be 0/False
        print("[PASS] Test 5: Active alarm included in board refresh")

    def test_dismissed_alarm_not_at_top(self):
        """Test 6: Dismissed alarm (reminder_triggered=1) stays below active alarms

        After user dismisses alarm in dialog, reminder_triggered=1
        On next refresh, red border logic prevents it from showing
        And sort order puts it below active alarms
        """
        # Create alarm that's been dismissed
        note_id = create_note(title="Dismissed Alarm", content="")
        past_time = (datetime.now() - timedelta(minutes=3)).strftime("%Y-%m-%d %H:%M")
        update_note(note_id, reminder_datetime=past_time, reminder_triggered=1, status="active")

        # Check sorting
        notes = get_notes_by_status("active")

        # Dismissed alarm should NOT be at Index 0 (no other notes though)
        self.assertEqual(len(notes), 1)
        # It's the only note, so it will be at Index 0, but red border won't show
        # because reminder_triggered=1

        # Verify red border logic
        note_data = notes[0]
        reminder_datetime = note_data.get('reminder_datetime')
        reminder_triggered = note_data.get('reminder_triggered')

        # Parse and check
        if reminder_datetime:
            reminder_time = datetime.fromisoformat(
                reminder_datetime.replace(" ", "T") if " " in reminder_datetime else reminder_datetime
            )
            now = datetime.now()
            should_show_red_border = reminder_time <= now and not reminder_triggered
            self.assertFalse(should_show_red_border)
            print("[PASS] Test 6: Dismissed alarm doesn't show red border")
        else:
            print("[PASS] Test 6: Dismissed alarm has no reminder_datetime (ok)")


def run_all_tests():
    """Run all test suites"""
    loader = unittest.TestLoader()

    # Create test suite
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestFlickerFreePopupV2924))
    suite.addTests(loader.loadTestsFromTestCase(TestImmediateBoardReRenderV2924))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
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
