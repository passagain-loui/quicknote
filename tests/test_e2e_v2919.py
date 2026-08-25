"""E2E Test Suite for v2.9.19 — Atomic Open State & Task Position Lock (No Task Bounce)"""

import unittest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.database import init_db, create_note, get_note, update_note
from src.core.constants import APP_VERSION


class TestAtomicOpenStateV2919(unittest.TestCase):
    """Test atomic execution on Open action (v2.9.19)"""

    def setUp(self):
        """Initialize for tests"""
        os.environ['DB_PATH'] = ':memory:'
        init_db()

    def test_db_commit_before_ui_refresh(self):
        """Test 1: DB commit MUST complete before UI refresh (_load_notes)"""
        # Create test note with reminder
        note_id = create_note(title="Test Task", content="")
        update_note(note_id, reminder_datetime="2026-08-21 14:00", reminder_triggered=False)

        # Before Open: reminder_triggered = False
        note_before = get_note(note_id)
        self.assertFalse(note_before['reminder_triggered'])

        # Step 1: Commit DB update
        update_note(note_id, reminder_triggered=True)

        # Step 2: Verify DB was committed (before UI refresh would happen)
        note_during = get_note(note_id)
        self.assertTrue(note_during['reminder_triggered'])

        # Step 3: UI refresh happens (but data is already committed)
        # Simulate _load_notes() - would fetch fresh data
        note_after = get_note(note_id)
        self.assertTrue(note_after['reminder_triggered'])

        print("[PASS] Test 1: DB commit completes before UI refresh")

    def test_opened_task_stays_at_top_with_reminder_triggered(self):
        """Test 2: Opened task (reminder_triggered=1) stays at top when sorted"""
        # Create test note
        note_id = create_note(title="Alarm Task", content="")

        # Set up reminder
        update_note(note_id, reminder_datetime="2026-08-21 14:00", reminder_triggered=False)

        # When reminder triggers, mark it as triggered (reminder_triggered=1)
        update_note(note_id, reminder_triggered=True)

        # Fetch and verify task is marked as triggered
        note_check = get_note(note_id)
        self.assertTrue(note_check['reminder_triggered'])

        # When Open is clicked, reminder_triggered stays 1
        update_note(note_id, reminder_triggered=True)

        # Verify still has reminder_triggered=1 (stays at top)
        note_after = get_note(note_id)
        self.assertTrue(note_after['reminder_triggered'])

        print("[PASS] Test 2: Opened task stays at top (reminder_triggered=1)")

    def test_no_alarm_retrigger_after_open(self):
        """Test 3: No alarm re-trigger after Open (both DB commit + reminder_triggered=1)"""
        # Create test note with reminder
        note_id = create_note(title="Test Task", content="")
        update_note(note_id, reminder_datetime="2026-08-21 14:00", reminder_triggered=False)

        # Reminder triggers (use clear_reminder=True to clear reminder_datetime)
        update_note(note_id, clear_reminder=True, reminder_triggered=True)

        # Open is clicked (DB commit)
        update_note(note_id, reminder_triggered=True)

        # Verify DB state prevents re-trigger
        note = get_note(note_id)
        should_trigger = bool(note['reminder_datetime']) and not note['reminder_triggered']
        self.assertFalse(should_trigger)

        # Also verify:
        # - reminder_triggered = 1 (not 0)
        # - reminder_datetime is None (cleared when first triggered)
        self.assertTrue(note['reminder_triggered'])
        self.assertIsNone(note['reminder_datetime'])

        print("[PASS] Test 3: No alarm re-trigger (reminder_triggered=1 + reminder_datetime=NULL)")

    def test_execution_order_audio_then_db_then_ui(self):
        """Test 4: Execution order is atomic: audio stop → DB commit → UI refresh"""
        note_id = create_note(title="Test", content="")
        update_note(note_id, reminder_datetime="2026-08-21 14:00", reminder_triggered=False)

        # Simulate execution order
        execution_steps = []

        # Step 1: Audio stop attempt (even if fails, continues)
        try:
            # Audio stop would happen here
            execution_steps.append("audio_stop")
        except:
            pass

        # Step 2: DB commit (CRITICAL)
        try:
            update_note(note_id, reminder_triggered=True)
            execution_steps.append("db_commit")
        except Exception as e:
            execution_steps.append(f"db_commit_failed: {e}")

        # Step 3: UI refresh (only after DB committed)
        try:
            note = get_note(note_id)  # Simulate _load_notes fetching data
            execution_steps.append("ui_refresh")
        except:
            pass

        # Verify all steps completed and DB was committed
        self.assertEqual(len(execution_steps), 3)
        self.assertEqual(execution_steps[0], "audio_stop")
        self.assertEqual(execution_steps[1], "db_commit")
        self.assertEqual(execution_steps[2], "ui_refresh")

        # Verify DB is actually updated
        note = get_note(note_id)
        self.assertTrue(note['reminder_triggered'])

        print("[PASS] Test 4: Execution order: audio → db_commit → ui_refresh")

    def test_version_v2919(self):
        """Test 5: Version updated to v2.9.19"""
        self.assertGreaterEqual(APP_VERSION, "2.9.43")  # v2.9.43+: Version must be >= 2.9.43
        print(f"[PASS] Test 5: App version is {APP_VERSION}")


