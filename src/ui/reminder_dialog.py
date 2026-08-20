"""ReminderDialog — v2.0.5: Clean Native Time Picker & Button Restoration"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
from tkcalendar import DateEntry
from .theme import Theme
from ..core.database import update_note  # v2.3.2: Direct database persistence


class ReminderDialog:
    """Reminder datetime picker — non-modal, independent topmost window (v2.0.3)"""

    def __init__(self, parent, note, theme: Theme):
        self.parent = parent
        self.note = note
        self.theme = theme
        self.on_save = lambda: None
        self.on_clear = lambda: None

        # Drag state
        self._drag_x = 0
        self._drag_y = 0

        # Create non-modal dialog window (v2.0.3: NO grab_set, pure topmost)
        self.dialog = tk.Toplevel(parent)
        # v2.0.3: Use normal frame window (not frameless) for native OS titlebar
        self.dialog.title("Set Reminder")
        self.dialog.geometry("380x320")
        self.dialog.config(bg="#F5F5F7")

        # v1.8.1: Force geometry refresh before centering
        parent.update_idletasks()
        self.dialog.update_idletasks()

        # Get parent's absolute screen position + size
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()

        # Dialog dimensions
        dialog_w = 380
        dialog_h = 320

        # Center dialog on parent window
        x = parent_x + (parent_w - dialog_w) // 2
        y = parent_y + (parent_h - dialog_h) // 2

        self.dialog.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")

        # v2.5.7: STANDARD MODAL PATTERN — No aggressive focus loop that breaks dropdowns
        # Establish parent-child relationship for proper Z-order
        try:
            self.dialog.transient(parent.winfo_toplevel())
        except Exception:
            pass

        # Window-level modal lock (doesn't interfere with dropdown widgets)
        try:
            self.dialog.grab_set()
        except Exception:
            pass

        # Keep dialog on top
        self.dialog.attributes("-topmost", True)

        # Initial lift to front (one-time, not continuous loop)
        self.dialog.lift()
        self.dialog.focus_set()  # Use focus_set() instead of focus_force() (gentler)

        # v2.5.9: TRUE MODAL PATTERN — Disable main window (prevents OS refocus on dropdown close)
        # When dropdown closes, OS won't refocus main window (it's disabled)
        # This is the proper Tkinter modal behavior and prevents Z-order jitter
        self.parent_root = parent.winfo_toplevel()

        # Disable main window (prevents user interaction AND OS refocus)
        try:
            self.parent_root.attributes("-disabled", True)
        except Exception:
            pass

        # v2.5.8: PAUSE SCHEDULER — Prevent root.after() callback from stealing focus while dialog open
        # Store reference to parent's scheduler state so we can pause it
        self.scheduler_was_running = False
        if hasattr(self.parent_root, '_scheduler_enabled'):
            self.scheduler_was_running = self.parent_root._scheduler_enabled
            self.parent_root._scheduler_enabled = False  # Pause reminder scheduler

        # v2.0.4: Using native OS titlebar - no custom header needed

        # === Content Frame ===
        content_frame = tk.Frame(self.dialog, bg="#F5F5F7")
        content_frame.pack(fill="both", expand=True, padx=16, pady=16)

        # === v2.2.0: Calendar Date Picker with Quick Preset ===
        date_header_frame = tk.Frame(content_frame, bg="#F5F5F7")
        date_header_frame.pack(fill="x", pady=(0, 8))

        date_label = tk.Label(
            date_header_frame,
            text="Select Date (dd-mm-yyyy)",
            bg="#F5F5F7",
            fg="#1C1C1E",
            font=("Segoe UI", 9, "bold"),
        )
        date_label.pack(side="left")

        # Quick "Today" button (v2.2.0)
        btn_today = tk.Button(
            date_header_frame,
            text="Today",
            bg="#E5E5EA",
            fg="#1C1C1E",
            font=("Segoe UI", 8),
            bd=0,
            relief="flat",
            command=self._set_today,
            padx=8,
            pady=2,
            activebackground="#D5D5DA",
            activeforeground="#1C1C1E",
            cursor="hand2",
        )
        btn_today.pack(side="right", padx=(4, 0))

        # Default to tomorrow
        default_date = datetime.now() + timedelta(days=1)
        self.date_entry = DateEntry(
            content_frame,
            width=22,
            background='darkblue',
            foreground='white',
            borderwidth=2,
            year=default_date.year,
            month=default_date.month,
            day=default_date.day,
            date_pattern='dd-mm-yyyy',  # v2.2.0: Use date_pattern for proper format
            showweeknumbers=False,
        )
        self.date_entry.pack(fill="x", pady=(0, 16))

        # === v2.2.0: Time Picker with Quick Preset ===
        time_header_frame = tk.Frame(content_frame, bg="#F5F5F7")
        time_header_frame.pack(fill="x", pady=(0, 4))

        time_label = tk.Label(
            time_header_frame,
            text="Select Time (HH:MM)",
            bg="#F5F5F7",
            fg="#1C1C1E",
            font=("Segoe UI", 9, "bold"),
        )
        time_label.pack(side="left")

        # Quick "Now (+5m)" button (v2.2.0)
        btn_now = tk.Button(
            time_header_frame,
            text="Now (+5m)",
            bg="#E5E5EA",
            fg="#1C1C1E",
            font=("Segoe UI", 8),
            bd=0,
            relief="flat",
            command=self._set_now_plus_5m,
            padx=8,
            pady=2,
            activebackground="#D5D5DA",
            activeforeground="#1C1C1E",
            cursor="hand2",
        )
        btn_now.pack(side="right", padx=(4, 0))

        # Time frame with hours and minutes
        time_frame = tk.Frame(content_frame, bg="#F5F5F7")
        time_frame.pack(fill="x", pady=(0, 16))

        # Hour selection using ttk.Combobox
        hour_label = tk.Label(time_frame, text="Hour:", bg="#F5F5F7", fg="#1C1C1E", font=("Segoe UI", 9))
        hour_label.pack(side="left", padx=(0, 8))

        # Generate 0-23 hour values
        hours = [f"{i:02d}" for i in range(24)]
        self.hour_combo = ttk.Combobox(time_frame, values=hours, width=3, state="readonly", font=("Segoe UI", 10))
        self.hour_combo.set("09")  # Default to 9 AM
        self.hour_combo.pack(side="left", padx=4)

        colon = tk.Label(time_frame, text=":", bg="#F5F5F7", fg="#1C1C1E", font=("Segoe UI", 10, "bold"))
        colon.pack(side="left")

        # Minute selection using ttk.Combobox
        min_label = tk.Label(time_frame, text=" Min:", bg="#F5F5F7", fg="#1C1C1E", font=("Segoe UI", 9))
        min_label.pack(side="left", padx=(4, 8))

        # Generate 0-59 minute values
        minutes = [f"{i:02d}" for i in range(60)]
        self.minute_combo = ttk.Combobox(time_frame, values=minutes, width=3, state="readonly", font=("Segoe UI", 10))
        self.minute_combo.set("00")
        self.minute_combo.pack(side="left", padx=4)

        # === Button Frame ===
        btn_frame = tk.Frame(content_frame, bg="#F5F5F7")
        btn_frame.pack(fill="x", pady=(8, 0))

        # Set button (Primary — blue)
        self.btn_set = tk.Button(
            btn_frame,
            text="Set",
            bg="#007AFF",
            fg="#FFFFFF",
            font=("Segoe UI", 9, "bold"),
            bd=0,
            relief="flat",
            command=self._save_reminder,
            padx=16,
            pady=6,
            activebackground="#0051C3",
            activeforeground="#FFFFFF",
            cursor="hand2",
        )
        self.btn_set.pack(side="left", padx=2)

        # Clear button (Secondary — gray)
        self.btn_clear = tk.Button(
            btn_frame,
            text="Clear",
            bg="#E5E5EA",
            fg="#1C1C1E",
            font=("Segoe UI", 9),
            bd=0,
            relief="flat",
            command=self._clear_reminder,
            padx=16,
            pady=6,
            activebackground="#D5D5DA",
            activeforeground="#1C1C1E",
            cursor="hand2",
        )
        self.btn_clear.pack(side="left", padx=2)

        # Cancel button (Secondary — gray)
        self.btn_cancel = tk.Button(
            btn_frame,
            text="Cancel",
            bg="#E5E5EA",
            fg="#1C1C1E",
            font=("Segoe UI", 9),
            bd=0,
            relief="flat",
            command=self._close_dialog,  # v2.6.2: Call _close_dialog() to restore state
            padx=16,
            pady=6,
            activebackground="#D5D5DA",
            activeforeground="#1C1C1E",
            cursor="hand2",
        )
        self.btn_cancel.pack(side="right", padx=2)

        # v2.6.2: Handle window close button (X) to restore state
        self.dialog.protocol("WM_DELETE_WINDOW", self._close_dialog)

        # v2.0.4: Native titlebar handles dragging - no custom drag binding needed

    def _close_dialog(self):
        """v2.5.9: Proper modal cleanup — re-enable main window, release grab, destroy dialog"""
        # v2.5.9: Re-enable main window (was disabled to prevent OS refocus)
        try:
            self.parent_root.attributes("-disabled", False)
            self.parent_root.lift()  # Lift main window to front
            self.parent_root.focus_force()  # Restore focus to main window
        except Exception:
            pass

        # v2.5.8: Resume scheduler if it was paused
        try:
            if hasattr(self.parent_root, '_scheduler_enabled') and self.scheduler_was_running:
                self.parent_root._scheduler_enabled = True  # Resume reminder scheduler
        except Exception:
            pass

        try:
            # Release modal lock before destroying
            self.dialog.grab_release()
        except Exception:
            pass

        try:
            # Reset topmost to prevent main window from staying hidden
            self.dialog.attributes("-topmost", False)
        except Exception:
            pass

        try:
            # Destroy dialog
            self.dialog.destroy()
        except Exception:
            pass

    def _save_reminder(self):
        """v2.3.2: Direct database persistence for reminder (no callback chain)"""
        try:
            # Get date from calendar widget (returns datetime.date)
            date_obj = self.date_entry.get_date()
            if not date_obj:
                self._close_dialog()
                return

            # Get time from comboboxes (v2.0.5: safe ttk.Combobox)
            hour_str = self.hour_combo.get().strip()
            minute_str = self.minute_combo.get().strip()

            # Parse time values safely
            try:
                hour = int(hour_str)
                minute = int(minute_str)
            except (ValueError, TypeError):
                self._close_dialog()
                return

            # Validate time ranges
            if not (0 <= hour <= 23) or not (0 <= minute <= 59):
                self._close_dialog()
                return

            # v2.2.1: ISO datetime normalization (YYYY-MM-DD HH:MM)
            # Ensure absolute format consistency for scheduler string comparison
            date_str = date_obj.strftime("%Y-%m-%d")
            time_str = f"{hour:02d}:{minute:02d}"
            reminder_str = f"{date_str} {time_str}"

            # Verify format is valid ISO-8601 (YYYY-MM-DD HH:MM)
            datetime.strptime(reminder_str, "%Y-%m-%d %H:%M")

            # v2.3.2: Direct database persistence (no callback chain)
            # Update database immediately with reminder fields
            update_note(self.note.id,
                       reminder_datetime=reminder_str,
                       reminder_triggered=False)

            # Update note object to keep UI state in sync
            self.note.reminder_datetime = reminder_str
            self.note.reminder_triggered = False

            # Refresh UI immediately
            if hasattr(self.parent, '_load_notes') and callable(self.parent._load_notes):
                self.parent._load_notes()

            # v2.4.0: Trigger reminder check immediately (no 5-second wait)
            if hasattr(self.parent, '_check_reminders') and callable(self.parent._check_reminders):
                self.parent._check_reminders()

            # Legacy callback for compatibility
            self.on_save()
            self._close_dialog()
        except (ValueError, AttributeError, TypeError):
            # Invalid format or input — close
            self._close_dialog()

    def _clear_reminder(self):
        """v2.3.2: Clear reminder with direct database persistence"""
        # v2.3.2: Direct database persistence (no callback chain)
        update_note(self.note.id,
                   reminder_datetime=None,
                   reminder_triggered=False)

        # Update note object
        self.note.reminder_datetime = None
        self.note.reminder_triggered = False

        # Refresh UI immediately
        if hasattr(self.parent, '_load_notes') and callable(self.parent._load_notes):
            self.parent._load_notes()

        # v2.4.0: Trigger reminder check immediately (no 5-second wait)
        if hasattr(self.parent, '_check_reminders') and callable(self.parent._check_reminders):
            self.parent._check_reminders()

        # Legacy callback for compatibility
        self.on_clear()
        self._close_dialog()

    def _set_today(self):
        """v2.2.1: Quick preset - set date to today (fixed tkcalendar API)"""
        try:
            from datetime import date
            # tkcalendar uses set_date() with datetime.date object
            self.date_entry.set_date(date.today())
        except Exception:
            pass

    def _set_now_plus_5m(self):
        """v2.2.0: Quick preset - set time to now + 5 minutes"""
        try:
            now = datetime.now()
            future = now + timedelta(minutes=5)

            # Set hour and minute comboboxes
            hour_str = f"{future.hour:02d}"
            minute_str = f"{future.minute:02d}"

            self.hour_combo.set(hour_str)
            self.minute_combo.set(minute_str)
        except Exception:
            pass
