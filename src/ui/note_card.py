"""NoteCard widget — macOS Pastel style card ด้วย rounded corners + color bar"""

import tkinter as tk
from .theme import Theme, FONT_UI, PASTEL_PALETTE
from ..core.models import Note


class NoteCard(tk.Frame):
    """การ์ดโน้ตแบบ macOS Pastel — color bar + rounded style + strikethrough"""

    def __init__(self, master, note: Note, theme: Theme, **kwargs):
        super().__init__(master, **kwargs)
        self.note = note
        self.theme = theme

        # สีพาสเทลแบบสุ่ม (หรือตั้งเอง)
        color_list = list(PASTEL_PALETTE.values())
        self.color_idx = hash(note.id) % len(color_list)
        self.card_color = color_list[self.color_idx]

        # Card frame (white background สำหรับ light mode)
        self.config(
            bg=theme.c("note_bg"),
            highlightthickness=0,
            relief="flat",
            padx=0,
            pady=0,
        )

        # Left color bar (thin pastel stripe)
        color_bar = tk.Frame(self, bg=self.card_color, width=4)
        color_bar.pack(side="left", fill="y", padx=0, pady=0)
        color_bar.pack_propagate(False)

        # Main content frame
        main_frame = tk.Frame(self, bg=theme.c("note_bg"))
        main_frame.pack(side="left", fill="both", expand=True)

        # === Header ===
        header = tk.Frame(main_frame, bg=theme.c("note_bg"))
        header.pack(fill="x", padx=8, pady=4)

        # Fold button
        fold_text = "▾" if not note.collapsed else "▸"
        self.btn_fold = tk.Button(
            header,
            text=fold_text,
            width=2,
            height=1,
            bd=0,
            bg=theme.c("note_bg"),
            fg=theme.c("fg"),
            activebackground=theme.c("bg_hover"),
            font=FONT_UI,
            command=self._on_toggle_fold,
        )
        self.btn_fold.pack(side="left", padx=2)

        # Title (with strikethrough effect when completed)
        self.title_var = tk.StringVar(value=note.title)
        self.title_entry = tk.Entry(
            header,
            textvariable=self.title_var,
            bg=theme.c("note_bg"),
            fg=theme.c("fg"),
            font=("Segoe UI", 10, "bold"),
            bd=0,
            relief="flat",
        )
        self.title_entry.pack(side="left", padx=4, fill="x", expand=True)
        self.title_entry.bind("<FocusOut>", self._on_title_change)

        # Status button (○ = active, ✓ = completed)
        status_text = "✓" if note.status == "completed" else "○"
        self.btn_status = tk.Button(
            header,
            text=status_text,
            width=2,
            height=1,
            bd=0,
            bg=theme.c("note_bg"),
            fg=theme.c("fg"),
            activebackground=theme.c("bg_hover"),
            font=FONT_UI,
            command=self._on_toggle_status,
        )
        self.btn_status.pack(side="right", padx=2)

        # Delete button
        self.btn_delete = tk.Button(
            header,
            text="✕",
            width=2,
            height=1,
            bd=0,
            bg=theme.c("note_bg"),
            fg=theme.c("fg"),
            activebackground=theme.c("bg_hover"),
            font=FONT_UI,
            command=self._on_delete,
        )
        self.btn_delete.pack(side="right", padx=2)

        # === Content area ===
        self.content_frame = None
        self.content_text = None
        if not note.collapsed:
            self._show_content()

        # Apply strikethrough if completed
        self._update_strikethrough()

        # Callbacks
        self.on_update = lambda: None
        self.on_delete_note = lambda: None

    def _show_content(self):
        """แสดง content area"""
        if self.content_frame is not None:
            return

        self.content_frame = tk.Frame(self, bg=self.theme.c("note_bg"))
        self.content_frame.pack(fill="both", expand=True, padx=8, pady=4)

        self.content_text = tk.Text(
            self.content_frame,
            height=4,
            width=40,
            bg=self.theme.c("bg"),
            fg=self.theme.c("fg"),
            font=("Consolas", 9),
            wrap="word",
            relief="flat",
            bd=0,
        )
        self.content_text.insert("1.0", self.note.content)
        self.content_text.pack(fill="both", expand=True)
        self.content_text.bind("<FocusOut>", self._on_content_change)

    def _hide_content(self):
        """ซ่อน content area"""
        if self.content_frame is not None:
            self.content_frame.destroy()
            self.content_frame = None
            self.content_text = None

    def _update_strikethrough(self):
        """ใส่/เอา strikethrough ตามสถานะ"""
        if self.note.status == "completed":
            # Add strikethrough
            self.title_entry.config(font=("Segoe UI", 10, "bold overstrike"))
        else:
            # Remove strikethrough
            self.title_entry.config(font=("Segoe UI", 10, "bold"))

    def _on_toggle_fold(self):
        """ปุ่มพับ/กาง"""
        self.note.toggle_collapse()

        if self.note.collapsed:
            self._hide_content()
            self.btn_fold.config(text="▸")
        else:
            self._show_content()
            self.btn_fold.config(text="▾")

        self.on_update()

    def _on_toggle_status(self):
        """ปุ่ม status (○ ↔ ✓) — อัปเดต note object แล้วเรียก callback"""
        if self.note.status == "active":
            self.note.mark_done()
            self.btn_status.config(text="✓")
        else:
            self.note.mark_active()
            self.btn_status.config(text="○")

        self._update_strikethrough()
        self.on_update()

    def _on_title_change(self, event):
        """เมื่อเปลี่ยน title จากช่อง Entry"""
        new_title = self.title_var.get().strip()
        if new_title:
            self.note.title = new_title
            self.on_update()

    def _on_content_change(self, event):
        """เมื่อเปลี่ยน content จากช่อง Text"""
        new_content = self.content_text.get("1.0", "end-1c")
        self.note.content = new_content
        self.on_update()

    def _on_delete(self):
        """ปุ่ม delete"""
        self.on_delete_note()

    def apply_theme(self, theme: Theme):
        """เปลี่ยนธีมตอนโปรแกรมทำงาน"""
        self.theme = theme
        self.config(bg=theme.c("note_bg"))

        for btn in [self.btn_fold, self.btn_status, self.btn_delete]:
            btn.config(bg=theme.c("note_bg"), fg=theme.c("fg"),
                      activebackground=theme.c("bg_hover"))

        self.title_entry.config(bg=theme.c("note_bg"), fg=theme.c("fg"))

        if self.content_text:
            self.content_text.config(bg=theme.c("bg"), fg=theme.c("fg"))
