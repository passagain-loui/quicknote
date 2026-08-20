"""Windows Autostart — Create/Remove shortcut ใน Startup folder"""

import os
import sys
from pathlib import Path
from typing import Optional


def get_startup_dir() -> Path:
    """ได้ path โฟลเดอร์ Windows Startup"""
    return Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup"


def get_executable_path() -> str:
    """ได้ path ไปที่ .exe (หลัง build) หรือ python.exe + script ตอน dev"""
    if getattr(sys, "frozen", False):
        # PyInstaller bundle → exe
        return sys.executable
    # Dev mode → python.exe + script
    return str(Path(sys.argv[0]).resolve())


def enable_autostart(app_name: str = "QuickNote") -> bool:
    """สร้าง shortcut ใน Startup folder — จะรันพร้อม Windows"""
    try:
        from win32com.client import Dispatch

        startup_dir = get_startup_dir()
        link_path = startup_dir / f"{app_name}.lnk"

        shell = Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(link_path))
        shortcut.Targetpath = sys.executable

        # Arguments: ถ้า dev mode ให้ส่ง script path
        if not getattr(sys, "frozen", False):
            shortcut.Arguments = str(Path(sys.argv[0]).resolve())

        shortcut.WorkingDirectory = str(Path(sys.argv[0]).resolve().parent)
        shortcut.save()

        print(f"[OK] Autostart enabled: {link_path}")
        return True

    except ImportError:
        print("[!] pywin32 not found — autostart skipped")
        return False
    except Exception as e:
        print(f"[!] Failed to enable autostart: {e}")
        return False


def disable_autostart(app_name: str = "QuickNote") -> bool:
    """ลบ shortcut จาก Startup folder"""
    try:
        startup_dir = get_startup_dir()
        link_path = startup_dir / f"{app_name}.lnk"

        if link_path.exists():
            link_path.unlink()
            print(f"[OK] Autostart disabled: {link_path}")
            return True
        else:
            print(f"[!] Shortcut not found: {link_path}")
            return False

    except Exception as e:
        print(f"[!] Failed to disable autostart: {e}")
        return False


def is_autostart_enabled(app_name: str = "QuickNote") -> bool:
    """ตรวจสอบว่า autostart เปิดอยู่"""
    startup_dir = get_startup_dir()
    link_path = startup_dir / f"{app_name}.lnk"
    return link_path.exists()
