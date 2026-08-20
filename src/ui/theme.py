"""QuickNote theme — macOS Pastel สี + Tk fonts"""

from typing import Literal


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

THEMES = {
    "light": {
        "bg": "#FAFAFA",           # Very light gray
        "fg": "#1F1F1F",           # Dark text
        "fg_muted": "#999999",     # Muted gray (for footer/credits)
        "bg_hover": "#F0F0F0",     # Hover state
        "border": "#E5E5E5",       # Soft border
        "accent": "#007AFF",       # iOS blue
        "note_bg": "#FFFFFF",      # White cards
        "note_border": "#E8E8E8",  # Subtle border
        "scrollbar": "#D0D0D0",
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
        "scrollbar": "#545456",
    },
}

PALETTE = PASTEL_PALETTE


class Theme:
    """โอเปอเรเตอร์สีสำหรับหน้าต่าง"""

    def __init__(self, mode: Literal["light", "dark"] = "light"):
        self.mode = mode
        self._colors = THEMES[mode]

    def c(self, key: str) -> str:
        """ดึงสี — เช่น theme.c('bg')"""
        return self._colors.get(key, "#000000")

    def palette(self, name: str) -> str:
        """ดึงจานสี — เช่น theme.palette('yellow')"""
        return PALETTE.get(name, "#999999")

    def set_mode(self, mode: Literal["light", "dark"]) -> None:
        """เปลี่ยนธีมตอนโปรแกรมทำงาน"""
        self.mode = mode
        self._colors = THEMES[mode]

    def to_dict(self) -> dict:
        """ส่งออก theme config สำหรับบันทึก settings"""
        return {
            "mode": self.mode,
            "font_ui": FONT_UI,
            "font_mono": FONT_MONO,
            "font_title": FONT_TITLE,
        }
