"""Export โน้ตเป็น Markdown"""

import logging
import os
from datetime import datetime
from pathlib import Path

from . import database

log = logging.getLogger("quicknote.export")

_REPEAT_LABEL = {
    "th": {"daily": "ทุกวัน", "weekdays": "จันทร์–ศุกร์", "weekly": "ทุกสัปดาห์"},
    "en": {"daily": "daily", "weekdays": "weekdays", "weekly": "weekly"},
}
_TEXT = {
    "th": {"untitled": "(ไม่มีชื่อ)", "reminder": "เตือน", "priority": "ความสำคัญ",
           "pinned": "ปักหมุด", "exported": "ส่งออกเมื่อ"},
    "en": {"untitled": "(untitled)", "reminder": "Reminder", "priority": "Priority",
           "pinned": "Pinned", "exported": "Exported"},
}


def export_markdown(path: str, lang: str = "th") -> bool:
    """เขียนโน้ตทั้งหมด (active ก่อน completed) เป็น Markdown — คืน False ถ้าเขียนไม่สำเร็จ"""
    lang = lang if lang in _TEXT else "th"
    tx = _TEXT[lang]
    try:
        lines = ["# QuickNote", "", f"_{tx['exported']} {datetime.now():%Y-%m-%d %H:%M}_", ""]
        for status, mark in (("active", " "), ("completed", "x")):
            for n in database.get_notes_by_status(status):
                title = " ".join((n.get("title") or "").split()) or tx["untitled"]
                lines += [f"## {title}", "", f"- [{mark}] {title}"]
                if n.get("is_pinned"):
                    lines.append(f"- {tx['pinned']}")
                if n.get("priority") not in (None, "none"):
                    lines.append(f"- {tx['priority']}: {n['priority']}")
                if n.get("reminder_datetime"):
                    rep = _REPEAT_LABEL[lang].get(n.get("reminder_repeat") or "none")
                    lines.append(f"- {tx['reminder']}: {n['reminder_datetime']}" + (f" ({rep})" if rep else ""))
                if (n.get("content") or "").strip():
                    lines += ["", n["content"].rstrip()]
                lines.append("")

        # atomic: เขียน tmp แล้วค่อย replace กันไฟล์ปลายทางเสียกลางคัน
        target = Path(path)
        tmp = target.with_name(target.name + ".tmp")
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
        return True
    except Exception as e:
        log.error("export failed: %s", e)
        return False
