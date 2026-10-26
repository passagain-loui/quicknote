"""Windows Autostart — สร้าง/ลบ shortcut ใน Startup folder (ใช้จากหน้า Settings: สวิตช์ "เปิดพร้อม Windows")"""

import logging
import os
import sys
from pathlib import Path

log = logging.getLogger("quicknote.autostart")

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def get_startup_dir() -> Path:
    """โฟลเดอร์ Startup ของผู้ใช้ปัจจุบัน"""
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def _link_path(app_name: str) -> Path:
    return get_startup_dir() / f"{app_name}.lnk"


def _launch_target() -> tuple[str, str, str]:
    """(โปรแกรมที่รัน, arguments, working dir) ทั้งแบบ .exe ที่ build แล้วและ `python main.py`

    dev mode ใช้ pythonw.exe (ไม่เปิดหน้าต่างคอนโซลตอนบูต) และชี้ไปที่ main.py ของโปรเจกต์ตรง ๆ
    แทนที่จะเชื่อ sys.argv[0] — รันผ่าน tools/ หรือ `-m` แล้ว argv[0] จะไม่ใช่ main.py
    path มีช่องว่าง ("Noted Planing and Record") จึงต้องครอบด้วย quote ไม่งั้น Windows แยก argument ผิด
    """
    if getattr(sys, "frozen", False):
        return sys.executable, "", str(Path(sys.executable).parent)
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")
    target = str(pythonw if pythonw.exists() else exe)
    return target, f'"{_PROJECT_ROOT / "main.py"}"', str(_PROJECT_ROOT)


def enable_autostart(app_name: str = "QuickNote") -> bool:
    """สร้าง shortcut ใน Startup — คืน True เมื่อไฟล์ .lnk ถูกสร้างจริง"""
    try:
        from win32com.client import Dispatch

        link_path = _link_path(app_name)
        link_path.parent.mkdir(parents=True, exist_ok=True)
        target, arguments, workdir = _launch_target()

        shortcut = Dispatch("WScript.Shell").CreateShortCut(str(link_path))
        shortcut.Targetpath = target
        shortcut.Arguments = arguments
        shortcut.WorkingDirectory = workdir
        shortcut.IconLocation = target if getattr(sys, "frozen", False) else str(_PROJECT_ROOT / "assets" / "icon.ico")
        shortcut.save()
        return link_path.exists()
    except ImportError:
        log.warning("pywin32 not found — autostart unavailable")
        return False
    except Exception as e:
        log.error("failed to enable autostart: %s", e)
        return False


def disable_autostart(app_name: str = "QuickNote") -> bool:
    """ลบ shortcut — ถ้าไม่มีอยู่แล้วถือว่าสำเร็จ (ผลลัพธ์ที่ต้องการคือ "ไม่มี shortcut")"""
    try:
        _link_path(app_name).unlink(missing_ok=True)
        return True
    except Exception as e:
        log.error("failed to disable autostart: %s", e)
        return False


def is_autostart_enabled(app_name: str = "QuickNote") -> bool:
    """สถานะจริงจากดิสก์ (ไม่เก็บใน settings.json เพื่อไม่ให้เพี้ยนจากสิ่งที่ผู้ใช้ลบเอง)"""
    try:
        return _link_path(app_name).exists()
    except Exception:
        return False
