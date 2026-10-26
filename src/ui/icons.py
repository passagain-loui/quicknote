"""ไอคอน Segoe Fluent Icons (Win11) / Segoe MDL2 Assets (Win10) — ตั้งชื่อตามการใช้งาน

ทุก codepoint ตรวจกับ cmap ของ SegoeIcons.ttf และ segmdl2.ttf แล้ว (fonttools) + render ดูจริง
ที่ต่างจาก DESIGN_SPEC 2.4:
  - clock: spec ระบุ U+E917 แต่ MDL2 (Win10) ไม่มี glyph นี้ (กลายเป็นกล่องว่าง)
    → ใช้ U+E823 ซึ่งมีทั้งสองฟอนต์และหน้าตาเหมือนกันใน Fluent
"""

ICONS: dict[str, str] = {
    # --- ตาม spec 2.4 ---
    "add": "\ue710",
    "search": "\ue721",
    "settings": "\ue713",
    "pin": "\ue718",
    "unpin": "\ue77a",
    "topmost": "\ue718",          # ปุ่ม toggle ใน toolbar (สถานะแสดงด้วยพื้น accent)
    "more": "\ue712",
    "clock": "\ue823",
    "calendar": "\ue787",
    "delete": "\ue74d",
    "cancel": "\ue711",
    "circle": "\uea3a",           # CircleRing — งานยังไม่เสร็จ
    "completed": "\uec61",        # CompletedSolid — งานเสร็จแล้ว
    "check": "\ue73e",
    "chevron_down": "\ue70d",
    "chevron_right": "\ue76c",
    "flag": "\ue7c1",
    "color": "\ue790",
    "undo": "\ue7a7",
    # --- เพิ่มเอง (ตรวจแล้วมีทั้ง Fluent และ MDL2) ---
    "chevron_up": "\ue70e",
    "repeat": "\ue8ee",
    "warning": "\ue7ba",
    "info": "\ue946",
    "folder": "\ue8b7",
    "save": "\ue74e",
    "export": "\uede1",
}


def glyph(name: str) -> str:
    """คืนอักษรไอคอน — ชื่อไม่รู้จักคืน '' (ไม่ crash ตอนวาด UI)"""
    return ICONS.get(name, "")
