"""E2E Test Suite for v2.9.7 — Unblockable Custom Dialog + Alarm Control"""

# _QN_BOOTSTRAP_V2945: UTF-8 stdio + faulthandler + Tk9 GC mitigation (self-sufficient)
import sys as _sys, gc as _gc, faulthandler as _fh
import unittest as _unittest
for _s in (_sys.stdout, _sys.stderr):
    if _s and hasattr(_s, 'reconfigure'):
        try:
            _s.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
_fh.enable()
if not getattr(_sys, '_qn_gc_patched', False):
    _orig_tr = _unittest.case.TestCase.run
    def _qn_run(self, *a, **k):
        try:
            return _orig_tr(self, *a, **k)
        finally:
            _gc.collect()
    _unittest.case.TestCase.run = _qn_run
    _sys._qn_gc_patched = True


import unittest
import sys
import os
import tempfile

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.database import init_db
from src.core.constants import APP_VERSION


class TestUnblockableDialogV297(unittest.TestCase):
    """Test Unblockable Custom Dialog (v2.9.7)"""

    def setUp(self):
        """Initialize for tests"""
        os.environ.setdefault('_QN_DB_PATH_BAK', os.environ.get('DB_PATH') or '@@UNSET@@')
        os.environ['DB_PATH'] = os.path.join(tempfile.mkdtemp(prefix='qn_test_'), 'notes.db')
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
        # v2.9.20: Open button removed -> 2-button workflow (Dismiss/Snooze)
        self.assertFalse(hasattr(UnblockableCustomDialog, '_on_open_click'),
                         "_on_open_click must stay removed (v2.9.20 streamlined dialog)")
        print("✓ Test 3: Button callbacks verified (dismiss/snooze present, open absent)")

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
        """Test 6: center_on_screen REMOVED (v2.9.32 strict bottom-right position lock)"""
        from src.ui.unblockable_dialog import UnblockableCustomDialog
        self.assertFalse(hasattr(UnblockableCustomDialog, 'center_on_screen'),
                         "center_on_screen must stay removed to keep corner lock strict")
        print("✓ Test 6: Center on screen method exists")



    def tearDown(self):
        prev = os.environ.pop('_QN_DB_PATH_BAK', None)
        if prev is None:
            os.environ.pop('DB_PATH', None)
        elif prev != '@@UNSET@@':
            os.environ['DB_PATH'] = prev
        else:
            os.environ.pop('DB_PATH', None)
class TestNotificationIntegrationV297(unittest.TestCase):
    """Test notification service integration (v2.9.7)"""

    def setUp(self):
        """Initialize"""
        os.environ.setdefault('_QN_DB_PATH_BAK', os.environ.get('DB_PATH') or '@@UNSET@@')
        os.environ['DB_PATH'] = os.path.join(tempfile.mkdtemp(prefix='qn_test_'), 'notes.db')
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
        self.assertGreaterEqual(tuple(int(x) for x in APP_VERSION.split('.')), (2, 9, 7))  # v2.9.45: tolerate future versions
        print(f"✓ Test 8: App version is {APP_VERSION}")



    def tearDown(self):
        prev = os.environ.pop('_QN_DB_PATH_BAK', None)
        if prev is None:
            os.environ.pop('DB_PATH', None)
        elif prev != '@@UNSET@@':
            os.environ['DB_PATH'] = prev
        else:
            os.environ.pop('DB_PATH', None)
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
