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

    def to_dict(self) -> dict:
        """แปลงเป็น dict สำหรับส่งเข้า database"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Note":
        """สร้าง Note จาก dict (จาก database) — ทนข้อมูลเพี้ยนได้"""
        # สกัดฟิลด์ที่คาดหวัง ปฏิเสธอันที่เหลือ
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            content=data.get("content", ""),
            status=data.get("status", "active"),
            collapsed=bool(data.get("collapsed", False)),
            created_at=data.get("created_at", datetime.now().isoformat()),
            completed_at=data.get("completed_at"),
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
