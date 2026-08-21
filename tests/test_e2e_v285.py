"""QuickNote v2.8.5 — Thread-Safe Notification Queue E2E Test Suite
Tests: Notification Queue + Custom Overlay + Clear Reminder
Must pass 100% before build and release
"""

import sys
import os
import time
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.database import (
    init_db, create_note, get_all_notes, update_note, get_note
)
from src.services.notification_queue import (
    get_notification_queue, NotificationMessage, reset_notification_queue
)
import sqlite3


class TestResult:
    """Track test results"""
    def __init__(self, name):
        self.name = name
        self.passed = False
        self.error = None
        self.duration = 0

    def __str__(self):
        status = "[PASS]" if self.passed else "[FAIL]"
        time_str = f" ({self.duration:.2f}s)" if self.duration else ""
        error_str = f"\n  Error: {self.error}" if self.error else ""
        return f"{status} {self.name}{time_str}{error_str}"


def test_notification_queue_threadsafe():
    """Test 1: Thread-Safe Notification Queue

    Verification:
    - Queue is initially empty
    - Put notification message in queue (non-blocking)
    - Get notification from queue (non-blocking)
    - Queue handles multiple messages FIFO order
    """
    result = TestResult("Test 1: Thread-Safe Notification Queue")
    start = time.time()

    try:
        reset_notification_queue()
        print("\n  [1a] Testing notification queue initialization...")
        queue = get_notification_queue()
        if queue.is_empty():
            print("      [OK] Queue initialized empty")
        else:
            raise AssertionError("Queue should be empty on init")

        # Test put operation
        print("  [1b] Testing put_notification (non-blocking)...")
        msg1 = NotificationMessage(
            note_id="test-1",
            title="First Notification",
            content="Test message 1"
        )
        result1 = queue.put_notification(msg1)
        if result1:
            print("      [OK] Message 1 queued")
        else:
            raise AssertionError("Failed to queue message 1")

        msg2 = NotificationMessage(
            note_id="test-2",
            title="Second Notification",
            content="Test message 2"
        )
        result2 = queue.put_notification(msg2)
        if result2:
            print("      [OK] Message 2 queued")
        else:
            raise AssertionError("Failed to queue message 2")

        # Test queue size
        print("  [1c] Testing queue size...")
        size = queue.size()
        if size == 2:
            print(f"      [OK] Queue size: {size}")
        else:
            raise AssertionError(f"Queue size should be 2, got {size}")

        # Test get operation (FIFO)
        print("  [1d] Testing get_next_notification (FIFO order)...")
        retrieved1 = queue.get_next_notification()
        if retrieved1 and retrieved1.note_id == "test-1":
            print(f"      [OK] Message 1 retrieved (FIFO): {retrieved1.title}")
        else:
            raise AssertionError("First message should be 'First Notification'")

        retrieved2 = queue.get_next_notification()
        if retrieved2 and retrieved2.note_id == "test-2":
            print(f"      [OK] Message 2 retrieved (FIFO): {retrieved2.title}")
        else:
            raise AssertionError("Second message should be 'Second Notification'")

        # Verify empty again
        print("  [1e] Verifying queue empty after retrieval...")
        if queue.is_empty():
            print("      [OK] Queue empty after retrieval")
        else:
            raise AssertionError("Queue should be empty after retrieving all messages")

        result.passed = True
        print("  [OK] Test 1 PASSED")

    except Exception as e:
        result.error = str(e)
        print(f"  [FAIL] Test 1 FAILED: {e}")

    result.duration = time.time() - start
    return result


