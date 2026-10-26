"""Windows 11 helpers — ctypes/winreg ทั้งหมดรวมไว้ที่นี่

กติกา: ทุกฟังก์ชัน public ห้าม raise — Windows 10 ไม่มี DWM attr 33/35,
non-Windows ไม่มี ctypes.windll ฯลฯ ให้ fallback เงียบ ๆ แล้วแอปยังเปิดได้
"""

from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes

log = logging.getLogger(__name__)

_IS_WIN = sys.platform == "win32"

# DWM window attributes
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36
DWMWCP_ROUND = 2

_ICON_FLUENT = "Segoe Fluent Icons"
_ICON_MDL2 = "Segoe MDL2 Assets"
_icon_family_cache: str | None = None

if _IS_WIN:
    # ใช้ WinDLL ของเราเอง (ไม่แตะ ctypes.windll ที่ใช้ร่วมกับ lib อื่น) เพื่อกำหนด argtypes
    # ให้ถูกบน 64-bit — HWND เป็น pointer ถ้าไม่กำหนดจะถูกตัดเป็น int 32 บิต
    _dwm = ctypes.WinDLL("dwmapi", use_last_error=True)
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _shell32 = ctypes.WinDLL("shell32", use_last_error=True)

    _dwm.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, wintypes.LPCVOID, wintypes.DWORD]
    _dwm.DwmSetWindowAttribute.restype = ctypes.c_long
    _user32.GetParent.argtypes = [wintypes.HWND]
    _user32.GetParent.restype = wintypes.HWND
    _user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    _user32.MonitorFromWindow.restype = wintypes.HANDLE
    _user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
    _user32.MonitorFromPoint.restype = wintypes.HANDLE
    _user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
    _user32.GetMonitorInfoW.restype = wintypes.BOOL
    _user32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT]
    _user32.SystemParametersInfoW.restype = wintypes.BOOL
    _shell32.SetCurrentProcessExplicitAppUserModelID.argtypes = [wintypes.LPCWSTR]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


class _HIGHCONTRAST(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwFlags", wintypes.DWORD),
                ("lpszDefaultScheme", wintypes.LPWSTR)]


def _hex_to_colorref(hex_color: str) -> int:
    """'#RRGGBB' → COLORREF 0x00BBGGRR (DWM ใช้รูปแบบนี้ ไม่ใช่ RGB)"""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (b << 16) | (g << 8) | r


def _frame_hwnd(window) -> int | None:
    """HWND ของ "กรอบหน้าต่างจริง" (ที่มี titlebar)

    winfo_id() ของ Tk คือ HWND ของพื้นที่ client ภายใน ส่วนกรอบนอกคือ parent ของมัน
    DWM attribute ต้องตั้งที่กรอบนอก (ทดสอบแล้วบนเครื่องนี้ — ดู tools/demo_foundation.py)
    """
    try:
        window.update_idletasks()
        inner = int(window.winfo_id())
        parent = _user32.GetParent(inner)
        if parent:
            return int(parent)
    except Exception:
        pass
    try:
        return int(window.wm_frame(), 16)
    except Exception:
        return None


def _set_dwm(hwnd: int, attr: int, value: int) -> bool:
    try:
        v = ctypes.c_int(value)
        return _dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), 4) == 0
    except Exception:
        return False


def apply_titlebar(window, dark: bool, caption_hex: str | None = None) -> None:
    """titlebar มืด/สว่างตามธีม + มุมโค้ง + สี caption ให้กลืนกับพื้นแอป (Win11 22000+)"""
    if not _IS_WIN:
        return
    try:
        hwnd = _frame_hwnd(window)
        if not hwnd:
            return
        _set_dwm(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 1 if dark else 0)
        _set_dwm(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND)  # Win10 → ล้มเหลวเงียบ ๆ
        if caption_hex and caption_hex.startswith("#") and len(caption_hex) == 7:
            _set_dwm(hwnd, DWMWA_CAPTION_COLOR, _hex_to_colorref(caption_hex))
            # สีตัวอักษร title ให้อ่านออกบนพื้น caption ที่เรากำหนดเอง
            _set_dwm(hwnd, DWMWA_TEXT_COLOR, _hex_to_colorref("#FFFFFF" if dark else "#1A1A1A"))
        # ให้ caption วาดใหม่ทันที (บางเครื่องไม่เปลี่ยนจนกว่า window จะ activate)
        try:
            window.update_idletasks()
        except Exception:
            pass
    except Exception as e:  # pragma: no cover - กันทุกกรณี
        log.debug("apply_titlebar failed: %s", e)


