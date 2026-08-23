"""Build QuickNote เป็น .exe + Windows Installer ด้วย PyInstaller + Inno Setup

ใช้:
    python build_windows.py            # Build ปกติ (ซ่อน console + สร้าง installer)
    python build_windows.py --debug    # Build ด้วย console เปิดไว้
    python build_windows.py --exe-only # เฉพาะ .exe ไม่สร้าง installer
"""

import shutil
import subprocess
import sys
from pathlib import Path

# Fix encoding for Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from src.core.constants import APP_NAME, APP_VERSION

ENTRY = "main.py"
ICON = "assets/quicknote.ico"
INSTALLER_SCRIPT = "installer.iss"

ROOT = Path(__file__).resolve().parent


def find_iscc() -> str | None:
    """หา Inno Setup Compiler (ISCC.exe) ใน registry"""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1") as key:
            inno_path = winreg.QueryValueEx(key, "InstallLocation")[0]
            iscc = Path(inno_path) / "ISCC.exe"
            if iscc.exists():
                return str(iscc)
    except Exception:
        pass

    # Common paths
    common_paths = [
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
    ]
    for path in common_paths:
        if path.exists():
            return str(path)

    return None


def build_exe(debug: bool = False) -> int:
    """Build exe ด้วย PyInstaller"""
    entry = ROOT / ENTRY
    if not entry.exists():
        print(f"[x] ไม่พบ entry point: {entry}")
        return 1

    # Generate versioned exe name
    exe_name = f"{APP_NAME}_v{APP_VERSION}"

    args = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconfirm",
        "--clean",
        "--name", exe_name,
        "--hidden-import=src.ui.settings_window",
        "--hidden-import=src.ui.board",
        "--hidden-import=src.ui.titlebar",
        "--hidden-import=src.ui.note_card",
        "--hidden-import=src.ui.theme",
        "--hidden-import=src.ui.custom_toast",
        "--hidden-import=src.ui.reminder_dialog",
        "--hidden-import=src.core.database",
        "--hidden-import=src.core.models",
        "--hidden-import=src.core.settings",
        "--hidden-import=src.services.notification",
        "--hidden-import=src.services.notification_queue",
        "--hidden-import=src.services.tray_service",
        "--hidden-import=src.services.google_tasks",
        "--hidden-import=src.platform.tray",
        "--hidden-import=src.platform.hotkey",
        # v2.9.4: Add win10toast_click for click-aware notifications
        "--hidden-import=win10toast_click",
        # v2.9.40: CRITICAL - Add ALL platform dependencies (pystray, pynput, PIL)
        "--hidden-import=pystray",
        "--hidden-import=pystray._win32",
        "--collect-all=pystray",
        # pynput for global hotkey support (Windows-specific)
        "--hidden-import=pynput",
        "--hidden-import=pynput.keyboard",
        "--hidden-import=pynput.mouse",
        "--hidden-import=pynput.keyboard._win32",
        "--hidden-import=pynput.mouse._win32",
        # Pillow/PIL for image processing
        "--hidden-import=PIL",
        "--hidden-import=PIL.Image",
        "--collect-all=PIL",
        # v2.5.5: Use --collect-all for tkcalendar + babel (--hidden-import misses submodules)
        "--collect-all=tkcalendar",  # Collects all submodules + data files
        "--collect-all=babel",        # Collects all babel locale data
    ]

    if not debug:
        args.append("--noconsole")

    icon = ROOT / ICON
    if icon.exists():
        args += ["--icon", str(icon)]
    else:
        print(f"[!] ไอคอนไม่พบที่ {ICON} — ข้ามไป")

    args.append(str(entry))

    print("[>] Building .exe...")
    print("[>] " + " ".join(args))
    result = subprocess.run(args, cwd=ROOT)

    if result.returncode != 0:
        print("[x] PyInstaller build ไม่สำเร็จ")
        return result.returncode

    exe = ROOT / "dist" / f"{exe_name}.exe"
    size_mb = exe.stat().st_size / 1024 / 1024 if exe.exists() else 0
    print(f"\n[/] .exe เสร็จแล้ว: {exe}  ({size_mb:.1f} MB)")
    return 0


def build_installer() -> int:
    """Build Windows Installer ด้วย Inno Setup"""
    script = ROOT / INSTALLER_SCRIPT
    if not script.exists():
        print(f"[x] ไม่พบ installer script: {script}")
        return 1

    iscc = find_iscc()
    if not iscc:
        print("[!] Inno Setup ไม่พบ — ข้ามการสร้าง installer")
        print("    ติดตั้ง Inno Setup จาก: https://jrsoftware.org/isinfo.php")
        return 0

    print(f"\n[>] Building installer...")
    print(f"[>] ISCC: {iscc}")

    # สร้าง output directory
    (ROOT / "installer_output").mkdir(exist_ok=True)

    args = [iscc, str(script)]
    result = subprocess.run(args, cwd=ROOT)

    if result.returncode != 0:
        print("[x] Inno Setup build ไม่สำเร็จ")
        return result.returncode

    setup_exe = ROOT / "installer_output" / f"{APP_NAME}-Setup-v{APP_VERSION}.exe"
    if setup_exe.exists():
        size_mb = setup_exe.stat().st_size / 1024 / 1024
        print(f"\n[/] Installer เสร็จแล้ว: {setup_exe}  ({size_mb:.1f} MB)")
    return 0


def clean() -> None:
    """ลบของที่ build ค้าง"""
    for name in ("build", "dist"):
        shutil.rmtree(ROOT / name, ignore_errors=True)
    (ROOT / f"{APP_NAME}.spec").unlink(missing_ok=True)
    print("[OK] ลบ build artifacts")


if __name__ == "__main__":
    clean()

    # Build .exe
    exe_result = build_exe(debug="--debug" in sys.argv)
    if exe_result != 0:
        sys.exit(exe_result)

    # Build installer (ถ้าไม่ใส่ --exe-only)
    if "--exe-only" not in sys.argv:
        installer_result = build_installer()
        sys.exit(installer_result)
    else:
        print("\n[OK] Skipped installer build (--exe-only)")
        sys.exit(0)
