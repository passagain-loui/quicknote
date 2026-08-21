"""Custom Overlay Notification Toast (v2.9.2) — Center-Screen Guaranteed Visibility"""

import tkinter as tk
from tkinter import font
import winsound
import threading
import logging
from datetime import datetime, timedelta

log = logging.getLogger(__name__)


class CustomToastNotification:
    """Custom frameless overlay notification in bottom-right corner

    v2.8.5: Replaces Windows native notifications which are blocked by portable .exe
    Features:
    - Frameless Toplevel window (no title bar)
    - Positioned at screen bottom-right corner
    - Windows 11 styling (light background, rounded edges if possible)
    - Requires explicit dismiss or open action (won't auto-hide)
    - Plays audio when shown
    - Thread-safe: called only from main Tkinter thread
    """

    def __init__(self, parent_root, title: str, message: str = None,
                 on_open=None, on_dismiss=None, note_id: str = None, board=None):
        """Create and show custom notification overlay

        Args:
            parent_root: Parent window (main QuickNote window)
            title: Notification title
            message: Notification message/content preview
            on_open: Callback when user clicks [Open]
            on_dismiss: Callback when user clicks [Dismiss]
            note_id: Note ID for snooze feature
            board: Board instance for re-render after snooze
        """
        self.parent_root = parent_root
        self.title_text = title[:100] if title else "QuickNote"
        self.message_text = message[:200] if message else "Reminder triggered"
        self.on_open = on_open
        self.on_dismiss = on_dismiss
        self.note_id = note_id
        self.board = board
        self.toast_window = None

        # Create notification window
        self._create_notification()

        # Play audio in background thread (non-blocking)
        threading.Thread(target=self._play_audio, daemon=True).start()

    def _create_notification(self):
        """Create frameless overlay notification at center screen (v2.9.2: Pure logical coords)"""
        try:
            # v2.9.2: Create and position BEFORE any visibility changes (proper window sequence)
            self.toast_window = tk.Toplevel(self.parent_root)
            self.toast_window.withdraw()  # Hide while configuring
            self.toast_window.overrideredirect(True)  # Remove decorations (frameless)

            # v2.8.5: Windows 11-style notification styling
            self.toast_window.config(bg="#F3F3F3")  # Light gray background

            # v2.9.2: Force geometry calculation BEFORE positioning (ensures accurate dimensions)
            self.toast_window.update_idletasks()

            # Notification dimensions
            toast_width = 360
            toast_height = 150

            # v2.9.2: Use pure Tkinter logical coordinates (already handles Windows DPI scaling)
            # NEVER use win32api physical pixels — causes mismatch when Windows scaling is enabled
            screen_width = self.parent_root.winfo_screenwidth()
            screen_height = self.parent_root.winfo_screenheight()

            log.info(f"[Toast] Screen bounds (Tkinter logical): {screen_width}x{screen_height}")

            # v2.9.2: CENTER SCREEN positioning for guaranteed 100% visibility
            # Logical center calculation works correctly on all DPI/scaling configurations
            x = int((screen_width - toast_width) / 2)
            y = int((screen_height - toast_height) / 2)

            log.info(f"[Toast] Center position calculated: {x}+{y}")

            # v2.9.2: Bulletproof Windows DWM sequence for frameless windows
            self.toast_window.geometry(f"{toast_width}x{toast_height}+{x}+{y}")
            self.toast_window.attributes("-topmost", True)  # Lock to top
            self.toast_window.attributes("-alpha", 0.98)    # Slightly transparent
            self.toast_window.deiconify()  # Show window
            self.toast_window.lift()  # Bring to front
            self.toast_window.focus_force()  # Force focus

            # Main frame
            main_frame = tk.Frame(self.toast_window, bg="#F3F3F3", relief="flat", bd=1)
            main_frame.pack(fill="both", expand=True, padx=12, pady=12)

            # Title label
            title_font = ("Segoe UI", 10, "bold")
            title_label = tk.Label(
                main_frame,
                text=self.title_text,
                bg="#F3F3F3",
                fg="#1C1C1E",
                font=title_font,
                wraplength=330,
                justify="left",
                anchor="w"
            )
            title_label.pack(fill="x", pady=(0, 6))

            # Message label
            msg_font = ("Segoe UI", 9)
            msg_label = tk.Label(
                main_frame,
                text=self.message_text,
                bg="#F3F3F3",
                fg="#515155",
                font=msg_font,
                wraplength=330,
                justify="left",
                anchor="w"
            )
            msg_label.pack(fill="x", pady=(0, 10))

            # Button frame
            button_frame = tk.Frame(main_frame, bg="#F3F3F3")
            button_frame.pack(fill="x", pady=(0, 0))

            # Dismiss button (left)
            dismiss_btn = tk.Button(
                button_frame,
                text="Dismiss",
                bg="#E5E5EA",
                fg="#1C1C1E",
                font=("Segoe UI", 8),
                bd=0,
                relief="flat",
                padx=10,
                pady=4,
                command=self._on_dismiss_click,
                activebackground="#D5D5DA",
                cursor="hand2"
            )
            dismiss_btn.pack(side="left", padx=(0, 3))

            # Snooze button (v2.9.0) - new feature
            snooze_btn = tk.Button(
                button_frame,
                text="Snooze 5m",
                bg="#F9A825",
                fg="#FFFFFF",
                font=("Segoe UI", 8),
                bd=0,
                relief="flat",
                padx=10,
                pady=4,
                command=self._on_snooze_click,
                activebackground="#E69700",
                cursor="hand2"
            )
            snooze_btn.pack(side="left", padx=(0, 3))

            # Open button (right, blue accent)
            open_btn = tk.Button(
                button_frame,
                text="Open",
                bg="#007AFF",
                fg="#FFFFFF",
                font=("Segoe UI", 8, "bold"),
                bd=0,
                relief="flat",
                padx=10,
                pady=4,
                command=self._on_open_click,
                activebackground="#0051C3",
                cursor="hand2"
            )
            open_btn.pack(side="right", padx=(3, 0))

            # Close button (X) in top-right corner
            close_x_frame = tk.Frame(self.toast_window, bg="#F3F3F3")
            close_x_frame.pack(anchor="ne", padx=8, pady=4)

            close_x_btn = tk.Button(
                close_x_frame,
                text="✕",
                bg="#F3F3F3",
                fg="#999999",
                font=("Segoe UI", 10),
                bd=0,
                relief="flat",
                padx=4,
                pady=0,
                command=self._on_dismiss_click,
                activebackground="#E5E5EA",
                cursor="hand2"
            )
            close_x_btn.pack()

            log.info(f"[Toast] Custom notification shown: {self.title_text}")

        except Exception as e:
            log.error(f"[Toast] Failed to create notification window: {e}")

    def _play_audio(self):
        """Play notification sound (non-blocking)"""
        try:
            # Use MailBeep for soft ding-dong sound
            winsound.PlaySound("MailBeep", winsound.SND_ALIAS | winsound.SND_ASYNC)
        except Exception as e:
            log.warning(f"[Toast] Failed to play audio: {e}")

    def _on_open_click(self):
        """User clicked [Open] - bring main window to front and callback"""
        try:
            # Execute callback if provided
            if self.on_open:
                self.on_open()

            # Bring main window to front
            self._bring_main_window_to_front()

            # Close notification
            self._close_notification()

        except Exception as e:
            log.error(f"[Toast] Error on open click: {e}")
            self._close_notification()

    def _on_dismiss_click(self):
        """User clicked [Dismiss] or [X] - close notification"""
        try:
            # Execute callback if provided
            if self.on_dismiss:
                self.on_dismiss()

            self._close_notification()

        except Exception as e:
            log.error(f"[Toast] Error on dismiss click: {e}")
            self._close_notification()

    def _on_snooze_click(self):
        """User clicked [Snooze 5m] - reschedule reminder for 5 minutes later"""
        try:
            if not self.note_id or not self.board:
                log.warning("[Toast] Snooze: note_id or board not available")
                self._close_notification()
                return

            # v2.9.0: Calculate new reminder time (5 minutes from now)
            new_time = datetime.now() + timedelta(minutes=5)
            new_time_str = new_time.strftime("%Y-%m-%d %H:%M")

            # Import database function
            from src.core.database import update_note

            # Update database synchronously - reschedule reminder
            log.info(f"[Toast] Snoozing reminder for {self.note_id} to {new_time_str}")
            update_note(
                self.note_id,
                reminder_datetime=new_time_str,
                reminder_triggered=False  # Reset triggered flag to allow re-trigger
            )

            # Re-render board to update UI immediately
            if self.board:
                self.board._load_notes()

            # Close notification
            self._close_notification()

        except Exception as e:
            log.error(f"[Toast] Error on snooze click: {e}")
            self._close_notification()

    def _bring_main_window_to_front(self):
        """Force main window to foreground (unblockable)"""
        try:
            # v2.8.5: Absolute foreground override technique
            self.parent_root.deiconify()  # Ensure window is visible
            self.parent_root.attributes("-topmost", True)  # Force to top
            self.parent_root.lift()  # Lift above all windows
            self.parent_root.focus_force()  # Force focus to main window

            # Small delay to ensure window is visible
            self.parent_root.after(100, lambda: self.parent_root.attributes("-topmost", False))

            log.info("[Toast] Main window brought to foreground")

        except Exception as e:
            log.warning(f"[Toast] Failed to bring main window to front: {e}")

    def _close_notification(self):
        """Close and cleanup notification window"""
        try:
            if self.toast_window:
                self.toast_window.destroy()
                log.info("[Toast] Notification window closed")
        except Exception as e:
            log.warning(f"[Toast] Error closing notification: {e}")


def show_custom_notification(parent_root, title: str, message: str = None,
                            on_open=None, on_dismiss=None,
                            note_id: str = None, board=None) -> bool:
    """Convenience function to show custom notification

    Args:
        parent_root: Parent window (main app)
        title: Notification title
        message: Notification message
        on_open: Callback when user clicks Open
        on_dismiss: Callback when user clicks Dismiss
        note_id: Note ID for snooze feature
        board: Board instance for re-render

    Returns:
        True if notification shown successfully
    """
    try:
        notification = CustomToastNotification(
            parent_root, title, message,
            on_open=on_open, on_dismiss=on_dismiss,
            note_id=note_id, board=board
        )
        return True
    except Exception as e:
        log.error(f"[Toast] Failed to show notification: {e}")
        return False
