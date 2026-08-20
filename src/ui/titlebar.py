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
        self.config(bg=theme.c("bg"), height=32)
        self.pack(side="top", fill="x")
        self.pack_propagate(False)

        # Traffic Light buttons (left side)
        button_frame = tk.Frame(self, bg=theme.c("bg"))
        button_frame.pack(side="left", padx=12, pady=6)

        # Red button (Close)
        self.btn_close = tk.Button(
            button_frame,
            text="●",
            fg=CONTROL_RED,
            bg=theme.c("bg"),
            font=("Segoe UI", 12),
            bd=0,
            relief="flat",
            activebackground=theme.c("bg_hover"),
            command=self._on_close,
        )
        self.btn_close.pack(side="left", padx=4)

        # Yellow button (Roll-up)
        self.btn_minimize = tk.Button(
            button_frame,
            text="●",
            fg=CONTROL_YELLOW,
            bg=theme.c("bg"),
            font=("Segoe UI", 12),
            bd=0,
            relief="flat",
            activebackground=theme.c("bg_hover"),
            command=self._on_minimize,
        )
        self.btn_minimize.pack(side="left", padx=4)

        # Green button (New Note)
        self.btn_new = tk.Button(
            button_frame,
            text="●",
            fg=CONTROL_GREEN,
            bg=theme.c("bg"),
            font=("Segoe UI", 12),
            bd=0,
            relief="flat",
            activebackground=theme.c("bg_hover"),
            command=self._on_new,
        )
        self.btn_new.pack(side="left", padx=4)

        # Center — title (clickable for roll-up)
        self.title_label = tk.Label(
            self,
            text="QuickNote",
            bg=theme.c("bg"),
            fg=theme.c("fg"),
            font=("Segoe UI", 10, "bold"),
        )
        self.title_label.pack(side="left", expand=True)
        self.title_label.bind("<Double-Button-1>", self._on_title_dblclick)
        self.title_label.bind("<Button-1>", self._start_drag)
        self.title_label.bind("<B1-Motion>", self._on_drag)

        # Filter toggle (Active / Completed) — right side
        filter_frame = tk.Frame(self, bg=theme.c("bg"))
        filter_frame.pack(side="right", padx=12)

        self.btn_active = tk.Button(
            filter_frame,
            text="Active",
            bg=theme.c("bg"),
            fg=theme.c("fg"),
            font=("Segoe UI", 9),
            bd=1,
            relief="solid",
            activebackground=theme.c("bg_hover"),
            command=self._on_filter_active,
        )
        self.btn_active.pack(side="left", padx=2, pady=2)

        self.btn_completed = tk.Button(
            filter_frame,
            text="Completed",
            bg=theme.c("bg_hover"),
            fg=theme.c("fg"),
            font=("Segoe UI", 9),
            bd=1,
            relief="solid",
            activebackground=theme.c("bg_hover"),
            command=self._on_filter_completed,
        )
        self.btn_completed.pack(side="left", padx=2, pady=2)

        self.current_filter = "active"

        # Enable dragging on titlebar
        self.bind("<Button-1>", self._start_drag)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._end_drag)

        # Callback funcs
        self.on_new = lambda: None
        self.on_minimize = lambda: None
        self.on_close = lambda: None
        self.on_roll_up = lambda: None
        self.on_filter_changed = lambda status: None

    def _start_drag(self, event):
        """เก็บตำแหน่ง pointer เพื่อลากหน้าต่าง"""
        self._drag_start_x = self.root.winfo_pointerx() - self.root.winfo_x()
        self._drag_start_y = self.root.winfo_pointery() - self.root.winfo_y()

    def _on_drag(self, event):
        """ลากหน้าต่าง"""
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
        """อัปเดตสไตล์ปุ่ม filter ตามสถานะปัจจุบัน"""
        if self.current_filter == "active":
            self.btn_active.config(relief="solid", bd=2)
            self.btn_completed.config(relief="solid", bd=1)
        else:
            self.btn_active.config(relief="solid", bd=1)
            self.btn_completed.config(relief="solid", bd=2)

    def apply_theme(self, theme: Theme) -> None:
        """เปลี่ยนธีมระหว่างโปรแกรมทำงาน"""
        self.theme = theme
        self.config(bg=theme.c("bg"))
        self.title_label.config(bg=theme.c("bg"), fg=theme.c("fg"))

        for btn in [self.btn_new, self.btn_minimize, self.btn_close]:
            btn.config(bg=theme.c("bg"), activebackground=theme.c("bg_hover"))
