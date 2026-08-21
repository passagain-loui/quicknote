"""Main Board window — Tk + overrideredirect + scrollable canvas"""

import tkinter as tk
import ctypes
from .theme import Theme
from .titlebar import TitleBar
from .note_card import NoteCard
from .settings_window import SettingsWindow
from .custom_toast import CustomToastNotification
from ..core.models import Note
from ..core.constants import APP_NAME, APP_VERSION, APP_AUTHOR
from ..core.database import get_all_notes, get_notes_by_status, get_note, create_note, delete_note, update_note, update_note_status_only
from ..services.notification_queue import get_notification_queue


def _get_screen_bounds() -> tuple:
    """ได้ขนาดและตำแหน่ง screen (clamp บน Windows multi-monitor)"""
    try:
        gsm = ctypes.windll.user32.GetSystemMetrics
        x = gsm(76)       # SM_XVIRTUALSCREEN
        y = gsm(77)       # SM_YVIRTUALSCREEN
        w = gsm(78)       # SM_CXVIRTUALSCREEN
        h = gsm(79)       # SM_CYVIRTUALSCREEN
        return (x, y, w, h)
    except Exception:
        # Fallback สำหรับ non-Windows หรือไม่สำเร็จ
        return (0, 0, 1920, 1080)


class Board:
    """หน้าต่างหลัก — borderless, always-on-top, scrollable + load notes from DB"""

    def __init__(self, geometry: str = "", theme_mode: str = "light", settings_obj=None, on_settings_saved=None, on_open_settings=None):
        self.theme = Theme(theme_mode)
        self.settings = settings_obj  # Settings object from main.py
        self.on_settings_saved = on_settings_saved  # Callback when settings are saved
        self.on_open_settings = on_open_settings  # Callback to open settings window
        self._resize_start_x = 0
        self._resize_start_y = 0
        self.note_cards = {}  # id → NoteCard widget
        self.current_filter = "active"  # 'active' or 'completed'
        self.settings_window_instance = None  # Singleton Settings window
        self._scheduler_enabled = True  # v2.5.8: Flag to pause scheduler when dialog open
        self.active_toasts = []  # v2.8.1: Keep references to prevent GC from destroying Toplevel windows

        # Create window
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.config(bg=self.theme.c("bg"))

        # Set minimum window size (for proper UI layout)
        # ✓ v1.3.5: Increased from 450 to 500px width for header buttons (Status + Reminder + Delete)
        self.root.minsize(500, 400)

        # v1.8.6: Withdraw protocol for native centering (prevents top-left glitch)
        self._center_main_window()

        # DPI awareness (อาจจะตั้งไปแล้วใน main.py แต่ทำอีกที่เพื่อให้ปลอดภัย)
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        # TitleBar
        self.titlebar = TitleBar(self.root, self.root, self.theme)

        # v1.8.4: Reset unpinned state AFTER titlebar is created (CRITICAL: order matters!)
        self.root.attributes("-topmost", False)
        self.titlebar.is_topmost = False
        if hasattr(self.titlebar, 'btn_window_pin'):
            self.titlebar.btn_window_pin.config(text="📍")
        self.titlebar.on_new = self._on_new
        self.titlebar.on_close = self._on_close
        self.titlebar.on_minimize = self._on_minimize
        self.titlebar.on_roll_up = self._on_roll_up
        self.titlebar.on_toggle_topmost = self._on_toggle_topmost  # v1.5.1: window pin
        self.titlebar.on_filter_changed = self._on_filter_changed

        # v2.6.1: Toast banner state (in-app notification, no Toplevel)
        self.toast_visible = False
        self.toast_timer = None

        # Roll-up state
        self._rolled_up = False
        self._saved_height = 600

        # v2.6.1: Toast banner (in-app notification, no Toplevel window)
        # Hidden by default, shown only when reminder triggers
        self.toast_frame = tk.Frame(self.root, bg="#FF3B30", highlightthickness=0)
        # Don't pack by default — pack dynamically when shown
        self.toast_content = {}  # Store toast message content

        # v2.3.0: Search Bar — Real-time note filtering
        # v2.3.2: Minimal icon redesign (thin line + muted gray)
        from tkinter import ttk
        self.search_frame = tk.Frame(self.root, bg=self.theme.c("bg"), highlightthickness=0)
        self.search_frame.pack(side="top", fill="x", padx=6, pady=3)

        # v2.3.2: Minimal search icon (thin line style, muted gray)
        self.search_label = tk.Label(
            self.search_frame,
            text="⌕",  # Minimal thin line search symbol
            bg=self.theme.c("bg"),
            fg="#8C8C8C",  # Muted gray color
            font=("Segoe UI", 9),  # Smaller font for minimal appearance
        )
        self.search_label.pack(side="left", padx=(0, 6))

        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(
            self.search_frame,
            textvariable=self.search_var,
            width=28,
            font=("Segoe UI", 9),
        )
        self.search_entry.pack(side="left", fill="x", expand=True, pady=2)
        self.search_entry.bind("<KeyRelease>", self._on_search)

        # Bind clear button (Escape to clear search)
        self.search_entry.bind("<Escape>", lambda e: self.search_var.set("") or self._on_search())

        # Body — scrollable area
        # v1.6.1: Add highlightthickness=0 to prevent border bleeds
        self.body_frame = tk.Frame(self.root, bg=self.theme.c("note_bg"), highlightthickness=0)
        self.body_frame.pack(side="top", fill="both", expand=True)

        # Canvas + scrollbar pattern
        # v1.6.1: Ensure canvas has proper background color for seamless Dark Mode
        self.canvas = tk.Canvas(
            self.body_frame,
            bg=self.theme.c("note_bg"),
            highlightthickness=0,
            height=300,
            bd=0,  # v1.6.1: Remove border
        )
        self.canvas.pack(side="left", fill="both", expand=True)

        self.scrollbar = tk.Scrollbar(self.body_frame, command=self.canvas.yview)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.config(yscrollcommand=self.scrollbar.set)

        # Inner frame inside canvas
        # v1.6.1: Add highlightthickness=0 to prevent border bleeds
        self.inner_frame = tk.Frame(self.canvas, bg=self.theme.c("note_bg"), highlightthickness=0)
        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.inner_frame, anchor="nw"
        )

        # Empty state label (shown when no notes)
        self.empty_state_label = tk.Label(
            self.inner_frame,
            text="ยังไม่มีโน้ต\n\nกดปุ่ม + เพื่อเริ่มสร้างโน้ตแรก",
            bg=self.theme.c("note_bg"),
            fg=self.theme.c("fg_muted"),
            font=("Segoe UI", 11),
            justify="center",
            pady=60,
        )
        self.empty_state_label.pack(fill="both", expand=True)

        # Bind canvas resize to update inner frame width
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        # Mouse wheel scroll
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", self._on_mousewheel)   # Linux wheel up
        self.canvas.bind("<Button-5>", self._on_mousewheel)   # Linux wheel down

        # Focus on canvas click only (don't intercept widgets)
        self.canvas.bind("<Button-1>", lambda e: self.root.focus_force(), add="+")

        # Footer — credit line + heartbeat (v2.2.2)
        footer_frame = tk.Frame(self.root, bg=self.theme.c("bg"))
        footer_frame.pack(side="bottom", fill="x", padx=8, pady=4)

        footer_text = f"{APP_NAME} v{APP_VERSION} • By {APP_AUTHOR}"
        self.footer_label = tk.Label(
            footer_frame,
            text=footer_text,
            bg=self.theme.c("bg"),
            fg=self.theme.c("fg_muted"),
            font=("Segoe UI", 7),
        )
        self.footer_label.pack(side="left")

        # Heartbeat indicator (v2.2.2) — shows scheduler is running
        # v2.6.2: Make label expand to fill available space, right-align text to prevent clipping
        self.heartbeat_label = tk.Label(
            footer_frame,
            text="● Scheduler: Running",
            bg=self.theme.c("bg"),
            fg="#4CAF50",  # Green for active
            font=("Segoe UI", 7),
            justify="right",
        )
        self.heartbeat_label.pack(side="right", fill="x", expand=True, padx=(8, 0), anchor="e")

        # Settings button (⚙) — right side of footer
        self.btn_settings = tk.Button(
            footer_frame,
            text="⚙",
            bg=self.theme.c("bg"),
            fg=self.theme.c("fg"),
            font=("Segoe UI Symbol", 10),
            bd=0,
            relief="flat",
            activebackground=self.theme.c("bg_hover"),
            activeforeground=self.theme.c("fg"),
            command=self._open_settings,
            padx=4,
            pady=1,
        )
        self.btn_settings.pack(side="right", padx=(0, 4))

        # Store references for theme refresh
        self.footer_frame = footer_frame
        self.footer_label = self.footer_label  # Already set above

        # Resize handle (corner)
        self.resize_corner = tk.Label(
            self.root, text="◢", bg=self.theme.c("bg"), fg=self.theme.c("fg"),
            cursor="sizing", font=("Segoe UI", 10)
        )
        self.resize_corner.place(relx=1.0, rely=1.0, anchor="se")
        self.resize_corner.bind("<B1-Motion>", self._on_resize)

        # Always on top
        self.root.attributes("-topmost", True)
        # Alpha (default fully opaque)
        self.root.update_idletasks()
        self.root.attributes("-alpha", 1.0)

        # Visibility verification — ให้แน่ใจว่าหน้าต่างขึ้นมาจริง
        self.root.update_idletasks()
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.root.attributes("-topmost", True)

        # Re-apply topmost every 3 seconds (Windows bug)
        self._reapply_topmost()

        # v1.6.0: Register as theme change listener for real-time updates
        self.theme.register_theme_change_listener(self._on_theme_changed)

        # Load notes from database
        self._load_notes()

        # Start reminder checker (v1.3.0) — non-blocking, runs every 5 seconds
        self._check_reminders()

        # v2.8.6: Start notification queue checker — non-blocking, runs every 500ms
        self._check_notification_queue()

        # v2.9.3: Bind custom event for immediate notification processing (thread-safe wake-up)
        self.root.bind("<<NewNotification>>", lambda e: self._on_new_notification_event())

    def _get_safe_geometry(self, geometry: str) -> str:
        """ตรวจสอบ geometry — ถ้าไม่ปลอดภัยให้ center ที่จอ"""
        # Parse geometry string: "WxH+X+Y" or default
        if not geometry or "x" not in geometry.lower():
            # ไม่มี geometry → center ที่จอ
            screen_x, screen_y, screen_w, screen_h = _get_screen_bounds()
            w, h = 450, 550
            x = screen_x + (screen_w - w) // 2
            y = screen_y + (screen_h - h) // 2
            return f"{w}x{h}+{x}+{y}"

        # Parse WxH+X+Y
        try:
            parts = geometry.lower().split("+")
            wh = parts[0].split("x")
            w, h = int(wh[0]), int(wh[1])
            x = int(parts[1]) if len(parts) > 1 else 0
            y = int(parts[2]) if len(parts) > 2 else 0
        except (ValueError, IndexError):
            # Parse failed → center
            screen_x, screen_y, screen_w, screen_h = _get_screen_bounds()
            w, h = 450, 550
            x = screen_x + (screen_w - w) // 2
            y = screen_y + (screen_h - h) // 2
            return f"{w}x{h}+{x}+{y}"

        # Clamp x, y เข้าขอบเขต screen
        screen_x, screen_y, screen_w, screen_h = _get_screen_bounds()
        min_visible = 80  # ต้องเห็นแถบหัวอย่างน้อย 80px

        # ถ้า x,y อยู่นอกขอบเขตจอ ให้ center ใหม่
        if x + min_visible < screen_x or x >= screen_x + screen_w or \
           y + min_visible < screen_y or y >= screen_y + screen_h:
            x = screen_x + (screen_w - w) // 2
            y = screen_y + (screen_h - h) // 2

        return f"{w}x{h}+{x}+{y}"

    def _restore_geometry(self, geometry: str) -> None:
        """โหลด geometry ปลอดภัยลงหน้าต่าง"""
        self.root.geometry(geometry)

    def _center_main_window(self) -> None:
        """v1.8.6: Native window centering with withdraw protocol (prevents top-left glitch)"""
        try:
            # Hide window during positioning (withdraw protocol)
            self.root.withdraw()
            self.root.update_idletasks()

            # Get screen dimensions
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()

            # If we got valid screen dimensions (>100px), use calculated center
            if screen_w > 100 and screen_h > 100:
                win_w, win_h = 420, 600
                x = int((screen_w - win_w) / 2)
                y = int((screen_h - win_h) / 2)
                self.root.geometry(f"{win_w}x{win_h}+{x}+{y}")
            else:
                # Timing bug: winfo_screenwidth() returned 0
                # Fallback to native Tkinter centering engine
                try:
                    self.root.eval('tk::PlaceWindow . center')
                except Exception:
                    pass

            # Show window after positioning
            self.root.deiconify()
        except Exception:
            # Fallback: just show the window
            try:
                self.root.deiconify()
            except Exception:
                pass

    def _on_canvas_resize(self, event):
        """ปรับความกว้างของ inner frame ให้เท่า canvas"""
        self.canvas.itemconfig(self.canvas_window, width=event.width)
        # Update scroll region
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_mousewheel(self, event):
        """เลื่อนด้วย mouse wheel"""
        if event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(3, "units")
        elif event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-3, "units")

    def _on_resize(self, event):
        """ลากมุมล่างขวาเพื่อปรับขนาดหน้าต่าง"""
        w = max(260, self.root.winfo_pointerx() - self.root.winfo_x())
        h = max(180, self.root.winfo_pointery() - self.root.winfo_y())
        self.root.geometry(f"{w}x{h}")

    def _load_notes(self):
        """อ่านโน้ตตาม current_filter จาก DB แล้วแสดง"""
        # v2.3.0: Clear search when reloading notes (except from search event itself)
        if hasattr(self, 'search_var'):
            self.search_var.set("")

        # ลบการ์ดเก่าออกทั้งหมด
        for card in self.note_cards.values():
            card.pack_forget()
            card.destroy()
        self.note_cards.clear()

        # โหลดตาม filter
        notes_data = get_notes_by_status(self.current_filter)

        if not notes_data:
            # Show empty state (create if not exists)
            if not hasattr(self, '_empty_state_created') or not self._empty_state_created:
                self.empty_state_label = tk.Label(
                    self.inner_frame,
                    text="ยังไม่มีโน้ต\n\nกดปุ่ม + เพื่อเริ่มสร้างโน้ตแรก",
                    bg=self.theme.c("note_bg"),
                    fg=self.theme.c("fg_muted"),
                    font=("Segoe UI", 11),
                    justify="center",
                    pady=60,
                )
                self._empty_state_created = True
            self.empty_state_label.pack(fill="both", expand=True, pady=60)
        else:
            # Destroy empty state completely (no layout gap)
            if hasattr(self, 'empty_state_label'):
                try:
                    if self.empty_state_label.winfo_exists():
                        self.empty_state_label.destroy()
                except Exception:
                    pass
                self._empty_state_created = False

            # Load notes
            for row in notes_data:
                note = Note.from_dict(row)
                # v2.8.6: Default all notes to collapsed on startup
                note.collapsed = True
                # ✓ v1.3.8: Pass tab info so NoteCard can show different icons
                is_completed_tab = (self.current_filter == "completed")
                card = NoteCard(self.inner_frame, note, self.theme, is_completed_tab=is_completed_tab)
                card.on_update = lambda n=note: self._on_note_update(n)
                card.on_status_update = lambda n=note: self._on_note_status_update(n)  # v1.3.9: status-only
                card.on_pin_change = lambda: self._load_notes()  # v1.5.0: Re-sort on pin change
                card.on_delete_note = lambda n=note: self._on_note_delete(n)
                card.pack(fill="x", padx=4, pady=4)
                self.note_cards[note.id] = card

        # Update scroll region
        self.root.after(100, lambda: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

    def _on_filter_changed(self, new_filter: str):
        """เมื่อเปลี่ยน filter (Active ↔ Completed)"""
        self.current_filter = new_filter
        self._load_notes()  # This will clear search via _load_notes()

    def _on_search(self, event=None):
        """v2.3.0: Real-time search filter — show/hide notes based on keyword match"""
        keyword = self.search_var.get().lower().strip()

        # If search is empty, show all notes
        if not keyword:
            for card in self.note_cards.values():
                card.pack(fill="x", padx=4, pady=4)
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            return

        # Filter notes: match title or content
        for note_id, card in self.note_cards.items():
            note = card.note if hasattr(card, 'note') else None
            if note:
                title_match = keyword in note.title.lower()
                content_match = keyword in note.content.lower()
                if title_match or content_match:
                    card.pack(fill="x", padx=4, pady=4)
                else:
                    card.pack_forget()
            else:
                card.pack(fill="x", padx=4, pady=4)

        # Update scroll region
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _open_settings(self):
        """Settings button (⚙) clicked — open SettingsWindow (singleton pattern)"""
        try:
            # Singleton check: if Settings window already open, just lift it to front
            if self.settings_window_instance:
                try:
                    if self.settings_window_instance.root.winfo_exists():
                        print("[UI] Settings Window already open — lifting to front")
                        self.settings_window_instance.root.lift()
                        self.settings_window_instance.root.focus_force()
                        return
                except Exception:
                    self.settings_window_instance = None

            print("[UI] Opening Settings Window...")

            # Check if settings object exists
            if not self.settings:
                import tkinter.messagebox as msgbox
                msgbox.showerror("Settings Error", "Settings object not initialized")
                return

            # Pass settings object directly (not copy) so changes sync back
            # SettingsWindow needs reference to settings dict, not a copy
            settings_data = self.settings if isinstance(self.settings, dict) else (
                self.settings.data if hasattr(self.settings, 'data') else {}
            )

            # Create new SettingsWindow (only if not already open)
            # v1.5.2: Add on_window_closed callback to clear reference when window is closed
            self.settings_window_instance = SettingsWindow(
                self.root,
                settings_data,  # Pass reference, not copy
                self.theme,
                on_save_callback=self._on_settings_saved,
                main_root=self.root,  # Main QuickNote window for opacity/theme
                on_window_closed=self._on_settings_window_closed  # v1.5.2: garbage collection fix
            )
            print("[OK] Settings Window opened successfully")

        except Exception as e:
            print(f"[ERROR] Failed to open settings: {e}")
            import traceback
            traceback.print_exc()

            # Show error to user
            try:
                import tkinter.messagebox as msgbox
                msgbox.showerror("Settings Error", f"Cannot open settings window:\n{str(e)}")
            except Exception as err:
                print(f"[ERROR] Failed to show error dialog: {err}")

    def _on_note_update(self, note: Note):
        """v2.2.3: Save note updates including reminder fields"""
        # Save all note fields including reminder_datetime and reminder_triggered
        update_note(note.id, title=note.title, content=note.content,
                   status=note.status, collapsed=note.collapsed,
                   reminder_datetime=note.reminder_datetime,
                   reminder_triggered=note.reminder_triggered)

        # ถ้า status เปลี่ยนและไม่ตรงกับ filter ปัจจุบัน ให้ลบออก
        if note.status != self.current_filter:
            if note.id in self.note_cards:
                self.note_cards[note.id].pack_forget()
                self.note_cards[note.id].destroy()
                del self.note_cards[note.id]

        # Refresh scroll region (เนื่องจากการพับ/กางอาจเปลี่ยนขนาด)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_note_status_update(self, note: Note):
        """v1.3.9: อัปเดตสถานะเท่านั้น (ไม่แตะ title/content) — prevent corruption on status change"""
        # v1.4.0: Fetch fresh data from DB before saving to ensure content payload is complete
        fresh_note_data = get_note(note.id)
        if fresh_note_data:
            # Update note object with fresh database state
            note.title = fresh_note_data.get("title", note.title)
            note.content = fresh_note_data.get("content", note.content)
            note.collapsed = fresh_note_data.get("collapsed", note.collapsed)

        # Save status change only
        update_note_status_only(note.id, status=note.status)

        # ถ้า status เปลี่ยนและไม่ตรงกับ filter ปัจจุบัน ให้ลบออก
        if note.status != self.current_filter:
            if note.id in self.note_cards:
                self.note_cards[note.id].pack_forget()
                self.note_cards[note.id].destroy()
                del self.note_cards[note.id]

        # Refresh scroll region
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_note_delete(self, note: Note):
        """ลบโน้ต"""
        delete_note(note.id)
        if note.id in self.note_cards:
            self.note_cards[note.id].pack_forget()
            self.note_cards[note.id].destroy()
            del self.note_cards[note.id]
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_new(self):
        """ปุ่ม + เพิ่มโน้ตใหม่ — v2.3.1: Reload to respect sorting (newest notes first)"""
        note_id = create_note(title="New Note", content="")
        # v2.3.1: Reload all notes to respect sorting order (newest first)
        self._load_notes()
        # Focus on newly created note's title field (should be first in list)
        if note_id in self.note_cards:
            card = self.note_cards[note_id]
            card.title_entry.focus()
            card.title_entry.select_range(0, tk.END)

    def _on_minimize(self):
        """ปุ่มสีเหลือง — ถ้าไม่ได้ roll up ให้ withdraw ลง tray — ถ้า roll up แล้วให้ restore"""
        if self._rolled_up:
            self._on_roll_up()
        else:
            self.root.withdraw()

    def _on_roll_up(self):
        """Roll-up/restore — พับเหลือแถบหัวหรือกางกลับ"""
        if self._rolled_up:
            # Restore
            self.body_frame.pack(side="top", fill="both", expand=True)
            # Parse current geometry
            geom = self.root.geometry()
            # geom format: "WxH+X+Y"
            parts = geom.split("+")
            wh = parts[0].split("x")
            w = int(wh[0])
            x = int(parts[1]) if len(parts) > 1 else 100
            y = int(parts[2]) if len(parts) > 2 else 100
            self.root.geometry(f"{w}x{self._saved_height}+{x}+{y}")
            self._rolled_up = False
        else:
            # Roll-up (save height, hide body)
            self._saved_height = self.root.winfo_height()
            self.body_frame.pack_forget()
            # Minimize height to just titlebar
            geom = self.root.geometry()
            parts = geom.split("+")
            wh = parts[0].split("x")
            w = int(wh[0])
            x = int(parts[1]) if len(parts) > 1 else 100
            y = int(parts[2]) if len(parts) > 2 else 100
            self.root.geometry(f"{w}x32+{x}+{y}")
            self._rolled_up = True

    def _on_toggle_topmost(self, is_topmost: bool):
        """Toggle window always-on-top state — v1.5.1"""
        self.root.attributes("-topmost", is_topmost)

    def _on_settings_window_closed(self):
        """Settings window closed — v1.5.2: clear reference for garbage collection"""
        print("[UI] Settings window closed — clearing reference")
        self.settings_window_instance = None

    def _on_theme_changed(self, theme):
        """Handle real-time theme changes — v1.6.0: broadcast to all UI elements"""
        try:
            print(f"[Board] Theme changed to {theme.mode}, updating all UI...")
            self.theme = theme
            # Update main window colors
            self.root.config(bg=theme.c("bg"))
            # Update canvas
            self.canvas.config(bg=theme.c("note_bg"))
            # Update scrollbar
            self.scrollbar.config(troughcolor=theme.c("bg"))
            # Update footer
            self.footer_frame.config(bg=theme.c("bg"))
            self.footer_label.config(bg=theme.c("bg"), fg=theme.c("fg_muted"))
            self.btn_settings.config(bg=theme.c("bg"), fg=theme.c("fg"),
                                    activebackground=theme.c("bg_hover"))
            # Update titlebar
            self.titlebar.apply_theme(theme)
            # Update all note cards
            for card in self.note_cards.values():
                try:
                    card.apply_theme(theme)
                except Exception as e:
                    print(f"[Board] Failed to update card theme: {e}")
            print("[Board] All UI elements updated")
        except Exception as e:
            print(f"[Board] Failed to update theme: {e}")

    def _on_close(self):
        """ปุ่ม close — ปิดโปรแกรม"""
        # v1.8.2: Safety guard — release any modal grab before closing
        try:
            self.root.grab_release()
        except Exception:
            pass
        self.root.quit()

    def _reapply_topmost(self):
        """รี-apply -topmost ทุก 3 วินาที (Windows fix)"""
        try:
            self.root.attributes("-topmost", True)
        except Exception:
            pass
        self.root.after(3000, self._reapply_topmost)

    def _check_reminders(self):
        """v2.2.3: Unbreakable reminder scheduler with visual debug (next reminder display)
        v2.5.8: Check if scheduler is paused (dialog open) — if so, skip but reschedule anyway"""
        try:
            from datetime import datetime
            from src.core.database import get_next_due_reminder

            # v2.5.8: Skip checking reminders if scheduler is paused (dialog open)
            # Still reschedule to keep loop alive
            if not getattr(self, '_scheduler_enabled', True):
                # Scheduler is paused, just reschedule and return
                self.root.after(5000, self._check_reminders)
                return

            # Update heartbeat indicator with next due reminder (v2.2.3)
            # v2.6.2: Shorten date format to time-only to prevent footer clipping
            try:
                timestamp = datetime.now().strftime("%H:%M:%S")
                next_reminder = get_next_due_reminder()
                # Extract time-only part (HH:MM) from next_reminder if available
                if next_reminder:
                    # Format: "YYYY-MM-DD HH:MM" — extract just "HH:MM"
                    next_text = next_reminder.split()[-1] if " " in next_reminder else next_reminder
                else:
                    next_text = "None"
                self.heartbeat_label.config(
                    text=f"● Scheduler: {timestamp} | Next: {next_text}"
                )
            except Exception:
                pass  # Silently fail heartbeat update

            # Get all notes and check reminders
            try:
                all_notes = get_all_notes()
            except Exception:
                all_notes = []

            # Use string comparison for reliability (ISO format: YYYY-MM-DD HH:MM)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

            for note_data in all_notes:
                try:
                    # Skip if no reminder set
                    if not note_data.get("reminder_datetime"):
                        continue

                    # Skip if already triggered
                    if note_data.get("reminder_triggered"):
                        continue

                    # Get reminder time string (should be ISO format)
                    reminder_str = note_data.get("reminder_datetime", "")
                    if not reminder_str:
                        continue

                    # Safe string comparison: "2026-08-20 14:30" <= "2026-08-20 14:35"
                    # This avoids datetime parsing exceptions entirely
                    if reminder_str <= now_str:
                        # v2.6.0: Trigger reminder notification (non-blocking via after_idle)
                        # _trigger_reminder now handles DB update safely without blocking
                        try:
                            self._trigger_reminder(note_data)
                        except Exception:
                            pass  # Silently fail on notification error

                except Exception:
                    # Silently skip this note on any error
                    pass

        except Exception:
            # Catch-all for any unexpected exception
            pass

        finally:
            # v2.1.1: GUARANTEED to reschedule, unbreakable loop
            # This ensures scheduler never dies, even on catastrophic failure
            self.root.after(5000, self._check_reminders)

    def _trigger_reminder(self, note_data: dict):
        """v2.8.1: Windows native notification (no in-app GUI, zero freeze risk)
        Use OS native toast notifications to Action Center — non-blocking, no Tkinter involvement"""
        try:
            # Convert note_data dict to Note object
            from src.core.models import Note
            note_obj = Note.from_dict(note_data)

            # v2.8.0: SYNCHRONOUS DB UPDATE (must complete before notification)
            # Clear reminder_datetime (consume the reminder) and mark as triggered
            # This CRITICAL: prevents reminder from triggering multiple times
            try:
                update_note(note_data["id"], reminder_datetime=None, reminder_triggered=True)
                # Flush/sync the database to ensure write completes before next check cycle
                from src.core.database import get_db_connection
                conn = get_db_connection()
                conn.commit()
                conn.close()
            except Exception:
                pass  # Silently fail on DB update error

            # v2.8.1: Show Windows native notification (not Tkinter in-app toast)
            # This completely avoids GUI freeze by using OS notification system
            def show_native_notification():
                try:
                    from src.services.notification import get_notification_service
                    service = get_notification_service()

                    # Create callback for when user clicks notification
                    def on_notification_click():
                        try:
                            self._on_note_reminder_open(note_obj)
                        except Exception:
                            pass

                    # Show Windows native toast notification
                    service.show_reminder_notification(
                        note_title=note_obj.title[:50],
                        note_content=note_obj.content[:100] if note_obj.content else "Reminder triggered",
                        on_click=on_notification_click,
                        duration=8
                    )

                    # Also play notification sound
                    service.play_notification_sound()

                    # Refresh note cards to update UI state
                    try:
                        self._load_notes()
                    except Exception:
                        pass
                except Exception:
                    pass  # Silently fail to avoid blocking UI

            # Run notification in background to avoid any UI blocking
            import threading
            thread = threading.Thread(target=show_native_notification, daemon=True)
            thread.start()

        except Exception:
            pass  # Silently fail to avoid blocking UI

    def _show_toast_banner(self, note):
        """v2.8.1: DEPRECATED — Use Windows native notifications instead
        This method is kept for backwards compatibility but does nothing"""
        pass  # No-op: Native Windows notifications used instead

    def _hide_toast_banner(self):
        """v2.8.1: DEPRECATED — Use Windows native notifications instead
        This method is kept for backwards compatibility but does nothing"""
        pass  # No-op: Native Windows notifications used instead

    def _dismiss_and_open_note(self, note):
        """v2.8.1: DEPRECATED — Use Windows native notification click handler instead
        This method is kept for backwards compatibility but does nothing"""
        pass  # No-op: Native notification click handler used instead

    def _play_notification_alert(self):
        """v2.7.2: Play soft Ding-Dong audio alert (softer than notification, non-jarring)"""
        try:
            import winsound
            # Primary: Use MailBeep for soft Ding-Dong tone (friendly, not harsh)
            try:
                winsound.PlaySound("MailBeep", winsound.SND_ALIAS | winsound.SND_ASYNC)
            except Exception:
                # Fallback 1: System notification sound
                try:
                    winsound.PlaySound("SystemNotification", winsound.SND_ALIAS | winsound.SND_ASYNC)
                except Exception:
                    # Fallback 2: Generic beep
                    winsound.MessageBeep(winsound.MB_OK)
        except Exception:
            pass

    def _on_note_reminder_open(self, note):
        """v2.7.0: Callback when 'Open Note' clicked from reminder notification
        Opens note and clears reminder state (stops icon from showing reminder is set)"""
        try:
            # v2.7.0: Clear reminder state when opening from notification
            # This resets the reminder_datetime and reminder_triggered flags
            # So the clock icon shows as "not set" instead of "already triggered"
            try:
                update_note(note.id, reminder_datetime=None, reminder_triggered=False)
            except Exception:
                pass  # Silently fail if DB update doesn't work

            # Refresh the note card to show cleared reminder state
            try:
                self._load_notes()
            except Exception:
                pass

            # Scroll to note in the view
            self._show_note_in_view(note)
        except Exception:
            pass

    def _check_notification_queue(self):
        """v2.8.1: Check notification queue and display custom overlay toasts

        v2.8.1 Critical Fix:
        - Keep references to toasts to prevent GC from destroying Toplevel windows
        - Re-render board after notification to move triggered tasks to top
        """
        try:
            # Clean up closed toasts (those that were destroyed)
            self.active_toasts = [t for t in self.active_toasts if t.toast_window and t.toast_window.winfo_exists()]

            # Process all queued notifications (can be multiple)
            notification_queue = get_notification_queue()
            notifications_shown = False

            while not notification_queue.is_empty():
                msg = notification_queue.get_next_notification()
                if msg:
                    try:
                        # Create custom overlay notification
                        def on_open_callback():
                            # Clear reminder from DB
                            try:
                                update_note(msg.note_id, clear_reminder=True)
                            except Exception:
                                pass
                            # Bring main window to front and highlight the note
                            self._on_open_note_from_notification(msg.note_id)

                        # v2.9.0: Create toast with snooze support and keep reference (prevent GC)
                        toast = CustomToastNotification(
                            self.root,
                            title=msg.title,
                            message=msg.content,
                            on_open=on_open_callback,
                            on_dismiss=None,
                            note_id=msg.note_id,  # v2.9.0: Enable snooze feature
                            board=self  # v2.9.0: Allow re-render after snooze
                        )
                        self.active_toasts.append(toast)  # v2.8.1: Keep reference
                        notifications_shown = True
                    except Exception:
                        pass  # Silently fail to avoid blocking UI

            # v2.8.1: Re-render board to move triggered tasks to top (dynamic sorting)
            if notifications_shown:
                try:
                    self._load_notes()
                except Exception:
                    pass

        except Exception:
            pass  # Silently fail

        finally:
            # Reschedule to check queue again in 500ms
            self.root.after(500, self._check_notification_queue)

    def _on_new_notification_event(self):
        """v2.9.3: Event-based handler for immediate notification processing (thread-safe)"""
        try:
            # Force main window to foreground
            self._force_main_window_foreground()
            # Process queue immediately
            self._check_notification_queue()
        except Exception:
            pass

    def _force_main_window_foreground(self):
        """v2.9.3: Bring main window to foreground when notification arrives"""
        try:
            if self.root.winfo_exists():
                self.root.deiconify()
                self.root.state('normal')
                self.root.attributes('-topmost', True)
                self.root.lift()
                self.root.focus_force()
                # Release topmost after 1 second (allow user to use other apps)
                self.root.after(1000, lambda: self.root.attributes('-topmost', False) if self.root.winfo_exists() else None)
        except Exception:
            pass

    def _on_open_note_from_notification(self, note_id: str):
        """Open note when user clicks [Open] on custom notification"""
        try:
            # Reload notes to update UI
            self._load_notes()
            # Find and highlight the note card
            if note_id in self.note_cards:
                self.note_cards[note_id]._show_content()
        except Exception:
            pass

    def _on_settings_saved(self):
        """Called when settings are saved — refresh UI (theme/alpha changes)"""
        try:
            if self.settings:
                # Get settings dict (handle both dict and Settings object)
                settings_dict = self.settings if isinstance(self.settings, dict) else (
                    self.settings.data if hasattr(self.settings, 'data') else {}
                )

                # Handle opacity change
                new_alpha = settings_dict.get("alpha", 1.0)
                try:
                    new_alpha = float(new_alpha)
                    new_alpha = max(0.2, min(1.0, new_alpha))
                    self.root.attributes("-alpha", new_alpha)
                    self.root.update_idletasks()
                    print(f"[UI] Applied opacity: {new_alpha:.0%}")
                except Exception as e:
                    print(f"[WARN] Failed to apply opacity: {e}")

                # Handle theme change — always refresh to ensure colors sync
                new_theme_mode = settings_dict.get("theme", "light")
                print(f"[UI] Setting theme to {new_theme_mode}...")
                self.theme.set_mode(new_theme_mode)
                self._refresh_ui_colors()
                print("[OK] UI colors refreshed")

        except Exception as e:
            print(f"[WARN] Failed to refresh UI: {e}")

    def _refresh_ui_colors(self):
        """Refresh all UI widget colors based on current theme"""
        try:
            # Refresh main window background
            self.root.config(bg=self.theme.c("bg"))
            self.body_frame.config(bg=self.theme.c("bg"))
            self.canvas.config(bg=self.theme.c("note_bg"), highlightthickness=0)
            self.inner_frame.config(bg=self.theme.c("note_bg"))
            self.scrollbar.config(bg=self.theme.c("bg"), troughcolor=self.theme.c("bg"))
            self.empty_state_label.config(
                bg=self.theme.c("note_bg"),
                fg=self.theme.c("fg_muted"),
                font=("Segoe UI", 11)
            )

            # Refresh titlebar colors
            if hasattr(self, 'titlebar') and self.titlebar:
                self.titlebar.root.config(bg=self.theme.c("bg"))
                # Refresh titlebar filter buttons
                try:
                    for btn in [self.titlebar.btn_active, self.titlebar.btn_completed]:
                        if btn:
                            btn.config(bg=self.theme.c("bg"), fg=self.theme.c("fg"))
                except Exception:
                    pass

            # Refresh footer colors
            if hasattr(self, 'footer_frame') and self.footer_frame:
                self.footer_frame.config(bg=self.theme.c("bg"))
                if hasattr(self, 'footer_label'):
                    self.footer_label.config(bg=self.theme.c("bg"), fg=self.theme.c("fg_muted"))
                if hasattr(self, 'btn_settings'):
                    self.btn_settings.config(bg=self.theme.c("bg"), fg=self.theme.c("fg"),
                                           activebackground=self.theme.c("bg_hover"))

            # Refresh ALL note cards — this is critical for theme change!
            print(f"[UI] Updating {len(self.note_cards)} note cards...")
            for card_id, card in self.note_cards.items():
                try:
                    # Update card widget colors
                    card.config(bg=self.theme.c("bg"))
                    # Update card internal structure (if has update_theme method)
                    if hasattr(card, 'update_theme'):
                        card.update_theme(self.theme)
                    # Fallback: manually update key card elements
                    else:
                        # Update main frame
                        if hasattr(card, 'main_frame'):
                            card.main_frame.config(bg=self.theme.c("note_bg"))
                        # Update header elements
                        if hasattr(card, 'title_entry'):
                            card.title_entry.config(bg=self.theme.c("note_bg"), fg=self.theme.c("fg"))
                        if hasattr(card, 'content_text'):
                            card.content_text.config(bg=self.theme.c("note_bg"), fg=self.theme.c("fg"))
                except Exception as card_err:
                    print(f"[WARN] Failed to update card {card_id}: {card_err}")

            # Force UI redraw with new colors
            self.root.update_idletasks()
            self.root.update()
            print("[OK] All UI colors refreshed successfully")

        except Exception as e:
            print(f"[ERROR] Failed to refresh colors: {e}")
            import traceback
            traceback.print_exc()

    def add_note_card(self, widget: tk.Widget) -> None:
        """เพิ่ม note card ลงใน inner frame (legacy method)"""
        widget.pack(fill="x", padx=4, pady=4)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def mainloop(self):
        """รัน event loop"""
        self.root.mainloop()

    def destroy(self):
        """ปิดหน้าต่าง"""
        self.root.quit()
