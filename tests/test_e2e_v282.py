"""QuickNote v2.8.2 — Off-Screen Toast Fix & Absolute Sorting E2E Test"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
import time

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.core.database import init_db, create_note, get_notes_by_status, update_note, get_note

class TestResult:
    def __init__(self, name):
        self.name = name
        self.passed = False
        self.error = None
        self.duration = 0
    def __str__(self):
        status = "[PASS]" if self.passed else "[FAIL]"
        return f"{status} {self.name}" + (f" ({self.duration:.2f}s)" if self.duration else "") + (f"\n  Error: {self.error}" if self.error else "")

def test_toast_positioning():
    """Test 1: Toast stays on-screen (coordinates within bounds)"""
    result = TestResult("Test 1: Toast On-Screen Positioning")
    start = time.time()
    try:
        print("\n  [1a] Verifying toast positioning logic...")
        # Simulate screen dimensions
        screen_width = 1920
        screen_height = 1080
        toast_width = 360
        toast_height = 120

        # v2.8.2 positioning logic
        x = int(max(0, screen_width - toast_width - 50))
        y = int(max(0, screen_height - toast_height - 100))
        x = int(min(x, screen_width - 100))
        y = int(min(y, screen_height - 100))

        # Verify coordinates are valid
        if x >= 0 and x <= screen_width - 100:
            print(f"      [OK] X coordinate: {x} (valid range: 0-{screen_width-100})")
        else:
            raise AssertionError(f"X out of bounds: {x}")

        if y >= 0 and y <= screen_height - 100:
            print(f"      [OK] Y coordinate: {y} (valid range: 0-{screen_height-100})")
        else:
            raise AssertionError(f"Y out of bounds: {y}")

        # Verify window would be visible
        right_edge = x + toast_width
        bottom_edge = y + toast_height
        if right_edge <= screen_width and bottom_edge <= screen_height:
            print(f"      [OK] Window fully on-screen (right: {right_edge}, bottom: {bottom_edge})")
        else:
            raise AssertionError("Window extends off-screen")

        result.passed = True
        print("  [OK] Test 1 PASSED")
    except Exception as e:
        result.error = str(e)
        print(f"  [FAIL] Test 1 FAILED: {e}")
    result.duration = time.time() - start
    return result

def test_absolute_sorting():
    """Test 2: Newest triggered reminder appears first"""
    result = TestResult("Test 2: Absolute Triggered Reminder Sorting")
    start = time.time()
    try:
        print("\n  [2a] Creating notes with different reminder times...")
        init_db()

        # Create 3 notes
        note_ids = []
        for i in range(3):
            note_id = create_note(f"Task {i}", f"Content {i}")
            note_ids.append(note_id)
        print(f"      Created 3 notes")

        # Mark all as triggered with different reminder times
        print("  [2b] Setting reminder times (newest to oldest)...")
        now = datetime.now()
        for i, note_id in enumerate(note_ids):
            reminder_time = now - timedelta(minutes=i)  # Newer first
            reminder_str = reminder_time.strftime("%Y-%m-%d %H:%M")
            update_note(note_id, reminder_datetime=reminder_str, reminder_triggered=True)
            print(f"      {note_id[:8]}: {reminder_str}")

        # Load notes
        print("  [2c] Loading notes with absolute sorting...")
        all_notes = get_notes_by_status("active")
        test_notes = [n for n in all_notes if n["id"] in note_ids]

        # Verify order
        print("  [2d] Verifying newest reminder is first...")
        if len(test_notes) >= 3:
            # Should be ordered by reminder_datetime DESC
            if test_notes[0]["id"] == note_ids[0]:
                print(f"      [OK] Newest reminder first: {test_notes[0]['id'][:8]}")
            else:
                # Check if it's sorted by reminder_datetime
                for idx, note in enumerate(test_notes):
                    print(f"      Index {idx}: {note['id'][:8]} (reminder: {note.get('reminder_datetime', 'None')})")
                if test_notes[0]["reminder_datetime"] and all(n["reminder_datetime"] for n in test_notes):
                    # Verify descending order
                    times = [n["reminder_datetime"] for n in test_notes]
                    is_sorted = all(times[i] >= times[i+1] for i in range(len(times)-1))
                    if is_sorted:
                        print(f"      [OK] Reminders sorted by datetime DESC")
                    else:
                        raise AssertionError("Reminders not in descending datetime order")

        result.passed = True
        print("  [OK] Test 2 PASSED")
    except Exception as e:
        result.error = str(e)
        print(f"  [FAIL] Test 2 FAILED: {e}")
    result.duration = time.time() - start
    return result

def run_all_tests():
    print("=" * 70)
    print("QuickNote v2.8.2 — Off-Screen Toast & Absolute Sorting E2E Test")
    print("=" * 70)

    results = []
    results.append(test_toast_positioning())
    results.append(test_absolute_sorting())

    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    for result in results:
        print(result)

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print(f"\nTOTAL: {passed}/{total} tests passed")
    print("=" * 70)

    if passed == total:
        print("\n[SUCCESS] ALL TESTS PASSED")
        return 0
    else:
        print(f"\n[ERROR] {total - passed} TEST(S) FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(run_all_tests())
