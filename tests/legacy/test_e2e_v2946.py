"""E2E Tests for v2.9.46: Single-Instance Signal Listener + Graceful Shutdown + Temp Cleanup

1. Lock acquire/release semantics
2. Second-instance SHOW signal actually reaches first instance's dispatcher (socket round-trip)
3. graceful_shutdown() is safe to call repeatedly / with None args
4. cleanup_temp_artifacts() purges stale qn_test_* dirs and keeps fresh ones
5. Version constant is 2.9.46 (semantic format)
"""

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

import os
import time
import tempfile
import threading
import unittest
from pathlib import Path

# Import main module pieces (main.py at repo root)
sys_path_root = str(Path(__file__).resolve().parent.parent)
if sys_path_root not in _sys.path:
    _sys.path.insert(0, sys_path_root)

import importlib.util

_spec = importlib.util.spec_from_file_location("qn_main", Path(sys_path_root) / "main.py")
qn_main = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qn_main)

from src.core.constants import APP_VERSION


class TestV2946SingleInstanceLock(unittest.TestCase):
    """Test Suite 1: Lock semantics"""

    def test_lock_acquire_release_reacquire(self):
        """Test 1a: acquire→True, after release another acquire succeeds"""
        lock1 = qn_main.SingleInstanceLock()
        self.assertTrue(lock1.acquire(), "First acquire must succeed")
        lock1.release()

        lock2 = qn_main.SingleInstanceLock()
        self.assertTrue(lock2.acquire(), "Acquire after release must succeed")
        lock2.release()

    def test_lock_exclusive_while_held(self):
        """Test 1b: second acquire fails while first holds the port"""
        lock1 = qn_main.SingleInstanceLock()
        self.assertTrue(lock1.acquire())
        try:
            lock2 = qn_main.SingleInstanceLock()
            self.assertFalse(lock2.acquire(), "Second acquire must fail while held")
        finally:
            lock1.release()


class TestV2946SignalDispatch(unittest.TestCase):
    """Test Suite 2: SHOW signal reaches the first instance's dispatcher"""

    def test_show_signal_dispatches_bring_to_front(self):
        """Test 2a: send_signal_to_existing_instance() triggers registered dispatcher"""
        lock = qn_main.SingleInstanceLock()
        self.assertTrue(lock.acquire())

        dispatched = threading.Event()
        def dispatcher():
            dispatched.set()

        thread = qn_main.start_lock_signal_listener(lock, dispatcher)
        self.assertIsNotNone(thread, "Listener thread must start while lock held")

        ok = qn_main.send_signal_to_existing_instance()
        self.assertTrue(ok, "Signal sender must connect+send successfully")

        self.assertTrue(dispatched.wait(timeout=5.0),
                        "Dispatcher must fire within 5s of SHOW signal")

        # Closing the socket stops the listener loop cleanly
        lock.release()
        thread.join(timeout=3.0)
        self.assertFalse(thread.is_alive(), "Listener must exit after socket close")


class TestV2946GracefulShutdown(unittest.TestCase):
    """Test Suite 3: shutdown helper safety"""

    def test_shutdown_none_args_safe_and_repeatable(self):
        """Test 3a: graceful_shutdown(None, None) twice raises nothing"""
        qn_main.graceful_shutdown(None, None)
        qn_main.graceful_shutdown(None, None)  # idempotent


class TestV2946TempCleanup(unittest.TestCase):
    """Test Suite 4: stale temp artifact purge"""

    def test_stale_qn_test_dir_removed_fresh_kept(self):
        """Test 4a: qn_test_* older than 7 days removed; fresh ones kept"""
        tmp = tempfile.gettempdir()
        stale = Path(tmp) / f"qn_test_v2946_stale_{os.getpid()}"
        fresh = Path(tmp) / f"qn_test_v2946_fresh_{os.getpid()}"
        stale.mkdir(exist_ok=True)
        fresh.mkdir(exist_ok=True)
        # Backdate stale dir by 8 days
        old_ts = time.time() - 8 * 86400
        os.utime(stale, (old_ts, old_ts))

        try:
            qn_main.cleanup_temp_artifacts()
            self.assertFalse(stale.exists(), "Stale qn_test_ dir must be purged")
            self.assertTrue(fresh.exists(), "Fresh qn_test_ dir must be kept")
        finally:
            import shutil
            shutil.rmtree(str(stale), ignore_errors=True)
            shutil.rmtree(str(fresh), ignore_errors=True)


class TestV2946Version(unittest.TestCase):
    """Test Suite 5: version constant"""

    def test_version_is_2946(self):
        """Test 5a: APP_VERSION == '2.9.46'"""
        self.assertEqual(APP_VERSION, "2.9.46")

    def test_version_semantic_format(self):
        """Test 5b: version matches semantic X.Y.Z"""
        parts = APP_VERSION.split(".")
        self.assertEqual(len(parts), 3)
        for part in parts:
            self.assertTrue(part.isdigit())


if __name__ == "__main__":
    unittest.main(verbosity=2)
