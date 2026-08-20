"""System Tray Icon — pystray + menu"""

import threading
import pystray
from PIL import Image, ImageDraw
from typing import Callable


def create_icon_image(size: int = 64) -> Image.Image:
    """วาดไอคอนด้วยโค้ด — pastel yellow square ตรงกับ theme"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Pastel yellow square
    draw.rounded_rectangle([4, 4, size - 4, size - 4], radius=10, fill="#FFF3C4", outline="#E5E5E5", width=2)
    return img


class TrayIcon:
    """System Tray Icon ที่ launcher แอป + menu"""

    def __init__(self, on_show: Callable, on_settings: Callable, on_quit: Callable):
        self.on_show = on_show
        self.on_settings = on_settings
        self.on_quit = on_quit

        # สร้างเมนู
        menu = pystray.Menu(
            pystray.MenuItem("Show QuickNote", lambda: self.on_show()),
            pystray.MenuItem("Settings", lambda: self.on_settings()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", lambda: self.on_quit()),
        )

        # สร้าง icon
        self.icon = pystray.Icon(
            "quicknote",
            create_icon_image(),
            "QuickNote — Notes on Top",
            menu,
        )

    def run(self):
        """รัน tray icon loop (บน daemon thread)"""
        try:
            self.icon.run()
        except Exception:
            pass

    def stop(self):
        """หยุด tray icon"""
        try:
            self.icon.stop()
        except Exception:
            pass


def start_tray_thread(on_show: Callable, on_settings: Callable, on_quit: Callable) -> TrayIcon:
    """เปิด tray icon บน daemon thread"""
    tray = TrayIcon(on_show, on_settings, on_quit)
    thread = threading.Thread(target=tray.run, daemon=True)
    thread.start()
    return tray
