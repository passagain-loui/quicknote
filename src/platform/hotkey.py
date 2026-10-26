"""Global Hotkey — Win32 RegisterHotKey (ไม่ใช้ pynput แล้ว)

ทำไมไม่ใช้ pynput: GlobalHotKeys เทียบ "ตัวอักษร" ที่แปลจากแป้น ซึ่งขึ้นกับภาษาแป้นพิมพ์ — ตอนเปิดแป้นไทยอยู่
Ctrl+Alt+N แปลเป็นอักษรไทย/ไม่มีอักษร คีย์ลัดเลยไม่ทำงานเลย (ทดสอบจริงด้วย smoke test)
RegisterHotKey ใช้ virtual-key code จึงไม่ขึ้นกับภาษา และบอกได้เมื่อคีย์นั้นถูกโปรแกรมอื่นจองไปแล้ว

THREADING: on_hotkey ถูกเรียกจาก thread ของ listener — ผู้เรียก (main.py) ต้องห่อด้วย root.after(0, ...) เอง
"""

import ctypes
import logging
import re
import sys
import threading
from ctypes import wintypes
from typing import Callable, Dict, Optional

log = logging.getLogger("quicknote.hotkey")

_WM_HOTKEY, _WM_QUIT = 0x0312, 0x0012
_MOD_ALT, _MOD_CONTROL, _MOD_SHIFT, _MOD_WIN, _MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
_MODIFIERS = {"alt": _MOD_ALT, "ctrl": _MOD_CONTROL, "shift": _MOD_SHIFT, "cmd": _MOD_WIN}

# ชื่อแป้นแบบ pynput ที่หน้า Settings บันทึก (ดู key_token ใน settings_window.py) → virtual-key code
_NAMED_VK = {
    "space": 0x20, "enter": 0x0D, "tab": 0x09, "backspace": 0x08, "delete": 0x2E, "insert": 0x2D,
    "home": 0x24, "end": 0x23, "page_up": 0x21, "page_down": 0x22,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
}
_OEM_VK = {";": 0xBA, "=": 0xBB, ",": 0xBC, "-": 0xBD, ".": 0xBE, "/": 0xBF, "`": 0xC0,
           "[": 0xDB, "\\": 0xDC, "]": 0xDD, "'": 0xDE}
_FKEY = re.compile(r"f(\d{1,2})")


def parse_hotkey(combo: str) -> tuple[int, int]:
    """'<ctrl>+<alt>+n' → (modifiers, vk); รูปแบบผิด/ไม่มี modifier/ไม่รู้จักแป้น → ValueError"""
    mods, vk = 0, None
    for raw in str(combo).strip().lower().split("+"):
        tok = raw.strip()
        word = tok[1:-1] if tok.startswith("<") and tok.endswith(">") and len(tok) > 2 else None
        if word in _MODIFIERS:
            mods |= _MODIFIERS[word]
            continue
        if vk is not None:
            raise ValueError(f"more than one key in {combo!r}")
        if word is not None:
            m = _FKEY.fullmatch(word)
            if m and 1 <= int(m.group(1)) <= 24:
                vk = 0x6F + int(m.group(1))
            elif word in _NAMED_VK:
                vk = _NAMED_VK[word]
        elif len(tok) == 1 and ("a" <= tok <= "z" or "0" <= tok <= "9"):
            vk = ord(tok.upper())  # VK ของ A-Z / 0-9 เท่ากับรหัส ASCII ตัวพิมพ์ใหญ่
        elif tok in _OEM_VK:
            vk = _OEM_VK[tok]
        if vk is None:
            raise ValueError(f"unknown key {tok!r} in {combo!r}")
    if vk is None or not mods & (_MOD_ALT | _MOD_CONTROL | _MOD_WIN):
        raise ValueError(f"hotkey needs a key and Ctrl/Alt/Win: {combo!r}")
    return mods, vk


class HotkeyListener:
    """ลงทะเบียนคีย์ลัดทั้งระบบบน thread ของตัวเอง (RegisterHotKey ผูกกับ thread ที่เรียก จึงต้องมี message loop ที่นั่น)"""

    def __init__(self, hotkeys_config: Dict[str, str], on_hotkey: Callable[[str], None]):
        """
        Args:
            hotkeys_config: dict ของ { "name": "<ctrl>+<alt>+key", ... }
            on_hotkey: callback func(hotkey_name) เมื่อกดลัด
        """
        self.on_hotkey = on_hotkey
        self.config = hotkeys_config
        self._thread: Optional[threading.Thread] = None
        self._thread_id = 0
        self._ready = threading.Event()
        self._ok = False

    def start(self) -> bool:
        """คืน False ถ้าคีย์ลัดรูปแบบผิด หรือถูกโปรแกรมอื่นจองไปแล้ว (ผู้เรียกจะได้แจ้งผู้ใช้ได้)"""
        if sys.platform != "win32":
            return False
        try:
            parsed = {name: parse_hotkey(combo) for name, combo in self.config.items()}
        except ValueError as e:
            log.warning("invalid hotkey: %s", e)
            return False
        self._ready.clear()
        self._thread = threading.Thread(target=self._loop, args=(parsed,), daemon=True, name="qn-hotkeys")
        self._thread.start()
        if not self._ready.wait(3.0) or not self._ok:
            self.stop()
            return False
        return True

    def _loop(self, parsed: Dict[str, tuple[int, int]]) -> None:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        self._thread_id = kernel32.GetCurrentThreadId()
        ids: Dict[int, str] = {}
        try:
            try:
                for i, (name, (mods, vk)) in enumerate(parsed.items(), start=1):
                    if not user32.RegisterHotKey(None, i, mods | _MOD_NOREPEAT, vk):
                        log.warning("cannot register hotkey %s (%s): Win32 error %s", name, self.config[name],
                                    ctypes.get_last_error())
                        return
                    ids[i] = name
                self._ok = True
            finally:
                self._ready.set()
            msg = wintypes.MSG()
            while self._ok and user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == _WM_HOTKEY and msg.wParam in ids:
                    try:
                        self.on_hotkey(ids[msg.wParam])
                    except Exception:
                        log.exception("hotkey callback failed")
        finally:
            for i in ids:
                user32.UnregisterHotKey(None, i)  # ต้องยกเลิกบน thread เดียวกับที่ลงทะเบียน (รวมกรณีลงทะเบียนไม่ครบ)

    def stop(self) -> None:
        """หยุดฟัง — เรียกซ้ำได้"""
        thread, self._thread = self._thread, None
        if thread is None:
            return
        self._ok = False
        if self._thread_id:
            ctypes.WinDLL("user32").PostThreadMessageW(self._thread_id, _WM_QUIT, 0, 0)
        thread.join(timeout=2.0)


def create_default_hotkeys() -> Dict[str, str]:
    """สร้างค่าเริ่มต้นของคีย์ลัด"""
    return {
        "new_note": "<ctrl>+<alt>+n",
        "toggle_show": "<ctrl>+<alt>+s",
    }


def start_hotkey_listener(config: Dict[str, str], on_hotkey: Callable[[str], None]) -> Optional[HotkeyListener]:
    """เปิด global hotkey listener — ลงทะเบียนไม่ได้คืน None"""
    listener = HotkeyListener(config, on_hotkey)
    return listener if listener.start() else None
