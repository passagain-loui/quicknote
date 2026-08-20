"""Global Hotkey — pynput keyboard listener"""

import threading
from pynput import keyboard
from typing import Callable, Dict


class HotkeyListener:
    """ฟัง global hotkey — ต้องสั่งงาน GUI ผ่าน root.after(0, callback)"""

    def __init__(self, hotkeys_config: Dict[str, str], on_hotkey: Callable):
        """
        Args:
            hotkeys_config: dict ของ { "name": "<ctrl>+<alt>+key", ... }
            on_hotkey: callback func(hotkey_name) เมื่อกดลัด
        """
        self.on_hotkey = on_hotkey
        self.config = hotkeys_config
        self.listener = None

    def start(self):
        """เปิดฟัง hotkey บน daemon thread"""
        # สร้าง GlobalHotKeys dict
        hotkeys_dict = {}

        for name, key_combo in self.config.items():
            # ตัวอย่าง: "<ctrl>+<alt>+n" → "<ctrl>+<alt>+n"
            hotkeys_dict[key_combo] = lambda n=name: self.on_hotkey(n)

        try:
            self.listener = keyboard.GlobalHotKeys(hotkeys_dict)
            thread = threading.Thread(target=self.listener.start, daemon=True)
            thread.start()
        except Exception as e:
            print(f"[!] Hotkey init failed: {e} — continuing without hotkeys")

    def stop(self):
        """หยุดฟัง hotkey"""
        if self.listener:
            try:
                self.listener.stop()
            except Exception:
                pass


def create_default_hotkeys() -> Dict[str, str]:
    """สร้างค่าเริ่มต้นของคีย์ลัด"""
    return {
        "new_note": "<ctrl>+<alt>+n",
        "toggle_show": "<ctrl>+<alt>+s",
    }


def start_hotkey_listener(config: Dict[str, str], on_hotkey: Callable) -> HotkeyListener:
    """เปิด global hotkey listener"""
    listener = HotkeyListener(config, on_hotkey)
    listener.start()
    return listener
