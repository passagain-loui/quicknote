"""NotificationPopup — v2.1.0: Desktop Notification Window with Audio Alert"""

import tkinter as tk
import winsound
import threading
from .theme import Theme


class NotificationPopup:
    """Desktop popup notification window — appears on reminder trigger"""

    def __init__(self, parent, note, theme: Theme, on_dismiss=None, on_open=None):
        self.parent = parent
        self.note = note
        self.theme = theme
        self.on_dismiss = on_dismiss or (lambda: None)
        self.on_open = on_open or (lambda: None)

        # Play audio alert in background thread (non-blocking)
        threading.Thread(target=self._play_alert, daemon=True).start()

        # Create topmost notification window
        self.popup = tk.Toplevel(parent)
        self.popup.attributes("-topmost", True)
        self.popup.attributes("-alpha", 0.95)
        self.popup.title("Reminder")
        self.popup.geometry("400x200")

        # Get screen dimensions for positioning (bottom-right corner)
        self.popup.update_idletasks()
        screen_w = self.popup.winfo_screenwidth()
        screen_h = self.popup.winfo_screenheight()
        window_w = 400
        window_h = 200
        x = screen_w - window_w - 20  # 20px margin from right
        y = screen_h - window_h - 60  # 60px margin from bottom (taskbar clearance)
        self.popup.geometry(f"{window_w}x{window_h}+{x}+{y}")

        # Configure background color
        bg_color = "#F5F5F7"
        self.popup.config(bg=bg_color)

        # === Main Content Frame ===
        content_frame = tk.Frame(self.popup, bg=bg_color)
        content_frame.pack(fill="both", expand=True, padx=16, pady=16)

        # === Title (Note Name) ===
        title_label = tk.Label(
            content_frame,
            text="⏰ REMINDER",
            bg=bg_color,
            fg="#FF3B30",  # Alert red
            font=("Segoe UI", 11, "bold"),
        )
        title_label.pack(anchor="w", pady=(0, 8))

        # === Note Title ===
        note_title = tk.Label(
            content_frame,
            text=self.note.title[:60],  # Truncate long titles
            bg=bg_color,
            fg="#1C1C1E",
            font=("Segoe UI", 10, "bold"),
            wraplength=350,
            justify="left",
        )
        note_title.pack(anchor="w", pady=(0, 4))

        # === Note Content Preview ===
        if self.note.content:
            content_preview = self.note.content[:80].replace("\n", " ")
            content_label = tk.Label(
                content_frame,
                text=content_preview,
                bg=bg_color,
                fg="#666666",
                font=("Segoe UI", 9),
                wraplength=350,
                justify="left",
            )
            content_label.pack(anchor="w", pady=(0, 8))

        # === Button Frame ===
        btn_frame = tk.Frame(content_frame, bg=bg_color)
        btn_frame.pack(fill="x", pady=(8, 0))

        # Dismiss button
        btn_dismiss = tk.Button(
            btn_frame,
            text="Dismiss",
            bg="#E5E5EA",
            fg="#1C1C1E",
            font=("Segoe UI", 9),
            bd=0,
            relief="flat",
            command=self._on_dismiss,
            padx=12,
            pady=5,
            activebackground="#D5D5DA",
            activeforeground="#1C1C1E",
            cursor="hand2",
        )
        btn_dismiss.pack(side="left", padx=(0, 8))

        # Open Note button (Primary)
        btn_open = tk.Button(
            btn_frame,
            text="Open Note",
            bg="#007AFF",
            fg="#FFFFFF",
            font=("Segoe UI", 9, "bold"),
            bd=0,
            relief="flat",
            command=self._on_open,
            padx=12,
            pady=5,
            activebackground="#0051C3",
            activeforeground="#FFFFFF",
            cursor="hand2",
        )
        btn_open.pack(side="left")

        # Auto-dismiss after 8 seconds
        self.popup.after(8000, self._on_dismiss)

    def _play_alert(self):
        """v2.2.0: Play system alert sound with multi-layer fallback"""
        try:
            # Layer 1: System exclamation sound
            winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC)
        except Exception:
            pass

        try:
            # Layer 2: OS-level message beep (guaranteed on Windows)
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass

        # Layer 3: Fallback beeps to guarantee audio output
        try:
            winsound.Beep(1000, 500)  # 1000 Hz for 500ms
            winsound.Beep(1000, 500)  # Repeat for emphasis
        except Exception:
            pass

    def _on_dismiss(self):
        """Dismiss notification"""
        try:
            self.popup.destroy()
        except Exception:
            pass
        self.on_dismiss()

    def _on_open(self):
        """Open note (callback to main window)"""
        try:
            self.popup.destroy()
        except Exception:
            pass
        self.on_open()
