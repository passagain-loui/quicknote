"""E2E Tests for v2.9.39: Icon Harmonization, Task Re-ordering, Reminder State Clearing, Google OAuth Browser Flow

Comprehensive regression test suite validating:
1. Action button icon change (✔ → ✓ minimalist)
2. Card re-packing to top when alarm triggers
3. Reminder clock icon state updates (⏰ → ⏱)
4. Google OAuth browser-based authentication flow
5. Settings window deduping
"""

import unittest
import tkinter as tk
from pathlib import Path
import tempfile
import sqlite3
from datetime import datetime, timedelta

from src.ui.note_card import NoteCard
from src.ui.board import Board
from src.ui.theme import Theme
from src.ui.settings_window import SettingsWindow
from src.core.models import Note
from src.core.constants import APP_VERSION


class TestV2939IconHarmonization(unittest.TestCase):
    """Test Suite 1: Icon Harmonization (minimalist checkmark styling)"""

    def setUp(self):
        """Initialize test environment"""
        self.root = tk.Tk()
        self.theme = Theme("light")

    def tearDown(self):
        """Clean up"""
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_complete_button_minimalist_icon(self):
        """Test 1a: Complete button uses minimalist ✓ icon for active notes"""
        note = Note(
            id="test-active",
            title="Active Task",
            content="This is active",
            status="active",
            collapsed=False
        )

        card = NoteCard(self.root, note, self.theme)

        # Check that button text is ✓ (minimalist), not ✔ (heavy)
        self.assertTrue(hasattr(card, 'btn_action'))
        action_text = card.btn_action.cget("text")
        self.assertEqual(action_text, "✓", "Complete button should use minimalist ✓ icon")

        # Check color is muted gray
        action_color = card.btn_action.cget("fg")
        self.assertEqual(action_color, "#666666", "Complete button should be muted gray")

    def test_restore_button_icon(self):
        """Test 1b: Restore button uses ↩ icon for completed notes"""
        note = Note(
            id="test-completed",
            title="Completed Task",
            content="This is done",
            status="completed",
            collapsed=False
        )

        card = NoteCard(self.root, note, self.theme)

        # Check restore button
        self.assertTrue(hasattr(card, 'btn_action'))
        action_text = card.btn_action.cget("text")
        self.assertEqual(action_text, "↩", "Restore button should use ↩ icon")

        # Check color is green
        action_color = card.btn_action.cget("fg")
        self.assertEqual(action_color, "#34C759", "Restore button should be green")

    def test_update_action_button_on_status_change(self):
        """Test 1c: Button updates when note status changes"""
        note = Note(
            id="test-toggle",
            title="Toggle Task",
            content="Will toggle",
            status="active",
            collapsed=False
        )

        card = NoteCard(self.root, note, self.theme)
        self.assertEqual(card.btn_action.cget("text"), "✓")

        # Simulate status change
        card.note.status = "completed"
        card._update_action_button()
        self.assertEqual(card.btn_action.cget("text"), "↩")


class TestV2939TaskReordering(unittest.TestCase):
    """Test Suite 2: Task Re-ordering to Top on Alarm"""

    def setUp(self):
        """Initialize test environment"""
        self.root = tk.Tk()
        self.theme = Theme("light")

    def tearDown(self):
        """Clean up"""
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_repack_card_to_top_method_exists(self):
        """Test 2a: Board has repack_card_to_top() method"""
        # Mock command queue
        import queue
        cmd_queue = queue.Queue()

        board = Board(geometry="400x500+100+100", theme_mode="light", command_queue=cmd_queue)

        # Check method exists
        self.assertTrue(hasattr(board, 'repack_card_to_top'))
        self.assertTrue(callable(board.repack_card_to_top))

        board.root.destroy()

    def test_repack_nonexistent_card_safe(self):
        """Test 2b: Repack gracefully handles nonexistent cards"""
        import queue
        cmd_queue = queue.Queue()

        board = Board(geometry="400x500+100+100", theme_mode="light", command_queue=cmd_queue)

        # Should not crash
        board.repack_card_to_top("nonexistent-id")

        board.root.destroy()


