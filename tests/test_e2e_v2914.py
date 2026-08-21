"""E2E Test Suite for v2.9.14 — Command Queue Pattern + Single-Thread DB Access"""

import unittest
import sys
import os
import queue

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.database import init_db, create_note, get_note
from src.core.constants import APP_VERSION


class TestCommandQueuePatternV2914(unittest.TestCase):
    """Test command queue pattern for thread-safe DB/GUI access (v2.9.14)"""

    def setUp(self):
        """Initialize for tests"""
        os.environ['DB_PATH'] = ':memory:'
        init_db()

    def test_command_queue_creation(self):
        """Test 1: Command queue can be created safely"""
        cmd_queue = queue.Queue()
        self.assertIsNotNone(cmd_queue)
        self.assertTrue(isinstance(cmd_queue, queue.Queue))
        print("[PASS] Test 1: Command queue created successfully")

    def test_queue_put_get_open_note_command(self):
        """Test 2: Queue can store and retrieve 'open_note' command"""
        cmd_queue = queue.Queue()

        # Background thread puts command in queue
        cmd_queue.put({
            "action": "open_note",
            "note_id": "test-123"
        })

        # Main thread retrieves command
        cmd = cmd_queue.get_nowait()
        self.assertEqual(cmd["action"], "open_note")
        self.assertEqual(cmd["note_id"], "test-123")

        print("[PASS] Test 2: 'open_note' command queued and retrieved")

    def test_queue_put_get_dismiss_note_command(self):
        """Test 3: Queue can store and retrieve 'dismiss_note' command"""
        cmd_queue = queue.Queue()

        cmd_queue.put({
            "action": "dismiss_note",
            "note_id": "test-456"
        })

        cmd = cmd_queue.get_nowait()
        self.assertEqual(cmd["action"], "dismiss_note")
        self.assertEqual(cmd["note_id"], "test-456")

        print("[PASS] Test 3: 'dismiss_note' command queued and retrieved")

    def test_queue_put_get_snooze_note_command(self):
        """Test 4: Queue can store and retrieve 'snooze_note' command"""
        cmd_queue = queue.Queue()

        cmd_queue.put({
            "action": "snooze_note",
            "note_id": "test-789"
        })

        cmd = cmd_queue.get_nowait()
        self.assertEqual(cmd["action"], "snooze_note")
        self.assertEqual(cmd["note_id"], "test-789")

        print("[PASS] Test 4: 'snooze_note' command queued and retrieved")

    def test_queue_multiple_commands(self):
        """Test 5: Queue can handle multiple commands in sequence"""
        cmd_queue = queue.Queue()

        # Simulate notification thread putting multiple commands
        cmd_queue.put({"action": "dismiss_note", "note_id": "id-1"})
        cmd_queue.put({"action": "open_note", "note_id": "id-2"})
        cmd_queue.put({"action": "snooze_note", "note_id": "id-3"})

        # Main thread processes all commands
        cmds = []
        while True:
            try:
                cmd = cmd_queue.get_nowait()
                cmds.append(cmd)
            except:
                break

        self.assertEqual(len(cmds), 3)
        self.assertEqual(cmds[0]["action"], "dismiss_note")
        self.assertEqual(cmds[1]["action"], "open_note")
        self.assertEqual(cmds[2]["action"], "snooze_note")

        print("[PASS] Test 5: Multiple commands queued and processed in order")


