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
                 on_open: Callable = None, stop_alarm: Callable = None):
        """Initialize unblockable dialog

        Args:
            parent: Parent window
            title: Dialog title
            message: Dialog message
            on_dismiss: Callback when Dismiss clicked
            on_snooze: Callback when Snooze clicked
            on_open: Callback when Open clicked
            stop_alarm: Callback to stop alarm sound
        """
        super().__init__(parent)

        self.title(title)
        self.message = message
        self.on_dismiss = on_dismiss
        self.on_snooze = on_snooze
        self.on_open = on_open
        self.stop_alarm = stop_alarm

        # Configure window appearance
        self.configure(bg="#F3F3F3", width=400, height=200)
        self.resizable(False, False)
        self.attributes("-topmost", True)

        # Create UI
        self._create_ui()

        # Apply Win32 forceful positioning AFTER window is created
        self.update_idletasks()
        self._force_to_foreground()

    def _create_ui(self):
        """Create dialog UI with title, message, and buttons"""
        # Title Label
        title_label = tk.Label(
            self,
            text=self.title(),
            font=("Segoe UI", 14, "bold"),
            bg="#F3F3F3",
            fg="#000000",
            wraplength=350
        )
        title_label.pack(pady=(15, 10), padx=15)

        # Message Label
        message_label = tk.Label(
            self,
            text=self.message if self.message else "Reminder triggered",
            font=("Segoe UI", 11),
            bg="#F3F3F3",
            fg="#333333",
            wraplength=350,
            justify="center"
        )
        message_label.pack(pady=(0, 20), padx=15)

        # Button Frame
        button_frame = tk.Frame(self, bg="#F3F3F3")
        button_frame.pack(pady=(0, 15))

        # [Dismiss] Button - Red
        dismiss_btn = tk.Button(
            button_frame,
            text="Dismiss",
            font=("Segoe UI", 10),
            bg="#FF3B30",
            fg="white",
            width=12,
            command=self._on_dismiss_click
        )
        dismiss_btn.pack(side="left", padx=5)

        # [Snooze 5m] Button - Orange
        snooze_btn = tk.Button(
            button_frame,
            text="Snooze 5m",
            font=("Segoe UI", 10),
            bg="#F9A825",
            fg="white",
            width=12,
            command=self._on_snooze_click
        )
        snooze_btn.pack(side="left", padx=5)

        # [Open] Button - Blue
        open_btn = tk.Button(
            button_frame,
            text="Open",
            font=("Segoe UI", 10),
            bg="#007AFF",
            fg="white",
            width=12,
            command=self._on_open_click
        )
        open_btn.pack(side="left", padx=5)

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
        """Dismiss button clicked"""
        try:
            self._stop_alarm_sound()
            if self.on_dismiss:
                self.on_dismiss()
        except Exception as e:
            log.error(f"[UnblockableDialog] Dismiss callback failed: {e}")
        finally:
            self.destroy()

    def _on_snooze_click(self):
        """Snooze 5m button clicked"""
        try:
            self._stop_alarm_sound()
            if self.on_snooze:
                self.on_snooze()
        except Exception as e:
            log.error(f"[UnblockableDialog] Snooze callback failed: {e}")
        finally:
            self.destroy()

    def _on_open_click(self):
        """Open button clicked"""
        try:
            self._stop_alarm_sound()
            if self.on_open:
                self.on_open()
        except Exception as e:
            log.error(f"[UnblockableDialog] Open callback failed: {e}")
        finally:
            self.destroy()

    def center_on_screen(self):
        """Center dialog on screen"""
        try:
            self.update_idletasks()
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            window_w = self.winfo_width()
            window_h = self.winfo_height()

            x = (screen_w - window_w) // 2
            y = (screen_h - window_h) // 2

            self.geometry(f"{window_w}x{window_h}+{x}+{y}")
        except Exception as e:
            log.warning(f"[UnblockableDialog] Failed to center: {e}")
