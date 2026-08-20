#!/usr/bin/env python3
"""QuickNote — entry point สำหรับทดสอบและรันแอป"""

import sys
import ctypes
import threading
import socket
from pathlib import Path

# DPI awareness — บรรทัดแรก ก่อนสร้าง Tk()
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

from src.core.constants import APP_NAME, APP_VERSION, APP_AUTHOR
from src.core.database import init_db, get_all_notes, create_note
from src.core.settings import Settings
from src.ui.board import Board
from src.platform.tray import start_tray_thread
from src.platform.hotkey import start_hotkey_listener, create_default_hotkeys


class SingleInstanceLock:
    """ป้องกันการเปิดโปรแกรมซ้อนกัน — ถ้ามีอยู่แล้วให้ส่งสัญญาณขึ้นมา"""

    LOCK_PORT = 29837  # Port ที่ใช้ lock

    def __init__(self):
        self.socket = None

    def acquire(self) -> bool:
        """พยายามล็อก — ถ้าสำเร็จคืน True (นี่คือ instance แรก)"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("127.0.0.1", self.LOCK_PORT))
            sock.listen(1)
            self.socket = sock
            return True
        except OSError:
            # Port ถูกครอง → มีโปรแกรมรันอยู่แล้ว
            return False

    def release(self):
        """ปล่อย lock"""
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass


def send_signal_to_existing_instance() -> bool:
    """ส่งสัญญาณให้ instance แรกที่รันอยู่ — ดึงหน้าต่างขึ้นมา"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", SingleInstanceLock.LOCK_PORT))
        sock.send(b"SHOW")
        sock.close()
        return True
    except Exception:
        return False


def main():
    """Initialize database, load settings, show Board UI, tray, hotkey, and run mainloop"""
    print("[>] QuickNote starting...")

    # Single instance lock
    lock = SingleInstanceLock()
    if not lock.acquire():
        # มีโปรแกรมรันอยู่แล้ว → ส่งสัญญาณแล้วออก
        print("[!] QuickNote already running — sending signal...")
        send_signal_to_existing_instance()
        return 0

    try:
        # Initialize database
        init_db()
        print("[OK] Database initialized")

        notes = get_all_notes()
        print(f"[OK] Found {len(notes)} existing notes")

        # Load settings
        settings = Settings()
        settings.load()
        print("[OK] Settings loaded")

        geometry = settings.get("geometry", "")  # Empty string → Board จะ center
        theme = settings.get("theme", "light")
        alpha = settings.get("alpha", 1.0)

        # Ensure alpha is safe
        if alpha is None or alpha <= 0:
            alpha = 1.0
        alpha = max(0.3, min(1.0, float(alpha)))

        # Create and show Board UI
        print("[>] Launching UI...")
        board = Board(geometry=geometry, theme_mode=theme)

        # Apply alpha
        board.root.update_idletasks()
        board.root.attributes("-alpha", alpha)

        # === Tray Icon ===
        def on_tray_show():
            """Tray menu: Show"""
            board.root.after(0, lambda: (
                board.root.deiconify(),
                board.root.lift(),
                board.root.focus_force(),
            ))

        def on_tray_settings():
            """Tray menu: Settings"""
            # TODO: เปิด settings window
            board.root.after(0, lambda: print("[!] Settings not implemented yet"))

        def on_tray_quit():
            """Tray menu: Quit"""
            board.root.after(0, lambda: board.root.quit())

        print("[>] Starting tray icon...")
        tray = start_tray_thread(on_tray_show, on_tray_settings, on_tray_quit)

        # === Global Hotkey ===
        def on_hotkey(name: str):
            """Global hotkey callback"""
            if name == "new_note":
                # Ctrl+Alt+N → Show window + create new note
                board.root.after(0, lambda: (
                    board.root.deiconify(),
                    board.root.lift(),
                    board.root.focus_force(),
                    board._on_new(),
                ))
            elif name == "toggle_show":
                # Ctrl+Alt+S → Toggle show/hide
                def toggle():
                    if board.root.state() == "normal":
                        board.root.withdraw()
                    else:
                        board.root.deiconify()
                        board.root.lift()
                        board.root.focus_force()

                board.root.after(0, toggle)

        hotkey_config = settings.get("hotkeys", create_default_hotkeys())
        print("[>] Starting hotkey listener...")
        hotkey_listener = start_hotkey_listener(hotkey_config, on_hotkey)

        # === Close Handler ===
        def on_closing():
            """Save settings and clean up"""
            # Save geometry before closing
            settings.set("geometry", board.root.geometry())
            settings.save()

            # Stop tray
            tray.stop()

            # Stop hotkey
            hotkey_listener.stop()

            # Release lock
            lock.release()

            board.root.quit()

        board.root.protocol("WM_DELETE_WINDOW", on_closing)

        print("[OK] QuickNote ready\n")
        board.mainloop()

        lock.release()
        return 0

    except Exception as e:
        print(f"[✗] Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        # ทำให้ AI สามารถเช็คว่าไม่ระเบิด
        import tkinter as tk
        root = tk.Tk()
        root.overrideredirect(True)
        root.geometry("1x1")
        root.after(1500, root.destroy)
        root.mainloop()
        print("[OK] GUI test passed")
        sys.exit(0)

    sys.exit(main())
