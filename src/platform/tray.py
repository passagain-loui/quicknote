"""System tray — ไอคอนเดียว (pystray) คลิกซ้าย = แสดง/ซ่อน

THREADING: callback ทุกตัว (on_toggle/on_new_note/on_settings/on_quit) ถูกเรียกจาก thread ของ pystray
ไม่ใช่ Tk main thread — ผู้เรียก (main.py) ต้องห่อด้วย `root.after(0, ...)` เอง
ไฟล์นี้ไม่แตะ Tk เลย (platform layer) เพื่อไม่ให้มีทางเผลอสร้าง widget ข้าม thread
"""

from __future__ import annotations

import itertools
import logging
import sys
import threading
from pathlib import Path
from typing import Callable

import pystray
from PIL import Image, ImageDraw

from ..ui.strings import t

log = logging.getLogger(__name__)

_TIP_LIMIT = 127  # NOTIFYICONDATA.szTip เก็บได้ 128 ตัวอักษรรวม NUL
_seq = itertools.count()  # pystray ลงทะเบียน window class ด้วยชื่อ+id(self) → id ซ้ำหลัง GC ทำให้ "Class already exists"
_ACTIVE: "TrayIcon | None" = None  # กันสร้างไอคอนซ้ำถ้า start_tray_thread ถูกเรียกสองครั้ง (M14)


def _asset(rel: str) -> Path:
    """หาไฟล์ใน assets/ ทั้งตอนรันจาก source และตอนเป็น .exe (PyInstaller แตกไว้ที่ sys._MEIPASS)"""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base / rel


def _small_icon_px() -> int:
    """ขนาดไอคอนถาดที่ระบบต้องการ (SM_CXSMICON) — เลือกเฟรมจาก .ico ให้ตรงเพื่อไม่ต้องย่อรูปจนเบลอที่ DPI สูง"""
    try:
        import ctypes
        return int(ctypes.windll.user32.GetSystemMetrics(49)) or 16
    except Exception:
        return 16


