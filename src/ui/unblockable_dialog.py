"""Unblockable Custom Reminder Dialog (v2.9.7) — Custom Buttons + Alarm Control"""

import tkinter as tk
import ctypes
import logging
from typing import Optional, Callable

log = logging.getLogger(__name__)


class UnblockableCustomDialog(tk.Toplevel):
    """Unblockable custom reminder dialog with Dismiss/Snooze/Open buttons (v2.9.7)

    Features:
    - Custom Toplevel window that mimics Win32 MessageBox behavior
    - Three action buttons: [Dismiss] [Snooze 5m] [Open]
    - Forced to foreground using Win32 SetWindowPos + SetForegroundWindow
    - Alarm sound control (stop on any button click)
    - Professional appearance with center positioning
    """

    # Win32 constants
    HWND_TOPMOST = -1
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002

    def __init__(self, parent, title: str = "QuickNote Reminder", message: str = "",
                 on_dismiss: Callable = None, on_snooze: Callable = None,
                 on_open: Callable = None, stop_alarm: Callable = None, parent_board=None,
                 snooze_duration_minutes: int = 5):  # v2.9.26: Custom snooze duration
        """Initialize unblockable dialog

        Args:
            parent: Parent window
            title: Dialog title
            message: Dialog message
            on_dismiss: Callback when Dismiss clicked
            on_snooze: Callback when Snooze clicked
            on_open: Callback when Open clicked
            stop_alarm: Callback to stop alarm sound
            parent_board: Parent Board instance for UI re-render (v2.9.9)
            snooze_duration_minutes: Duration in minutes for snooze (v2.9.26)
        """
        super().__init__(parent)

        self.title(title)
        self.message = message
        self.on_dismiss = on_dismiss
        self.on_snooze = on_snooze
        self.on_open = on_open
        self.stop_alarm = stop_alarm
        self.parent_board = parent_board  # v2.9.9: For forced UI re-render
        self.snooze_duration_minutes = snooze_duration_minutes  # v2.9.26

        # v2.9.9: Get theme from parent board for consistent styling
        self.theme = None
        if parent_board and hasattr(parent_board, 'theme'):
            self.theme = parent_board.theme

        # Configure window appearance with theme colors
        bg_color = self.theme.c("bg") if self.theme else "#F3F3F3"
        self.configure(bg=bg_color, width=400, height=200)
        self.resizable(False, False)

        # v2.9.30: Non-blocking Z-order lock using transient() instead of grab_set()
        # transient() makes this dialog a child of parent window at OS level
        # Ensures dialog stays above parent without blocking event loop (non-modal)
        try:
            self.transient(parent)  # Link dialog to parent at OS window manager level
            log.debug("[UnblockableDialog] transient(parent) applied for Z-order lock")
        except Exception as e:
            log.warning(f"[UnblockableDialog] Failed to set transient: {e}")

        # v2.9.35: Force dialog to stay on top (ONCE at init, ONLY ONCE to avoid focus flapping)
        self.attributes("-topmost", True)
        self.lift()  # Immediately bring to front
        self.focus_force()  # Force focus to this window

        # Create UI
        self._create_ui()

        # v2.9.35: REMOVED FocusOut event binding (causes focus flapping loop)
        # Single -topmost attribute at init is sufficient for Z-order lock

        # Apply Win32 forceful positioning AFTER window is created
        self.update_idletasks()
        self._position_bottom_right()  # v2.9.33: Position as bottom-right toast notification (DPI-aware in v2.9.35)
        self._force_to_foreground()

    def _create_ui(self):
        """Create dialog UI with title, message, and buttons (v2.9.12: Minimal left-aligned design)"""
        # v2.9.9: Use theme colors for consistent UI
        bg_color = self.theme.c("bg") if self.theme else "#F3F3F3"
        fg_color = self.theme.c("fg") if self.theme else "#000000"
        fg_muted_color = self.theme.c("fg_muted") if self.theme else "#333333"

        # v2.9.12: Create a content frame for left-aligned layout
        content_frame = tk.Frame(self, bg=bg_color)
        content_frame.pack(fill="both", expand=True, padx=12, pady=12)

        # Title Label (v2.9.12: Left-aligned, smaller font)
        title_label = tk.Label(
            content_frame,
            text=self.title(),
            font=("Segoe UI", 12, "bold"),
            bg=bg_color,
            fg=fg_color,
            wraplength=350,
            justify="left",
            anchor="w"
        )
        title_label.pack(fill="x", pady=(0, 6))

        # Message Label (v2.9.12: Left-aligned, compact)
        message_label = tk.Label(
            content_frame,
            text=self.message if self.message else "Reminder triggered",
            font=("Segoe UI", 10),
            bg=bg_color,
            fg=fg_muted_color,
            wraplength=350,
            justify="left",
            anchor="w"
        )
        message_label.pack(fill="x", pady=(0, 12))

        # v2.9.12: Button Frame with minimal compact buttons
        button_frame = tk.Frame(content_frame, bg=bg_color)
        button_frame.pack(fill="x", pady=(6, 0))

        # v2.9.11: Modern flat design with muted pastel colors
        # v2.9.12: Compact minimal buttons (reduced padding)
        # [Dismiss] Button - Pastel Red
        dismiss_btn = tk.Button(
            button_frame,
            text="Dismiss",
            font=("Segoe UI", 9),
            bg="#FFEBEE",  # Pastel red background
            fg="#C62828",  # Dark red text
            width=11,
            height=1,
            bd=0,
            relief="flat",
            padx=4,
            pady=3,
            command=self._on_dismiss_click
        )
        dismiss_btn.pack(side="left", padx=2)

        # v2.9.26: Snooze button with custom duration
        # Button text shows the configured snooze duration (e.g., "Snooze 10m")
        snooze_text = f"Snooze {self.snooze_duration_minutes}m"
        snooze_btn = tk.Button(
            button_frame,
            text=snooze_text,
            font=("Segoe UI", 9),
            bg="#FFF3E0",  # Pastel orange background
            fg="#E65100",  # Dark orange text
            width=14,
            height=1,
            bd=0,
            relief="flat",
            padx=4,
            pady=3,
            command=self._on_snooze_click
        )
        snooze_btn.pack(side="left", padx=2, fill="x", expand=True)

    def _position_bottom_right(self):
        """v2.9.35: Position dialog at bottom-right corner with DPI-aware scaling

        Toast positioning (v2.9.35 DPI-aware):
        - Places dialog in bottom-right corner of screen
        - DPI-scaling aware: margins scale with system DPI (96 DPI = 1 inch)
        - Leaves 25px margin from right edge + 160px from bottom (well above taskbar)
        - Elevated positioning prevents taskbar overlap on various screen sizes (96-192 DPI)
        - Classic Windows notification toast appearance with extra clearance

        DPI Scaling:
        - winfo_fpixels('1i') returns pixels per inch on current display
        - Scale factor = 1i_pixels / 72.0 (points per inch in tkinter)
        - Margins scale proportionally with DPI
        """
        try:
            self.update_idletasks()
            width = self.winfo_width() or 340
            height = self.winfo_height() or 180
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()

            # Calculate DPI scale factor (96 DPI = 1.0, 192 DPI = 2.0, etc.)
            try:
                scale = self.winfo_fpixels('1i') / 72.0  # Convert points to pixels
            except Exception:
                scale = 1.0  # Fallback to 1:1 if DPI detection fails

            # Scale margins based on DPI
            margin_x = int(25 * scale)
            margin_y = int(160 * scale)

            # Calculate position: bottom-right with DPI-scaled margins
            # Ensure position stays within screen bounds (no negative coordinates)
            x = max(0, screen_width - width - margin_x)
            y = max(0, screen_height - height - margin_y)

            self.geometry(f"{width}x{height}+{x}+{y}")
            log.debug(f"[UnblockableDialog] Positioned at elevated bottom-right (DPI scale {scale:.2f}): ({x}, {y})")
        except Exception as e:
            log.warning(f"[UnblockableDialog] Failed to position at elevated bottom-right: {e}")

    def _force_to_foreground(self):
        """Force dialog to foreground using Win32 API (v2.9.7)"""
        try:
            # Get window handle
            hwnd = int(self.winfo_id())

            # Use SetWindowPos to make window topmost
            # Flags: SWP_NOSIZE | SWP_NOMOVE (don't resize or move)
            ctypes.windll.user32.SetWindowPos(
                hwnd,
                self.HWND_TOPMOST,
                0, 0, 0, 0,
                self.SWP_NOSIZE | self.SWP_NOMOVE
            )

            # Force as foreground window (takes input focus)
            ctypes.windll.user32.SetForegroundWindow(hwnd)

            # Lift above other windows
            self.lift()

            log.info("[UnblockableDialog] Forced to foreground")
        except Exception as e:
            log.warning(f"[UnblockableDialog] Failed to force foreground: {e}")

    def _stop_alarm_sound(self):
        """Stop alarm sound immediately"""
        try:
            if self.stop_alarm:
                self.stop_alarm()
                log.info("[UnblockableDialog] Alarm stopped")
        except Exception as e:
            log.warning(f"[UnblockableDialog] Failed to stop alarm: {e}")

    def _on_dismiss_click(self):
        """Dismiss button clicked — v2.9.18: Delegate to queue callback (no direct DB operations)"""
        try:
            # v2.9.18: ONLY delegate to callback (which puts message in command queue)
            # All DB operations and audio stop happen in queue handler, not here
            if self.on_dismiss:
                self.on_dismiss()
        except Exception as e:
            log.error(f"[UnblockableDialog] Dismiss callback failed: {e}")
        finally:
            self._safe_destroy()

    def _on_snooze_click(self):
        """Snooze 5m button clicked — v2.9.18: Delegate to queue callback (no direct DB operations)"""
        try:
            # v2.9.18: ONLY delegate to callback (which puts message in command queue)
            # All DB operations and audio stop happen in queue handler, not here
            if self.on_snooze:
                self.on_snooze()
        except Exception as e:
            log.error(f"[UnblockableDialog] Snooze callback failed: {e}")
        finally:
            self._safe_destroy()

    def _safe_destroy(self):
        """v2.9.36: Safely destroy dialog with minimal scope impact

        v2.9.36 FIX: Removed unbind_all() to prevent scope leak
        - unbind_all() was removing bindings from parent/root, causing issues
        - Only clear WM_DELETE_WINDOW protocol (our specific binding)
        - Let destroy() handle all cleanup naturally
        """
        try:
            # Clear WM_DELETE_WINDOW protocol to prevent double-destroy
            try:
                self.protocol("WM_DELETE_WINDOW", lambda: None)
                log.debug("[UnblockableDialog] WM_DELETE_WINDOW protocol cleared")
            except Exception as e:
                log.warning(f"[UnblockableDialog] Failed to clear protocol: {e}")
        finally:
            # Guaranteed destroy attempt (happens even if protocol clear fails)
            try:
                self.destroy()
                log.debug("[UnblockableDialog] Dialog destroyed successfully")
            except Exception as e:
                log.warning(f"[UnblockableDialog] Failed to destroy: {e}")


    def _mark_reminder_triggered(self):
        """v2.9.8: Mark reminder as triggered in database to prevent re-trigger on app restart"""
        try:
            # The actual DB update is handled by the on_dismiss/on_open callback from board._trigger_reminder
            # That callback calls update_note with reminder_triggered = True
            log.info("[UnblockableDialog] Reminder marked as triggered (via callback chain)")
        except Exception as e:
            log.warning(f"[UnblockableDialog] Failed to mark reminder triggered: {e}")

    def _snooze_reminder_5m(self):
        """v2.9.8: Reschedule reminder +5 minutes"""
        try:
            # The snooze logic is handled by the on_snooze callback from board._trigger_reminder
            # That callback calls update_note with new reminder_datetime = now + 5m
            log.info("[UnblockableDialog] Reminder rescheduled +5 minutes (via callback chain)")
        except Exception as e:
            log.warning(f"[UnblockableDialog] Failed to snooze reminder: {e}")

    def _force_ui_rerender(self):
        """v2.9.9: Force parent board to re-render UI (update note card icons)"""
        try:
            if self.parent_board and hasattr(self.parent_board, '_load_notes'):
                # Call _load_notes() to refresh all note cards and icon states
                self.parent_board._load_notes()
                log.info("[UnblockableDialog] UI re-render forced via _load_notes()")
        except Exception as e:
            log.warning(f"[UnblockableDialog] Failed to force UI re-render: {e}")

    def _commit_reminder_triggered_sync(self):
        """v2.9.13: Synchronous DB commit to prevent race condition with Scheduler thread

        CRITICAL: This is a BLOCKING call that waits for DB to write to disk.
        Ensures Scheduler thread sees reminder_triggered=1 on next check cycle.
        """
        try:
            # Import here to avoid circular dependency
            from src.core.database import update_note

            # Get note_id from parent_board if available (board stores reference in root._board)
            if self.parent_board and hasattr(self.parent_board, 'root'):
                root = self.parent_board.root
                if hasattr(root, '_current_reminder_note_id'):
                    note_id = root._current_reminder_note_id
                    # Synchronous DB update with explicit commit
                    update_note(note_id, reminder_triggered=True)
                    log.info(f"[UnblockableDialog] Synchronous DB commit: reminder_triggered=1 for {note_id}")
        except Exception as e:
            log.warning(f"[UnblockableDialog] Failed to commit reminder_triggered: {e}")

    def _force_main_window_to_foreground_win32(self):
        """v2.9.13: Force main window to foreground using Win32 API (hard override)

        Tkinter deiconify() alone doesn't work on Windows 10/11 due to Foreground Lock.
        Use ShowWindow(RESTORE=9) + SwitchToThisWindow() to force focus.
        """
        try:
            if not self.parent_board or not hasattr(self.parent_board, 'root'):
                return

            root = self.parent_board.root
            hwnd = int(root.winfo_id())

            # Step 1: Restore window from minimized state
            # ShowWindow(hwnd, SW_RESTORE=9)
            ctypes.windll.user32.ShowWindow(hwnd, 9)
            log.info(f"[UnblockableDialog] ShowWindow(RESTORE=9) called")

            # Step 2: Switch to this window (bypasses Foreground Lock)
            # SwitchToThisWindow(hwnd, True) - allocate input queue to this window
            ctypes.windll.user32.SwitchToThisWindow(hwnd, True)
            log.info(f"[UnblockableDialog] SwitchToThisWindow() called")

            # Step 3: Traditional foreground + lift + focus as fallback
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            root.lift()
            root.focus_force()

            log.info(f"[UnblockableDialog] Main window forced to foreground via Win32 API")
        except Exception as e:
            log.warning(f"[UnblockableDialog] Failed to force foreground with Win32: {e}")

