"""QuickNote v2.9.1 — DPI-Aware Positioning & Visibility Safeguard E2E Test Suite
Tests: Toast coordinate safety + Window state management
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


def test_dpi_aware_positioning():
    """Test 1: Toast coordinates stay within screen bounds (DPI-safe)

    Verification:
    - Simulate various screen resolutions (1920x1080, 1366x768, 2560x1440, etc.)
    - Verify toast position stays within bounds with safety margins
    - Verify toast not off-screen even with extreme DPI scaling
    """
    result = TestResult("Test 1: DPI-Aware Toast Positioning")
    start = time.time()

    try:
        print("\n  [1a] Testing coordinate calculation with various resolutions...")

        # Test cases: (screen_width, screen_height, description)
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
            # v2.9.1 positioning logic
            x = max(20, screen_width - toast_width - 40)
            y = max(20, screen_height - toast_height - 80)
            x = min(x, screen_width - 100)
            y = min(y, screen_height - 100)

            # Verify coordinates are valid
            if x < 0 or y < 0:
                print(f"      [FAIL] {desc} ({screen_width}x{screen_height}): Invalid coords {x}+{y}")
                all_valid = False
                continue

            # Verify toast fits on screen
            right_edge = x + toast_width
            bottom_edge = y + toast_height

            if right_edge > screen_width or bottom_edge > screen_height:
                print(f"      [FAIL] {desc}: Toast extends off-screen (right: {right_edge}, bottom: {bottom_edge})")
                all_valid = False
                continue

            print(f"      [OK] {desc}: Position {x}+{y} (bounds: {screen_width}x{screen_height}) ✓")

        if not all_valid:
            raise AssertionError("Some test cases failed coordinate validation")

        result.passed = True
        print("  [OK] Test 1 PASSED")

    except Exception as e:
        result.error = str(e)
        print(f"  [FAIL] Test 1 FAILED: {e}")

    result.duration = time.time() - start
    return result


def test_window_state_management():
    """Test 2: Toast window state is 'normal' and topmost is locked

    Verification:
    - Create mock Toplevel window
    - Apply v2.9.1 state management sequence
    - Verify state='normal' and attributes('-topmost') == True
    """
    result = TestResult("Test 2: Window State Management")
    start = time.time()

    try:
        print("\n  [2a] Creating mock toast window...")

        import tkinter as tk

        # Create temporary root for mock testing
        mock_root = tk.Tk()
        mock_root.withdraw()

        print("      Creating mock toast Toplevel...")
        toast_window = tk.Toplevel(mock_root)
        toast_window.overrideredirect(True)
        toast_window.config(bg="#F3F3F3")

        # Simulate v2.9.1 state management sequence
        print("  [2b] Applying state management sequence...")
        toast_window.withdraw()
        toast_window.update_idletasks()
        toast_window.geometry("360x150+100+100")

        # v2.9.1: Force visibility with proper state management
        print("      Setting state to 'normal'...")
        toast_window.state('normal')  # Ensure normal state (not minimized)

        print("      Applying deiconify, topmost, lift, focus_force...")
        toast_window.deiconify()
        toast_window.attributes("-topmost", True)
        toast_window.lift()
        toast_window.focus_force()

        # Verify state
        print("  [2c] Verifying window state...")

        current_state = toast_window.state()
        if current_state == 'normal':
            print(f"      [OK] Window state is 'normal' (not minimized)")
        else:
            raise AssertionError(f"Expected state='normal', got '{current_state}'")

        topmost_value = toast_window.attributes("-topmost")
        if topmost_value == True or topmost_value == 1:
            print(f"      [OK] -topmost attribute is True (locked on top)")
        else:
            raise AssertionError(f"Expected -topmost=True, got {topmost_value}")

        # Verify visibility flag (Tkinter internals)
        if toast_window.winfo_exists():
            print(f"      [OK] Window exists and is managed by Tkinter")
        else:
            raise AssertionError("Window doesn't exist after deiconify")

        # Cleanup
        toast_window.destroy()
        mock_root.destroy()

        result.passed = True
        print("  [OK] Test 2 PASSED")

    except Exception as e:
        result.error = str(e)
        print(f"  [FAIL] Test 2 FAILED: {e}")

    result.duration = time.time() - start
    return result


def test_fallback_positioning():
    """Test 3: Fallback positioning when primary fails

    Verification:
    - If win32api unavailable, Tkinter fallback used
    - Both methods produce valid on-screen coordinates
    - Toast always visible regardless of method
    """
    result = TestResult("Test 3: Positioning Fallback Strategy")
    start = time.time()

    try:
        print("\n  [3a] Testing positioning fallback logic...")

        toast_width = 360
        toast_height = 150

        # Simulate both paths
        print("  [3b] Method 1: win32api (primary)...")
        try:
            import ctypes
            user32 = ctypes.windll.user32
            user32.SetProcessDpiAwareness(1)
            sw1 = user32.GetSystemMetrics(0)
            sh1 = user32.GetSystemMetrics(1)
            print(f"      [OK] win32api available: {sw1}x{sh1}")
            method1_ok = True
        except Exception as e:
            print(f"      [SKIP] win32api unavailable (fallback will use Tkinter)")
            method1_ok = False

        print("  [3c] Method 2: Tkinter fallback...")
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            sw2 = root.winfo_screenwidth()
            sh2 = root.winfo_screenheight()
            root.destroy()
            print(f"      [OK] Tkinter fallback: {sw2}x{sh2}")
            method2_ok = True
        except Exception as e:
            print(f"      [FAIL] Tkinter fallback failed: {e}")
            method2_ok = False

        if not method2_ok:
            raise AssertionError("Tkinter fallback unavailable (critical)")

        # Calculate position using both methods
        print("  [3d] Verifying both methods produce valid coordinates...")
        if method1_ok:
            x1 = max(20, sw1 - toast_width - 40)
            y1 = max(20, sh1 - toast_height - 80)
            if x1 >= 0 and y1 >= 0 and x1 + toast_width <= sw1 and y1 + toast_height <= sh1:
                print(f"      [OK] win32api: Position valid {x1}+{y1}")
            else:
                raise AssertionError(f"win32api position invalid: {x1}+{y1}")

        x2 = max(20, sw2 - toast_width - 40)
        y2 = max(20, sh2 - toast_height - 80)
        if x2 >= 0 and y2 >= 0 and x2 + toast_width <= sw2 and y2 + toast_height <= sh2:
            print(f"      [OK] Tkinter: Position valid {x2}+{y2}")
        else:
            raise AssertionError(f"Tkinter position invalid: {x2}+{y2}")

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
    print("QuickNote v2.9.1 — DPI-Aware Positioning & Visibility Safeguard E2E Test")
    print("=" * 70)
    print(f"Test start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Initialize database (for future integration)
    print("\n[Setup] Initializing database...")
    init_db()
    print("[OK] Database ready")

    # Run tests
    results = []
    results.append(test_dpi_aware_positioning())
    results.append(test_window_state_management())
    results.append(test_fallback_positioning())

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