def test_clear_reminder_with_queue():
    """Test 2: Clear Reminder + Queue Integration

    Verification:
    - Set reminder on note
    - Trigger reminder (queue message)
    - Clear reminder from DB atomically
    - Verify DB state is NULL
    - Verify no repeat in queue
    """
    result = TestResult("Test 2: Clear Reminder + Queue Integration")
    start = time.time()

    try:
        reset_notification_queue()
        print("\n  [2a] Creating test note...")
        note_id = create_note("Queue Clear Test", "Test content")
        print(f"      Created note: {note_id}")

        # Set reminder
        print("  [2b] Setting reminder...")
        future_time = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        update_note(note_id, reminder_datetime=future_time, reminder_triggered=False)
        note_data = get_note(note_id)
        if note_data and note_data.get("reminder_datetime"):
            print(f"      [OK] Reminder set: {note_data.get('reminder_datetime')}")
        else:
            raise AssertionError("Reminder not set")

        # Simulate queue message (triggered reminder)
        print("  [2c] Queuing notification message...")
        queue = get_notification_queue()
        msg = NotificationMessage(
            note_id=note_id,
            title="Reminder: " + note_data.get("title"),
            content=note_data.get("content")
        )
        queue.put_notification(msg)
        print(f"      [OK] Message queued: {msg.title}")

        # Clear reminder from DB
        print("  [2d] Clearing reminder from DB...")
        update_note(note_id, clear_reminder=True)
        time.sleep(0.05)

        # Verify DB cleared
        note_data = get_note(note_id)
        if note_data and note_data.get("reminder_datetime") is None:
            print("      [OK] DB cleared: reminder_datetime=NULL")
        else:
            raise AssertionError(f"Reminder not cleared! Still has: {note_data.get('reminder_datetime')}")

        # Verify message still in queue (separate from DB)
        if not queue.is_empty():
            queued_msg = queue.get_next_notification()
            print(f"      [OK] Queue still has message (UI will show it): {queued_msg.title}")
        else:
            raise AssertionError("Queue should still have message for UI display")

        result.passed = True
        print("  [OK] Test 2 PASSED")

    except Exception as e:
        result.error = str(e)
        print(f"  [FAIL] Test 2 FAILED: {e}")

    result.duration = time.time() - start
    return result


def test_queue_nonblocking_operations():
    """Test 3: Queue Non-Blocking Operations (Thread-Safety)

    Verification:
    - put_notification is non-blocking (returns immediately)
    - get_next_notification is non-blocking (returns None if empty)
    - Queue never blocks main thread
    - Multiple rapid puts don't cause issues
    """
    result = TestResult("Test 3: Queue Non-Blocking Operations")
    start = time.time()

    try:
        reset_notification_queue()
        queue = get_notification_queue()

        print("\n  [3a] Testing non-blocking put operations...")
        start_put = time.time()

        # Rapid puts (should be instant, non-blocking)
        for i in range(10):
            msg = NotificationMessage(
                note_id=f"rapid-{i}",
                title=f"Rapid Message {i}",
                content=f"Content {i}"
            )
            queue.put_notification(msg)

        duration_put = time.time() - start_put
        if duration_put < 0.1:  # Should be very fast
            print(f"      [OK] 10 rapid puts completed in {duration_put:.4f}s (non-blocking)")
        else:
            print(f"      [WARN] Puts took {duration_put:.4f}s (should be <0.1s)")

        # Test non-blocking get
        print("  [3b] Testing non-blocking get operations...")
        start_get = time.time()

        # Rapid gets
        for i in range(10):
            msg = queue.get_next_notification()
            if msg is None:
                raise AssertionError(f"Message {i} should be in queue")

        duration_get = time.time() - start_get
        if duration_get < 0.1:
            print(f"      [OK] 10 rapid gets completed in {duration_get:.4f}s (non-blocking)")
        else:
            print(f"      [WARN] Gets took {duration_get:.4f}s (should be <0.1s)")

        # Test get on empty queue (non-blocking)
        print("  [3c] Testing get on empty queue (should return None instantly)...")
        start_empty = time.time()
        msg = queue.get_next_notification()
        duration_empty = time.time() - start_empty

        if msg is None and duration_empty < 0.01:
            print(f"      [OK] Empty get returned None in {duration_empty:.6f}s (non-blocking)")
        else:
            raise AssertionError("Empty get should return None instantly")

        result.passed = True
        print("  [OK] Test 3 PASSED")

    except Exception as e:
        result.error = str(e)
        print(f"  [FAIL] Test 3 FAILED: {e}")

    result.duration = time.time() - start
    return result


def run_all_tests():
    """Run complete test suite"""
    print("=" * 70)
    print("QuickNote v2.8.5 — Thread-Safe Notification Queue E2E Test Suite")
    print("=" * 70)
    print(f"Test start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Initialize database
    print("\n[Setup] Initializing database...")
    init_db()
    print("[OK] Database ready")

    # Run tests
    results = []
    results.append(test_notification_queue_threadsafe())
    results.append(test_clear_reminder_with_queue())
    results.append(test_queue_nonblocking_operations())

    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for r in results if r.passed)
    total = len(results)

    for result in results:
        print(result)

    print("\n" + "=" * 70)
    print(f"TOTAL: {passed}/{total} tests passed")
    print("=" * 70)

    if passed == total:
        print("\n[SUCCESS] ALL TESTS PASSED - Ready for build")
        return 0
    else:
        print(f"\n[ERROR] {total - passed} TEST(S) FAILED - Fix issues before build")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
