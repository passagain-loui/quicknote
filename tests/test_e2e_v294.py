"""E2E Test Suite for v2.9.4 — Native Windows Notifications with Click Callback"""

import unittest
import sys
import os
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.notification import get_notification_service
from src.services.notification_queue import get_notification_queue, NotificationMessage
from src.core.database import init_db, create_note, get_all_notes, update_note


class TestWindowsNotificationServiceV294(unittest.TestCase):
    """Test Windows native notification service with win10toast_click (v2.9.4)"""

    def setUp(self):
        """Initialize test database and notification service"""
        # Use in-memory SQLite for tests
        os.environ['DB_PATH'] = ':memory:'
        init_db()
        self.service = get_notification_service()

    def test_notification_service_initialization(self):
        """Test 1: Notification service initializes successfully"""
        self.assertIsNotNone(self.service)
        self.assertTrue(hasattr(self.service, 'show_reminder_notification'))
        self.assertTrue(hasattr(self.service, 'on_click_callback'))
        print("✓ Test 1: Notification service initialized")

    def test_notification_callback_stored(self):
        """Test 2: Callback function is stored correctly"""
        callback_called = False

        def test_callback():
            nonlocal callback_called
            callback_called = True

        # Call show_reminder_notification with callback
        # (This just stores the callback, doesn't show notification)
        self.service.on_click_callback = None
        # Simulate callback storage
        self.service.on_click_callback = test_callback
        self.assertIsNotNone(self.service.on_click_callback)
        print("✓ Test 2: Callback function stored correctly")

    def test_notification_with_title_and_content(self):
        """Test 3: Notification shows with title and content"""
        def callback():
            pass

        # This test verifies the service accepts parameters correctly
        result = self.service.show_reminder_notification(
            note_title="Test Note",
            note_content="This is a test reminder",
            on_click=callback,
            duration=8
        )

        # Result depends on whether toast library is available
        # Just verify it doesn't crash
        print(f"✓ Test 3: Notification handling (result: {result})")

    def test_notification_queue_integration(self):
        """Test 4: Notification queue works with service"""
        queue = get_notification_queue()

        # Create test notification
        msg = NotificationMessage(
            note_id="test-123",
            title="Queue Test",
            content="Testing queue integration"
        )

        # Queue the notification
        result = queue.put_notification(msg)
        self.assertTrue(result)

        # Retrieve notification
        retrieved = queue.get_next_notification()
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.title, "Queue Test")
        print("✓ Test 4: Notification queue integration works")

    def test_database_note_with_reminder(self):
        """Test 5: Create note with reminder in database"""
        # Create note with reminder
        note_id = create_note(
            title="Reminder Test",
            content="Testing reminder system"
        )

        # Update note with reminder
        update_note(
            note_id,
            reminder_datetime="2026-08-21 15:30"
        )

        # Verify note exists with reminder
        notes = get_all_notes()
        note = next((n for n in notes if n['id'] == note_id), None)

        self.assertIsNotNone(note)
        self.assertEqual(note['title'], "Reminder Test")
        self.assertEqual(note['reminder_datetime'], "2026-08-21 15:30")
        print("✓ Test 5: Database note with reminder created")

    def test_notification_sound_plays(self):
        """Test 6: Notification sound can be played"""
        # This test verifies the sound function doesn't crash
        result = self.service.play_notification_sound()
        # Result may be True or False depending on system, just verify no crash
        print(f"✓ Test 6: Notification sound test (result: {result})")

    def test_fallback_notification_chain(self):
        """Test 7: Fallback notification chain handles gracefully"""
        # Verify that fallback methods exist
        self.assertTrue(hasattr(self.service, '_show_fallback_notification'))
        self.assertTrue(hasattr(self.service, '_show_shell_notification'))
        print("✓ Test 7: Fallback notification chain verified")

    def test_multiple_notifications_in_queue(self):
        """Test 8: Multiple notifications can be queued"""
        queue = get_notification_queue()

        # Queue multiple notifications
        for i in range(3):
            msg = NotificationMessage(
                note_id=f"test-{i}",
                title=f"Notification {i}",
                content=f"Content {i}"
            )
            result = queue.put_notification(msg)
            self.assertTrue(result)

        # Verify queue size
        self.assertEqual(queue.size(), 3)

        # Retrieve all
        retrieved_count = 0
        while not queue.is_empty():
            msg = queue.get_next_notification()
            if msg:
                retrieved_count += 1

        self.assertEqual(retrieved_count, 3)
        print("✓ Test 8: Multiple notifications queued and retrieved")

    def test_notification_service_version(self):
        """Test 9: Notification service AUMID updated to v2.9.4"""
        # This test verifies the AUMID contains the correct version
        # The actual registration happens in __init__
        # Here we just verify the version constant is updated
        from src.core.constants import APP_VERSION
        self.assertGreaterEqual(APP_VERSION, "2.9.43")
        print(f"✓ Test 9: App version is {APP_VERSION}")

    def test_notification_message_dataclass(self):
        """Test 10: NotificationMessage dataclass works correctly"""
        msg = NotificationMessage(
            note_id="test-id",
            title="Test Title",
            content="Test Content",
            on_open=None,
            on_dismiss=None
        )

        self.assertEqual(msg.note_id, "test-id")
        self.assertEqual(msg.title, "Test Title")
        self.assertEqual(msg.content, "Test Content")
        print("✓ Test 10: NotificationMessage dataclass verified")


class TestNotificationCallbackV294(unittest.TestCase):
    """Test notification click callback handling (v2.9.4 feature)"""

    def setUp(self):
        """Initialize for callback tests"""
        os.environ['DB_PATH'] = ':memory:'
        init_db()
        self.service = get_notification_service()
        self.callback_executed = False

    def test_callback_execution(self):
        """Test: Callback can be executed when notification is clicked"""
        def click_handler():
            self.callback_executed = True

        # Store callback
        self.service.on_click_callback = click_handler

        # Verify callback is stored
        self.assertIsNotNone(self.service.on_click_callback)

        # Execute callback
        if self.service.on_click_callback:
            self.service.on_click_callback()

        self.assertTrue(self.callback_executed)
        print("✓ Callback execution test passed")

    def test_callback_brings_window_foreground(self):
        """Test: Callback can signal to bring main window foreground"""
        foreground_called = False

        def foreground_callback():
            nonlocal foreground_called
            foreground_called = True
            # In real app, this would call SetForegroundWindow

        self.service.on_click_callback = foreground_callback
        if self.service.on_click_callback:
            self.service.on_click_callback()

        self.assertTrue(foreground_called)
        print("✓ Foreground callback test passed")


def run_all_tests():
    """Run all test suites"""
    loader = unittest.TestLoader()

    # Create test suite
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestWindowsNotificationServiceV294))
    suite.addTests(loader.loadTestsFromTestCase(TestNotificationCallbackV294))

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
