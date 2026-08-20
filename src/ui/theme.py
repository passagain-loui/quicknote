"""QuickNote theme — macOS Pastel สี + Tk fonts — Centralized Palette (v1.6.0)"""

from typing import Literal, Callable


FONT_UI = ("Segoe UI", 10)           # หลัก (ไทยรองรับดี)
FONT_MONO = ("Consolas", 9)          # code snippets
FONT_TITLE = ("Segoe UI", 11, "bold")


# macOS Traffic Light Control Buttons
CONTROL_RED = "#FF605C"      # Close
CONTROL_YELLOW = "#FFBD44"   # Minimize/Roll-up
CONTROL_GREEN = "#00CA4E"    # New Note

# macOS Pastel Note Colors
PASTEL_PALETTE = {
    "yellow": "#FFF3C4",     # Soft yellow
    "blue": "#D0E8FF",       # Light sky blue
    "mint": "#D1F2D9",       # Soft mint
    "pink": "#FFD6E8",       # Soft pink
    "purple": "#E8D5FF",     # Soft purple
}

# Priority Flag Colors (v1.3.0)
PRIORITY_COLORS = {
    "none": None,                # ใช้สีปกติของธีม
    "low": "#007AFF",           # 🔵 iOS Blue
    "medium": "#FF9500",        # 🟡 iOS Orange
    "high": "#FF3B30",          # 🔴 iOS Red
}

THEMES = {
    "light": {
        "bg": "#F2F2F7",           # ✓ v1.3.5: Off-white (iOS/macOS style, not pure white)
        "fg": "#1F1F1F",           # Dark text
        "fg_muted": "#999999",     # Muted gray (for footer/credits)
        "bg_hover": "#E8E8ED",     # Hover state (slightly darker)
        "border": "#D1D1D6",       # ✓ v1.3.5: Darker border for better contrast
        "accent": "#007AFF",       # iOS blue
        "note_bg": "#FFFFFF",      # White cards (stands out from off-white bg)
        "note_border": "#D1D1D6",  # ✓ v1.3.5: Visible border to separate cards
        "note_border_soft": "#E0E0E5",  # ✓ v1.4.2: Softer border for modern card styling
        "scrollbar": "#C7C7CC",
    },
    "dark": {
        "bg": "#1C1C1E",           # Dark background (macOS dark)
        "fg": "#F5F5F7",           # Light text
        "fg_muted": "#888888",     # Muted gray (for footer/credits)
        "bg_hover": "#2C2C2E",     # Hover state
        "border": "#3A3A3C",       # Dark border
        "accent": "#0A84FF",       # Bright blue for dark
        "note_bg": "#2C2C2E",      # Dark cards
        "note_border": "#3A3A3C",  # Subtle dark border
        "note_border_soft": "#434346",  # ✓ v1.4.2: Softer border for modern card styling (dark)
        "scrollbar": "#545456",
    },
}

PALETTE = PASTEL_PALETTE


class Theme:
    """โอเปอเรเตอร์สีสำหรับหน้าต่าง — v1.6.0: Theme change broadcast"""

    def __init__(self, mode: Literal["light", "dark"] = "light"):
        self.mode = mode
        self._colors = THEMES[mode]
        self._theme_change_listeners: list[Callable] = []  # v1.6.0: real-time theme update

    def c(self, key: str) -> str:
        """ดึงสี — เช่น theme.c('bg')"""
        return self._colors.get(key, "#000000")

    def palette(self, name: str) -> str:
        """ดึงจานสี — เช่น theme.palette('yellow')"""
        return PALETTE.get(name, "#999999")

    def priority_color(self, priority: str) -> str:
        """ดึงสีจาก priority level (v1.3.0) — คืน color or None"""
        return PRIORITY_COLORS.get(priority, None)

    def set_mode(self, mode: Literal["light", "dark"]) -> None:
        """เปลี่ยนธีมตอนโปรแกรมทำงาน — v1.6.0: broadcast to all listeners"""
        self.mode = mode
        self._colors = THEMES[mode]
        self._broadcast_theme_change()  # Notify all listeners

    def register_theme_change_listener(self, callback: Callable) -> None:
        """Register callback for real-time theme updates — v1.6.0"""
        if callback not in self._theme_change_listeners:
            self._theme_change_listeners.append(callback)

    def unregister_theme_change_listener(self, callback: Callable) -> None:
        """Unregister theme change callback — v1.6.0"""
        if callback in self._theme_change_listeners:
            self._theme_change_listeners.remove(callback)

    def _broadcast_theme_change(self) -> None:
        """Notify all listeners of theme change — v1.6.0"""
        for callback in self._theme_change_listeners:
            try:
                callback(self)
            except Exception as e:
                print(f"[Theme] Callback error: {e}")

    def to_dict(self) -> dict:
        """ส่งออก theme config สำหรับบันทึก settings"""
        return {
            "mode": self.mode,
            "font_ui": FONT_UI,
            "font_mono": FONT_MONO,
            "font_title": FONT_TITLE,
        }
