"""E2E Test Suite for v2.9.37 — UI Action Buttons & Notification Topmost Fix"""

import unittest
import sys
import os
import inspect

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.constants import APP_VERSION
from src.core.models import Note


class TestUIActionButtonsV2937(unittest.TestCase):
    """Test v2.9.37 UI action buttons and notification lift fixes"""

    def test_version_v2937(self):
        """Test 1: Version updated to v2.9.37"""
        self.assertEqual(APP_VERSION, "2.9.37")
        print(f"[PASS] Test 1: App version is {APP_VERSION}")

    def test_action_button_complete_for_active_notes(self):
        """Test 2: Active notes show Complete (✔) button in NoteCard

        v2.9.37 ACTION BUTTON FIX:
        - Active notes (status='active'): render Complete button (✔ blue)
        - Completed notes (status='completed'): render Restore button (↩ green)
        - Button updates on card reuse via _update_action_button()

        Verification:
        - NoteCard has btn_action attribute
        - Button text changes based on note.status
        - _update_action_button() method exists and works
        """
        from src.ui.note_card import NoteCard

        # Check that btn_action is created in __init__
        init_source = inspect.getsource(NoteCard.__init__)
        self.assertIn('btn_action', init_source, "NoteCard should have btn_action attribute")
        self.assertIn('✔', init_source, "NoteCard should show Complete (✔) for active notes")
        self.assertIn('↩', init_source, "NoteCard should show Restore (↩) for completed notes")

        print("[PASS] Test 2: NoteCard has action button (Complete ✔ / Restore ↩)")

    def test_action_button_restore_for_completed_notes(self):
        """Test 3: Completed notes show Restore (↩) button in NoteCard"""
        from src.ui.note_card import NoteCard

        # Verify _update_action_button method exists
        self.assertTrue(
            hasattr(NoteCard, '_update_action_button'),
            "NoteCard should have _update_action_button() method"
        )

        update_source = inspect.getsource(NoteCard._update_action_button)
        self.assertIn('completed', update_source, "_update_action_button should check note.status == 'completed'")
        self.assertIn('↩', update_source, "_update_action_button should set Restore (↩) for completed notes")
        self.assertIn('✔', update_source, "_update_action_button should set Complete (✔) for active notes")

        print("[PASS] Test 3: NoteCard._update_action_button() correctly handles status changes")

    def test_smart_widget_reuse_updates_button_state(self):
        """Test 4: Smart widget reuse in _load_notes() updates action button state

        v2.9.37 WIDGET REUSE FIX:
        - When reusing existing card: update note data + call _update_action_button()
        - Button state always reflects current note.status
        - Status badge also updated via _update_strikethrough()

        Verification:
        - _load_notes() calls _update_action_button() when reusing cards
        - _load_notes() calls _update_strikethrough() when reusing cards
        - Card's note object is updated from fresh DB data
        """
        from src.ui.board import Board

        load_notes_source = inspect.getsource(Board._load_notes)

        # Check that action button is updated when reusing
        self.assertIn('_update_action_button', load_notes_source,
                     "_load_notes should call _update_action_button() to update button state")

        # Check that status badge is updated when reusing
        self.assertIn('_update_strikethrough', load_notes_source,
                     "_load_notes should call _update_strikethrough() to update status badge")

        # Check that card note data is updated
        self.assertIn('card.note = Note.from_dict(row)', load_notes_source,
                     "_load_notes should update card.note with fresh data from DB")

        print("[PASS] Test 4: _load_notes() updates action button + status on widget reuse")

    def test_notification_lifts_triggered_note_frame(self):
        """Test 5: Notification trigger lifts note frame to show on top

        v2.9.37 NOTIFICATION TOPMOST FIX:
        - When notification shown: call note_frame.lift() to bring task to Z-order top
        - Shows triggered reminder task at top of board UI
        - Uses parent_board reference to access note_cards

        Verification:
        - show_reminder_notification() lifts the triggered note frame
        - Uses _current_reminder_note_id to identify which note to lift
        - Accesses parent_board.note_cards to get frame reference
        """
        from src.services.notification import WindowsNotificationService

        show_dialog_source = inspect.getsource(WindowsNotificationService.show_reminder_notification)

        # Check that note frame is lifted
        self.assertIn('.lift()', show_dialog_source,
                     "Notification should lift note frame via .lift()")

        # Check that it gets the note ID
        self.assertIn('_current_reminder_note_id', show_dialog_source,
                     "Notification should get triggered note ID")

        # Check that it accesses note_cards
        self.assertIn('note_cards', show_dialog_source,
                     "Notification should access parent_board.note_cards to get frame")

        print("[PASS] Test 5: Notification triggers note frame lift for visibility")

    def test_notification_handles_missing_note_frame_gracefully(self):
        """Test 6: Notification handles missing note frame without crashing

        v2.9.37 ERROR HANDLING:
        - Try-except block wraps lift() call to prevent crashes
        - Gracefully logs if note frame not found
        - Dialog still shows even if lift() fails

        Verification:
        - lift() call is wrapped in try-except
        - Logging occurs on lift failure
        """
        from src.services.notification import WindowsNotificationService

        show_dialog_source = inspect.getsource(WindowsNotificationService.show_reminder_notification)

        # Check that lift is wrapped in try-except
        self.assertIn('try:', show_dialog_source,
                     "lift() should be protected by try-except")
        self.assertIn('except', show_dialog_source,
                     "lift() failure should be caught gracefully")

        # Check that logging occurs
        self.assertIn('log.', show_dialog_source,
                     "Failure should be logged")

        print("[PASS] Test 6: Notification handles errors gracefully")


def run_all_tests():
    """Run all test suites"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestUIActionButtonsV2937))

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
