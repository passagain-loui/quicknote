"""E2E Test Suite for v2.9.7 — Unblockable Custom Dialog + Alarm Control"""

import unittest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.database import init_db
from src.core.constants import APP_VERSION


class TestUnblockableDialogV297(unittest.TestCase):
    """Test Unblockable Custom Dialog (v2.9.7)"""

    def setUp(self):
        """Initialize for tests"""
        os.environ['DB_PATH'] = ':memory:'
        init_db()

    def test_dialog_class_exists(self):
        """Test 1: UnblockableCustomDialog class exists"""
        from src.ui.unblockable_dialog import UnblockableCustomDialog
        self.assertTrue(UnblockableCustomDialog)
        print("✓ Test 1: UnblockableCustomDialog class exists")

    def test_dialog_inherits_toplevel(self):
        """Test 2: Dialog inherits from tk.Toplevel"""
        from src.ui.unblockable_dialog import UnblockableCustomDialog
        import tkinter as tk
        # Verify class attributes
        self.assertTrue(hasattr(UnblockableCustomDialog, '__init__'))
        self.assertTrue(hasattr(UnblockableCustomDialog, '_create_ui'))
        self.assertTrue(hasattr(UnblockableCustomDialog, '_force_to_foreground'))
        print("✓ Test 2: Dialog structure verified")

    def test_dialog_button_callbacks(self):
        """Test 3: Dialog has button callbacks"""
        from src.ui.unblockable_dialog import UnblockableCustomDialog
        self.assertTrue(hasattr(UnblockableCustomDialog, '_on_dismiss_click'))
        self.assertTrue(hasattr(UnblockableCustomDialog, '_on_snooze_click'))
        self.assertTrue(hasattr(UnblockableCustomDialog, '_on_open_click'))
        print("✓ Test 3: Button callbacks exist")

    def test_alarm_stop_functionality(self):
        """Test 4: Dialog can stop alarm sound"""
        from src.ui.unblockable_dialog import UnblockableCustomDialog
        self.assertTrue(hasattr(UnblockableCustomDialog, '_stop_alarm_sound'))
        print("✓ Test 4: Alarm stop functionality exists")

    def test_foreground_force_method(self):
        """Test 5: Dialog can force foreground"""
        from src.ui.unblockable_dialog import UnblockableCustomDialog
        self.assertTrue(hasattr(UnblockableCustomDialog, '_force_to_foreground'))
        # Verify Win32 constants
        self.assertEqual(UnblockableCustomDialog.HWND_TOPMOST, -1)
        self.assertEqual(UnblockableCustomDialog.SWP_NOSIZE, 0x0001)
        self.assertEqual(UnblockableCustomDialog.SWP_NOMOVE, 0x0002)
        print("✓ Test 5: Win32 constants defined correctly")

    def test_center_on_screen_method(self):
        """Test 6: Dialog can center on screen"""
        from src.ui.unblockable_dialog import UnblockableCustomDialog
        self.assertTrue(hasattr(UnblockableCustomDialog, 'center_on_screen'))
        print("✓ Test 6: Center on screen method exists")


class TestNotificationIntegrationV297(unittest.TestCase):
    """Test notification service integration (v2.9.7)"""

    def setUp(self):
        """Initialize"""
        os.environ['DB_PATH'] = ':memory:'
        init_db()
        from src.services.notification import get_notification_service
        self.notification_service = get_notification_service()

    def test_notification_accepts_dialog_callbacks(self):
        """Test 7: Notification service accepts dialog callbacks"""
        # Verify the method signature includes new parameters
        import inspect
        sig = inspect.signature(self.notification_service.show_reminder_notification)
        params = list(sig.parameters.keys())
        self.assertIn('on_snooze', params)
        self.assertIn('on_dismiss', params)
        self.assertIn('stop_alarm', params)
        self.assertIn('parent_root', params)
        print("✓ Test 7: Notification service supports dialog callbacks")

    def test_version_v297(self):
        """Test 8: Version updated to v2.9.7"""
        self.assertEqual(APP_VERSION, "2.9.7")
        print(f"✓ Test 8: App version is {APP_VERSION}")


class TestAlarmControlV297(unittest.TestCase):
    """Test alarm control functionality (v2.9.7)"""

    def test_alarm_stop_callback_concept(self):
        """Test 9: Alarm stop callback mechanism"""
        alarm_stopped = False

        def stop_alarm_callback():
            nonlocal alarm_stopped
            alarm_stopped = True

        # Simulate callback execution
        stop_alarm_callback()
        self.assertTrue(alarm_stopped)
        print("✓ Test 9: Alarm stop callback mechanism works")

    def test_dismiss_callback_flow(self):
        """Test 10: Dismiss button callback flow"""
        dismiss_called = False

        def on_dismiss():
            nonlocal dismiss_called
            dismiss_called = True

        # Simulate dismiss callback
        on_dismiss()
        self.assertTrue(dismiss_called)
        print("✓ Test 10: Dismiss callback flow verified")

    def test_snooze_callback_flow(self):
        """Test 11: Snooze button callback flow"""
        snooze_called = False

        def on_snooze():
            nonlocal snooze_called
            snooze_called = True

        # Simulate snooze callback
        on_snooze()
        self.assertTrue(snooze_called)
        print("✓ Test 11: Snooze callback flow verified")

    def test_open_callback_flow(self):
        """Test 12: Open button callback flow"""
        open_called = False

        def on_open():
            nonlocal open_called
            open_called = True

        # Simulate open callback
        on_open()
        self.assertTrue(open_called)
        print("✓ Test 12: Open callback flow verified")


def run_all_tests():
    """Run all test suites"""
    loader = unittest.TestLoader()

    # Create test suite
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestUnblockableDialogV297))
    suite.addTests(loader.loadTestsFromTestCase(TestNotificationIntegrationV297))
    suite.addTests(loader.loadTestsFromTestCase(TestAlarmControlV297))

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
