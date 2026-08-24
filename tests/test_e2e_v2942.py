"""E2E Tests for v2.9.42: New Task Top-Positioning Fix (Refined)

Comprehensive regression test suite validating:
1. New task created on empty board appears at top
2. New task created on board with existing notes appears at top (repacked)
3. Empty board case properly handled by repack_card_to_top()
4. Verify card_widgets filtering excludes empty state label
"""

import unittest
import tkinter as tk
from pathlib import Path
import queue
import tempfile
import shutil
import sqlite3
import os

from src.ui.board import Board
from src.ui.theme import Theme
from src.core.models import Note
from src.core.database import create_note, get_notes_by_status, init_db, DB_FILE
from src.core.constants import APP_VERSION


class TestV2942NewTaskTopPositioningFixed(unittest.TestCase):
    """Test Suite 1: New Task Positioning on Empty Board (v2.9.42 Fix)"""

    @classmethod
    def setUpClass(cls):
        """Set up test database once for all tests in this class"""
        # Backup original database
        cls.original_db = None
        if DB_FILE.exists():
            cls.original_db = DB_FILE.with_suffix('.bak.db')
            if cls.original_db.exists():
                cls.original_db.unlink()
            shutil.copy(DB_FILE, cls.original_db)

    @classmethod
    def tearDownClass(cls):
        """Restore original database after all tests"""
        if cls.original_db and cls.original_db.exists():
            if DB_FILE.exists():
                DB_FILE.unlink()
            shutil.copy(cls.original_db, DB_FILE)
            cls.original_db.unlink()

    def setUp(self):
        """Initialize test environment with fresh database"""
        # Delete and recreate database for each test
        if DB_FILE.exists():
            DB_FILE.unlink()

        self.root = tk.Tk()
        self.theme = Theme("light")
        self.cmd_queue = queue.Queue()

        # Initialize fresh database for testing
        init_db()

    def tearDown(self):
        """Clean up"""
        try:
            self.root.destroy()
        except Exception:
            pass
        # Clean up test database
        if DB_FILE.exists():
            DB_FILE.unlink()

    def test_new_task_on_empty_board_appears_at_index_0(self):
        """Test 1a: New task created on empty board appears at Index 0 (top)"""
        board = Board(geometry="400x500+100+100", theme_mode="light", command_queue=self.cmd_queue)

        # Verify board starts empty
        self.assertEqual(len(board.note_cards), 0, "Board should start empty")

        # Create new note via _on_new() which should place it at top
        board._on_new()

        # Allow UI to update
        board.root.update_idletasks()

        # Verify note was created
        self.assertGreater(len(board.note_cards), 0, "New note should be created")

        # Get the note_id (should be only one)
        note_id = list(board.note_cards.keys())[0]
        card = board.note_cards[note_id]

        # Verify it's the first (and only) child in inner_frame
        children = [c for c in board.inner_frame.winfo_children() if c in board.note_cards.values()]
        self.assertEqual(len(children), 1, "Should have exactly 1 card")
        self.assertEqual(children[0], card, "Card should be at Index 0")

        board.root.destroy()

    def test_new_task_positioning_empty_board_repack_safe(self):
        """Test 1b: repack_card_to_top() handles empty board correctly (no crash)"""
        board = Board(geometry="400x500+100+100", theme_mode="light", command_queue=self.cmd_queue)

        # Create a note
        note_id = create_note(title="Test Note", content="Test")
        board._load_notes()

        # Verify note is in board
        self.assertIn(note_id, board.note_cards, "Note should be created")

        # Call repack_card_to_top (should handle empty board case gracefully)
        try:
            board.repack_card_to_top(note_id)
        except Exception as e:
            self.fail(f"repack_card_to_top should not raise exception: {e}")

        # Allow UI to update
        board.root.update_idletasks()

        # Verify card is still accessible
        self.assertIn(note_id, board.note_cards, "Card should still be accessible")

        board.root.destroy()


