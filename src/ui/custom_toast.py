"""Custom Overlay Notification Toast (v2.8.5) — Unblockable Windows 11-Style Popup"""

import tkinter as tk
from tkinter import font
import winsound
import threading
import logging

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
                 on_open=None, on_dismiss=None):
        """Create and show custom notification overlay

        Args:
            parent_root: Parent window (main QuickNote window)
            title: Notification title
            message: Notification message/content preview
            on_open: Callback when user clicks [Open]
            on_dismiss: Callback when user clicks [Dismiss]
        """
        self.parent_root = parent_root
        self.title_text = title[:100] if title else "QuickNote"
        self.message_text = message[:200] if message else "Reminder triggered"
        self.on_open = on_open
        self.on_dismiss = on_dismiss
        self.toast_window = None

        # Create notification window
        self._create_notification()

        # Play audio in background thread (non-blocking)
        threading.Thread(target=self._play_audio, daemon=True).start()

    def _create_notification(self):
        """Create frameless overlay window at bottom-right corner"""
        try:
            # Create toplevel without decorations
            self.toast_window = tk.Toplevel(self.parent_root)
            self.toast_window.overrideredirect(True)  # Remove window decorations

            # v2.8.5: Windows 11-style notification styling
            self.toast_window.config(bg="#F3F3F3")  # Light gray background

            # v2.8.2: Force geometry calculation BEFORE positioning (DPI/scaling fix)
            self.toast_window.update_idletasks()

            # Notification dimensions
            toast_width = 360
            toast_height = 120

            # v2.8.2: Get screen dimensions AFTER update_idletasks (accurate after scaling)
            screen_width = self.parent_root.winfo_screenwidth()
            screen_height = self.parent_root.winfo_screenheight()

            # v2.8.2: Position at bottom-right corner with safe margins (prevent off-screen)
            # Ensure coordinates stay within screen bounds
            x = int(max(0, screen_width - toast_width - 50))  # 50px margin from right edge
            y = int(max(0, screen_height - toast_height - 100))  # 100px margin from bottom (taskbar)

            # Ensure not larger than screen
            x = int(min(x, screen_width - 100))
            y = int(min(y, screen_height - 100))

            self.toast_window.geometry(f"{toast_width}x{toast_height}+{x}+{y}")
            self.toast_window.attributes("-topmost", True)  # Always on top
            self.toast_window.attributes("-alpha", 0.98)    # Slightly transparent

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
                padx=12,
                pady=4,
                command=self._on_dismiss_click,
                activebackground="#D5D5DA",
                cursor="hand2"
            )
            dismiss_btn.pack(side="left", padx=(0, 4))

            # Open button (right, blue accent)
            open_btn = tk.Button(
                button_frame,
                text="Open",
                bg="#007AFF",
                fg="#FFFFFF",
                font=("Segoe UI", 8, "bold"),
                bd=0,
                relief="flat",
                padx=12,
                pady=4,
                command=self._on_open_click,
                activebackground="#0051C3",
                cursor="hand2"
            )
            open_btn.pack(side="right", padx=(4, 0))

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

            # Ensure window stays on top
            self.toast_window.lift()
            self.toast_window.focus_set()

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
                            on_open=None, on_dismiss=None) -> bool:
    """Convenience function to show custom notification

    Args:
        parent_root: Parent window (main app)
        title: Notification title
        message: Notification message
        on_open: Callback when user clicks Open
        on_dismiss: Callback when user clicks Dismiss

    Returns:
        True if notification shown successfully
    """
    try:
        notification = CustomToastNotification(
            parent_root, title, message,
            on_open=on_open, on_dismiss=on_dismiss
        )
        return True
    except Exception as e:
        log.error(f"[Toast] Failed to show notification: {e}")
        return False
