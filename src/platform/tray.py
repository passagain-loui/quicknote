"""System Tray Icon — pystray + menu"""

import threading
import logging
import pystray
from PIL import Image, ImageDraw
from typing import Callable

log = logging.getLogger(__name__)


def create_icon_image(size: int = 64) -> Image.Image:
    """วาดไอคอนด้วยโค้ด — pastel yellow square ตรงกับ theme"""
    try:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Pastel yellow square
        draw.rounded_rectangle([4, 4, size - 4, size - 4], radius=10, fill="#FFF3C4", outline="#E5E5E5", width=2)
        log.debug(f"[Tray] Icon image created ({size}x{size})")
        return img
    except Exception as e:
        log.error(f"[Tray] Failed to create icon image: {e}")
        # Fallback: create minimal 1x1 transparent image
        fallback = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        return fallback


class TrayIcon:
    """System Tray Icon ที่ launcher แอป + menu"""

    def __init__(self, on_show: Callable, on_settings: Callable, on_quit: Callable):
        self.on_show = on_show
        self.on_settings = on_settings
        self.on_quit = on_quit
        self.icon = None

        try:
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
            log.info("[Tray] Icon initialized successfully")
        except Exception as e:
            log.error(f"[Tray] Failed to initialize icon: {e}")
            import traceback
            traceback.print_exc()

    def run(self):
        """รัน tray icon loop (บน daemon thread)"""
        if not self.icon:
            log.error("[Tray] Icon is None, cannot run")
            return
        try:
            log.info("[Tray] Starting icon loop...")
            self.icon.run()
        except Exception as e:
            log.error(f"[Tray] Exception in icon.run(): {e}")
            import traceback
            traceback.print_exc()

    def stop(self):
        """หยุด tray icon"""
        if not self.icon:
            return
        try:
            log.info("[Tray] Stopping icon...")
            self.icon.stop()
        except Exception as e:
            log.error(f"[Tray] Exception in icon.stop(): {e}")


def start_tray_thread(on_show: Callable, on_settings: Callable, on_quit: Callable) -> TrayIcon:
    """เปิด tray icon บน daemon thread"""
    try:
        tray = TrayIcon(on_show, on_settings, on_quit)
        if tray.icon is None:
            log.warning("[Tray] Icon is None after initialization, thread will not start")
            return tray
        thread = threading.Thread(target=tray.run, daemon=True)
        thread.start()
        log.info("[Tray] Tray thread started successfully")
        return tray
    except Exception as e:
        log.error(f"[Tray] Failed to start tray thread: {e}")
        import traceback
        traceback.print_exc()
        return TrayIcon(on_show, on_settings, on_quit)
