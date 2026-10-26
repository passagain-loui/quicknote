"""QuickNote data models — Note dataclass + SQLite serialization"""

from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional

PRIORITIES = ("none", "low", "medium", "high")
COLORS = ("none", "yellow", "green", "pink", "purple", "blue", "gray")
REPEATS = ("none", "daily", "weekdays", "weekly")


def _enum(value, allowed: tuple, default: str = "none") -> str:
    """ค่าใน DB ที่เพี้ยนต้องไม่ทำให้ UI พัง — ตกกลับเป็น default"""
    return value if value in allowed else default


@dataclass
class Note:
    """โน้ตเดียว — database row model"""
    id: str
    title: str
    content: str = ""
    status: str = "active"  # 'active' | 'completed'
    collapsed: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    completed_at: Optional[str] = None
    priority: str = "none"  # 'none' | 'low' | 'medium' | 'high'
    reminder_datetime: Optional[str] = None  # local "YYYY-MM-DD HH:MM"
    reminder_triggered: bool = False  # True = กำลังดัง (รอ dismiss/snooze)
    is_pinned: bool = False
    color: str = "none"  # v3.0.0: ดู COLORS
    reminder_repeat: str = "none"  # v3.0.0: ดู REPEATS
    deleted_at: Optional[str] = None  # v3.0.0: soft delete (รอ Undo / purge)

    def to_dict(self) -> dict:
        """แปลงเป็น dict สำหรับส่งเข้า database"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Note":
        """สร้าง Note จาก dict (จาก database) — ทนข้อมูลเพี้ยนได้"""
        return cls(
            id=data.get("id", ""),
            title=data.get("title", "") or "",
            content=data.get("content", "") or "",
            status=_enum(data.get("status"), ("active", "completed"), "active"),
            # H4: อ่านตามจริงจาก DB — เดิมบังคับ True ทำให้สถานะกางหาย
            collapsed=bool(data.get("collapsed", False)),
            created_at=data.get("created_at") or datetime.now().isoformat(timespec="seconds"),
            completed_at=data.get("completed_at"),
            priority=_enum(data.get("priority"), PRIORITIES),
            reminder_datetime=data.get("reminder_datetime"),
            reminder_triggered=bool(data.get("reminder_triggered", False)),
            is_pinned=bool(data.get("is_pinned", False)),
            color=_enum(data.get("color"), COLORS),
            reminder_repeat=_enum(data.get("reminder_repeat"), REPEATS),
            deleted_at=data.get("deleted_at"),
        )

    def mark_done(self) -> None:
        """ทำเครื่องหมายว่าเสร็จแล้ว"""
        self.status = "completed"
        self.completed_at = datetime.now().isoformat(timespec="seconds")

    def mark_active(self) -> None:
        """ยกเลิกการเสร็จสิ้น"""
        self.status = "active"
        self.completed_at = None

    def toggle_collapse(self) -> None:
        """สลับสถานะพับ/กาง"""
        self.collapsed = not self.collapsed
