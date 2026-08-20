"""Main Board window — Tk + overrideredirect + scrollable canvas"""

import tkinter as tk
import ctypes
from .theme import Theme
from .titlebar import TitleBar
from .note_card import NoteCard
from ..core.models import Note
from ..core.constants import APP_NAME, APP_VERSION, APP_AUTHOR
from ..core.database import get_all_notes, get_notes_by_status, create_note, delete_note, update_note


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

    def __init__(self, geometry: str = "", theme_mode: str = "light"):
        self.theme = Theme(theme_mode)
        self._resize_start_x = 0
        self._resize_start_y = 0
        self.note_cards = {}  # id → NoteCard widget
        self.current_filter = "active"  # 'active' or 'completed'

        # Create window
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.config(bg=self.theme.c("bg"))

        # Set geometry (clamp to screen if needed)
        safe_geometry = self._get_safe_geometry(geometry)
        self._restore_geometry(safe_geometry)

        # DPI awareness (อาจจะตั้งไปแล้วใน main.py แต่ทำอีกที่เพื่อให้ปลอดภัย)
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        # TitleBar
        self.titlebar = TitleBar(self.root, self.root, self.theme)
        self.titlebar.on_new = self._on_new
        self.titlebar.on_close = self._on_close
        self.titlebar.on_minimize = self._on_minimize
        self.titlebar.on_roll_up = self._on_roll_up
        self.titlebar.on_filter_changed = self._on_filter_changed

        # Roll-up state
        self._rolled_up = False
        self._saved_height = 600

        # Body — scrollable area
        self.body_frame = tk.Frame(self.root, bg=self.theme.c("bg"))
        self.body_frame.pack(side="top", fill="both", expand=True)

        # Canvas + scrollbar pattern
        self.canvas = tk.Canvas(
            self.body_frame,
            bg=self.theme.c("note_bg"),
            highlightthickness=0,
            height=300,
        )
        self.canvas.pack(side="left", fill="both", expand=True)

        self.scrollbar = tk.Scrollbar(self.body_frame, command=self.canvas.yview)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.config(yscrollcommand=self.scrollbar.set)

        # Inner frame inside canvas
        self.inner_frame = tk.Frame(self.canvas, bg=self.theme.c("note_bg"))
        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.inner_frame, anchor="nw"
        )

        # Bind canvas resize to update inner frame width
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        # Mouse wheel scroll
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", self._on_mousewheel)   # Linux wheel up
        self.canvas.bind("<Button-5>", self._on_mousewheel)   # Linux wheel down

        # Focus on click
        self.root.bind("<Button-1>", lambda e: self.root.focus_force(), add="+")

        # Footer — credit line
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

        # Load notes from database
        self._load_notes()

    def _get_safe_geometry(self, geometry: str) -> str:
        """ตรวจสอบ geometry — ถ้าไม่ปลอดภัยให้ center ที่จอ"""
        # Parse geometry string: "WxH+X+Y" or default
        if not geometry or "x" not in geometry.lower():
            # ไม่มี geometry → center ที่จอ
            screen_x, screen_y, screen_w, screen_h = _get_screen_bounds()
            w, h = 400, 600
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
            w, h = 400, 600
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
        # ลบการ์ดเก่าออกทั้งหมด
        for card in self.note_cards.values():
            card.pack_forget()
            card.destroy()
        self.note_cards.clear()

        # โหลดตาม filter
        notes_data = get_notes_by_status(self.current_filter)
        for row in notes_data:
            note = Note.from_dict(row)
            card = NoteCard(self.inner_frame, note, self.theme)
            card.on_update = lambda n=note: self._on_note_update(n)
            card.on_delete_note = lambda n=note: self._on_note_delete(n)
            card.pack(fill="x", padx=4, pady=4)
            self.note_cards[note.id] = card

        # Update scroll region
        self.root.after(100, lambda: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

    def _on_filter_changed(self, new_filter: str):
        """เมื่อเปลี่ยน filter (Active ↔ Completed)"""
        self.current_filter = new_filter
        self._load_notes()

    def _on_note_update(self, note: Note):
        """เมื่อมีการแก้ไขโน้ต — เซฟ DB + refresh UI"""
        update_note(note.id, title=note.title, content=note.content,
                   status=note.status, collapsed=note.collapsed)

        # ถ้า status เปลี่ยนและไม่ตรงกับ filter ปัจจุบัน ให้ลบออก
        if note.status != self.current_filter:
            if note.id in self.note_cards:
                self.note_cards[note.id].pack_forget()
                self.note_cards[note.id].destroy()
                del self.note_cards[note.id]

        # Refresh scroll region (เนื่องจากการพับ/กางอาจเปลี่ยนขนาด)
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
        """ปุ่ม + เพิ่มโน้ตใหม่"""
        note_id = create_note(title="New Note", content="")
        note = Note.from_dict({
            "id": note_id,
            "title": "New Note",
            "content": "",
            "status": "active",
            "collapsed": False,
        })
        card = NoteCard(self.inner_frame, note, self.theme)
        card.on_update = lambda n=note: self._on_note_update(n)
        card.on_delete_note = lambda n=note: self._on_note_delete(n)
        card.pack(fill="x", padx=4, pady=4)
        self.note_cards[note.id] = card
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        # Focus on title field
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

    def _on_close(self):
        """ปุ่ม close — ปิดโปรแกรม"""
        self.root.quit()

    def _reapply_topmost(self):
        """รี-apply -topmost ทุก 3 วินาที (Windows fix)"""
        try:
            self.root.attributes("-topmost", True)
        except Exception:
            pass
        self.root.after(3000, self._reapply_topmost)

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