class TestV2942NewTaskWithExistingNotes(unittest.TestCase):
    """Test Suite 2: New Task Positioning When Board Has Notes (v2.9.42 Fix)"""

    @classmethod
    def setUpClass(cls):
        """Set up test database once for all tests in this class"""
        # Backup original database
        cls.original_db = None
        if DB_FILE.exists():
            cls.original_db = DB_FILE.with_suffix('.bak.db')
            if cls.original_db.exists():
                cls.original_db.unlink()
            shutil.copy(DB_FILE, cls.original_db)

    @classmethod
    def tearDownClass(cls):
        """Restore original database after all tests"""
        if cls.original_db and cls.original_db.exists():
            if DB_FILE.exists():
                DB_FILE.unlink()
            shutil.copy(cls.original_db, DB_FILE)
            cls.original_db.unlink()

    def setUp(self):
        """Initialize test environment with fresh database"""
        # Delete and recreate database for each test
        if DB_FILE.exists():
            DB_FILE.unlink()

        self.root = tk.Tk()
        self.theme = Theme("light")
        self.cmd_queue = queue.Queue()

        # Initialize fresh database for testing
        init_db()

    def tearDown(self):
        """Clean up"""
        try:
            self.root.destroy()
        except Exception:
            pass
        # Clean up test database
        if DB_FILE.exists():
            DB_FILE.unlink()

    def test_new_task_repacks_above_existing_verified_at_index_0(self):
        """Test 2a: New task created with existing notes goes to top (Index 0)"""
        board = Board(geometry="400x500+100+100", theme_mode="light", command_queue=self.cmd_queue)

        # Create first note
        note1_id = create_note(title="First Note", content="First")
        board._load_notes()
        board.root.update_idletasks()

        # Verify first note is in board
        self.assertIn(note1_id, board.note_cards, "First note should be created")

        # Create second note via _on_new() — should go to top via repack_card_to_top()
        board._on_new()
        board.root.update_idletasks()

        # Verify we now have 2 notes
        self.assertEqual(len(board.note_cards), 2, "Should have 2 notes now")

        # Get the pack_slaves order (actual visual pack order, not winfo_children)
        pack_order = board.inner_frame.pack_slaves()
        card_pack_order = [c for c in pack_order if c in board.note_cards.values()]

        self.assertEqual(len(card_pack_order), 2, "Should have 2 cards in pack order")

        # Find the newly created note (it's the one that's NOT note1_id)
        new_note_id = None
        for nid in board.note_cards:
            if nid != note1_id:
                new_note_id = nid
                break

        self.assertIsNotNone(new_note_id, "Should have created a new note")
        new_card = board.note_cards[new_note_id]
        old_card = board.note_cards[note1_id]

        # Verify pack order: new card should be at Index 0, old card at Index 1
        first_in_pack_order = card_pack_order[0]
        second_in_pack_order = card_pack_order[1]

        self.assertEqual(first_in_pack_order, new_card, "Newly created note should be at Index 0 in pack order (top)")
        self.assertEqual(second_in_pack_order, old_card, "Original note should be at Index 1 in pack order")

        board.root.destroy()

    def test_repack_excludes_empty_state_label(self):
        """Test 2b: repack_card_to_top filters out empty state label correctly"""
        board = Board(geometry="400x500+100+100", theme_mode="light", command_queue=self.cmd_queue)

        # Create a note (empty state label should disappear)
        note_id = create_note(title="Test", content="Content")
        board._load_notes()
        board.root.update_idletasks()

        # Get card_widgets as the repack_card_to_top method does
        card_widgets = [c for c in board.inner_frame.winfo_children() if c in board.note_cards.values()]

        # Verify empty_state_label is NOT in card_widgets
        if hasattr(board, 'empty_state_label'):
            self.assertNotIn(board.empty_state_label, card_widgets, "empty_state_label should not be in card_widgets")

        # Verify only the actual card is in card_widgets
        self.assertEqual(len(card_widgets), 1, "Should have exactly 1 card")
        self.assertEqual(card_widgets[0], board.note_cards[note_id], "Should be the created card")

        board.root.destroy()


class TestV2942VersionAndIntegration(unittest.TestCase):
    """Test Suite 3: Version String and Integration"""

    def test_version_string_is_v2942(self):
        """Test 3a: Version constant is updated to 2.9.42"""
        self.assertEqual(APP_VERSION, "2.9.42", "APP_VERSION should be 2.9.42")

    def test_version_format_is_valid(self):
        """Test 3b: Version format matches semantic versioning"""
        parts = APP_VERSION.split(".")
        self.assertEqual(len(parts), 3, "Version should have 3 parts: major.minor.patch")
        self.assertTrue(parts[0].isdigit(), "Major version should be numeric")
        self.assertTrue(parts[1].isdigit(), "Minor version should be numeric")
        self.assertTrue(parts[2].isdigit(), "Patch version should be numeric")


if __name__ == "__main__":
    unittest.main()
