"""Reminder helpers — คำนวณรอบถัดไป, จัดรูปแบบเวลาแสดงผล, ปุ่มลัดเวลา (ไม่ import tkinter/ui)"""

from datetime import datetime, timedelta
from typing import Optional

FMT = "%Y-%m-%d %H:%M"

# ชื่อวัน/เดือนอยู่ที่นี่ เพราะ core ห้าม import ui (index ตาม datetime.weekday(): จันทร์=0)
_TH_DAYS = ("จ.", "อ.", "พ.", "พฤ.", "ศ.", "ส.", "อา.")
_TH_MONTHS = ("ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
              "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.")
_EN_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_EN_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def parse_dt(value: str) -> datetime:
    """'YYYY-MM-DD HH:MM' → datetime (raise ValueError ถ้ารูปแบบผิด)"""
    return datetime.strptime(value, FMT)


def format_dt(value: datetime) -> str:
    return value.strftime(FMT)


def next_occurrence(when: str, repeat: str, now: Optional[datetime] = None) -> str:
    """รอบถัดไปที่เลยทั้ง now และ when — ข้ามรอบที่พลาดไป (เปิดเครื่องหลังหยุดหลายวัน)

    repeat='none' หรือค่าไม่รู้จัก → คืน when เดิม (ไม่มีรอบถัดไป)
    weekdays = จันทร์–ศุกร์ (ศุกร์ → จันทร์)
    """
    if repeat not in ("daily", "weekdays", "weekly"):
        return when
    now = now or datetime.now()
    base_dt = parse_dt(when)
    # ต้อง > ทั้ง now และรอบเดิม ไม่งั้น dismiss ก่อนเวลาจะได้ค่าเดิมกลับมาแล้วดังซ้ำ
    floor = max(now, base_dt)
    cand = datetime.combine(floor.date(), base_dt.time())

    if repeat == "weekly":
        # ขยับไปวันเดียวกับ when ในสัปดาห์ แล้วเดินทีละ 7 วันจนพ้น floor
        cand += timedelta(days=(base_dt.weekday() - cand.weekday()) % 7)
        while cand <= floor:
            cand += timedelta(days=7)
    else:
        while cand <= floor or (repeat == "weekdays" and cand.weekday() >= 5):
            cand += timedelta(days=1)
    return format_dt(cand)


def _day_label(d: datetime, lang: str) -> str:
    if lang == "en":
        return f"{_EN_DAYS[d.weekday()]} {d.day} {_EN_MONTHS[d.month - 1]}"
    return f"{_TH_DAYS[d.weekday()]} {d.day} {_TH_MONTHS[d.month - 1]}"


def format_reminder(when: str, now: datetime, lang: str) -> tuple[str, bool]:
    """ข้อความเวลาเตือนสำหรับแสดงบนการ์ด → (ข้อความ, is_overdue)"""
    try:
        dt = parse_dt(when)
    except (ValueError, TypeError):
        return (str(when or ""), False)

    en = lang == "en"
    hm = dt.strftime("%H:%M")
    today = now.date()

    if dt < now:
        label = "Overdue" if en else "เลยกำหนด"
        # เลยมาคนละวัน เวลาอย่างเดียวกำกวม → ต่อด้วยวันที่
        if dt.date() != today:
            return (f"{label} {_day_label(dt, lang)} {hm}", True)
        return (f"{label} {hm}", True)

    if dt.date() == today:
        return (f"{'Today' if en else 'วันนี้'} {hm}", False)
    if dt.date() == today + timedelta(days=1):
        return (f"{'Tomorrow' if en else 'พรุ่งนี้'} {hm}", False)
    return (f"{_day_label(dt, lang)} {hm}", False)


def quick_times(now: datetime) -> dict[str, Optional[str]]:
    """ปุ่มลัดใน ReminderDialog — this_evening เป็น None เมื่อ 17:00 ผ่านไปแล้ว"""
    base = now.replace(second=0, microsecond=0)
    evening = base.replace(hour=17, minute=0)
    tomorrow = (base + timedelta(days=1)).replace(hour=9, minute=0)
    return {
        "in15m": format_dt(base + timedelta(minutes=15)),
        "in1h": format_dt(base + timedelta(hours=1)),
        "this_evening": format_dt(evening) if evening > now else None,
        "tomorrow_9": format_dt(tomorrow),
    }
