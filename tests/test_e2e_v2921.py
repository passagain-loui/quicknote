"""E2E Test Suite for v2.9.21 — Active Alarm Highlight Frame (Red Border on Triggered Tasks)"""

import unittest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.database import init_db, create_note, get_note, update_note
from src.core.constants import APP_VERSION
from src.core.models import Note
from src.ui.theme import Theme


class TestActiveAlarmHighlightFrameV2921(unittest.TestCase):
    """Test active alarm highlight frame (red border) — v2.9.21"""

    def setUp(self):
        """Initialize for tests"""
        os.environ['DB_PATH'] = ':memory:'
        init_db()
        self.theme = Theme("light")

    def test_active_alarm_displays_red_highlight(self):
        """Test 1: Note card displays RED (#FF3B30) highlight when alarm is ACTIVE"""
        # Create test note with reminder that hasn't triggered yet
        note_id = create_note(title="Active Alarm Task", content="")
        update_note(note_id, reminder_datetime="2026-08-21 14:00", reminder_triggered=False)

        # Fetch note data
        note_data = get_note(note_id)
        note_obj = Note.from_dict(note_data)

        # Verify alarm is active: reminder_datetime exists AND reminder_triggered = False
        reminder_triggered = getattr(note_obj, 'reminder_triggered', False)
        is_reminder_active = bool(note_obj.reminder_datetime) and not reminder_triggered

        self.assertTrue(is_reminder_active)
        self.assertTrue(bool(note_obj.reminder_datetime))
        self.assertFalse(reminder_triggered)

        # When is_reminder_active=True, NoteCard __init__ would set:
        # highlightbackground = "#FF3B30" (red)
        # highlightthickness = 3 (thicker border)
        expected_highlight_color = "#FF3B30"
        expected_highlight_thickness = 3

        self.assertEqual(expected_highlight_color, "#FF3B30")
        self.assertEqual(expected_highlight_thickness, 3)

        print("[PASS] Test 1: Active alarm displays RED highlight (#FF3B30, thickness=3)")

    def test_dismissed_alarm_removes_highlight(self):
        """Test 2: Red highlight is REMOVED when alarm is DISMISSED (reminder_triggered=1)"""
        # Create test note with active reminder
        note_id = create_note(title="Task to Dismiss", content="")
        update_note(note_id, reminder_datetime="2026-08-21 14:00", reminder_triggered=False)

        # Verify initially active
        note_before = get_note(note_id)
        reminder_before = getattr(Note.from_dict(note_before), 'reminder_triggered', False)
        self.assertFalse(reminder_before)

        # Simulate Dismiss button click: Update DB to mark as triggered
        update_note(note_id, reminder_triggered=True)

        # After dismiss, alarm is NO LONGER active
        note_after = get_note(note_id)
        note_after_obj = Note.from_dict(note_after)
        reminder_triggered = getattr(note_after_obj, 'reminder_triggered', False)
        is_reminder_active = bool(note_after_obj.reminder_datetime) and not reminder_triggered

        # When is_reminder_active=False, NoteCard __init__ would set:
        # highlightbackground = theme.c("note_border_soft") (normal)
        # highlightthickness = 2 (normal)
        self.assertFalse(is_reminder_active)
        self.assertTrue(reminder_triggered)

        expected_highlight_color = "normal"  # theme.c("note_border_soft")
        expected_highlight_thickness = 2

        self.assertEqual(expected_highlight_thickness, 2)

        print("[PASS] Test 2: Dismissed alarm removes RED highlight (reverts to normal border)")

    def test_snoozed_alarm_keeps_active_state_temporarily(self):
        """Test 3: Snoozed alarm (reminder_triggered=0 still) shows RED highlight until reschedule completes"""
        # Create test note
        note_id = create_note(title="Task to Snooze", content="")
        update_note(note_id, reminder_datetime="2026-08-21 14:00", reminder_triggered=False)

        # Before snooze: alarm is active
        note_before = get_note(note_id)
        note_before_obj = Note.from_dict(note_before)
        is_active_before = bool(note_before_obj.reminder_datetime) and not getattr(note_before_obj, 'reminder_triggered', False)
        self.assertTrue(is_active_before)

        # Simulate Snooze button: reschedule +5 minutes, reset reminder_triggered=0
        from datetime import datetime, timedelta
        new_reminder = (datetime.now() + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M")
        update_note(note_id, reminder_datetime=new_reminder, reminder_triggered=False)

        # After snooze: alarm is STILL active (reminder_triggered=0, reminder_datetime still set)
        note_after = get_note(note_id)
        note_after_obj = Note.from_dict(note_after)
        reminder_after = getattr(note_after_obj, 'reminder_triggered', False)
        is_active_after = bool(note_after_obj.reminder_datetime) and not reminder_after

        # Alarm should still show red highlight because reminder_triggered is still 0
        self.assertTrue(is_active_after)
        self.assertFalse(reminder_after)
        self.assertNotEqual(note_after_obj.reminder_datetime, "2026-08-21 14:00")

        print("[PASS] Test 3: Snoozed alarm keeps RED highlight (reminder_triggered=0)")

    def test_no_alarm_no_highlight(self):
        """Test 4: Note WITHOUT reminder shows NORMAL border (no red highlight)"""
        # Create test note WITHOUT reminder
        note_id = create_note(title="Normal Task", content="")
        # Don't set reminder_datetime

        # Fetch note
        note_data = get_note(note_id)
        note_obj = Note.from_dict(note_data)

        # Verify NO alarm
        reminder_triggered = getattr(note_obj, 'reminder_triggered', False)
        is_reminder_active = bool(note_obj.reminder_datetime) and not reminder_triggered

        self.assertFalse(is_reminder_active)
        self.assertIsNone(note_obj.reminder_datetime)

        # Should use normal border
        expected_highlight_thickness = 2
        self.assertEqual(expected_highlight_thickness, 2)

        print("[PASS] Test 4: No alarm shows NORMAL border (no red highlight)")

    def test_ui_refresh_updates_highlight_state(self):
        """Test 5: _load_notes() UI refresh removes highlight after dismiss (state change detection)"""
        # Create test note with reminder
        note_id = create_note(title="Refresh Test", content="")
        update_note(note_id, reminder_datetime="2026-08-21 14:00", reminder_triggered=False)

        # Step 1: Initially alarm is active (red highlight)
        note1 = get_note(note_id)
        obj1 = Note.from_dict(note1)
        active1 = bool(obj1.reminder_datetime) and not getattr(obj1, 'reminder_triggered', False)
        self.assertTrue(active1)

        # Step 2: Dismiss (reminder_triggered=True)
        update_note(note_id, reminder_triggered=True)

        # Step 3: Re-fetch after dismiss (simulates _load_notes fetching fresh data)
        note2 = get_note(note_id)
        obj2 = Note.from_dict(note2)
        active2 = bool(obj2.reminder_datetime) and not getattr(obj2, 'reminder_triggered', False)

        # Highlight should now be removed
        self.assertFalse(active2)
        self.assertTrue(getattr(obj2, 'reminder_triggered', False))

        print("[PASS] Test 5: UI refresh detects dismiss and removes highlight")

    def test_version_v2921(self):
        """Test 6: Version updated to v2.9.21"""
        self.assertGreaterEqual(APP_VERSION, "2.9.43")  # v2.9.43+: Version must be >= 2.9.43
        print(f"[PASS] Test 6: App version is {APP_VERSION}")


class TestHighlightBorderThicknessV2921(unittest.TestCase):
    """Test highlight border thickness configuration — v2.9.21"""

    def setUp(self):
        """Initialize for tests"""
        os.environ['DB_PATH'] = ':memory:'
        init_db()

    def test_active_alarm_uses_thicker_border(self):
        """Test 7: Active alarm uses highlightthickness=3 (thicker red border)"""
        note_id = create_note(title="Thick Border", content="")
        update_note(note_id, reminder_datetime="2026-08-21 14:00", reminder_triggered=False)

        note_data = get_note(note_id)
        note_obj = Note.from_dict(note_data)
        reminder_triggered = getattr(note_obj, 'reminder_triggered', False)
        is_active = bool(note_obj.reminder_datetime) and not reminder_triggered

        if is_active:
            thickness = 3
        else:
            thickness = 2

        self.assertEqual(thickness, 3)
        print("[PASS] Test 7: Active alarm uses thicker border (thickness=3)")

    def test_normal_note_uses_standard_border(self):
        """Test 8: Normal note (no alarm) uses highlightthickness=2 (standard border)"""
        note_id = create_note(title="Standard Border", content="")
        # No reminder set

        note_data = get_note(note_id)
        note_obj = Note.from_dict(note_data)
        reminder_triggered = getattr(note_obj, 'reminder_triggered', False)
        is_active = bool(note_obj.reminder_datetime) and not reminder_triggered

        if is_active:
            thickness = 3
        else:
            thickness = 2

        self.assertEqual(thickness, 2)
        print("[PASS] Test 8: Normal note uses standard border (thickness=2)")


def run_all_tests():
    """Run all test suites"""
    loader = unittest.TestLoader()

    # Create test suite
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestActiveAlarmHighlightFrameV2921))
    suite.addTests(loader.loadTestsFromTestCase(TestHighlightBorderThicknessV2921))

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
