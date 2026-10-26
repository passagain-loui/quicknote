"""Settings management — เก็บที่ ~/.quicknote/settings.json (สัญญา: docs/v3/ARCHITECTURE.md ข้อ 3)"""

import copy
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Callable

from .constants import MIN_ALPHA
from .database import APP_DIR, get_app_dir

log = logging.getLogger("quicknote.settings")

SETTINGS_FILE = APP_DIR / "settings.json"

DEFAULTS = {
    "geometry": "380x600+120+120",  # WxH+X+Y
    "theme": "system",              # light|dark|system
    "language": "th",
    "font_size": "normal",          # small|normal|large
    "compact": False,
    "alpha": 1.0,
    "always_on_top": True,
    "close_to_tray": True,
    "tray_hint_shown": False,
    "sound": True,
    "snooze_default_minutes": 5,    # 5|10|15|30|60
    "auto_backup": True,
    "last_auto_backup": "",
    "hotkeys": {
        "new_note": "<ctrl>+<alt>+n",
        "toggle_show": "<ctrl>+<alt>+s",
    },
}

_ENUMS = {
    "theme": ("light", "dark", "system"),
    "language": ("th", "en"),
    "font_size": ("small", "normal", "large"),
    "snooze_default_minutes": (5, 10, 15, 30, 60),
}
_BOOLS = ("compact", "always_on_top", "close_to_tray", "tray_hint_shown", "sound", "auto_backup")


def _settings_file() -> Path:
    """QUICKNOTE_HOME (ถ้าตั้ง) ต้องชี้ settings.json ไปโฟลเดอร์เดียวกับ DB — ไม่งั้นรันเทสแล้วไปเขียนทับค่าจริงของผู้ใช้"""
    if os.environ.get("QUICKNOTE_HOME"):
        return get_app_dir() / "settings.json"
    return SETTINGS_FILE


def _bak_path() -> Path:
    return Path(str(_settings_file()) + ".bak")


def _coerce_value(key: str, value):
    """บังคับค่าให้ถูกชนิด/ช่วง — ค่าผิดตกกลับเป็น default (ไม่ raise)"""
    default = DEFAULTS.get(key)
    if key in _ENUMS:
        if key == "snooze_default_minutes":
            try:
                value = int(value)
            except (TypeError, ValueError):
                return default
        return value if value in _ENUMS[key] else default
    if key in _BOOLS:
        if isinstance(value, bool):
            return value
        return bool(value) if value in (0, 1) else default
    if key == "alpha":
        try:
            alpha = float(value)
        except (TypeError, ValueError):
            return default
        if alpha != alpha:  # NaN
            return default
        return max(MIN_ALPHA, min(1.0, alpha))
    if key in ("geometry", "last_auto_backup"):
        return value if isinstance(value, str) and (value or key == "last_auto_backup") else default
    if key == "hotkeys":
        merged = copy.deepcopy(default)
        if isinstance(value, dict):
            for name, combo in value.items():
                if isinstance(combo, str) and combo.strip():
                    merged[name] = combo
        return merged
    return value  # key ที่ไม่รู้จัก (forward compat) ปล่อยผ่าน


def _read_json(path: Path):
    """อ่านไฟล์ settings — คืน dict หรือ None ถ้าไม่มี/พัง"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        return loaded if isinstance(loaded, dict) else None
    except (OSError, ValueError):
        return None


class Settings:
    """โหลด/เซฟค่าตั้งจาก JSON — ทนไฟล์พัง, เขียนแบบ atomic, แจ้ง listener เมื่อค่าเปลี่ยน"""

    def __init__(self):
        self.data: dict = copy.deepcopy(DEFAULTS)  # L7: shallow copy ทำให้ hotkeys ใช้ร่วมกับ DEFAULTS
        self._listeners: list[Callable[[str, object], None]] = []

    def load(self) -> None:
        """ไฟล์หลักพัง → ลอง .bak → DEFAULTS"""
        path = _settings_file()
        loaded = _read_json(path)
        if loaded is None:
            loaded = _read_json(_bak_path())
            if loaded is not None:
                log.warning("settings.json unreadable/missing; restored from .bak")
        self.data = copy.deepcopy(DEFAULTS)
        if loaded:
            self.data.update(copy.deepcopy(loaded))
        self._coerce()

    def save(self) -> None:
        """atomic: tmp → fsync → สำรองไฟล์เดิมเป็น .bak → os.replace (ไฟดับกลางคันไม่ทำไฟล์เสีย)"""
        path = _settings_file()
        tmp = Path(str(path) + ".tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            # สำรองเฉพาะไฟล์เดิมที่ยังอ่านได้ ไม่งั้น .bak ดี ๆ จะถูกทับด้วยไฟล์เสีย
            if path.exists() and _read_json(path) is not None:
                shutil.copy2(path, _bak_path())
            os.replace(tmp, path)
        except OSError as e:
            log.error("cannot save settings: %s", e)  # บันทึกไม่ได้ไม่ใช่ fatal
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    def _coerce(self) -> None:
        for key in DEFAULTS:
            self.data[key] = _coerce_value(key, self.data.get(key, DEFAULTS[key]))

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value, save: bool = True) -> None:
        """ตั้งค่า — บันทึก/แจ้ง listener เฉพาะเมื่อค่าเปลี่ยนจริง"""
        value = _coerce_value(key, value)
        if key in self.data and self.data[key] == value:
            return
        self.data[key] = copy.deepcopy(value)
        if save:
            self.save()
        for cb in list(self._listeners):
            try:
                cb(key, value)
            except Exception:
                log.exception("settings listener failed for %s", key)

    def subscribe(self, cb: Callable[[str, object], None]) -> None:
        self._listeners.append(cb)

    def unsubscribe(self, cb: Callable[[str, object], None]) -> None:
        """หน้าต่างที่ปิดแล้วต้องถอด listener ออก ไม่งั้นค้างอยู่ใน list ตลอดอายุแอป"""
        try:
            self._listeners.remove(cb)
        except ValueError:
            pass