def _draw_fallback(size: int = 64) -> Image.Image:
    """ไอคอนสำรองที่วาดเอง (กระดาษโน้ตเหลืองพับมุม) ใช้เมื่อหา/อ่าน assets/icon.ico ไม่ได้"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m, fold = size // 8, size // 4
    d.polygon([(m, m), (size - m, m), (size - m, size - m - fold), (size - m - fold, size - m), (m, size - m)],
              fill="#FFD93B", outline="#C9A400")
    d.polygon([(size - m - fold, size - m), (size - m, size - m - fold), (size - m - fold, size - m - fold)],
              fill="#E8B800", outline="#C9A400")
    return img


def load_icon_image() -> Image.Image:
    """โหลด assets/icon.ico เฟรมที่ใกล้ขนาดถาดที่สุด (ไม่เล็กกว่าที่ต้องการ) — พังแล้วใช้ภาพที่วาดเอง"""
    try:
        with Image.open(_asset("assets/icon.ico")) as ico:
            sizes = sorted(s[0] for s in ico.info.get("sizes", {(ico.width, ico.height)}))
            want = _small_icon_px()
            pick = next((s for s in sizes if s >= want), sizes[-1])
            ico.size = (pick, pick)
            return ico.convert("RGBA")  # convert โหลดพิกเซลออกมาก่อนไฟล์ถูกปิด
    except Exception as e:
        log.warning("cannot load tray icon (%s) — using drawn fallback", e)
        return _draw_fallback()


class TrayIcon:
    """ไอคอนถาดระบบ: เมนู แสดง QuickNote (default) · โน้ตใหม่ · ── · ตั้งค่า · ── · ออก"""

    def __init__(self, on_toggle: Callable[[], None], on_new_note: Callable[[], None],
                 on_settings: Callable[[], None], on_quit: Callable[[], None],
                 tooltip: Callable[[], str]) -> None:
        self._on_toggle, self._on_new_note = on_toggle, on_new_note
        self._on_settings, self._on_quit = on_settings, on_quit
        self._tooltip = tooltip
        self._started = False
        self._stopped = False
        self._lock = threading.Lock()
        self.icon = pystray.Icon(f"quicknote{next(_seq)}", load_icon_image(), self._tooltip_text(), self._build_menu())

    # ---------------------------------------------------------------- menu
    def _safe(self, fn: Callable[[], None]) -> Callable[[], None]:
        """callback พังต้องไม่ฆ่า thread ของ pystray (ไม่งั้นไอคอนค้างอยู่แต่คลิกไม่ได้อีก)"""
        def run() -> None:
            try:
                fn()
            except Exception:
                log.exception("tray callback failed")
        return run

    def _build_menu(self) -> pystray.Menu:
        # text เป็น callable → pystray อ่านข้อความใหม่ทุกครั้งที่สร้างเมนู จึงตามภาษาปัจจุบันของ t() เสมอ
        def item(key: str, action: Callable[[], None], default: bool = False) -> pystray.MenuItem:
            return pystray.MenuItem(lambda _item, k=key: t(k), self._safe(action), default=default)

        return pystray.Menu(
            item("tray.show", lambda: self._on_toggle(), default=True),  # default = คลิกซ้ายที่ไอคอน (M15)
            item("tray.new_note", lambda: self._on_new_note()),
            pystray.Menu.SEPARATOR,
            item("tray.settings", lambda: self._on_settings()),
            pystray.Menu.SEPARATOR,
            item("tray.quit", lambda: self._on_quit()),
        )

    def update_menu_language(self) -> None:
        """เปลี่ยนภาษาแล้วให้เมนูอ่านข้อความใหม่ — ต้องเรียกหลัง set_language()"""
        try:
            self.icon.update_menu()
        except Exception:
            log.debug("tray menu refresh skipped", exc_info=True)

    # ---------------------------------------------------------------- tooltip
    def _tooltip_text(self) -> str:
        try:
            text = str(self._tooltip() or "")
        except Exception:
            log.debug("tray tooltip callback failed", exc_info=True)
            text = ""
        return (text or t("tray.tooltip"))[:_TIP_LIMIT]

    def update_tooltip(self) -> None:
        """อ่าน tooltip() ใหม่แล้วตั้งให้ไอคอน — เรียกจาก main thread ได้ (เช่นทุก tick ของ scheduler)"""
        try:
            self.icon.title = self._tooltip_text()
        except Exception:
            log.debug("tray tooltip update skipped", exc_info=True)

    # ---------------------------------------------------------------- lifecycle
    @property
    def is_running(self) -> bool:
        """ไอคอนโผล่ในถาดจริงอยู่ — ใช้ตัดสินว่าซ่อนหน้าต่างลงถาดได้ปลอดภัยไหม (ถ้า pystray เริ่มไม่ขึ้นจะเป็น False)"""
        return self._started and not self._stopped and bool(self.icon.visible)

    def run(self) -> None:
        """loop ของ pystray (บล็อกจนกว่าจะ stop) — เรียกซ้ำบนอินสแตนซ์เดิมไม่ทำอะไร กันไอคอนซ้อน"""
        with self._lock:
            if self._started:
                return
            self._started = True
        try:
            self.icon.run()
        except Exception:
            log.exception("tray icon loop crashed")

    def stop(self) -> None:
        """ถอดไอคอนออกจากถาด (ปลอดภัยที่จะเรียกซ้ำ/เรียกตอนยังไม่ได้ run)"""
        self._stopped = True
        try:
            self.icon.stop()
        except Exception:
            log.debug("tray stop skipped", exc_info=True)


def start_tray_thread(on_toggle: Callable[[], None], on_new_note: Callable[[], None],
                      on_settings: Callable[[], None], on_quit: Callable[[], None],
                      tooltip: Callable[[], str]) -> TrayIcon:
    """สร้างไอคอนและรันบน daemon thread — ถ้ามีไอคอนทำงานอยู่แล้วคืนตัวเดิม (ไอคอนเดียวเสมอ)"""
    global _ACTIVE
    if _ACTIVE is not None and not _ACTIVE._stopped:
        return _ACTIVE
    tray = TrayIcon(on_toggle, on_new_note, on_settings, on_quit, tooltip)
    threading.Thread(target=tray.run, daemon=True, name="quicknote-tray").start()
    _ACTIVE = tray
    return tray
