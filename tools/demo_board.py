"""Demo ของหน้าต่างหลัก (Board จริง + DB ชั่วคราว + toast จำลอง) — แคปภาพทุกสถานะออกมาตรวจ

รัน:  python tools/demo_board.py [โฟลเดอร์เก็บภาพ]
ภาพ: board_light / board_dark / board_expanded / board_completed / board_empty / board_compact / board_en
     + board_hover / board_scrolled / board_search (.png)
"""

from __future__ import annotations

import ctypes
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from demo_foundation import DEFAULT_OUT, shoot  # noqa: E402

from src.core import database as db  # noqa: E402
from src.core import settings as settings_mod  # noqa: E402
from src.core.reminders import FMT  # noqa: E402
from src.ui import strings  # noqa: E402
from src.ui.board import Board  # noqa: E402
from src.ui.theme import Theme  # noqa: E402
from tests.v3.board_base import FakeToasts  # noqa: E402


def fmt(dt: datetime) -> str:
    return dt.strftime(FMT)


def seed() -> dict[str, str]:
    """โน้ตตัวอย่างครบทุกสถานะ → คืน id ตามชื่อเรียก"""
    now = datetime.now()
    soon = now + timedelta(hours=2)
    if soon.date() != now.date():
        soon = now + timedelta(minutes=20)
    ids: dict[str, str] = {}

    def add(key: str, title: str, content: str = "", **fields) -> None:
        nid = db.create_note(title, content)
        ids[key] = nid
        if fields:
            db.update_fields(nid, **fields)
        # created_at ละเอียดระดับวินาที → กำหนดเองให้ลำดับ "ใหม่สุดก่อน" คงที่โดยไม่ต้องรอ
        conn = sqlite3.connect(os.environ["DB_PATH"])
        conn.execute("UPDATE notes SET created_at = ? WHERE id = ?",
                     ((now - timedelta(minutes=100 - len(ids))).isoformat(timespec="seconds"), nid))
        conn.commit()
        conn.close()

    add("plain", "ทดสอบภาษาไทย ผู้ใหญ่ ที่ปรึกษา ปั้นจั่น", "ตรวจสระบนและวรรณยุกต์ไม่ขาด")
    add("long", "รายงานผลการดำเนินงานประจำไตรมาสที่สามของปีงบประมาณ ๒๕๖๙ ฝ่ายขายและการตลาด",
        "ตัวเลขยอดขายรายเดือน", color="blue")
    add("gray", "โทรหาลูกค้า", color="gray", priority="low")
    add("purple", "อ่านหนังสือ Atomic Habits", color="purple")
    add("pink", "ซื้อของขวัญวันเกิดแม่", "เค้กช็อกโกแลต · ดอกไม้", color="pink", priority="medium")
    add("overdue", "ส่งรายงานภาษี", "เอกสาร ภ.ง.ด.90")
    add("green", "ออกกำลังกาย 30 นาที", color="green")
    add("shop", "ซื้อของเข้าบ้าน", "นม ไข่ ขนมปัง", priority="medium", color="yellow")
    add("ring", "ประชุมทีมขาย", "เตรียมสไลด์ยอดขาย Q3")
    add("meeting", "ประชุมทีม Marketing", "เตรียมสไลด์ยอดขาย Q3\n- ตัวเลขรายเดือน\n- เปรียบเทียบกับปีก่อน",
        priority="high", is_pinned=True)
    add("done", "ปิดบัญชีเดือนที่แล้ว", "เสร็จเรียบร้อย")

    db.set_reminder(ids["meeting"], fmt(soon))
    db.set_reminder(ids["shop"], fmt((now + timedelta(days=1)).replace(hour=9, minute=0)))
    db.set_reminder(ids["overdue"], fmt((now - timedelta(days=1)).replace(hour=17, minute=0)))
    db.set_reminder(ids["ring"], fmt(now - timedelta(minutes=10)))
    db.mark_ringing(ids["ring"])
    db.set_status(ids["done"], "completed")
    return ids


def main() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
    out = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUT
    os.makedirs(out, exist_ok=True)

    tmp = Path(tempfile.mkdtemp(prefix="qn_demo_board_"))
    old_env = os.environ.get("DB_PATH")
    os.environ["DB_PATH"] = str(tmp / "notes.db")
    db.APP_DIR = tmp
    settings_mod.SETTINGS_FILE = tmp / "settings.json"
    db.init_db()
    ids = seed()

    root = tk.Tk()
    settings = settings_mod.Settings()
    settings.load()
    settings.set("theme", "light", save=False)
    strings.set_language("th")
    theme = Theme(root, settings)
    toasts = FakeToasts()
    board = Board(root, settings, theme, toasts)
    board.scheduler.stop()  # ไม่ให้ alarm ตัวอย่างถูกจัดการระหว่างแคปภาพ
    root.update()

    def snap(name: str, wait: float = 0.3) -> None:
        root.update()
        time.sleep(wait)
        shoot(root, os.path.join(out, name))

    snap("board_light.png")

    # hover (ปุ่ม 🕐 ⋯ ลอยทับ) + focus ring ของอีกใบ + เลื่อนลงล่างสุด (ดูข้อความไทยท้ายรายการ)
    board.note_cards[ids["shop"]]._on_enter()
    board.note_cards[ids["pink"]].focus_force()
    snap("board_hover.png")
    board.note_cards[ids["shop"]]._hover = False
    board._canvas.yview_moveto(1.0)
    snap("board_scrolled.png")
    board._canvas.yview_moveto(0.0)

    board._search.set_value("ประชุม")
    snap("board_search.png", wait=0.6)
    board._clear_search()

    settings.set("theme", "dark", save=False)
    root.update()
    snap("board_dark.png")

    board._on_request_expand(ids["meeting"])
    snap("board_expanded.png")
    board._expanded_card().collapse()

    settings.set("theme", "light", save=False)
    board._select_tab("completed")
    snap("board_completed.png")

    board._select_tab("active")
    settings.set("compact", True, save=False)
    snap("board_compact.png")
    settings.set("compact", False, save=False)

    settings.set("language", "en", save=False)
    snap("board_en.png")
    settings.set("language", "th", save=False)

    for nid in ids.values():
        db.soft_delete(nid)
    board.refresh(immediate=True)
    snap("board_empty.png")

    root.destroy()
    shutil.rmtree(tmp, ignore_errors=True)
    if old_env is None:
        os.environ.pop("DB_PATH", None)
    else:
        os.environ["DB_PATH"] = old_env


if __name__ == "__main__":
    main()
