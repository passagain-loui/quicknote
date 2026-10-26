"""Demo ของ ToastManager + ReminderDialog — เปิดจริง แคปภาพ สว่าง → มืด → อังกฤษ ไว้ตรวจด้วยตา

รัน:  python tools/demo_toast_dialog.py [โฟลเดอร์เก็บภาพ]
ภาพ: toast_light/dark.png, dialog_light/dark/en.png (ซ้าย = ว่าง, ขวา = ค่าเดิมที่เป็นเวลาอดีต),
     calendar_light/dark.png (dialog + ปฏิทิน dropdown)
"""

from __future__ import annotations

import ctypes
import os
import sys
import time
import tkinter as tk
from ctypes import wintypes
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src.core.models import Note  # noqa: E402
from src.ui import strings, win11  # noqa: E402
from src.ui.reminder_dialog import ReminderDialog  # noqa: E402
from src.ui.theme import Theme  # noqa: E402
from src.ui.toast import ToastManager  # noqa: E402

DEFAULT_OUT = r"C:\Users\PASSAG~1\AppData\Local\Temp\claude\D--AI-OpenCode-Noted-Planing-and-Record\5942156e-1758-4add-8e22-4048da503076\scratchpad"


class FakeSettings:
    """settings จำลอง (ไม่แตะ ~/.quicknote)"""

    def __init__(self, **kw) -> None:
        self.data = {"theme": "light", "font_size": "normal", "sound": False, **kw}
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


def pump(root: tk.Tk, seconds: float) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        root.update()
        time.sleep(0.01)


def frame_rect(window: tk.Misc) -> tuple[int, int, int, int]:
    """กรอบจริงของหน้าต่าง (รวม titlebar ไม่รวมเงา) จาก DWM"""
    hwnd = win11._frame_hwnd(window)
    rc = wintypes.RECT()
    dwm = ctypes.WinDLL("dwmapi")
    dwm.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    if hwnd and dwm.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(rc), ctypes.sizeof(rc)) == 0:
        return rc.left, rc.top, rc.right, rc.bottom
    x, y = window.winfo_rootx(), window.winfo_rooty()
    return x, y, x + window.winfo_width(), y + window.winfo_height()


def grab(bbox: tuple[int, int, int, int]):
    from PIL import ImageGrab
    return ImageGrab.grab(bbox=bbox, all_screens=True)


def side_by_side(a, b, gap: int = 24):
    from PIL import Image
    img = Image.new("RGB", (a.width + gap + b.width, max(a.height, b.height)), "#808080")
    img.paste(a, (0, 0))
    img.paste(b, (a.width + gap, 0))
    return img


def note(title: str, content: str = "", when: str | None = None, **kw) -> Note:
    return Note(id=title, title=title, content=content, reminder_datetime=when, **kw)


def shoot_toasts(root, theme, mgr: ToastManager, path: str) -> None:
    now = datetime.now()
    when = (now - timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M")
    mgr.show_reminder(
        {"id": "a", "title": "ประชุมทีม Marketing", "reminder_datetime": when,
         "content": "เตรียมสไลด์ยอดขาย Q3\nตัวเลขรายเดือน\nแผนงานไตรมาสหน้า และเรื่องงบประมาณที่ต้องคุยกับฝ่ายการเงิน"},
        lambda: None, lambda w: None, lambda: None, lambda: None)
    mgr.show_reminder(
        {"id": "b", "title": "Call the dentist about the appointment that was moved", "reminder_datetime": when,
         "content": ""},
        lambda: None, lambda w: None, lambda: None, lambda: None)
    mgr.show_missed([{"title": "จ่ายค่าไฟ"}, {"title": "ส่งรายงานประจำเดือน"}, {"title": "Renew the domain"}],
                    lambda: None)
    pump(root, 0.6)
    rects = [frame_rect(t.win) for t in mgr.toasts]
    pad = 20
    bbox = (min(r[0] for r in rects) - pad, min(r[1] for r in rects) - pad,
            max(r[2] for r in rects) + pad, max(r[3] for r in rects) + pad)
    grab(bbox).save(path)
    mgr.close_all()
    pump(root, 0.3)


def shoot_dialog(root, theme, lang_note: Note, open_calendar: bool = False):
    dlg = ReminderDialog(root, lang_note, theme, lambda w, r: None)
    dlg.top.attributes("-topmost", True)
    pump(root, 0.5)
    if open_calendar:
        dlg.date_entry.drop_down()
        pump(root, 0.4)
        r1 = frame_rect(dlg.top)
        cal = dlg.date_entry._top_cal
        r2 = (cal.winfo_rootx(), cal.winfo_rooty(), cal.winfo_rootx() + cal.winfo_width(),
              cal.winfo_rooty() + cal.winfo_height())
        bbox = (min(r1[0], r2[0]), min(r1[1], r2[1]), max(r1[2], r2[2]), max(r1[3], r2[3]))
    else:
        bbox = frame_rect(dlg.top)
    img = grab(bbox)
    dlg.close()
    pump(root, 0.2)
    return img


def make_backdrop(root: tk.Tk) -> tk.Toplevel:
    """พื้นหลังทึบคลุมทั้งจอ (topmost) — ภาพที่แคปจะไม่มีหน้าจอจริงของผู้ใช้ติดมา และ dialog ไม่ถูกแอปอื่นบัง"""
    bd = tk.Toplevel(root)
    bd.overrideredirect(True)
    bd.attributes("-topmost", True)
    bd.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0")
    return bd


def main() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
    out = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUT
    os.makedirs(out, exist_ok=True)
    root = tk.Tk()
    root.title("QuickNote — toast/dialog demo")
    root.geometry("420x520+140+120")
    settings = FakeSettings(theme="light")
    theme = Theme(root, settings)
    theme.apply_window(root)
    root.update()
    mgr = ToastManager(root, theme, settings)
    backdrop = make_backdrop(root)
    root.attributes("-topmost", True)
    root.lift()

    past = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
    empty = note("ประชุมทีม Marketing")
    prefilled = note("ประชุมทีม Marketing", when=past, reminder_repeat="weekdays")

    for mode in ("light", "dark"):
        settings.set("theme", mode)
        backdrop.configure(bg="#C9D1DC" if mode == "light" else "#0C0C0C")
        pump(root, 0.3)
        theme.apply_window(root)
        shoot_toasts(root, theme, mgr, os.path.join(out, f"toast_{mode}.png"))
        side_by_side(shoot_dialog(root, theme, empty), shoot_dialog(root, theme, prefilled)).save(
            os.path.join(out, f"dialog_{mode}.png"))
        shoot_dialog(root, theme, prefilled, open_calendar=True).save(os.path.join(out, f"calendar_{mode}.png"))

    settings.set("theme", "light")
    strings.set_language("en")
    pump(root, 0.3)
    en_empty = note("Team meeting")
    en_pref = note("Team meeting", when=past, reminder_repeat="daily")
    side_by_side(shoot_dialog(root, theme, en_empty), shoot_dialog(root, theme, en_pref)).save(
        os.path.join(out, "dialog_en.png"))
    shoot_toasts(root, theme, mgr, os.path.join(out, "toast_en.png"))
    root.destroy()
    print("saved to", out)


if __name__ == "__main__":
    main()
