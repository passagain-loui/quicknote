"""QuickNote E2E test package.

v2.9.45 Build-Release Audit Fix:
- Force UTF-8 stdio so unicode test output (✓ ✔ →) never crashes under
  legacy codepage consoles (charmap) when run from external gatekeepers.
"""
import sys
import gc
import unittest
import faulthandler

# v2.9.45: dump native/Python stacks on access violations (flaky Tk crash diagnosis)
faulthandler.enable()

# v2.9.45 Tk 9.0.2 AV mitigation: the suite creates/destroys hundreds of tk.Tk()
# roots in one process; delayed GC of destroyed-widget cycles accumulates native
# handles until tcl9tk90.dll faults. Force collection after EVERY test.
_orig_test_run = unittest.case.TestCase.run

def _gc_after_test_run(self, *args, **kwargs):
    try:
        return _orig_test_run(self, *args, **kwargs)
    finally:
        gc.collect()

unittest.case.TestCase.run = _gc_after_test_run

for _stream_name in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_name, None)
    if _stream is not None and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
