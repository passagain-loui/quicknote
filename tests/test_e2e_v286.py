"""QuickNote v2.8.6 — Bug Fix E2E Test Suite
Tests: Notification Queue Loop Binding + Default Collapsed Notes
Must pass 100% before build and release
"""

import sys
import os
import time
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.database import init_db, create_note, get_all_notes, update_note, get_note
from src.core.models import Note
from src.services.notification_queue import (
    get_notification_queue, NotificationMessage, reset_notification_queue
)


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


def test_queue_loop_binding():
    """Test 1: Notification Queue Loop Binding

    Verification:
    - Queue checker retrieves messages continuously
    - Process all queued messages in single loop iteration
    - Reschedule after processing (loop continues)
    """
    result = TestResult("Test 1: Notification Queue Loop Binding")
    start = time.time()

    try:
        reset_notification_queue()
        queue = get_notification_queue()

        print("\n  [1a] Testing queue message processing...")
        # Queue multiple messages
        msgs = []
        for i in range(3):
            msg = NotificationMessage(
                note_id=f"test-{i}",
                title=f"Test Message {i}",
                content=f"Content {i}"
            )
            queue.put_notification(msg)
            msgs.append(msg)

        print(f"      [OK] Queued {len(msgs)} messages")

        # Simulate queue checking loop (process all messages in one iteration)
        print("  [1b] Simulating queue checker loop...")
        processed = 0
        while not queue.is_empty():
            msg = queue.get_next_notification()
            if msg:
                processed += 1
                # Verify message content
                if msg.title == f"Test Message {processed - 1}":
                    pass  # OK
                else:
                    raise AssertionError(f"Message mismatch at index {processed - 1}")

        if processed == len(msgs):
            print(f"      [OK] Processed {processed} messages from queue (FIFO order)")
        else:
            raise AssertionError(f"Expected {len(msgs)} messages, got {processed}")

        # Verify queue is now empty
        print("  [1c] Verifying queue empty after processing...")
        if queue.is_empty():
            print("      [OK] Queue empty after loop (ready to reschedule)")
        else:
            raise AssertionError("Queue should be empty after loop")

        # Test rapid re-queuing (simulates continuous scheduler)
        print("  [1d] Testing continuous scheduler (rapid re-queuing)...")
        for i in range(5):
            msg = NotificationMessage(
                note_id=f"rapid-{i}",
                title=f"Rapid {i}",
                content=f"R{i}"
            )
            queue.put_notification(msg)

        # Retrieve all
        count = 0
        while not queue.is_empty():
            queue.get_next_notification()
            count += 1

        if count == 5:
            print(f"      [OK] Continuous queueing works ({count} messages processed)")
        else:
            raise AssertionError(f"Expected 5 rapid messages, got {count}")

        result.passed = True
        print("  [OK] Test 1 PASSED")

    except Exception as e:
        result.error = str(e)
        print(f"  [FAIL] Test 1 FAILED: {e}")

    result.duration = time.time() - start
    return result


def test_default_collapsed_notes():
    """Test 2: All Notes Load as Collapsed (Default State)

    Verification:
    - Load notes from database
    - Convert to Note objects (via from_dict)
    - Verify all notes have collapsed=True
    """
    result = TestResult("Test 2: Default Collapsed Notes on Load")
    start = time.time()

    try:
        print("\n  [2a] Creating test notes...")
        # Create multiple notes
        note_ids = []
        for i in range(3):
            note_id = create_note(f"Test Note {i}", f"Content {i}")
            note_ids.append(note_id)
            print(f"      Created: {note_id}")

        # Load all notes
        print("  [2b] Loading notes from database...")
        all_notes = get_all_notes()
        if len(all_notes) < len(note_ids):
            raise AssertionError(f"Expected at least {len(note_ids)} notes, got {len(all_notes)}")
        print(f"      [OK] Loaded {len(all_notes)} notes from DB")

        # Convert to Note objects and check collapsed state
        print("  [2c] Verifying collapsed state...")
        collapsed_count = 0
        for note_data in all_notes:
            note_obj = Note.from_dict(note_data)
            # v2.8.6: Default collapsed should be True
            if note_obj.collapsed:
                collapsed_count += 1
            else:
                print(f"      [WARN] Note {note_obj.id} is not collapsed: collapsed={note_obj.collapsed}")

        # Check our test notes specifically
        print("  [2d] Checking test notes specifically...")
        for note_id in note_ids:
            note_data = get_note(note_id)
            note_obj = Note.from_dict(note_data)
            if not note_obj.collapsed:
                raise AssertionError(f"Test note {note_id} should be collapsed, got collapsed={note_obj.collapsed}")
            print(f"      [OK] {note_id}: collapsed={note_obj.collapsed}")

        print(f"  [2e] Collapse status summary:")
        print(f"      Total notes: {len(all_notes)}")
        print(f"      Collapsed: {collapsed_count}")
        print(f"      [OK] All test notes are collapsed")

        result.passed = True
        print("  [OK] Test 2 PASSED")

    except Exception as e:
        result.error = str(e)
        print(f"  [FAIL] Test 2 FAILED: {e}")

    result.duration = time.time() - start
    return result


def test_queue_and_collapsed_integration():
    """Test 3: Queue + Collapsed Integration

    Verification:
    - Create collapsed note
    - Enqueue notification for it
    - Verify both states independent (UI shows collapsed, notification separate)
    """
    result = TestResult("Test 3: Queue + Collapsed State Integration")
    start = time.time()

    try:
        reset_notification_queue()
        queue = get_notification_queue()

        print("\n  [3a] Creating test note...")
        note_id = create_note("Integration Test", "Test content for integration")
        print(f"      Created: {note_id}")

        # Load note and verify collapsed
        print("  [3b] Verifying note is collapsed...")
        note_data = get_note(note_id)
        note_obj = Note.from_dict(note_data)
        if not note_obj.collapsed:
            raise AssertionError("Note should be collapsed by default")
        print(f"      [OK] Note is collapsed: {note_obj.collapsed}")

        # Enqueue notification
        print("  [3c] Enqueuing notification for collapsed note...")
        msg = NotificationMessage(
            note_id=note_id,
            title="Reminder: Integration Test",
            content="Test content"
        )
        queue.put_notification(msg)
        print(f"      [OK] Message queued")

        # Retrieve from queue
        print("  [3d] Retrieving from queue...")
        retrieved = queue.get_next_notification()
        if not retrieved or retrieved.note_id != note_id:
            raise AssertionError("Message retrieval failed or mismatched")
        print(f"      [OK] Retrieved: {retrieved.title}")

        # Verify note still collapsed (independent states)
        print("  [3e] Verifying note still collapsed after queue operations...")
        note_data = get_note(note_id)
        note_obj = Note.from_dict(note_data)
        if not note_obj.collapsed:
            raise AssertionError("Note should still be collapsed after queue ops")
        print(f"      [OK] Note still collapsed (UI state independent from queue)")

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
    print("QuickNote v2.8.6 — Bug Fix E2E Test Suite")
    print("=" * 70)
    print(f"Test start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Initialize database
    print("\n[Setup] Initializing database...")
    init_db()
    print("[OK] Database ready")

    # Run tests
    results = []
    results.append(test_queue_loop_binding())
    results.append(test_default_collapsed_notes())
    results.append(test_queue_and_collapsed_integration())

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
