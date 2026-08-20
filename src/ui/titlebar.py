"""Custom TitleBar สไตล์ macOS — traffic light buttons + drag support"""

import tkinter as tk
from .theme import Theme, FONT_UI, CONTROL_RED, CONTROL_YELLOW, CONTROL_GREEN


class TitleBar(tk.Frame):
    """แถบหัวแบบ macOS — ปุ่มสีพาสเทล traffic light + ลาก/roll-up"""

    def __init__(self, master, root: tk.Tk, theme: Theme, **kwargs):
        super().__init__(master, **kwargs)
        self.root = root
        self.theme = theme

        # Drag state
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._last_click_time = 0

        # Configure appearance
        # v1.8.7: Increased titlebar height from 32 to 42 for proper descender space (Completed text)
        self.config(bg=theme.c("bg"), height=42, cursor="hand2")
        self.pack(side="top", fill="x")
        self.pack_propagate(False)

        # Traffic Light buttons (left side)
        # v1.6.1: Add highlightthickness=0 to prevent border bleeds
        button_frame = tk.Frame(self, bg=theme.c("bg"), highlightthickness=0)
        button_frame.pack(side="left", padx=12, pady=8)

        # Red button (Close/Hide to Tray)
        self.btn_close = tk.Button(
            button_frame,
            text="✕",
            fg=CONTROL_RED,
            bg=theme.c("bg"),
            font=("Segoe UI", 12, "bold"),
            bd=0,
            relief="flat",
            activebackground=theme.c("bg_hover"),
            activeforeground=CONTROL_RED,
            command=self._on_close,
            padx=2,
            pady=0,
        )
        self.btn_close.pack(side="left", padx=4)

        # Yellow button (Minimize)
        self.btn_minimize = tk.Button(
            button_frame,
            text="−",
            fg=CONTROL_YELLOW,
            bg=theme.c("bg"),
            font=("Segoe UI", 14, "bold"),
            bd=0,
            relief="flat",
            activebackground=theme.c("bg_hover"),
            activeforeground=CONTROL_YELLOW,
            command=self._on_minimize,
            padx=2,
            pady=0,
        )
        self.btn_minimize.pack(side="left", padx=4)

        # Green button (New Note)
        self.btn_new = tk.Button(
            button_frame,
            text="+",
            fg=CONTROL_GREEN,
            bg=theme.c("bg"),
            font=("Segoe UI", 14, "bold"),
            bd=0,
            relief="flat",
            activebackground=theme.c("bg_hover"),
            activeforeground=CONTROL_GREEN,
            command=self._on_new,
            padx=2,
            pady=0,
        )
        self.btn_new.pack(side="left", padx=4)

        # Center — title (clickable for roll-up)
        self.title_label = tk.Label(
            self,
            text="QuickNote",
            bg=theme.c("bg"),
            fg=theme.c("fg"),
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",  # v1.7.1: Draggable cursor (will change to "arrow" if pinned)
        )
        self.title_label.pack(side="left", expand=True)
        self.title_label.bind("<Double-Button-1>", self._on_title_dblclick)
        self.title_label.bind("<Button-1>", self._start_drag)
        self.title_label.bind("<B1-Motion>", self._on_drag)

        # Window pin button (always-on-top toggle) — v1.5.1
        self.is_topmost = True  # Track topmost state
        self.btn_window_pin = tk.Button(
            self,
            text="📌",
            bg=theme.c("bg"),
            fg=theme.c("fg"),
            font=("Segoe UI Symbol", 10),
            bd=0,
            relief="flat",
            activebackground=theme.c("bg_hover"),
            activeforeground=theme.c("accent"),
            command=self._on_toggle_topmost,
            padx=4,
            pady=0,
        )
        self.btn_window_pin.pack(side="right", padx=4)

        # Filter toggle (Active / Completed) — Segmented Pill Container
        # Outer frame for pill container (pastel gray background)
        # v1.6.1: Add bd=0 to prevent border bleeds
        filter_container = tk.Frame(
            self,
            bg="#E8E9EC",  # Soft pastel gray
            highlightthickness=0,
            bd=0,  # v1.6.1: Remove border
        )
        filter_container.pack(side="right", padx=12, pady=6)

        # Inner frame for buttons (with border radius simulation)
        # v1.6.1: Add bd=0 to prevent border bleeds
        inner_filter = tk.Frame(filter_container, bg="#E8E9EC", bd=0, highlightthickness=0)
        inner_filter.pack(padx=2, pady=2, fill="both", expand=True)

        self.btn_active = tk.Button(
            inner_filter,
            text="Active",
            bg="#E8E9EC",
            fg=theme.c("fg"),
            font=("Segoe UI", 9),
            bd=0,
            relief="flat",
            activebackground="#E8E9EC",
            activeforeground=theme.c("fg"),
            command=self._on_filter_active,
            padx=8,
            pady=4,
        )
        self.btn_active.pack(side="left", padx=2, pady=3)

        self.btn_completed = tk.Button(
            inner_filter,
            text="Completed",
            bg="#E8E9EC",
            fg=theme.c("fg"),
            font=("Segoe UI", 9),
            bd=0,
            relief="flat",
            activebackground="#E8E9EC",
            activeforeground=theme.c("fg"),
            command=self._on_filter_completed,
            padx=8,
            pady=4,
        )
        self.btn_completed.pack(side="left", padx=2, pady=3)

        self.filter_container = filter_container
        self.inner_filter = inner_filter

        self.current_filter = "active"

        # Initialize filter button styles
        self._update_filter_buttons()

        # Enable dragging on titlebar
        self.bind("<Button-1>", self._start_drag)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._end_drag)

        # Callback funcs
        self.on_new = lambda: None
        self.on_minimize = lambda: None
        self.on_close = lambda: None
        self.on_roll_up = lambda: None
        self.on_toggle_topmost = lambda is_topmost: None  # v1.5.1: window pin toggle
        self.on_filter_changed = lambda status: None

    def _start_drag(self, event):
        """เก็บตำแหน่ง pointer เพื่อลากหน้าต่าง"""
        self._drag_start_x = self.root.winfo_pointerx() - self.root.winfo_x()
        self._drag_start_y = self.root.winfo_pointery() - self.root.winfo_y()

    def _on_drag(self, event):
        """ลากหน้าต่าง — v1.7.1: Lock position if window is pinned (topmost)"""
        # v1.7.1: If window is pinned, prevent dragging by skipping geometry update
        if self.is_topmost:
            return  # Window is pinned, don't allow dragging

        x = self.root.winfo_pointerx() - self._drag_start_x
        y = self.root.winfo_pointery() - self._drag_start_y
        self.root.geometry(f"+{x}+{y}")

    def _end_drag(self, event):
        """บันทึก geometry หลังลากจบ"""
        pass

    def _on_title_dblclick(self, event):
        """Double-click titlebar → roll-up/restore"""
        self.on_roll_up()

    def _on_new(self):
        """ปุ่มสีเขียว (New Note)"""
        self.on_new()

    def _on_minimize(self):
        """ปุ่มสีเหลือง (Minimize/Roll-up)"""
        self.on_minimize()

    def _on_close(self):
        """ปุ่มสีแดง (Close)"""
        self.on_close()

    def _on_toggle_topmost(self):
        """Toggle window always-on-top state — v1.5.1, v1.7.1: Update cursor feedback"""
        self.is_topmost = not self.is_topmost
        self.btn_window_pin.config(text="📌" if self.is_topmost else "📍")
        # v1.7.1: Update cursor to indicate pin state (locked vs draggable)
        cursor = "arrow" if self.is_topmost else "hand2"
        self.title_label.config(cursor=cursor)
        self.config(cursor=cursor)
        self.on_toggle_topmost(self.is_topmost)

    def _on_filter_active(self):
        """คลิก Active tab"""
        if self.current_filter != "active":
            self.current_filter = "active"
            self._update_filter_buttons()
            self.on_filter_changed("active")

    def _on_filter_completed(self):
        """คลิก Completed tab"""
        if self.current_filter != "completed":
            self.current_filter = "completed"
            self._update_filter_buttons()
            self.on_filter_changed("completed")

    def _update_filter_buttons(self):
        """อัปเดตสไตล์ปุ่ม filter ตามสถานะปัจจุบัน — Pill Style"""
        if self.current_filter == "active":
            # Active button: white/light highlight
            self.btn_active.config(
                bg="#FFFFFF",
                fg=self.theme.c("accent"),
                font=("Segoe UI", 9, "bold"),
            )
            self.btn_completed.config(
                bg="#E8E9EC",
                fg=self.theme.c("fg"),
                font=("Segoe UI", 9),
            )
        else:
            # Completed button: white/light highlight
            self.btn_active.config(
                bg="#E8E9EC",
                fg=self.theme.c("fg"),
                font=("Segoe UI", 9),
            )
            self.btn_completed.config(
                bg="#FFFFFF",
                fg=self.theme.c("accent"),
                font=("Segoe UI", 9, "bold"),
            )

    def apply_theme(self, theme: Theme) -> None:
        """เปลี่ยนธีมระหว่างโปรแกรมทำงาน"""
        self.theme = theme
        self.config(bg=theme.c("bg"))
        self.title_label.config(bg=theme.c("bg"), fg=theme.c("fg"))

        for btn in [self.btn_new, self.btn_minimize, self.btn_close]:
            btn.config(bg=theme.c("bg"), activebackground=theme.c("bg_hover"))
