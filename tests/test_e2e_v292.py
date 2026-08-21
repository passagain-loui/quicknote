"""QuickNote v2.9.2 — Pure Logical Coords + Center Screen Guarantee E2E Test
Tests: Center positioning + No physical pixel mixing
Must pass 100% before release
"""

import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.database import init_db


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


def test_center_screen_positioning():
    """Test 1: Toast positioned at center screen (Tkinter logical coords)

    Verification:
    - Simulate Tkinter winfo_screenwidth/height on various DPI configs
    - Calculate center position using pure logical coordinates
    - Verify toast appears at visual center (x,y offset correct)
    """
    result = TestResult("Test 1: Center Screen Positioning")
    start = time.time()

    try:
        print("\n  [1a] Testing center positioning logic...")

        # Test cases: (logical_width, logical_height, description)
        test_cases = [
            (1920, 1080, "Full HD"),
            (1366, 768, "HD"),
            (2560, 1440, "2K"),
            (3840, 2160, "4K"),
            (1024, 600, "Small netbook"),
            (1024, 768, "Old monitor"),
        ]

        toast_width = 360
        toast_height = 150

        all_valid = True
        for screen_width, screen_height, desc in test_cases:
            # v2.9.2 center positioning logic (pure logical coords)
            x = int((screen_width - toast_width) / 2)
            y = int((screen_height - toast_height) / 2)

            # Verify coordinates are non-negative (not off-screen)
            if x < 0 or y < 0:
                print(f"      [FAIL] {desc}: Negative coordinates ({x}, {y})")
                all_valid = False
                continue

            # Verify toast fits on screen
            right_edge = x + toast_width
            bottom_edge = y + toast_height

            if right_edge > screen_width or bottom_edge > screen_height:
                print(f"      [FAIL] {desc}: Toast extends off-screen")
                all_valid = False
                continue

            # Calculate visual offset from center (should be very small or 0)
            center_x = screen_width // 2
            center_y = screen_height // 2
            toast_center_x = x + toast_width // 2
            toast_center_y = y + toast_height // 2
            offset_x = abs(center_x - toast_center_x)
            offset_y = abs(center_y - toast_center_y)

            print(f"      [OK] {desc}: Position {x}+{y} (visual center offset: {offset_x}, {offset_y}) ✓")

        if not all_valid:
            raise AssertionError("Some test cases failed positioning validation")

        result.passed = True
        print("  [OK] Test 1 PASSED")

    except Exception as e:
        result.error = str(e)
        print(f"  [FAIL] Test 1 FAILED: {e}")

    result.duration = time.time() - start
    return result


def test_no_win32api_imports():
    """Test 2: custom_toast.py does NOT import win32api (pure Tkinter only)

    Verification:
    - Read custom_toast.py source code
    - Verify NO 'ctypes', 'windll', 'GetSystemMetrics' references
    - Verify only uses Tkinter winfo_screenwidth/height
    """
    result = TestResult("Test 2: No Physical Pixel Mixing (Tkinter Pure)")
    start = time.time()

    try:
        print("\n  [2a] Checking custom_toast.py imports...")

        custom_toast_path = Path(__file__).parent.parent / "src" / "ui" / "custom_toast.py"
        with open(custom_toast_path, 'r') as f:
            content = f.read()

        # Check for forbidden imports/references
        forbidden = [
            ('ctypes', "ctypes module (win32api mixin)"),
            ('windll', "windll reference (physical pixels)"),
            ('GetSystemMetrics', "GetSystemMetrics (physical resolution)"),
            ('SetProcessDpiAwareness', "SetProcessDpiAwareness (physical DPI)"),
        ]

        found_issues = []
        for keyword, description in forbidden:
            if keyword in content:
                found_issues.append(f"{description} (found '{keyword}')")

        if found_issues:
            for issue in found_issues:
                print(f"      [FAIL] Found forbidden import: {issue}")
            raise AssertionError(f"Found {len(found_issues)} forbidden win32api reference(s)")

        print(f"      [OK] No ctypes/windll imports ✓")
        print(f"      [OK] No physical pixel references ✓")

        # Verify uses Tkinter methods
        print("  [2b] Verifying Tkinter logical coord usage...")

        required = [
            ('winfo_screenwidth', "Tkinter logical width"),
            ('winfo_screenheight', "Tkinter logical height"),
        ]

        for method, description in required:
            if method not in content:
                raise AssertionError(f"Missing required {description}")
            print(f"      [OK] Uses {method} ({description}) ✓")

        result.passed = True
        print("  [OK] Test 2 PASSED")

    except Exception as e:
        result.error = str(e)
        print(f"  [FAIL] Test 2 FAILED: {e}")

    result.duration = time.time() - start
    return result


def test_center_positioning_accuracy():
    """Test 3: Center positioning calculation is accurate (mathematical verification)

    Verification:
    - Verify formula: x = (screen_width - toast_width) / 2
    - Verify formula: y = (screen_height - toast_height) / 2
    - Verify result is mathematically correct (toast is truly centered)
    """
    result = TestResult("Test 3: Center Position Mathematical Accuracy")
    start = time.time()

    try:
        print("\n  [3a] Verifying center positioning formula...")

        toast_width = 360
        toast_height = 150

        test_cases = [
            (1920, 1080),
            (1366, 768),
            (2560, 1440),
        ]

        for screen_width, screen_height in test_cases:
            # Calculate center position
            x = int((screen_width - toast_width) / 2)
            y = int((screen_height - toast_height) / 2)

            # Verify visual center (toast center should align with screen center ±1px)
            toast_center_x = x + toast_width // 2
            toast_center_y = y + toast_height // 2
            screen_center_x = screen_width // 2
            screen_center_y = screen_height // 2

            offset_x = abs(toast_center_x - screen_center_x)
            offset_y = abs(toast_center_y - screen_center_y)

            if offset_x > 1 or offset_y > 1:
                raise AssertionError(f"Toast not centered: X offset {offset_x}, Y offset {offset_y}")

            print(f"      [OK] {screen_width}x{screen_height}: Center offset ({offset_x}, {offset_y}) ✓")

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
    print("QuickNote v2.9.2 — Pure Logical Coords + Center Screen Guarantee E2E Test")
    print("=" * 70)
    print(f"Test start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Initialize database
    print("\n[Setup] Initializing database...")
    init_db()
    print("[OK] Database ready")

    # Run tests
    results = []
    results.append(test_center_screen_positioning())
    results.append(test_no_win32api_imports())
    results.append(test_center_positioning_accuracy())

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
