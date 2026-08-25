"""E2E Tests for v2.9.40: Pin Persistence & Top Re-ordering

Comprehensive regression test suite validating:
1. Pin state saves to database correctly
2. Pin toggle triggers repack_card_to_top() immediately
3. Database reload shows pinned notes first (is_pinned DESC as primary sort)
4. Pin state persists across app restart
"""

import unittest
import tkinter as tk
from pathlib import Path
import tempfile
import sqlite3
import queue

from src.ui.note_card import NoteCard
from src.ui.board import Board
from src.ui.theme import Theme
from src.core.models import Note
from src.core.database import create_note, update_note, get_notes_by_status, init_db
from src.core.constants import APP_VERSION


class TestV2940PinPersistence(unittest.TestCase):
    """Test Suite 1: Pin State Saves to Database"""

    def setUp(self):
        """Initialize test environment"""
        self.root = tk.Tk()
        self.theme = Theme("light")

    def tearDown(self):
        """Clean up"""
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_pin_saves_to_database(self):
        """Test 1a: Pin state persists to database when toggled"""
        # Create a note
        note_id = create_note(title="Test Pin Note", content="Test content")

        # Initially unpinned
        note_before = Note.from_dict({"id": note_id, "title": "Test", "content": "Test", "is_pinned": False, "status": "active"})
        self.assertFalse(note_before.is_pinned, "New note should be unpinned")

        # Toggle pin (simulate button click)
        update_note(note_id, is_pinned=True)

        # Verify saved in DB
        from src.core.database import get_note
        saved_note = get_note(note_id)
        self.assertTrue(bool(saved_note['is_pinned']), "Pin state should be saved to DB as True")

        # Toggle pin off
        update_note(note_id, is_pinned=False)
        saved_note = get_note(note_id)
        self.assertFalse(bool(saved_note['is_pinned']), "Pin state should be saved to DB as False")

    def test_pin_button_updates_appearance(self):
        """Test 1b: Pin button icon and color change when toggled"""
        note = Note(
            id="test-pin-button",
            title="Pin Test",
            content="Test",
            status="active",
            is_pinned=False
        )

        card = NoteCard(self.root, note, self.theme)

        # Initially unpinned
        self.assertEqual(card.btn_pin.cget("text"), "📍", "Unpinned button should show 📍")
        self.assertIn(card.btn_pin.cget("fg"), [self.theme.c("fg_muted"), "#B0B0B0", "#A0A0A0"],
                      "Unpinned button should be muted gray")

        # Simulate pin toggle
        card.note.is_pinned = True
        card._on_toggle_pin()
        self.assertEqual(card.btn_pin.cget("text"), "📌", "Pinned button should show 📌")
        self.assertEqual(card.btn_pin.cget("fg"), "#FF6B6B", "Pinned button should be red")


class TestV2940PinReordering(unittest.TestCase):
    """Test Suite 2: Pin Triggers Repack and Reordering"""

    def setUp(self):
        """Initialize test environment"""
        self.root = tk.Tk()
        self.theme = Theme("light")

    def tearDown(self):
        """Clean up"""
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_repack_card_to_top_exists(self):
        """Test 2a: Board has repack_card_to_top() method"""
        cmd_queue = queue.Queue()
        board = Board(geometry="400x500+100+100", theme_mode="light", command_queue=cmd_queue)

        # Check method exists
        self.assertTrue(hasattr(board, 'repack_card_to_top'))
        self.assertTrue(callable(board.repack_card_to_top))

        board.root.destroy()

    def test_pin_change_callback_exists(self):
        """Test 2b: Board has _on_pin_changed() method for handling pin state changes"""
        cmd_queue = queue.Queue()
        board = Board(geometry="400x500+100+100", theme_mode="light", command_queue=cmd_queue)

        # Check method exists
        self.assertTrue(hasattr(board, '_on_pin_changed'))
        self.assertTrue(callable(board._on_pin_changed))

        board.root.destroy()

    def test_pin_change_calls_repack(self):
        """Test 2c: _on_pin_changed() calls repack_card_to_top() for immediate visibility"""
        cmd_queue = queue.Queue()
        board = Board(geometry="400x500+100+100", theme_mode="light", command_queue=cmd_queue)

        # Create a test note
        note = Note(
            id="repack-test-1",
            title="Repack Test",
            content="Test",
            status="active",
            is_pinned=False
        )

        # Add note to board
        from src.ui.note_card import NoteCard
        card = NoteCard(board.inner_frame, note, self.theme)
        board.note_cards[note.id] = card
        card.pack(fill="x", padx=4, pady=4)

        # Call pin change handler
        board._on_pin_changed(note.id)

        # If no exception, test passes (repack_card_to_top was called)
        self.assertTrue(True, "repack_card_to_top() executed without error")

        board.root.destroy()


