"""Demo ของ UI foundation (theme/icons/widgets) — เปิดหน้าต่างโชว์ทุกอย่าง สว่าง→มืด แล้วแคปภาพออกมาตรวจ

รัน:  python tools/demo_foundation.py [โฟลเดอร์เก็บภาพ]
ภาพ: foundation_light.png / foundation_dark.png
"""

from __future__ import annotations

import ctypes
import os
import sys
import time
import tkinter as tk
from ctypes import wintypes
from tkinter import ttk

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src.ui import strings, win11  # noqa: E402
from src.ui.icons import ICONS  # noqa: E402
from src.ui.theme import NOTE_COLORS, Theme  # noqa: E402
from src.ui.widgets import IconButton, PlaceholderEntry, RoundedFrame, SettingsCard, UndoBar, px  # noqa: E402

DEFAULT_OUT = r"C:\Users\PASSAG~1\AppData\Local\Temp\claude\D--AI-OpenCode-Noted-Planing-and-Record\5942156e-1758-4add-8e22-4048da503076\scratchpad"


class FakeSettings:
    """settings จำลองให้ demo/test ไม่ต้องพึ่ง src/core/settings.py (เขียนใหม่โดยอีก agent)"""

    def __init__(self, **kw) -> None:
        self.data = {"theme": "light", "font_size": "normal", **kw}
        self._subs = []

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value, save: bool = True) -> None:
        if self.data.get(key) != value:
            self.data[key] = value
            for cb in list(self._subs):
                cb(key, value)

    def subscribe(self, cb) -> None:
        self._subs.append(cb)


def frame_rect(root: tk.Tk) -> tuple[int, int, int, int]:
    """กรอบจริงของหน้าต่าง (รวม titlebar, ไม่รวมเงา) จาก DWM — ใช้เป็น bbox แคปภาพ"""
    hwnd = win11._frame_hwnd(root)
    rc = wintypes.RECT()
    dwm = ctypes.WinDLL("dwmapi")
    dwm.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    if hwnd and dwm.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(rc), ctypes.sizeof(rc)) == 0:
        return rc.left, rc.top, rc.right, rc.bottom
    return root.winfo_rootx(), root.winfo_rooty(), root.winfo_rootx() + root.winfo_width(), root.winfo_rooty() + root.winfo_height()