def _read_reg_dword(path: str, name: str) -> int | None:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as k:
            val, _ = winreg.QueryValueEx(k, name)
            return int(val)
    except Exception:
        return None


def get_accent_color() -> str | None:
    """สี accent ของระบบเป็น '#RRGGBB' (registry เก็บเป็น 0xAABBGGRR) — อ่านไม่ได้คืน None"""
    v = _read_reg_dword(r"Software\Microsoft\Windows\DWM", "AccentColor")
    if v is None:
        return None
    r, g, b = v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF
    return f"#{r:02X}{g:02X}{b:02X}"


def is_system_dark() -> bool:
    """AppsUseLightTheme == 0 → โหมดมืด (ไม่มีค่า = สว่าง)"""
    v = _read_reg_dword(r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "AppsUseLightTheme")
    return v == 0


def is_high_contrast() -> bool:
    if not _IS_WIN:
        return False
    try:
        hc = _HIGHCONTRAST()
        hc.cbSize = ctypes.sizeof(hc)
        if _user32.SystemParametersInfoW(0x0042, hc.cbSize, ctypes.byref(hc), 0):  # SPI_GETHIGHCONTRAST
            return bool(hc.dwFlags & 0x1)  # HCF_HIGHCONTRASTON
    except Exception:
        pass
    return False


def animations_enabled() -> bool:
    """ผู้ใช้ปิด "Animation effects" ใน Windows → เราต้องข้าม fade/slide ด้วย (accessibility)"""
    if not _IS_WIN:
        return True
    try:
        flag = wintypes.BOOL()
        if _user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(flag), 0):  # SPI_GETCLIENTAREAANIMATION
            return bool(flag.value)
    except Exception:
        pass
    return True


def get_work_area(window) -> tuple[int, int, int, int]:
    """work area (ไม่รวม taskbar) ของจอที่ window อยู่ — (left, top, right, bottom)

    ต้องใช้จอของ window เองเพราะ multi-monitor: toast ต้องไปโผล่จอเดียวกับหน้าต่างหลัก
    """
    try:
        if _IS_WIN:
            hmon = None
            viewable = False
            try:
                viewable = bool(window.winfo_viewable())
            except Exception:
                pass
            if viewable:
                hwnd = _frame_hwnd(window)
                if hwnd:
                    hmon = _user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
            if not hmon:
                # window ซ่อนอยู่ → HWND อาจยังไม่มีตำแหน่งจริง ใช้พิกัดที่ Tk จำไว้แทน
                pt = wintypes.POINT(int(window.winfo_x()), int(window.winfo_y()))
                hmon = _user32.MonitorFromPoint(pt, 2)
            mi = _MONITORINFO()
            mi.cbSize = ctypes.sizeof(mi)
            if hmon and _user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                r = mi.rcWork
                return (int(r.left), int(r.top), int(r.right), int(r.bottom))
            rc = wintypes.RECT()
            if _user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rc), 0):  # SPI_GETWORKAREA
                return (int(rc.left), int(rc.top), int(rc.right), int(rc.bottom))
    except Exception as e:
        log.debug("get_work_area fallback: %s", e)
    try:
        return (0, 0, int(window.winfo_screenwidth()), int(window.winfo_screenheight()))
    except Exception:
        return (0, 0, 1280, 720)


def icon_font_family() -> str:
    """'Segoe Fluent Icons' (Win11) → fallback 'Segoe MDL2 Assets' (Win10)"""
    global _icon_family_cache
    if _icon_family_cache:
        return _icon_family_cache
    try:
        import tkinter
        import tkinter.font as tkfont
        if getattr(tkinter, "_default_root", None) is not None:
            fams = set(tkfont.families())
            _icon_family_cache = _ICON_FLUENT if _ICON_FLUENT in fams else _ICON_MDL2
            return _icon_family_cache
    except Exception:
        pass
    # ยังไม่มี Tk root → เดาจากไฟล์ฟอนต์ (ไม่ cache เพราะเป็นแค่การเดา)
    try:
        import os
        fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "SegoeIcons.ttf")
        return _ICON_FLUENT if os.path.exists(fonts) else _ICON_MDL2
    except Exception:
        return _ICON_MDL2


def set_app_user_model_id(app_id: str) -> None:
    """ให้ taskbar จับกลุ่ม/ไอคอนเป็นของ QuickNote ไม่ใช่ python.exe"""
    if not _IS_WIN:
        return
    try:
        _shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass
