"""NoteCard widget — macOS Pastel style card ด้วย rounded corners + color bar"""

import tkinter as tk
from .theme import Theme, PASTEL_PALETTE
from ..core.models import Note


class NoteCard(tk.Frame):
    """การ์ดโน้ตแบบ macOS Pastel — color bar + status badge + modern buttons"""

    def __init__(self, master, note: Note, theme: Theme, is_completed_tab: bool = False, **kwargs):
        super().__init__(master, **kwargs)
        self.note = note
        self.theme = theme
        self.is_completed_tab = is_completed_tab  # ✓ v1.3.8: Track which tab we're in

        # สีพาสเทลแบบสุ่ม (หรือตั้งเอง)
        color_list = list(PASTEL_PALETTE.values())
        self.color_idx = hash(note.id) % len(color_list)
        self.card_color = color_list[self.color_idx]

        # v2.9.26: Red border shows if alarm is TRIGGERED AND datetime still exists
        # v2.9.26: Complete dismiss clears both reminder_datetime and sets reminder_triggered=1
        # Before alarm: reminder_triggered = 0, reminder_datetime = set → No border
        # Alarm fires: reminder_triggered = 1, reminder_datetime = set → RED BORDER SHOWS
        # User dismisses: reminder_triggered = 1, reminder_datetime = NULL → No border (datetime cleared)
        # User snoozes: reminder_triggered = 0, reminder_datetime = future → No border (time not arrived)
        reminder_triggered = getattr(note, 'reminder_triggered', False)
        reminder_datetime = note.reminder_datetime

        # v2.9.26: Red border shows if reminder_triggered AND datetime still exists
        is_reminder_active = bool(reminder_triggered and reminder_datetime)

        # Card frame (white background สำหรับ light mode)
        # ✓ v1.3.5: Add visible border for Light Theme contrast
        # ✓ v1.4.2: Modern card styling — softer borders + modern spacing
        # v2.9.23: Dynamic highlight — RED (#FF3B30) if alarm time ARRIVED and not dismissed
        highlight_color = "#FF3B30" if is_reminder_active else theme.c("note_border_soft")
        highlight_thickness = 3 if is_reminder_active else 2

        self.config(
            bg=theme.c("note_bg"),
            highlightthickness=highlight_thickness,  # v2.9.21: Thicker red border when alarm active
            highlightbackground=highlight_color,  # v2.9.21: Red (#FF3B30) if reminder active, normal otherwise
            relief="flat",
            padx=12,  # ✓ v1.4.2: Increased padding for spacious, modern appearance
            pady=10,  # ✓ v1.4.2: Increased padding for better breathing room
        )

        # Left color bar (thin pastel stripe)
        color_bar = tk.Frame(self, bg=self.card_color, width=4)
        color_bar.pack(side="left", fill="y", padx=0, pady=0)
        color_bar.pack_propagate(False)

        # Main content frame — แยกจาก Header และ Content
        # v1.6.1: Add highlightthickness=0 to prevent border bleeds
        main_frame = tk.Frame(self, bg=theme.c("note_bg"), highlightthickness=0)
        main_frame.pack(side="left", fill="both", expand=True)

        # === Header (ปุ่มควบคุม) ===
        # v1.8.9: Reorganized packing order to prevent button overflow
        # v1.6.1: Add highlightthickness=0 to prevent border bleeds
        header = tk.Frame(main_frame, bg=theme.c("note_bg"), highlightthickness=0)
        # ✓ v1.4.2: Increased header padding for modern spacing
        header.pack(fill="x", padx=12, pady=10)

        # v2.5.0: Simplified header — no right-side elements, title gets full space

        # v1.8.9: NOW pack left-side elements (fold, priority, pin, title)
        # after right-side (status, control) have reserved their space

        # Fold button (collapse/expand)
        fold_text = "▾" if not note.collapsed else "▸"
        self.btn_fold = tk.Button(
            header,
            text=fold_text,
            width=2,
            height=1,
            bd=0,
            bg=theme.c("note_bg"),
            fg=theme.c("fg"),
            activebackground=theme.c("note_bg"),
            font=("Segoe UI", 9),
            command=self._on_toggle_fold,
            padx=2,
            pady=2,
        )
        self.btn_fold.pack(side="left", padx=2)

        # v2.5.0: Priority flag button — always use 🚩, change color by priority
        priority_icon_map = {
            "high": ("🚩", "#FF3B30"),      # Red
            "medium": ("🚩", "#FF9500"),    # Orange
            "low": ("🚩", "#007AFF"),       # Blue
            "none": ("🚩", "#B0B0B0"),      # Gray
        }
        flag_icon, flag_color = priority_icon_map.get(note.priority, ("🚩", "#B0B0B0"))

        self.btn_priority = tk.Button(
            header,
            text=flag_icon,
            width=2,
            height=1,
            bd=0,
            bg=theme.c("note_bg"),
            fg=flag_color,
            activebackground=theme.c("note_bg"),
            activeforeground=flag_color,
            font=("Segoe UI", 10),
            command=self._on_priority_clicked,
            padx=2,
            pady=2,
        )
        self.btn_priority.pack(side="left", padx=2)
        self.priority_icon_map = priority_icon_map

        # Pin button (v1.5.0)
        pin_icon = "📌" if note.is_pinned else "📍"
        self.btn_pin = tk.Button(
            header,
            text=pin_icon,
            width=2,
            height=1,
            bd=0,
            bg=theme.c("note_bg"),
            fg="#FF6B6B" if note.is_pinned else theme.c("fg_muted"),
            activebackground=theme.c("note_bg"),
            activeforeground="#FF6B6B",
            font=("Segoe UI", 10),
            command=self._on_toggle_pin,
            padx=2,
            pady=2,
        )
        self.btn_pin.pack(side="left", padx=2)

        # v1.8.9: Title entry — now only expands into remaining space (not pushing buttons off)
        self.title_var = tk.StringVar(value=note.title)
        self.title_entry = tk.Entry(
            header,
            textvariable=self.title_var,
            bg=theme.c("note_bg"),
            fg=theme.c("fg"),
            font=("Segoe UI", 9, "bold"),
            bd=0,
            relief="flat",
        )
        self.title_entry.pack(side="left", padx=4, fill="x", expand=True)
        self.title_entry.bind("<FocusOut>", self._on_title_change)

        # === Content area (stored for toggle) ===
        self.content_frame = None
        self.content_text = None
        self._main_frame_ref = main_frame  # เก็บ reference เพื่อให้ content_frame pack ลงใน main_frame
        # v1.4.0: Always display content if not collapsed (ensures payload persistence across tabs)
        if not note.collapsed:
            self._show_content()

        # === Footer Frame (v2.5.0: Actions + Status moved to bottom) ===
        footer = tk.Frame(main_frame, bg=theme.c("note_bg"), highlightthickness=0)
        footer.pack(fill="x", padx=12, pady=(0, 8))

        # Left side: Reminder button + Delete button
        left_frame = tk.Frame(footer, bg=theme.c("note_bg"), highlightthickness=0)
        left_frame.pack(side="left", fill="x", expand=False)

        # Reminder button (v1.3.0) — ⏰ for setting reminder datetime
        # v2.9.9: Check reminder_triggered FIRST to ensure icon shows correct state
        # v2.9.10: Use getattr() instead of .get() (Note is object, not dict)
        # If triggered=1, show inactive (⏱) gray regardless of reminder_datetime
        # If triggered=0 AND reminder_datetime set, show active (⏰) red
        reminder_triggered = getattr(note, 'reminder_triggered', False)
        is_reminder_active = bool(note.reminder_datetime) and not reminder_triggered
        reminder_icon = "⏰" if is_reminder_active else "⏱"
        self.btn_reminder = tk.Button(
            left_frame,
            text=reminder_icon,
            width=2,
            height=1,
            bd=0,
            bg=theme.c("note_bg"),
            fg=theme.priority_color("high") if is_reminder_active else theme.c("fg_muted"),
            activebackground=theme.c("note_bg"),
            activeforeground=theme.c("fg"),
            font=("Segoe UI", 10),
            command=self._on_set_reminder,
            padx=2,
            pady=2,
        )
        # v2.5.0: Show reminder button on all tabs (moved to footer)
        self.btn_reminder.pack(side="left", padx=2)

        # Delete button (v1.3.8) — changed from ✕ to 🗑 (trash icon)
        self.btn_delete = tk.Button(
            left_frame,
            text="🗑",
            width=2,
            height=1,
            bd=0,
            bg=theme.c("note_bg"),
            fg=theme.c("fg_muted"),
            activebackground=theme.c("note_bg"),
            activeforeground="#EF4444",  # Red on hover
            font=("Segoe UI", 10),
            command=self._on_delete,
            padx=2,
            pady=2,
        )
        self.btn_delete.pack(side="left", padx=2)

        # Spacer (expands to push right-side elements to edge)
        spacer = tk.Frame(footer, bg=theme.c("note_bg"))
        spacer.pack(side="left", fill="x", expand=True)

        # Right side: Action button + Status badge + Priority badge
        right_frame = tk.Frame(footer, bg=theme.c("note_bg"), highlightthickness=0)
        right_frame.pack(side="right", fill="x", expand=False, padx=2)

        # v2.9.37: Action button (Complete ✔ / Restore ↩) based on note status
        if note.status == "completed":
            action_text = "↩"  # Restore icon
            action_color = "#34C759"  # Green
        else:
            action_text = "✔"  # Complete icon
            action_color = "#007AFF"  # Blue

        self.btn_action = tk.Button(
            right_frame,
            text=action_text,
            width=2,
            height=1,
            bd=0,
            bg=theme.c("note_bg"),
            fg=action_color,
            activebackground=theme.c("note_bg"),
            activeforeground=action_color,
            font=("Segoe UI", 10, "bold"),
            command=self._on_toggle_status,
            padx=2,
            pady=2,
        )
        self.btn_action.pack(side="left", padx=2)

        # Status badge (Done / Active) — v2.5.3: Convert to Label for pixel-perfect alignment
        if note.status == "completed":
            badge_text = "Done"
            badge_bg = "#D1FAE5"  # Light green
            badge_fg = "#10B981"  # Green
        else:
            badge_text = "Active"
            badge_bg = "#DBEAFE"  # Light blue
            badge_fg = "#0EA5E9"  # Blue

        # v2.5.3: Unified Label (not Button) for exact pixel-perfect alignment with priority badge
        self.status_badge = tk.Label(
            right_frame,
            text=badge_text,
            bg=badge_bg,
            fg=badge_fg,
            font=("Segoe UI", 8, "bold"),  # v2.5.3: Identical to priority badge
            padx=8,  # v2.5.3: Identical padding
            pady=2,  # v2.5.3: Identical padding
            bd=0,
            relief="flat",
        )
        self.status_badge.pack(side="left", padx=2)
        # v2.5.3: Bind click event for status toggling
        self.status_badge.bind("<Button-1>", lambda e: self._on_toggle_status())

        # Priority badge (v1.3.1) — Pill-shaped badge with priority level
        # Only show if priority != "none"
        self.priority_badge = None
        if note.priority and note.priority != "none":
            self._create_priority_badge(right_frame, theme)

        # v2.5.1: Apply status styling AFTER status_badge is created
        self._update_strikethrough()

        # Callbacks
        self.on_update = lambda: None  # Title/content changes only
        self.on_status_update = lambda: None  # Status changes only (v1.3.9: prevent title corruption)
        self.on_pin_change = lambda: None  # Pin state changed (v1.5.0: trigger board re-sort)
        self.on_delete_note = lambda: None

    def _show_content(self):
        """แสดง content area — pack ลงใน main_frame ด้านล่าง header"""
        if self.content_frame is not None:
            # v1.4.0: Sync content from note object if already shown
            if self.content_text:
                self.content_text.config(state="normal")
                self.content_text.delete("1.0", "end")
                self.content_text.insert("1.0", self.note.content)
            return

        self.content_frame = tk.Frame(self._main_frame_ref, bg=self.theme.c("note_bg"), highlightthickness=0)  # v1.6.1
        # ✓ v1.4.2: Increased content padding for modern spacing
        self.content_frame.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        self.content_text = tk.Text(
            self.content_frame,
            height=4,
            width=50,
            bg=self.theme.c("note_bg"),  # v1.6.1: Use note_bg instead of main bg to match card
            fg=self.theme.c("fg"),
            font=("Segoe UI", 9),
            wrap="word",
            relief="flat",
            bd=0,
            highlightthickness=0,  # v1.6.1: Remove default border
        )
        # v1.4.0: Guarantee content is always displayed (never empty payload)
        content_to_show = self.note.content if self.note.content else ""
        self.content_text.insert("1.0", content_to_show)
        self.content_text.pack(fill="both", expand=True)
        self.content_text.bind("<FocusOut>", self._on_content_change)

    def _hide_content(self):
        """ซ่อน content area"""
        if self.content_frame is not None:
            self.content_frame.destroy()
            self.content_frame = None
            self.content_text = None

    def _update_strikethrough(self):
        """ปรับ status badge ไม่ใช้ strikethrough (v1.3.2) — ข้อความต้องอ่านได้ชัดเจน"""
        if self.note.status == "completed":
            # Keep font normal, no strikethrough for readability (v1.3.2)
            self.title_entry.config(font=("Segoe UI", 9, "bold"))
            # Update status badge
            self.status_badge.config(text="Done", bg="#D1FAE5", fg="#10B981")
        else:
            # Keep font normal
            self.title_entry.config(font=("Segoe UI", 9, "bold"))
            # Update status badge
            self.status_badge.config(text="Active", bg="#DBEAFE", fg="#0EA5E9")

    def _update_action_button(self):
        """v2.9.37: Update action button (Complete ✔ / Restore ↩) based on current note status"""
        if not hasattr(self, 'btn_action'):
            return

        if self.note.status == "completed":
            self.btn_action.config(text="↩", fg="#34C759")  # Restore (green)
        else:
            self.btn_action.config(text="✔", fg="#007AFF")  # Complete (blue)

    def _on_toggle_fold(self):
        """ปุ่มพับ/กาง"""
        self.note.toggle_collapse()

        if self.note.collapsed:
            self._hide_content()
            self.btn_fold.config(text="▸")
        else:
            self._show_content()
            self.btn_fold.config(text="▾")

        self.on_update(self.note)

    def _on_toggle_status(self):
        """ปุ่ม status (✓) — toggle note status ONLY (v1.3.9: no title/content modification)"""
        # v1.4.1: Force flush of unsaved UI changes BEFORE status change
        # If user typed but didn't click out, FocusOut event never fired, so changes are still in Widget only
        title_changed = False
        content_changed = False

        # Sync title from Entry widget (might not have triggered FocusOut yet)
        if self.title_entry:
            latest_title = self.title_entry.get().strip()
            if latest_title and latest_title != self.note.title:
                self.note.title = latest_title
                title_changed = True

        # Sync content from Text widget (might not have triggered FocusOut yet)
        if self.content_text:
            latest_content = self.content_text.get("1.0", "end-1c")
            if latest_content != self.note.content:
                self.note.content = latest_content
                content_changed = True

        # Save any pending changes to DB BEFORE status change
        if title_changed or content_changed:
            self.on_update(self.note)

        # Now change status
        if self.note.status == "active":
            self.note.mark_done()
        else:
            self.note.mark_active()

        self._update_strikethrough()
        # v1.3.9: Call status-only update to prevent title corruption — v2.3.1: Pass note explicitly
        if hasattr(self, 'on_status_update') and callable(self.on_status_update):
            self.on_status_update(self.note)
        else:
            self.on_update(self.note)

    def _on_toggle_pin(self):
        """ปุ่ม pin (📌/📍) — toggle note pinning (v1.5.0)"""
        self.note.is_pinned = not self.note.is_pinned

        # Update button appearance
        pin_icon = "📌" if self.note.is_pinned else "📍"
        pin_color = "#FF6B6B" if self.note.is_pinned else self.theme.c("fg_muted")
        self.btn_pin.config(text=pin_icon, fg=pin_color, activeforeground=pin_color)

        # Save to database
        from ..core.database import update_note
        update_note(self.note.id, is_pinned=self.note.is_pinned)

        # Trigger board refresh to re-sort notes
        if hasattr(self, 'on_pin_change') and callable(self.on_pin_change):
            self.on_pin_change()

    def _on_title_change(self, event):
        """เมื่อเปลี่ยน title จากช่อง Entry"""
        new_title = self.title_var.get().strip()
        if new_title:
            self.note.title = new_title
            self.on_update(self.note)

    def _on_content_change(self, event):
        """เมื่อเปลี่ยน content จากช่อง Text"""
        new_content = self.content_text.get("1.0", "end-1c")
        self.note.content = new_content
        self.on_update(self.note)

    def _on_delete(self):
        """ปุ่ม delete"""
        self.on_delete_note()

    def _on_priority_clicked(self):
        """เปิด priority menu เมื่อคลิกปุ่ม flag (v1.3.3) — improved visual labels"""
        menu = tk.Menu(self, tearoff=False)

        priorities = [
            ("🔴 P1 — High Priority", "high"),
            ("🟠 P2 — Medium Priority", "medium"),
            ("🔵 P3 — Low Priority", "low"),
            ("⚪ --- — No Priority", "none"),
        ]

        for label, priority_val in priorities:
            menu.add_command(
                label=label,
                command=lambda p=priority_val: self._set_priority(p)
            )

        # Position menu at button location
        try:
            x = self.btn_priority.winfo_rootx()
            y = self.btn_priority.winfo_rooty() + self.btn_priority.winfo_height()
            menu.post(x, y)
        except tk.TclError:
            pass

    def _open_priority_menu(self, event):
        """เปิด priority menu เมื่อคลิกที่ priority indicator (v1.3.0) — deprecated in v1.3.2"""
        self._on_priority_clicked()

    def _create_priority_badge(self, parent_frame, theme):
        """Create Pill-shaped priority badge (v1.3.1)"""
        # Priority color palette (light background + dark text)
        badge_config = {
            "high": {
                "bg": "#FFE5E5",  # Light red (#FF3B30 at 15% alpha)
                "fg": "#C41C00",  # Dark red text
                "text": "High"
            },
            "medium": {
                "bg": "#FFF4E5",  # Light orange (#FF9500 at 15% alpha)
                "fg": "#CC6600",  # Dark orange text
                "text": "Medium"
            },
            "low": {
                "bg": "#E5F2FF",  # Light blue (#007AFF at 15% alpha)
                "fg": "#003399",  # Dark blue text
                "text": "Low"
            }
        }

        config = badge_config.get(self.note.priority, {})
        if not config:
            return

        # Destroy old badge if exists
        if self.priority_badge:
            self.priority_badge.destroy()

        # v2.5.2: Unified badge styling with status badge
        self.priority_badge = tk.Label(
            parent_frame,
            text=config["text"],
            bg=config["bg"],
            fg=config["fg"],
            font=("Segoe UI", 8, "bold"),  # v2.5.2: Consistent with status badge (was 7)
            padx=8,  # v2.5.2: Unified padding (was 6)
            pady=2,  # v2.5.2: Unified padding (was 1)
            relief="flat",
            bd=0,
            # Removed fixed width for better flex styling
        )
        self.priority_badge.pack(side="left", padx=2)
        self.priority_badge.bind("<Button-1>", lambda e: self._open_priority_menu(e))

    def _set_priority(self, priority: str):
        """อัปเดต priority + update flag button color (v1.3.4) — emoji flag with color"""
        self.note.priority = priority

        # Update flag button (v1.3.4) — back to emoji flag (🚩) with color coding
        try:
            flag_icon, flag_color = self.priority_icon_map.get(priority, ("🏳", "#CCCCCC"))
            self.btn_priority.config(text=flag_icon, fg=flag_color, activeforeground=flag_color)
            # Force immediate redraw of button
            self.btn_priority.update_idletasks()
        except Exception:
            pass

        # Find status_frame to recreate badge
        # Navigate up to find the header/status frame
        try:
            # Get the parent frame of status badge
            status_frame = self.status_badge.master

            # Recreate badge
            if priority and priority != "none":
                self._create_priority_badge(status_frame, self.theme)
            else:
                # Destroy badge if priority is "none"
                if self.priority_badge:
                    self.priority_badge.destroy()
                    self.priority_badge = None
        except Exception:
            pass

        self.on_update(self.note)

    def _on_set_reminder(self):
        """เปิด DateTime picker dialog สำหรับตั้ง reminder — v1.7.2: Movable dialog with modern styling
        v1.9.0: Ensure callback triggers immediate UI update with explicit refresh
        v2.5.3: Add comprehensive error handling with messagebox feedback"""
        try:
            from .reminder_dialog import ReminderDialog
            from tkinter import messagebox

            reminder_dialog = ReminderDialog(self, self.note, self.theme)

            def on_save_callback():
                """v1.9.0: Force immediate UI update when reminder is set"""
                # Update button appearance
                self.btn_reminder.config(fg=self.theme.priority_color("high"), text="⏰")
                # Force immediate visual refresh (prevents UI lag)
                self.btn_reminder.update_idletasks()
                # Save to database — v2.3.1: Pass note object explicitly
                self.on_update(self.note)

            def on_clear_callback():
                """v1.9.0: Force immediate UI update when reminder is cleared"""
                # Reset button appearance
                self.btn_reminder.config(fg=self.theme.c("fg_muted"), text="⏱")
                # Force immediate visual refresh (prevents UI lag)
                self.btn_reminder.update_idletasks()
                # Save to database — v2.3.1: Pass note object explicitly
                self.on_update(self.note)

            reminder_dialog.on_save = on_save_callback
            reminder_dialog.on_clear = on_clear_callback
        except Exception as e:
            # v2.5.3: Show error immediately instead of silent failure
            from tkinter import messagebox
            messagebox.showerror("Reminder Error", f"Failed to open reminder dialog:\n{str(e)}")
            print(f"[Reminder Error] {e}")
            import traceback
            traceback.print_exc()

    def apply_theme(self, theme: Theme):
        """เปลี่ยนธีมตอนโปรแกรมทำงาน"""
        self.theme = theme
        self.config(bg=theme.c("note_bg"))

        # ✓ v1.3.3: Fixed button alignment — activebackground matches background to prevent shift
        # v2.5.3: Fixed reference to status_badge (was btn_status)
        for btn in [self.btn_fold, self.btn_delete, self.btn_reminder, self.btn_priority]:
            btn.config(bg=theme.c("note_bg"), activebackground=theme.c("note_bg"))

        # Update priority button color based on current priority
        try:
            flag_icon, flag_color = self.priority_icon_map.get(self.note.priority, ("🏳", "#CCCCCC"))
            self.btn_priority.config(fg=flag_color, activeforeground=flag_color)
        except Exception:
            pass

        # Update other buttons
        self.btn_fold.config(fg=theme.c("fg"))
        # v2.5.3: status_badge is a Label, not a button, so no need to update it here
        self.btn_delete.config(fg=theme.c("fg_muted"))

        # Update reminder button color based on state
        if self.note.reminder_datetime:
            self.btn_reminder.config(fg=theme.priority_color("high"))
        else:
            self.btn_reminder.config(fg=theme.c("fg_muted"))

        # Recreate priority badge to ensure theme colors apply
        if self.priority_badge and self.note.priority and self.note.priority != "none":
            try:
                status_frame = self.status_badge.master
                self._create_priority_badge(status_frame, theme)
            except Exception:
                pass

        self.title_entry.config(bg=theme.c("note_bg"), fg=theme.c("fg"))

        if self.content_text:
            self.content_text.config(bg=theme.c("bg"), fg=theme.c("fg"))