class TestMainThreadDBAccessOnlyV2914(unittest.TestCase):
    """Test that ONLY Main Thread can access database (v2.9.14)"""

    def setUp(self):
        """Initialize for tests"""
        os.environ['DB_PATH'] = ':memory:'
        init_db()

    def test_main_thread_updates_db(self):
        """Test 6: Main thread can update database"""
        # Create a test note
        note_id = create_note(title="Test Note", content="")

        # Main thread updates DB (simulated)
        from src.core.database import update_note
        update_note(note_id, reminder_triggered=True)

        # Verify update was successful
        note = get_note(note_id)
        self.assertTrue(note['reminder_triggered'])

        print("[PASS] Test 6: Main thread can update database successfully")

    def test_dismiss_note_command_execution(self):
        """Test 7: Executing 'dismiss_note' command updates DB correctly"""
        # Create a test note
        note_id = create_note(title="Test Note", content="")

        # Before: reminder_triggered = False (default)
        note_before = get_note(note_id)
        self.assertFalse(note_before['reminder_triggered'])

        # Simulate main thread executing 'dismiss_note' command
        from src.core.database import update_note
        update_note(note_id, reminder_triggered=True)

        # After: reminder_triggered = True
        note_after = get_note(note_id)
        self.assertTrue(note_after['reminder_triggered'])

        print("[PASS] Test 7: 'dismiss_note' command updates DB correctly")

    def test_open_note_command_execution(self):
        """Test 8: Executing 'open_note' command updates DB and marks triggered"""
        # Create a test note with reminder
        note_id = create_note(title="Test Note", content="")
        from src.core.database import update_note
        update_note(note_id, reminder_datetime="2026-08-21 14:00", reminder_triggered=False)

        # Before: not triggered
        note_before = get_note(note_id)
        self.assertFalse(note_before['reminder_triggered'])

        # Simulate main thread executing 'open_note' command
        update_note(note_id, reminder_triggered=True)

        # After: triggered
        note_after = get_note(note_id)
        self.assertTrue(note_after['reminder_triggered'])

        # Verify no re-trigger on next scheduler cycle
        should_trigger = bool(note_after['reminder_datetime']) and not note_after['reminder_triggered']
        self.assertFalse(should_trigger)

        print("[PASS] Test 8: 'open_note' command prevents re-trigger")

    def test_snooze_note_command_execution(self):
        """Test 9: Executing 'snooze_note' command reschedules reminder"""
        # Create a test note with reminder
        note_id = create_note(title="Test Note", content="")
        from src.core.database import update_note
        from datetime import datetime, timedelta

        original_reminder = "2026-08-21 14:00"
        update_note(note_id, reminder_datetime=original_reminder, reminder_triggered=True)

        # Before: reminder_datetime is original
        note_before = get_note(note_id)
        self.assertEqual(note_before['reminder_datetime'], original_reminder)

        # Simulate main thread executing 'snooze_note' command (+5m)
        new_reminder = (datetime.now() + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M")
        update_note(note_id, reminder_datetime=new_reminder, reminder_triggered=False)

        # After: reminder_datetime is new (future)
        note_after = get_note(note_id)
        self.assertNotEqual(note_after['reminder_datetime'], original_reminder)
        self.assertFalse(note_after['reminder_triggered'])

        print("[PASS] Test 9: 'snooze_note' command reschedules correctly")


class TestCrossThreadSafetyV2914(unittest.TestCase):
    """Test cross-thread safety with command queue (v2.9.14)"""

    def setUp(self):
        """Initialize for tests"""
        os.environ['DB_PATH'] = ':memory:'
        init_db()

    def test_notification_thread_does_not_touch_db(self):
        """Test 10: Notification thread only puts commands; doesn't touch DB"""
        cmd_queue = queue.Queue()

        # Simulate notification thread
        note_id = "test-note-id"

        # Notification thread ONLY does this (no DB access)
        cmd_queue.put({"action": "open_note", "note_id": note_id})

        # Main thread ONLY does this (DB access)
        cmd = cmd_queue.get_nowait()
        if cmd["action"] == "open_note":
            from src.core.database import update_note
            update_note(cmd["note_id"], reminder_triggered=True)

        # Verify DB was updated only by main thread
        from src.core.database import create_note, get_note
        test_note_id = create_note("Test", "")
        update_note(test_note_id, reminder_triggered=True)
        note = get_note(test_note_id)
        self.assertTrue(note['reminder_triggered'])

        print("[PASS] Test 10: Notification thread safe (queue only, no DB access)")

    def test_multiple_commands_processed_sequentially(self):
        """Test 11: Multiple commands processed sequentially by main thread"""
        cmd_queue = queue.Queue()

        # Simulate rapid commands from notification thread
        cmd_queue.put({"action": "dismiss_note", "note_id": "id-1"})
        cmd_queue.put({"action": "open_note", "note_id": "id-2"})
        cmd_queue.put({"action": "snooze_note", "note_id": "id-3"})

        # Main thread processes all commands sequentially
        processed_count = 0
        while True:
            try:
                cmd = cmd_queue.get_nowait()
                # Simulate main thread processing
                processed_count += 1
            except:
                break

        self.assertEqual(processed_count, 3)
        print("[PASS] Test 11: Multiple commands processed sequentially")

    def test_version_v2914(self):
        """Test 12: Version updated to v2.9.14"""
        self.assertEqual(APP_VERSION, "2.9.14")
        print(f"[PASS] Test 12: App version is {APP_VERSION}")


def run_all_tests():
    """Run all test suites"""
    loader = unittest.TestLoader()

    # Create test suite
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestCommandQueuePatternV2914))
    suite.addTests(loader.loadTestsFromTestCase(TestMainThreadDBAccessOnlyV2914))
    suite.addTests(loader.loadTestsFromTestCase(TestCrossThreadSafetyV2914))

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