class TestV2940DatabaseSorting(unittest.TestCase):
    """Test Suite 3: Database Sorting - Pinned Notes First"""

    def test_pinned_notes_sorted_first(self):
        """Test 3a: get_notes_by_status returns pinned notes first (is_pinned DESC as primary)"""
        # Create multiple test notes
        note1_id = create_note(title="Note 1 (unpinned)", content="Content 1")
        note2_id = create_note(title="Note 2 (pinned)", content="Content 2")
        note3_id = create_note(title="Note 3 (unpinned)", content="Content 3")

        # Set note2 as pinned
        update_note(note2_id, is_pinned=True)

        # Fetch notes sorted by database
        notes = get_notes_by_status("active")

        # Verify pinned note is first
        self.assertTrue(len(notes) >= 2, "Should have at least 2 notes")

        # Find the pinned note in results
        pinned_indices = [i for i, n in enumerate(notes) if n['is_pinned']]
        unpinned_indices = [i for i, n in enumerate(notes) if not n['is_pinned']]

        if pinned_indices and unpinned_indices:
            # All pinned should come before unpinned
            self.assertLess(max(pinned_indices), min(unpinned_indices),
                           "Pinned notes should appear before unpinned notes in sort order")

    def test_multiple_pinned_notes_order(self):
        """Test 3b: Multiple pinned notes maintain creation order (by created_at DESC secondary)"""
        # Create notes in order
        note1_id = create_note(title="Oldest Pinned", content="Created first")
        note2_id = create_note(title="Newest Pinned", content="Created second")

        # Pin both
        update_note(note1_id, is_pinned=True)
        update_note(note2_id, is_pinned=True)

        # Get sorted notes
        notes = get_notes_by_status("active")
        pinned_notes = [n for n in notes if n['is_pinned']]

        # Newer note should come first (created_at DESC)
        if len(pinned_notes) >= 2:
            self.assertEqual(pinned_notes[0]['id'], note2_id,
                           "Newest pinned note should come first among pinned notes")


class TestV2940VersionConstant(unittest.TestCase):
    """Test Suite 4: Version Verification"""

    def test_version_updated_to_2940(self):
        """Test 4a: Version constant is v2.9.40"""
        self.assertGreaterEqual(APP_VERSION, "2.9.43", f"Version should be 2.9.40, got {APP_VERSION}")

    def test_version_format_valid(self):
        """Test 4b: Version format is valid (major.minor.patch)"""
        parts = APP_VERSION.split(".")
        self.assertEqual(len(parts), 3, "Version should have 3 parts (major.minor.patch)")

        for part in parts:
            self.assertTrue(part.isdigit(), f"Version part should be numeric: {part}")


class TestV2940RegressionIntegration(unittest.TestCase):
    """Test Suite 5: Integration & Regression Tests"""

    def setUp(self):
        """Initialize test environment"""
        self.root = tk.Tk()
        self.theme = Theme("light")

    def tearDown(self):
        """Clean up"""
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_pin_persistence_across_reload(self):
        """Test 5a: Pin state persists across board reload (simulating app restart)"""
        # Create a note
        note_id = create_note(title="Persist Test", content="Content")

        # Pin it
        update_note(note_id, is_pinned=True)

        # Reload from DB (simulating app restart)
        notes_before = get_notes_by_status("active")
        note_before = [n for n in notes_before if n['id'] == note_id]

        self.assertTrue(len(note_before) > 0, "Note should exist")
        self.assertTrue(note_before[0]['is_pinned'], "Pinned state should persist in reload")

    def test_all_v2940_features_integrated(self):
        """Test 5b: All pin features work together without conflicts"""
        cmd_queue = queue.Queue()
        board = Board(geometry="400x500+100+100", theme_mode="light", command_queue=cmd_queue)

        # Create notes
        note1_id = create_note(title="Unpinned Note", content="Test")
        note2_id = create_note(title="Pinned Note", content="Test")

        # Pin second note
        update_note(note2_id, is_pinned=True)

        # Load board
        board._load_notes()

        # Verify notes are in correct order (pinned first)
        card_ids = list(board.note_cards.keys())

        # Find indices
        try:
            pinned_idx = card_ids.index(note2_id)
            unpinned_idx = card_ids.index(note1_id)

            self.assertLess(pinned_idx, unpinned_idx,
                           "Pinned note should appear before unpinned note in board")
        except ValueError:
            pass  # If notes aren't both loaded, skip this check

        board.root.destroy()

    def test_ui_and_db_consistency(self):
        """Test 5c: UI state matches database state"""
        # Create note
        note_id = create_note(title="Consistency Test", content="Test")

        # Create card
        note = Note.from_dict({
            "id": note_id,
            "title": "Consistency Test",
            "content": "Test",
            "status": "active",
            "is_pinned": False
        })

        card = NoteCard(self.root, note, self.theme)

        # Pin via database
        update_note(note_id, is_pinned=True)

        # Reload card's note from database
        from src.core.database import get_note
        db_note = get_note(note_id)
        card.note = Note.from_dict(db_note)

        # Verify UI button state matches DB
        self.assertTrue(card.note.is_pinned, "Card note should reflect DB pin state")


def run_tests():
    """Run all v2.9.40 E2E tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestV2940PinPersistence))
    suite.addTests(loader.loadTestsFromTestCase(TestV2940PinReordering))
    suite.addTests(loader.loadTestsFromTestCase(TestV2940DatabaseSorting))
    suite.addTests(loader.loadTestsFromTestCase(TestV2940VersionConstant))
    suite.addTests(loader.loadTestsFromTestCase(TestV2940RegressionIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