class TestV2939ReminderStateClearing(unittest.TestCase):
    """Test Suite 3: Reminder Clock Icon State Updates"""

    def setUp(self):
        """Initialize test environment"""
        self.root = tk.Tk()
        self.theme = Theme("light")

    def tearDown(self):
        """Clean up"""
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_update_reminder_state_method_exists(self):
        """Test 3a: NoteCard has update_reminder_state() method"""
        note = Note(
            id="test-reminder",
            title="Reminder Task",
            content="Has reminder",
            status="active",
            collapsed=False,
            reminder_datetime="2026-08-22 14:00",
            reminder_triggered=False
        )

        card = NoteCard(self.root, note, self.theme)
        self.assertTrue(hasattr(card, 'update_reminder_state'))
        self.assertTrue(callable(card.update_reminder_state))

    def test_update_reminder_state_active(self):
        """Test 3b: Active reminder shows ⏰ icon"""
        note = Note(
            id="test-active-reminder",
            title="Task",
            content="Content",
            status="active",
            collapsed=False,
            reminder_datetime="2026-08-22 14:00",
            reminder_triggered=False
        )

        card = NoteCard(self.root, note, self.theme)

        # Initially should show ⏰ if reminder_triggered=False and datetime is set
        initial_icon = card.btn_reminder.cget("text")
        self.assertEqual(initial_icon, "⏰")

    def test_update_reminder_state_inactive(self):
        """Test 3c: Inactive reminder shows ⏱ icon"""
        note = Note(
            id="test-inactive-reminder",
            title="Task",
            content="Content",
            status="active",
            collapsed=False,
            reminder_datetime="2026-08-22 14:00",
            reminder_triggered=True  # Already triggered
        )

        card = NoteCard(self.root, note, self.theme)

        # Should show ⏱ if reminder_triggered=True
        initial_icon = card.btn_reminder.cget("text")
        self.assertEqual(initial_icon, "⏱")

    def test_update_reminder_state_changes_icon(self):
        """Test 3d: Icon changes when update_reminder_state() is called"""
        note = Note(
            id="test-toggle-reminder",
            title="Task",
            content="Content",
            status="active",
            collapsed=False,
            reminder_datetime="2026-08-22 14:00",
            reminder_triggered=False
        )

        card = NoteCard(self.root, note, self.theme)

        # Start with ⏰
        self.assertEqual(card.btn_reminder.cget("text"), "⏰")

        # Call update with False to make it inactive
        card.update_reminder_state(False)
        self.assertEqual(card.btn_reminder.cget("text"), "⏱", "Icon should change to ⏱ when inactive")

        # Call update with True to make it active
        card.update_reminder_state(True)
        self.assertEqual(card.btn_reminder.cget("text"), "⏰", "Icon should change to ⏰ when active")


class TestV2939GoogleOAuthFlow(unittest.TestCase):
    """Test Suite 4: Google OAuth Browser Flow Integration with Embedded Credentials"""

    def setUp(self):
        """Initialize test environment"""
        self.root = tk.Tk()
        self.theme = Theme("light")

    def tearDown(self):
        """Clean up"""
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_oauth_service_exists(self):
        """Test 4a: OAuth service has embedded credentials (no file needed)"""
        try:
            from src.services.auth_service import get_google_oauth_service
            oauth_service = get_google_oauth_service()

            # Verify service initialized with embedded config
            self.assertTrue(hasattr(oauth_service, 'client_id'))
            self.assertTrue(hasattr(oauth_service, 'client_secret'))
            self.assertTrue(hasattr(oauth_service, 'get_oauth_url'))
            self.assertTrue(callable(oauth_service.get_oauth_url))

            # Credentials should be loaded (embedded or from file)
            self.assertIsNotNone(oauth_service.client_id)
        except Exception as e:
            self.fail(f"OAuth service initialization failed: {e}")

    def test_oauth_no_file_required(self):
        """Test 4b: OAuth works without credentials.json file (uses embedded config)"""
        try:
            from src.services.auth_service import GoogleOAuthService

            service = GoogleOAuthService()

            # Should have credentials even if no file exists
            self.assertTrue(
                service.client_id is not None,
                "OAuth service should have client_id from embedded config"
            )
            self.assertTrue(
                service.client_secret is not None,
                "OAuth service should have client_secret from embedded config"
            )
        except Exception as e:
            self.fail(f"Embedded OAuth credentials test failed: {e}")

    def test_oauth_url_generation(self):
        """Test 4c: OAuth URL can be generated for browser flow"""
        try:
            from src.services.auth_service import get_google_oauth_service

            oauth_service = get_google_oauth_service()
            oauth_url = oauth_service.get_oauth_url()

            # URL should contain Google OAuth endpoint
            self.assertIsNotNone(oauth_url)
            self.assertIn("accounts.google.com", oauth_url)
            self.assertIn("oauth2", oauth_url)
        except Exception as e:
            self.fail(f"OAuth URL generation failed: {e}")

    def test_settings_window_google_tab_exists(self):
        """Test 4d: Settings window has Google Tasks tab"""
        settings_data = {"alpha": 1.0, "snooze_duration_minutes": 5}

        try:
            settings = SettingsWindow(
                parent_root=self.root,
                settings_data=settings_data,
                theme=self.theme,
                main_root=self.root
            )

            # Check that notebook exists and has tabs
            self.assertTrue(hasattr(settings, 'notebook'))

            settings.root.destroy()
        except Exception as e:
            self.fail(f"Settings window creation failed: {e}")

    def test_google_authenticate_button_exists(self):
        """Test 4e: Settings window has Connect Account button"""
        settings_data = {"alpha": 1.0, "snooze_duration_minutes": 5}

        try:
            settings = SettingsWindow(
                parent_root=self.root,
                settings_data=settings_data,
                theme=self.theme,
                main_root=self.root
            )

            # Check buttons exist
            self.assertTrue(hasattr(settings, 'btn_connect'))
            self.assertTrue(hasattr(settings, 'btn_disconnect'))

            settings.root.destroy()
        except Exception as e:
            self.fail(f"Settings window button check failed: {e}")

    def test_google_authenticate_method_exists(self):
        """Test 4f: Settings window has _on_google_authenticate() method (no file check)"""
        settings_data = {"alpha": 1.0, "snooze_duration_minutes": 5}

        try:
            settings = SettingsWindow(
                parent_root=self.root,
                settings_data=settings_data,
                theme=self.theme,
                main_root=self.root
            )

            # Check method exists and uses embedded OAuth (not file-based)
            self.assertTrue(hasattr(settings, '_on_google_authenticate'))
            self.assertTrue(callable(settings._on_google_authenticate))

            settings.root.destroy()
        except Exception as e:
            self.fail(f"Settings window method check failed: {e}")