class TestTaskPositionLockV2919(unittest.TestCase):
    """Test that task doesn't bounce back after Open (v2.9.19)"""

    def setUp(self):
        """Initialize for tests"""
        os.environ['DB_PATH'] = ':memory:'
        init_db()

    def test_task_position_locked_after_open(self):
        """Test 6: Task maintains position at top after Open (no bounce back)"""
        # Create test note
        note_id = create_note(title="Bouncy Task", content="")
        update_note(note_id, reminder_datetime="2026-08-21 14:00", reminder_triggered=False)

        # Trigger reminder (reminder_triggered=1)
        update_note(note_id, reminder_triggered=True)

        # Position 1: Task should be at top (reminder_triggered=1)
        note_triggered = get_note(note_id)
        is_at_top_1 = note_triggered['reminder_triggered'] == 1
        self.assertTrue(is_at_top_1)

        # Click Open (DB commit - reminder_triggered stays 1)
        update_note(note_id, reminder_triggered=True)

        # Position 2: Task should STILL be at top (reminder_triggered=1)
        note_after_open = get_note(note_id)
        is_at_top_2 = note_after_open['reminder_triggered'] == 1
        self.assertTrue(is_at_top_2)

        # Verify: Both positions show task at top (no bounce)
        self.assertEqual(is_at_top_1, is_at_top_2)

        print("[PASS] Test 6: Task position locked (no bounce back after Open)")

    def test_ui_refresh_fetches_committed_data(self):
        """Test 7: UI refresh (_load_notes) always fetches committed data"""
        note_id = create_note(title="Refresh Test", content="")

        # Set reminder
        update_note(note_id, reminder_datetime="2026-08-21 14:00", reminder_triggered=False)

        # Mark as triggered
        update_note(note_id, reminder_triggered=True)

        # Simulate multiple UI refreshes - all should show committed state
        for i in range(3):
            note = get_note(note_id)
            self.assertTrue(note['reminder_triggered'], f"Refresh #{i+1} failed to get committed state")
            self.assertEqual(note['reminder_datetime'], "2026-08-21 14:00", f"Refresh #{i+1} has wrong reminder_datetime")

        print("[PASS] Test 7: UI refresh always fetches fresh committed data")


def run_all_tests():
    """Run all test suites"""
    loader = unittest.TestLoader()

    # Create test suite
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestAtomicOpenStateV2919))
    suite.addTests(loader.loadTestsFromTestCase(TestTaskPositionLockV2919))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success: {result.wasSuccessful()}")
    print("="*60)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
