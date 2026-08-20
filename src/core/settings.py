"""Settings management — geometry, theme, hotkeys เก็บไว้ที่ ~/.quicknote/settings.json"""

import json
from pathlib import Path
from .database import APP_DIR


SETTINGS_FILE = APP_DIR / "settings.json"

DEFAULTS = {
    "geometry": "400x600+100+100",  # WxH+X+Y format
    "theme": "light",
    "alpha": 1.0,
    "always_on_top": True,
    "hotkeys": {
        "new_note": "<ctrl>+<alt>+n",
        "toggle_show": "<ctrl>+<alt>+s",
    }
}


class Settings:
    """โหลด/เซฟค่าตั้งตั้งแต่ JSON — ทนค่าผิดประเภทได้"""

    def __init__(self):
        self.data = DEFAULTS.copy()

    def load(self) -> None:
        """อ่านไฟล์ settings — ไม่เจอให้ใช้ค่าเริ่มต้น"""
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self.data.update(loaded)
            except Exception:
                # JSON พัง ให้ใช้ default เลย
                self.data = DEFAULTS.copy()
        self._coerce()

    def save(self) -> None:
        """เขียนค่าตั้งลงไฟล์"""
        APP_DIR.mkdir(exist_ok=True)
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception:
            pass  # บันทึกไม่ได้ก็ปล่อยไป ไม่ใช่ fatal

    def _coerce(self) -> None:
        """ป้องกันค่าผิด — clamp alpha, validate theme, reset bad geometry"""
        # Alpha: 0.3–1.0 (ไม่ให้ต่ำเกินมองไม่เห็น)
        if "alpha" not in self.data:
            self.data["alpha"] = 1.0
        try:
            alpha = float(self.data.get("alpha", 1.0))
            # ถ้า alpha <= 0 ให้เป็น 1.0 แทน (ป้องกันหน้าต่างมองไม่เห็นเลย)
            if alpha <= 0:
                self.data["alpha"] = 1.0
            else:
                self.data["alpha"] = max(0.3, min(1.0, alpha))
        except (TypeError, ValueError):
            self.data["alpha"] = 1.0

        # Theme: light | dark
        if "theme" not in self.data:
            self.data["theme"] = "light"
        if self.data["theme"] not in ("light", "dark"):
            self.data["theme"] = "light"

        # Geometry: validate format WxH+X+Y
        if "geometry" not in self.data:
            self.data["geometry"] = DEFAULTS["geometry"]

    def get(self, key: str, default=None):
        """ดึงค่า — เช่น settings.get("theme")"""
        return self.data.get(key, default)

    def set(self, key: str, value) -> None:
        """ตั้งค่า"""
        self.data[key] = value