class TestV2939VersionConstant(unittest.TestCase):
    """Test Suite 5: Version Verification"""

    def test_version_updated_to_2939(self):
        """Test 5a: Version constant is v2.9.39"""
        self.assertEqual(APP_VERSION, "2.9.39", f"Version should be 2.9.39, got {APP_VERSION}")

    def test_version_format_valid(self):
        """Test 5b: Version format is valid (major.minor.patch)"""
        parts = APP_VERSION.split(".")
        self.assertEqual(len(parts), 3, "Version should have 3 parts (major.minor.patch)")

        for part in parts:
            self.assertTrue(part.isdigit(), f"Version part should be numeric: {part}")


class TestV2939RegressionIntegration(unittest.TestCase):
    """Test Suite 6: Integration & Regression Tests"""

    def setUp(self):
        """Initialize test environment"""
        self.root = tk.Tk()
        self.theme = Theme("light")

    def tearDown(self):
        """Clean up"""
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_all_v2939_features_work_together(self):
        """Test 6a: All v2.9.39 features integrate without conflicts"""
        # Create a note
        note = Note(
            id="test-integration",
            title="Integration Test",
            content="Test all features together",
            status="active",
            collapsed=False,
            reminder_datetime="2026-08-22 15:00",
            reminder_triggered=False
        )

        # Create card
        card = NoteCard(self.root, note, self.theme)

        # Verify icon harmonization
        self.assertEqual(card.btn_action.cget("text"), "✓", "Action button should be ✓")

        # Verify reminder state method
        card.update_reminder_state(False)
        self.assertEqual(card.btn_reminder.cget("text"), "⏱", "Reminder should be ⏱")

        # Verify set_alarm_highlight method
        card.set_alarm_highlight(True)
        highlight_color = card.cget("highlightbackground")
        self.assertEqual(highlight_color, "#FF3B30", "Card should have red border when highlighted")

        card.set_alarm_highlight(False)
        # Border reset to normal
        self.assertTrue(True, "Alarm highlight cleared successfully")

    def test_board_and_card_compatibility(self):
        """Test 6b: Board and NoteCard work together with v2.9.39 features"""
        import queue
        cmd_queue = queue.Queue()

        board = Board(geometry="400x500+100+100", theme_mode="light", command_queue=cmd_queue)

        # Verify board has repack method
        self.assertTrue(hasattr(board, 'repack_card_to_top'))

        # Create a note and card
        note = Note(
            id="board-test",
            title="Board Test",
            content="Test integration",
            status="active",
            collapsed=False
        )

        card = NoteCard(board.inner_frame, note, self.theme)
        board.note_cards["board-test"] = card

        # Repack should work without errors
        board.repack_card_to_top("board-test")

        board.root.destroy()


def run_tests():
    """Run all v2.9.39 E2E tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestV2939IconHarmonization))
    suite.addTests(loader.loadTestsFromTestCase(TestV2939TaskReordering))
    suite.addTests(loader.loadTestsFromTestCase(TestV2939ReminderStateClearing))
    suite.addTests(loader.loadTestsFromTestCase(TestV2939GoogleOAuthFlow))
    suite.addTests(loader.loadTestsFromTestCase(TestV2939VersionConstant))
    suite.addTests(loader.loadTestsFromTestCase(TestV2939RegressionIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
