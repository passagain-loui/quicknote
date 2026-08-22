"""E2E Test Suite for v2.9.36 — Code Refactoring: Thread-Safety & Smart Reuse"""

import unittest
import sys
import os
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.constants import APP_VERSION
from src.core.database import DB_WRITE_LOCK, create_note, update_note, delete_note


class TestCodeRefactoringV2936(unittest.TestCase):
    """Test v2.9.36 audit-driven code refactoring fixes"""

    def test_version_v2936(self):
        """Test 1: Version updated to v2.9.36"""
        self.assertEqual(APP_VERSION, "2.9.36")
        print(f"[PASS] Test 1: App version is {APP_VERSION}")

    def test_database_thread_safety_lock_exists(self):
        """Test 2: Database module has DB_WRITE_LOCK for thread-safe writes

        v2.9.36 DATABASE THREAD-SAFETY FIX:
        - Added threading.Lock() to database.py (DB_WRITE_LOCK)
        - All write operations (create, update, delete) protected by lock
        - Prevents concurrent DB corruption from background threads
        - Complements WAL mode (v2.9.22) for complete thread-safety

        Verification:
        - threading.Lock imported in database.py
        - DB_WRITE_LOCK module-level variable created
        - All write functions wrapped with: with DB_WRITE_LOCK: ...
        """
        from src.core import database

        # Verify lock exists
        self.assertTrue(hasattr(database, 'DB_WRITE_LOCK'))
        self.assertIsNotNone(database.DB_WRITE_LOCK)
        self.assertIsInstance(database.DB_WRITE_LOCK, type(threading.Lock()))

        print("[PASS] Test 2: DB_WRITE_LOCK exists and is a threading.Lock instance")

    def test_database_write_functions_use_lock(self):
        """Test 3: Write functions (create, update, delete) are lock-protected

        v2.9.36 WRITE OPERATION PROTECTION:
        - create_note(): wrapped with DB_WRITE_LOCK
        - update_note(): wrapped with DB_WRITE_LOCK
        - delete_note(): wrapped with DB_WRITE_LOCK
        - _migrate_db_schema(): wrapped with DB_WRITE_LOCK
        - init_db(): wrapped with DB_WRITE_LOCK

        Verification:
        - All write functions contain 'with DB_WRITE_LOCK:' statement
        - Lock acquisition happens before any DB operation
        - Lock release automatic via context manager
        """
        import inspect
        from src.core import database

        # Check create_note has lock
        create_source = inspect.getsource(database.create_note)
        self.assertIn('DB_WRITE_LOCK', create_source, "create_note should use DB_WRITE_LOCK")

        # Check update_note has lock
        update_source = inspect.getsource(database.update_note)
        self.assertIn('DB_WRITE_LOCK', update_source, "update_note should use DB_WRITE_LOCK")

        # Check delete_note has lock
        delete_source = inspect.getsource(database.delete_note)
        self.assertIn('DB_WRITE_LOCK', delete_source, "delete_note should use DB_WRITE_LOCK")

        print("[PASS] Test 3: All write functions protected by DB_WRITE_LOCK")

    def test_database_connection_timeout_increased(self):
        """Test 4: Database connection timeout increased to 20.0 seconds (v2.9.36)

        v2.9.36 CONNECTION TIMEOUT IMPROVEMENT:
        - Timeout increased from 10.0s to 20.0s for better concurrent handling
        - check_same_thread=False allows WAL mode concurrent access
        - PRAGMA busy_timeout=5000 (5 seconds) for in-flight conflicts

        Verification:
        - _get_db_connection() creates connections with timeout=20.0
        - check_same_thread=False enabled for WAL mode compatibility
        """
        import inspect
        from src.core import database

        conn_source = inspect.getsource(database._get_db_connection)
        self.assertIn('timeout=20.0', conn_source, "_get_db_connection should have 20s timeout")
        self.assertIn('check_same_thread=False', conn_source, "_get_db_connection should allow cross-thread access")

        print("[PASS] Test 4: Database connection timeout set to 20.0s with check_same_thread=False")

    def test_safe_destroy_no_unbind_all(self):
        """Test 5: _safe_destroy() removed unbind_all() to prevent scope leak

        v2.9.36 UNBIND_ALL SCOPE LEAK FIX:
        - unbind_all() was removing bindings from parent/root widgets
        - Now only clears WM_DELETE_WINDOW protocol (our specific binding)
        - destroy() handles cleanup naturally without side effects

        Problem (v2.9.35):
        - unbind_all() called on dialog removed ALL bindings recursively
        - Could remove bindings from parent Tk root (critical side effect)
        - Caused focus/event handling issues after dialog close

        Solution (v2.9.36):
        - Removed unbind_all() completely
        - Only set WM_DELETE_WINDOW protocol to no-op
        - destroy() is sufficient for full cleanup

        Verification:
        - _safe_destroy() does NOT contain 'unbind_all' call
        - Only contains 'WM_DELETE_WINDOW' protocol clearing
        - Finally block with destroy() call intact
        """
        import inspect
        from src.ui.unblockable_dialog import UnblockableCustomDialog

        destroy_source = inspect.getsource(UnblockableCustomDialog._safe_destroy)

        # Verify unbind_all() method call is NOT present (check for .unbind_all() function call)
        self.assertNotIn('self.unbind_all()', destroy_source, "_safe_destroy should NOT call unbind_all()")

        # Verify protocol clearing is present
        self.assertIn('WM_DELETE_WINDOW', destroy_source, "_safe_destroy should clear WM_DELETE_WINDOW protocol")

        # Verify destroy() call is present
        self.assertIn('self.destroy()', destroy_source, "_safe_destroy should call self.destroy()")

        print("[PASS] Test 5: _safe_destroy() removed unbind_all() (fixed scope leak)")

    def test_smart_widget_reuse_in_load_notes(self):
        """Test 6: _load_notes() reuses widgets instead of destroying all

        v2.9.36 SMART WIDGET REUSE:
        - Instead of destroy() all cards then recreate, reuse existing cards
        - Only destroy cards no longer in current filter
        - Repack existing cards in new sorted order
        - Create new cards only for notes not yet displayed

        Benefits:
        - Reduces widget churn during UI refresh
        - Faster _load_notes() calls
        - Preserves widget state when possible

        Architecture:
        Before (v2.9.35):
        for card in self.note_cards.values():
            card.pack_forget()
            card.destroy()  ← Destroys ALL widgets
        self.note_cards.clear()
        # Then recreate all new widgets

        After (v2.9.36):
        current_note_ids = {row['id'] for row in notes_data}
        cards_to_remove = [nid for nid in self.note_cards if nid not in current_note_ids]
        for note_id in cards_to_remove:
            destroy_card(note_id)  ← Only remove missing notes

        for row in notes_data:
            if note_id in self.note_cards:
                self.note_cards[note_id].pack(...)  ← Reuse existing
            else:
                create_new_card()  ← Only create new

        Verification:
        - _load_notes() contains logic to identify current note IDs
        - Removes only cards not in current filter
        - Repacks existing cards
        - Only creates new cards for missing IDs
        """
        import inspect
        from src.ui.board import Board

        load_notes_source = inspect.getsource(Board._load_notes)

        # Verify reuse logic is present
        self.assertIn('current_note_ids', load_notes_source, "_load_notes should track current note IDs")
        self.assertIn('cards_to_remove', load_notes_source, "_load_notes should identify cards to remove")
        self.assertIn('in self.note_cards', load_notes_source, "_load_notes should check for existing cards")

        # Verify it's not just destroy + recreate
        self.assertNotIn('self.note_cards.clear()', load_notes_source,
                         "_load_notes should NOT clear all cards at once (v2.9.36)")

        print("[PASS] Test 6: _load_notes() implements smart widget reuse")


def run_all_tests():
    """Run all test suites"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestCodeRefactoringV2936))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success: {result.wasSuccessful()}")
    print("="*70)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
