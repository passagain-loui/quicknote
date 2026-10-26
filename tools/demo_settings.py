"""Demo หน้าต่าง Settings — เปิดแบบสว่าง/มืด/อังกฤษ เลื่อนบน-ล่าง แล้วแคปภาพออกมาตรวจ

รัน:  python tools/demo_settings.py [โฟลเดอร์เก็บภาพ]
ภาพ: settings_light_top / settings_light_mid / settings_light_bottom / settings_dark_top / settings_dark_bottom / settings_en_top (.png)
ใช้ settings + DB ชั่วคราว ไม่แตะ ~/.quicknote จริง
"""

from __future__ import annotations

import ctypes
import os
import shutil
import sys
import tempfile
import time
import tkinter as tk

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from demo_foundation import DEFAULT_OUT, frame_rect  # noqa: E402
from src.core import database as db  # noqa: E402
from src.core import settings as settings_mod  # noqa: E402
from src.ui import strings  # noqa: E402
from src.ui.settings_window import SettingsActions, SettingsWindow  # noqa: E402
from src.ui.theme import Theme  # noqa: E402


def pump(root: tk.Tk, seconds: float = 0.4) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        root.update()
        time.sleep(0.01)


def shoot(win: tk.Toplevel, root: tk.Tk, path: str) -> None:
    win.attributes("-topmost", True)
    win.lift()
    pump(root, 0.6)
    from PIL import ImageGrab
    ImageGrab.grab(bbox=frame_rect(win), all_screens=True).save(path)
    win.attributes("-topmost", False)
    print("saved", path)


def main() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
    out = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUT
    os.makedirs(out, exist_ok=True)

    tmp = tempfile.mkdtemp(prefix="qn_test_demo_settings_")
    os.environ["DB_PATH"] = os.path.join(tmp, "notes.db")
    db.APP_DIR = type(db.APP_DIR)(tmp)
    settings_mod.SETTINGS_FILE = type(db.APP_DIR)(tmp) / "settings.json"
    db.init_db()

    strings.set_language("th")
    settings = settings_mod.Settings()
    settings.load()
    settings.set("theme", "light")

    root = tk.Tk()
    root.title("QuickNote")
    root.geometry("380x600+60+60")
    theme = Theme(root, settings)
    theme.apply_window(root)
    tk.Label(root, text="(หน้าต่างหลักจำลอง)", bg=theme.c("bg"), fg=theme.c("text")).pack(pady=40)

    noop = lambda: None  # noqa: E731
    closed: list[int] = []
    win = SettingsWindow(root, settings, theme, SettingsActions(noop, noop, noop, noop), lambda: closed.append(1))
    pump(root, 0.5)

    shoot(win.win, root, os.path.join(out, "settings_light_top.png"))
    win._canvas.yview_moveto(0.42)
    win.controls["hotkey_new_note"].winfo_children()[0].invoke()  # โหมดอัดคีย์ลัด: ปุ่มต้องเปลี่ยนข้อความ
    shoot(win.win, root, os.path.join(out, "settings_light_mid.png"))
    win._canvas.yview_moveto(1.0)
    shoot(win.win, root, os.path.join(out, "settings_light_bottom.png"))

    settings.set("theme", "dark")
    pump(root, 0.5)
    win._canvas.yview_moveto(0.0)
    shoot(win.win, root, os.path.join(out, "settings_dark_top.png"))
    win._canvas.yview_moveto(1.0)
    shoot(win.win, root, os.path.join(out, "settings_dark_bottom.png"))

    settings.set("theme", "light")
    combo = win.controls["language"]
    combo.set("English")
    combo.event_generate("<<ComboboxSelected>>")
    pump(root, 0.5)
    win._canvas.yview_moveto(0.0)
    shoot(win.win, root, os.path.join(out, "settings_en_top.png"))

    win._close()
    root.destroy()
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