class Demo:
    def __init__(self, root: tk.Tk, theme: Theme) -> None:
        self.root, self.theme = root, theme
        self.tracked: list[tuple[tk.Widget, dict[str, str]]] = []
        self.cards: list[RoundedFrame] = []
        self.card_parts: list[tuple[tk.Widget, str, str]] = []  # (widget, สีโน้ต, fg token)
        self.buttons: list[IconButton] = []
        self.build()

    # ผูก widget ของ demo เองกับ token เพื่อเปลี่ยนสีตอนสลับธีม (widget ใน widgets.py ทำเองผ่าน subscribe)
    def track(self, w: tk.Widget, **opts: str) -> tk.Widget:
        self.tracked.append((w, opts))
        w.configure(**{k: self.theme.c(v) for k, v in opts.items()})
        return w

    def recolor(self) -> None:
        for w, opts in self.tracked:
            w.configure(**{k: self.theme.c(v) for k, v in opts.items()})

    def label(self, parent, text, font="body", fg="text", bg="bg", **kw) -> tk.Label:
        lb = tk.Label(parent, text=text, font=self.theme.font(font), anchor="w", **kw)
        return self.track(lb, bg=bg, fg=fg)

    def build(self) -> None:
        th, root = self.theme, self.root
        pad = px(root, 16)
        main = self.track(tk.Frame(root), bg="bg")
        main.pack(fill="both", expand=True, padx=pad, pady=pad)
        main.grid_columnconfigure(0, weight=1, uniform="c")
        main.grid_columnconfigure(1, weight=1, uniform="c")

        # --- tokens
        self.label(main, "Tokens  /  โทเคนสี", "subtitle").grid(row=0, column=0, columnspan=2, sticky="w")
        sw = self.track(tk.Frame(main), bg="bg")
        sw.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 8))
        names = ["bg", "surface", "card", "card_hover", "stroke", "stroke_strong", "text", "text_secondary",
                 "text_disabled", "accent", "on_accent", "subtle_hover", "subtle_pressed", "critical", "caution", "success"]
        for i, n in enumerate(names):
            cell = self.track(tk.Frame(sw), bg="bg")
            cell.grid(row=i // 8, column=i % 8, padx=2, pady=2)
            box = tk.Frame(cell, width=px(root, 70), height=px(root, 26), highlightthickness=1)
            self.track(box, bg=n, highlightbackground="stroke_strong")
            box.pack()
            self.label(cell, n, "caption", "text_secondary").pack()

        # --- fonts
        self.label(main, "Fonts  /  ฟอนต์", "subtitle").grid(row=2, column=0, sticky="w")
        fr = self.track(tk.Frame(main), bg="bg")
        fr.grid(row=3, column=0, sticky="w", pady=(4, 8))
        self.label(fr, "Title 18 — หัวข้อใหญ่ Settings", "title").pack(anchor="w")
        self.label(fr, "Subtitle 14 — หัวข้อ dialog", "subtitle").pack(anchor="w")
        self.label(fr, "Body Strong 10 — ประชุมทีม Marketing", "body_strong").pack(anchor="w")
        self.label(fr, "Body 10 — เนื้อหาโน้ต The quick brown fox", "body").pack(anchor="w")
        self.label(fr, "Caption 9 — วันนี้ 14:30 · สูง · เตรียมสไลด์", "caption", "text_secondary").pack(anchor="w")

        # --- icons
        self.label(main, "Icons  /  ไอคอน (Segoe Fluent Icons)", "subtitle").grid(row=2, column=1, sticky="w")
        ic = self.track(tk.Frame(main), bg="bg")
        ic.grid(row=3, column=1, sticky="w", pady=(4, 8))
        for i, (name, ch) in enumerate(ICONS.items()):
            cell = self.track(tk.Frame(ic), bg="bg")
            cell.grid(row=i // 9, column=i % 9, padx=3, pady=2)
            tk.Label(cell, text=ch, font=th.font("icon14"), bd=0).pack()
            self.track(cell.winfo_children()[0], bg="bg", fg="text")
            self.label(cell, name[:9], "caption", "text_secondary").pack()

        # --- icon buttons / entries / ttk buttons
        self.label(main, "IconButton / Entry / Buttons", "subtitle").grid(row=4, column=0, sticky="w")
        bar = self.track(tk.Frame(main), bg="surface")
        bar.grid(row=5, column=0, sticky="ew", pady=(4, 8))
        for icon, kw in (("search", {}), ("settings", {}), ("topmost", {"toggle": True}), ("topmost", {"toggle": True}),
                         ("more", {"size": 28, "fg_token": "text_secondary"}), ("delete", {})):
            b = IconButton(bar, th, ICONS[icon], tooltip=icon, **kw)
            b.pack(side="left", padx=4, pady=6)
            self.buttons.append(b)
        self.buttons[3].set_active(True)
        dis = IconButton(bar, th, ICONS["add"], tooltip="disabled")
        dis.set_enabled(False)
        dis.pack(side="left", padx=4)
        self.buttons.append(dis)

        row2 = self.track(tk.Frame(main), bg="bg")
        row2.grid(row=6, column=0, sticky="ew", pady=(0, 6))
        e1 = PlaceholderEntry(row2, strings.t("board.search_placeholder"))
        e1.pack(fill="x", pady=2)
        e2 = PlaceholderEntry(row2, strings.t("board.quick_add_placeholder"))
        e2.pack(fill="x", pady=2)
        e2.set_value("ซื้อของเข้าบ้าน — นม ไข่ ขนมปัง")
        row3 = self.track(tk.Frame(main), bg="bg")
        row3.grid(row=7, column=0, sticky="w", pady=(0, 8))
        ttk.Button(row3, text="ปุ่มปกติ").pack(side="left", padx=2)
        ttk.Button(row3, text="บันทึก", style="Accent.TButton").pack(side="left", padx=2)
        ttk.Button(row3, text="Subtle", style="Subtle.TButton").pack(side="left", padx=2)
        ttk.Button(row3, text="ลบการแจ้งเตือน", style="Link.TButton").pack(side="left", padx=2)
        ttk.Checkbutton(row3, text="Switch", style="Switch.TCheckbutton").pack(side="left", padx=8)

        # --- note cards (RoundedFrame)
        self.label(main, "Note cards  /  สีโน้ต", "subtitle").grid(row=4, column=1, sticky="w")
        col = self.track(tk.Frame(main), bg="bg")
        col.grid(row=5, column=1, rowspan=5, sticky="new", pady=(4, 8))
        for i, color in enumerate(NOTE_COLORS):
            border, width = "stroke", 1
            if i == 1:
                border, width = "critical", 2   # ตัวอย่าง alarm
            if i == 2:
                border, width = "accent", 2     # ตัวอย่าง keyboard focus
            card = RoundedFrame(col, th, radius=8, bg="card", border=border, border_width=width)
            card.pack(fill="x", pady=2)
            card._demo_color = color
            self.cards.append(card)
            body = card.body
            bgc = th.note_bg(color)
            card.set_colors(bg=bgc)
            top = tk.Frame(body, bg=bgc)
            top.pack(fill="x", padx=8, pady=(6, 0))
            self.card_parts.append((top, color, ""))
            for parent, text, font, fg, side in ((top, ICONS["circle"], "icon14", "text_secondary", "left"),
                                                 (top, f"  โน้ตสี {color} — ประชุมทีม", "body_strong", "text", "left"),
                                                 (top, ICONS["pin"], "icon10", "text_secondary", "right")):
                lb = tk.Label(parent, text=text, font=th.font(font), bg=bgc, fg=th.c(fg))
                lb.pack(side=side)
                self.card_parts.append((lb, color, fg))
            meta = tk.Label(body, text="วันนี้ 14:30 · ● สูง · เตรียมสไลด์ยอดขาย Q3", font=th.font("caption"), bg=bgc,
                            fg=th.c("text_secondary"), anchor="w")
            meta.pack(fill="x", padx=(34, 8), pady=(0, 6))
            self.card_parts.append((meta, color, "text_secondary"))

        # --- settings card
        self.label(main, "SettingsCard  /  การ์ดตั้งค่า", "subtitle").grid(row=8, column=0, sticky="w")
        card = SettingsCard(main, th)
        card.grid(row=9, column=0, sticky="ew", pady=(4, 8))
        self.settings_card = card
        card.add_row(strings.t("settings.theme"), strings.t("settings.theme.desc"),
                     lambda p: ttk.Combobox(p, values=["สว่าง", "มืด", "ตามระบบ"], state="readonly", width=12))
        card.add_row(strings.t("settings.sound"), None,
                     lambda p: ttk.Checkbutton(p, style=card.ttk_style("Switch.TCheckbutton")))
        card.add_row(strings.t("settings.alpha"), strings.t("settings.alpha.desc"),
                     lambda p: ttk.Scale(p, from_=30, to=100, length=px(p, 140), style=card.ttk_style("Horizontal.TScale")))
        card.add_row(strings.t("settings.backup"), None,
                     lambda p: ttk.Button(p, text=strings.t("settings.backup.button")))

        # --- undo bar
        self.undo = UndoBar(root, th, {"side": "bottom", "fill": "x", "padx": 12, "pady": (0, 8), "before": main})
        self.undo.show(strings.t("undo.deleted"), on_undo=lambda: None, on_expire=None, seconds=3600)

    def apply_theme(self) -> None:
        self.recolor()
        for w, color, fg in self.card_parts:
            w.configure(bg=self.theme.note_bg(color), **({"fg": self.theme.c(fg)} if fg else {}))
        self.root.update_idletasks()


def shoot(root: tk.Tk, path: str) -> None:
    root.attributes("-topmost", True)
    root.lift()
    root.update()
    time.sleep(0.5)
    root.update()
    from PIL import ImageGrab
    ImageGrab.grab(bbox=frame_rect(root), all_screens=True).save(path)
    root.attributes("-topmost", False)
    print("saved", path)


def main() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
    out = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUT
    os.makedirs(out, exist_ok=True)
    root = tk.Tk()
    root.title("QuickNote — foundation demo")
    root.geometry("1000x1010+40+0")
    settings = FakeSettings(theme="light")
    theme = Theme(root, settings)
    theme.apply_window(root)
    demo = Demo(root, theme)
    root.update()
    shoot(root, os.path.join(out, "foundation_light.png"))

    settings.set("theme", "dark")  # → Theme.refresh() ผ่าน subscribe → widgets ปรับสีเองผ่าน after_idle
    demo.apply_theme()
    # Card ในตัวอย่างใช้สีโน้ตตาม mode → เติมสีใหม่ (NoteCard จริงทำผ่าน apply_theme ของตัวเอง)
    for card in demo.cards:
        card.apply_theme()
        card.set_colors(bg=theme.note_bg(card._demo_color))
    theme.apply_window(root)
    root.update()
    time.sleep(0.2)
    root.update()
    shoot(root, os.path.join(out, "foundation_dark.png"))
    root.destroy()


if __name__ == "__main__":
    main()
