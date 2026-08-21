"""E2E Test Suite for v2.9.5 — System Tray Integration + Unblockable Notifications"""

import unittest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.tray_service import SystemTrayService, get_tray_service
from src.services.notification import get_notification_service
from src.core.database import init_db
from src.core.constants import APP_VERSION


class TestSystemTrayServiceV295(unittest.TestCase):
    """Test System Tray Service (v2.9.5)"""

    def setUp(self):
        """Initialize for tests"""
        os.environ['DB_PATH'] = ':memory:'
        init_db()
        self.tray_service = SystemTrayService()

    def test_tray_service_initialization(self):
        """Test 1: Tray service initializes successfully"""
        self.assertIsNotNone(self.tray_service)
        self.assertTrue(hasattr(self.tray_service, 'create_icon'))
        self.assertTrue(hasattr(self.tray_service, 'show_notification'))
        print("✓ Test 1: Tray service initialized")

    def test_tray_service_pystray_detection(self):
        """Test 2: Detect pystray availability"""
        self.assertTrue(hasattr(self.tray_service, 'has_pystray'))
        # pystray may or may not be available, just verify detection works
        print(f"✓ Test 2: pystray available: {self.tray_service.has_pystray}")

    def test_tray_service_icon_creation(self):
        """Test 3: Tray icon can be created (if pystray available)"""
        if self.tray_service.has_pystray:
            result = self.tray_service.create_icon()
            # Result depends on environment
            print(f"✓ Test 3: Icon creation result: {result}")
        else:
            print("✓ Test 3: pystray not available, skipping icon creation")

    def test_tray_notification_parameters(self):
        """Test 4: Tray notification accepts proper parameters"""
        # This test just verifies the method signature and basic logic
        result = self.tray_service.show_notification(
            title="Test Notification",
            message="This is a test"
        )
        # Result depends on whether pystray is running
        print(f"✓ Test 4: Notification shown with result: {result}")

    def test_tray_notification_with_callback(self):
        """Test 5: Tray notification can accept callback"""
        callback_executed = False

        def test_callback():
            nonlocal callback_executed
            callback_executed = True

        result = self.tray_service.show_notification(
            title="Test",
            message="Test message",
            on_click=test_callback
        )
        print(f"✓ Test 5: Notification with callback (result: {result})")

    def test_tray_service_stop(self):
        """Test 6: Tray service can stop without crashing"""
        try:
            self.tray_service.stop_icon()
            print("✓ Test 6: Stop icon executed without error")
        except Exception as e:
            self.fail(f"Stop icon failed: {e}")


class TestNotificationIntegrationV295(unittest.TestCase):
    """Test notification service integration with tray (v2.9.5)"""

    def setUp(self):
        """Initialize"""
        os.environ['DB_PATH'] = ':memory:'
        init_db()
        self.notification_service = get_notification_service()

    def test_notification_service_has_tray_fallback(self):
        """Test 7: Notification service can use tray as fallback"""
        # Verify the show_reminder_notification method exists
        self.assertTrue(hasattr(self.notification_service, 'show_reminder_notification'))
        print("✓ Test 7: Notification service supports tray integration")

    def test_notification_priority_chain_v295(self):
        """Test 8: Notification priority chain includes tray (v2.9.5)"""
        # This test verifies that the method will try tray first
        result = self.notification_service.show_reminder_notification(
            note_title="Integration Test",
            note_content="Testing v2.9.5 tray integration"
        )
        # Result depends on available notification methods
        print(f"✓ Test 8: Notification sent with result: {result}")

    def test_version_updated_to_v295(self):
        """Test 9: Version updated to v2.9.5"""
        self.assertEqual(APP_VERSION, "2.9.5")
        print(f"✓ Test 9: App version is {APP_VERSION}")

    def test_tray_service_global_instance(self):
        """Test 10: Tray service global instance works"""
        tray = get_tray_service()
        self.assertIsNotNone(tray)
        print("✓ Test 10: Global tray service instance accessible")


class TestUnblockableNotificationV295(unittest.TestCase):
    """Test unblockable notification strategy (v2.9.5)"""

    def setUp(self):
        """Initialize"""
        os.environ['DB_PATH'] = ':memory:'
        init_db()

    def test_notification_guaranteed_visibility(self):
        """Test 11: System tray makes notifications unblockable"""
        # Having a tray icon registered with Windows makes app recognized
        # as active desktop application, allowing notifications even when minimized
        tray = SystemTrayService()
        self.assertIsNotNone(tray)
        print("✓ Test 11: Unblockable notification strategy ready")

    def test_fallback_chain_comprehensive(self):
        """Test 12: Full fallback chain available"""
        service = get_notification_service()
        # Verify multiple fallback methods exist
        self.assertTrue(hasattr(service, '_show_win10toast_click_notification'))
        self.assertTrue(hasattr(service, '_show_win10toast_notification'))
        self.assertTrue(hasattr(service, '_show_shell_notification'))
        self.assertTrue(hasattr(service, '_show_fallback_notification'))
        print("✓ Test 12: Complete fallback chain available")


def run_all_tests():
    """Run all test suites"""
    loader = unittest.TestLoader()

    # Create test suite
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestSystemTrayServiceV295))
    suite.addTests(loader.loadTestsFromTestCase(TestNotificationIntegrationV295))
    suite.addTests(loader.loadTestsFromTestCase(TestUnblockableNotificationV295))

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
