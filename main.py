#!/usr/bin/env python3
"""QuickNote — entry point สำหรับทดสอบและรันแอป"""

import sys
import ctypes
import threading
import socket
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="[%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

# DPI awareness — บรรทัดแรก ก่อนสร้าง Tk() (v1.8.9: Upgraded to Per-Monitor V2)
try:
    # v1.8.9: Per-Monitor DPI Awareness V2 for crisp UI on all monitor scales
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        # Fallback to v1 if v2 not available
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            # Last resort: basic DPI awareness
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# v2.5.5: Force hard-import for PyInstaller AST scanning — ensures tkcalendar + dependencies bundled
# Without this, PyInstaller's static analysis misses deep dependencies even with --hidden-import
try:
    import tkcalendar
    import babel.numbers
except ImportError:
    pass

from src.core.constants import APP_NAME, APP_VERSION, APP_AUTHOR
from src.core.database import init_db, get_all_notes, create_note
from src.core.settings import Settings
from src.ui.board import Board
from src.ui.settings_window import SettingsWindow
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

        # Create and show Board UI (will set on_open_settings callback below)
        print("[>] Launching UI...")
        board = Board(geometry=geometry, theme_mode=theme, settings_obj=settings)

        # Apply alpha
        board.root.update_idletasks()
        board.root.attributes("-alpha", alpha)

        # Settings Window instance (global to prevent duplicate windows)
        settings_window = None

        # Open Settings callback (PyInstaller safe — import at top level)
        def open_settings_window():
            """Open or focus Settings window (used by both tray and UI button)"""
            nonlocal settings_window

            # If window already exists and is valid, just focus it
            if settings_window is not None:
                try:
                    # Check if window still exists
                    if settings_window.root.winfo_exists():
                        print("[>] Settings window already open, focusing...")
                        settings_window.root.lift()
                        settings_window.root.focus_force()
                        return
                except Exception:
                    pass

            # Create new Settings window
            try:
                print("[>] Opening Settings window...")
                # Define callback that saves settings AND refreshes UI
                def on_settings_saved():
                    settings.save()
                    board._on_settings_saved()

                settings_window = SettingsWindow(
                    board.root,
                    settings.settings,
                    board.theme,
                    on_save_callback=on_settings_saved
                )
                print("[OK] Settings window opened")
            except Exception as e:
                print(f"[✗] Failed to open Settings: {e}")
                import traceback
                traceback.print_exc()

        # Set callback for Board (PyInstaller safe)
        board.on_open_settings = lambda: board.root.after(0, open_settings_window)

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
            # Ensure main window is visible first
            print("[>] Ensuring main window is visible...")
            board.root.after(0, lambda: (
                board.root.deiconify(),
                board.root.lift(),
                board.root.focus_force(),
            ))
            # Then open settings after a short delay
            board.root.after(200, open_settings_window)

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
        print(f"[✗] Error during startup: {e}")
        import traceback
        traceback.print_exc()

        # Show error dialog to user
        try:
            import tkinter as tk
            from tkinter import messagebox
            error_root = tk.Tk()
            error_root.withdraw()  # Hide the root window
            error_msg = f"QuickNote ไม่สามารถเปิดได้\n\nError: {str(e)}\n\nกรุณาตรวจสอบ Console หรือ Log file"
            messagebox.showerror("QuickNote Startup Error", error_msg)
            error_root.destroy()
        except Exception as msg_err:
            print(f"[!] Failed to show error dialog: {msg_err}")

        lock.release()
        return 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        # Run full initialization with timeout
        print("[TEST] Starting full initialization test...")

        def run_with_timeout():
            try:
                # Create minimal Tk to avoid full UI initialization
                import tkinter as tk
                root = tk.Tk()
                root.overrideredirect(True)
                root.geometry("1x1")

                # Test database and settings
                print("[TEST] Initializing database...")
                init_db()
                notes = get_all_notes()
                print(f"[TEST] Database OK: {len(notes)} notes")

                print("[TEST] Loading settings...")
                settings = Settings()
                settings.load()
                print("[TEST] Settings OK")

                print("[TEST] Testing tray icon initialization...")
                def dummy_callback():
                    pass
                from src.platform.tray import TrayIcon
                tray = TrayIcon(dummy_callback, dummy_callback, dummy_callback)
                if tray.icon:
                    print("[TEST] Tray icon initialized OK")
                else:
                    print("[WARN] Tray icon is None after initialization")

                # Close after test
                root.after(500, root.destroy)
                root.mainloop()
                print("[OK] Full test passed")
                sys.exit(0)
            except Exception as e:
                print(f"[ERROR] Test failed: {e}")
                import traceback
                traceback.print_exc()
                sys.exit(1)

        run_with_timeout()

    sys.exit(main())
