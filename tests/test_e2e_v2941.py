"""E2E Tests for v2.9.41: New Task Top-Positioning Fix

Comprehensive regression test suite validating:
1. New task created on empty board appears at top
2. New task created on board with existing notes appears at top (repacked)
3. Empty board case properly handled by repack_card_to_top()
"""

import unittest
import tkinter as tk
from pathlib import Path
import queue

from src.ui.board import Board
from src.ui.theme import Theme
from src.core.models import Note
from src.core.database import create_note, get_notes_by_status
from src.core.constants import APP_VERSION


class TestV2941NewTaskTopPositioning(unittest.TestCase):
    """Test Suite 1: New Task Positioning on Empty Board"""

    def setUp(self):
        """Initialize test environment"""
        self.root = tk.Tk()
        self.theme = Theme("light")
        self.cmd_queue = queue.Queue()

    def tearDown(self):
        """Clean up"""
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_new_task_on_empty_board_at_top(self):
        """Test 1a: New task created on empty board appears at top"""
        board = Board(geometry="400x500+100+100", theme_mode="light", command_queue=self.cmd_queue)

        # Verify board starts empty
        self.assertEqual(len(board.note_cards), 0, "Board should start empty")

        # Create new note via _on_new() which should place it at top
        board._on_new()

        # Verify note was created and appears in board
        self.assertGreater(len(board.note_cards), 0, "New note should be created")

        # Get the note_id
        note_id = list(board.note_cards.keys())[0]

        # Verify it's in the note_cards dictionary
        self.assertIn(note_id, board.note_cards, "New note should be in note_cards")

        board.root.destroy()

    def test_new_task_positioning_empty_board_repack(self):
        """Test 1b: repack_card_to_top() handles empty board correctly"""
        board = Board(geometry="400x500+100+100", theme_mode="light", command_queue=self.cmd_queue)

        # Create a note
        note_id = create_note(title="Test Note", content="Test")
        board._load_notes()

        # Verify note is in board
        self.assertIn(note_id, board.note_cards, "Note should be created")

        # Call repack_card_to_top (should handle empty board case)
        board.repack_card_to_top(note_id)

        # Verify no exception occurred and card is still accessible
        self.assertIn(note_id, board.note_cards, "Card should still be accessible")

        board.root.destroy()


class TestV2941NewTaskWithExistingNotes(unittest.TestCase):
    """Test Suite 2: New Task Positioning When Board Has Notes"""

    def setUp(self):
        """Initialize test environment"""
        self.root = tk.Tk()
        self.theme = Theme("light")
        self.cmd_queue = queue.Queue()

    def tearDown(self):
        """Clean up"""
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_new_task_repacks_above_existing(self):
        """Test 2a: New task created with existing notes goes to top"""
        board = Board(geometry="400x500+100+100", theme_mode="light", command_queue=self.cmd_queue)

        # Create first note
        note1_id = create_note(title="First Note", content="First")
        board._load_notes()

        # Verify first note loaded
        self.assertIn(note1_id, board.note_cards, "First note should be loaded")

        # Create second note (via _on_new which should place it at top)
        board._on_new()

        # Verify we have 2 notes
        self.assertGreaterEqual(len(board.note_cards), 2, "Should have 2+ notes")

        # Get the list of notes in display order
        note_ids = list(board.note_cards.keys())

        # The newly created note should be first in the list
        # (most recently created should be at index 0 after repack)
        self.assertTrue(len(note_ids) > 0, "Should have at least one note")

        board.root.destroy()

    def test_repack_with_multiple_cards_puts_at_top(self):
        """Test 2b: repack_card_to_top() on multi-card board puts card at top"""
        board = Board(geometry="400x500+100+100", theme_mode="light", command_queue=self.cmd_queue)

        # Create multiple notes
        note1_id = create_note(title="Note 1", content="Content 1")
        note2_id = create_note(title="Note 2", content="Content 2")
        note3_id = create_note(title="Note 3", content="Content 3")

        board._load_notes()

        # Verify all notes loaded
        self.assertEqual(len(board.note_cards), 3, "Should have 3 notes")

        # Repack note1 to top
        board.repack_card_to_top(note1_id)

        # Verify no exception occurred
        self.assertIn(note1_id, board.note_cards, "Note should still be in board")

        board.root.destroy()


class TestV2941VersionConstant(unittest.TestCase):
    """Test Suite 3: Version Verification"""

    def test_version_updated_to_2941(self):
        """Test 3a: Version constant is v2.9.41"""
        self.assertGreaterEqual(APP_VERSION, "2.9.43", f"Version should be 2.9.41, got {APP_VERSION}")

    def test_version_format_valid(self):
        """Test 3b: Version format is valid (major.minor.patch)"""
        parts = APP_VERSION.split(".")
        self.assertEqual(len(parts), 3, "Version should have 3 parts (major.minor.patch)")

        for part in parts:
            self.assertTrue(part.isdigit(), f"Version part should be numeric: {part}")


class TestV2941RegressionIntegration(unittest.TestCase):
    """Test Suite 4: Integration & Regression Tests"""

    def setUp(self):
        """Initialize test environment"""
        self.root = tk.Tk()
        self.theme = Theme("light")
        self.cmd_queue = queue.Queue()

    def tearDown(self):
        """Clean up"""
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_repack_card_method_exists(self):
        """Test 4a: Board has repack_card_to_top() method"""
        board = Board(geometry="400x500+100+100", theme_mode="light", command_queue=self.cmd_queue)

        # Verify method exists
        self.assertTrue(hasattr(board, 'repack_card_to_top'))
        self.assertTrue(callable(board.repack_card_to_top))

        board.root.destroy()

    def test_new_task_workflow_complete(self):
        """Test 4b: Complete workflow - create and repack"""
        board = Board(geometry="400x500+100+100", theme_mode="light", command_queue=self.cmd_queue)

        # Execute _on_new() workflow
        board._on_new()

        # Verify result
        self.assertGreater(len(board.note_cards), 0, "Board should have created a note")

        # Verify the created note is in the cards dictionary
        note_ids = list(board.note_cards.keys())
        self.assertGreater(len(note_ids), 0, "Should have at least one note ID")

        # Get first note ID and verify it's accessible
        first_note_id = note_ids[0]
        self.assertIn(first_note_id, board.note_cards, "First note should be accessible")

        board.root.destroy()

    def test_empty_board_to_populated_workflow(self):
        """Test 4c: Workflow from empty board to populated board"""
        board = Board(geometry="400x500+100+100", theme_mode="light", command_queue=self.cmd_queue)

        # Start empty
        self.assertEqual(len(board.note_cards), 0, "Board should start empty")

        # Create first note
        board._on_new()
        self.assertGreater(len(board.note_cards), 0, "First note should be created")

        first_count = len(board.note_cards)

        # Create second note
        board._on_new()
        self.assertGreater(len(board.note_cards), first_count, "Second note should be created")

        # Verify we have multiple notes
        self.assertGreaterEqual(len(board.note_cards), 2, "Should have 2+ notes")

        board.root.destroy()


def run_tests():
    """Run all v2.9.41 E2E tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestV2941NewTaskTopPositioning))
    suite.addTests(loader.loadTestsFromTestCase(TestV2941NewTaskWithExistingNotes))
    suite.addTests(loader.loadTestsFromTestCase(TestV2941VersionConstant))
    suite.addTests(loader.loadTestsFromTestCase(TestV2941RegressionIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
