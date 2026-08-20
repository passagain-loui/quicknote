"""QuickNote data models — Note dataclass + SQLite serialization"""

from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional


@dataclass
class Note:
    """โน้ตเดียว — database row model"""
    id: str
    title: str
    content: str = ""
    status: str = "active"  # 'active' | 'completed'
    collapsed: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    priority: str = "none"  # 'none' | 'low' | 'medium' | 'high' (v1.3.0)
    reminder_datetime: Optional[str] = None  # ISO format: "YYYY-MM-DD HH:MM" (v1.3.0)
    reminder_triggered: bool = False  # Track if reminder was shown (v1.3.0)
    is_pinned: bool = False  # Pin note to top of list (v1.5.0)

    def to_dict(self) -> dict:
        """แปลงเป็น dict สำหรับส่งเข้า database"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Note":
        """สร้าง Note จาก dict (จาก database) — ทนข้อมูลเพี้ยนได้"""
        # สกัดฟิลด์ที่คาดหวัง ปฏิเสธอันที่เหลือ
        # v2.8.2: Default new notes to collapsed=True (closed state)
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            content=data.get("content", ""),
            status=data.get("status", "active"),
            collapsed=bool(data.get("collapsed", True)),  # v2.8.2: Default True (collapsed)
            created_at=data.get("created_at", datetime.now().isoformat()),
            completed_at=data.get("completed_at"),
            priority=data.get("priority", "none"),  # v1.3.0
            reminder_datetime=data.get("reminder_datetime"),  # v1.3.0
            reminder_triggered=bool(data.get("reminder_triggered", False)),  # v1.3.0
            is_pinned=bool(data.get("is_pinned", False)),  # v1.5.0
        )

    def mark_done(self) -> None:
        """ทำเครื่องหมายว่าเสร็จแล้ว"""
        self.status = "completed"
        self.completed_at = datetime.now().isoformat()

    def mark_active(self) -> None:
        """ยกเลิกการเสร็จสิ้น"""
        self.status = "active"
        self.completed_at = None

    def toggle_collapse(self) -> None:
        """สลับสถานะพับ/กาง"""
        self.collapsed = not self.collapsed
