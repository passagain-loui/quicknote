#!/usr/bin/env python3
"""QuickNote v3 — entry point (สัญญา: docs/v3/ARCHITECTURE.md ข้อ 7)

จุดสำคัญ:
  - ทุกทางออก (✕ ตอนไม่มี tray, tray Quit, Esc, exception) ไปจบที่ App.quit_app / App.shutdown เท่านั้น (C3)
  - single instance ใช้ named mutex เป็นตัวล็อก ส่วน socket มีไว้ส่งสัญญาณ "SHOW" อย่างเดียว (L9)
  - thread อื่น (pystray / hotkey / socket) ห้ามแตะ widget — ทุก callback ผ่าน root.after(0, ...)
  - ห้ามลบไฟล์ WAL/SHM หรือโฟลเดอร์ชั่วคราวของใคร (C10)
"""

import argparse
import ctypes
import logging
import os
import shutil
import socket
import sqlite3
import sys
import tempfile
import threading
import tkinter as tk
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from tkinter import messagebox
from typing import Callable, Optional

# DPI awareness — ต้องมาก่อนสร้าง Tk ใด ๆ (Per-Monitor V2 แล้วไล่ถอยลง)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# tkcalendar → babel.numbers: PyInstaller มองไม่เห็นด้วยการวิเคราะห์ static ถ้าไม่ import ตรงนี้
try:
    import babel.numbers  # noqa: F401
    import tkcalendar  # noqa: F401
except ImportError:
    pass

from src.core import database as db  # noqa: E402
from src.core.constants import APP_ID, APP_NAME, APP_VERSION  # noqa: E402
from src.core.reminders import format_reminder  # noqa: E402
from src.core.settings import Settings  # noqa: E402
from src.platform.hotkey import start_hotkey_listener  # noqa: E402
from src.ui import strings, win11  # noqa: E402
from src.ui.board import Board  # noqa: E402
from src.ui.strings import t  # noqa: E402
from src.ui.theme import Theme  # noqa: E402
from src.ui.toast import ToastManager  # noqa: E402

log = logging.getLogger("quicknote.main")

MUTEX_NAME = "Local\\QuickNote.SingleInstance"
SIGNAL_PORT = 29837
_ERROR_ALREADY_EXISTS = 183
SELFTEST_SECONDS = 2.0


# ================================================================ logging
def setup_logging(app_dir: Path) -> None:
    """log file หมุนเวียน 1 MB × 3 + stdout เฉพาะเมื่อมี console (.exe แบบ --noconsole ไม่มี stdout — L10)"""
    root = logging.getLogger()
    if getattr(root, "_quicknote_configured", False):
        return
    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    handlers: list[logging.Handler] = []
    try:
        app_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(RotatingFileHandler(app_dir / "quicknote.log", maxBytes=1_000_000, backupCount=3,
                                            encoding="utf-8"))
    except OSError:
        pass  # โฟลเดอร์เขียนไม่ได้ — ยังรันต่อได้ แค่ไม่มีไฟล์ log
    if sys.stdout is not None:
        handlers.append(logging.StreamHandler(sys.stdout))
    for h in handlers:
        h.setFormatter(fmt)
        root.addHandler(h)
    root._quicknote_configured = True  # type: ignore[attr-defined]


def _install_exception_hooks() -> None:
    """exception ที่หลุดจาก thread/ไม่ได้จับ ต้องลงไฟล์ log — ไม่งั้น .exe แบบ noconsole ล้มเงียบ ๆ"""
    def hook(exc_type, exc, tb) -> None:
        log.error("unhandled exception", exc_info=(exc_type, exc, tb))

    def thread_hook(args: threading.ExceptHookArgs) -> None:
        log.error("unhandled exception in thread %s", getattr(args.thread, "name", "?"),
                  exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    sys.excepthook = hook
    threading.excepthook = thread_hook


# ================================================================ single instance (L9)
class SingleInstance:
    """named mutex = ตัวตัดสินว่าใครเป็น instance แรก; socket localhost ใช้ส่ง "SHOW" เท่านั้น

    แยกสองอย่างเพราะ port ถูกโปรแกรมอื่นจองได้ — ถ้าใช้ port เป็นล็อก QuickNote จะเปิดไม่ขึ้นเงียบ ๆ
    """

    def __init__(self, mutex_name: str = MUTEX_NAME, port: int = SIGNAL_PORT) -> None:
        self.mutex_name = mutex_name
        self.port = port
        self._mutex = None
        self._k32 = None
        self._server: Optional[socket.socket] = None
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def acquire(self) -> bool:
        """True = เราเป็น instance แรก (หรือสร้าง mutex ไม่ได้ → ยอมรันต่อดีกว่าไม่เปิด)"""
        if sys.platform != "win32":
            return True
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
        k32.CreateMutexW.restype = ctypes.c_void_p
        k32.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = k32.CreateMutexW(None, False, self.mutex_name)
        err = ctypes.get_last_error()
        if not handle:
            log.warning("CreateMutexW failed (error %s) — running without single-instance guard", err)
            return True
        if err == _ERROR_ALREADY_EXISTS:
            k32.CloseHandle(handle)
            return False
        self._mutex = handle
        self._k32 = k32
        return True

    def signal_existing(self) -> bool:
        """บอก instance แรกให้แสดงหน้าต่าง; timeout 1 วิ กันค้างถ้าอีกฝั่งไม่ตอบ"""
        try:
            with socket.create_connection(("127.0.0.1", self.port), timeout=1.0) as s:
                s.sendall(b"SHOW")
            return True
        except OSError as e:
            log.warning("cannot signal the running instance: %s", e)
            return False

    def start_listener(self, on_show: Callable[[], None]) -> bool:
        """เปิดรับ "SHOW" บน daemon thread — bind ไม่ได้แค่ log (สัญญาณใช้ไม่ได้ แต่แอปยังรัน)

        on_show ถูกเรียกจาก thread นี้ → ผู้เรียกต้องห่อ root.after เอง
        """
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.bind(("127.0.0.1", self.port))
            srv.listen(4)
            srv.settimeout(0.5)  # วนเช็ก _stop ได้ ไม่ต้องปิด socket ข้าม thread
        except OSError as e:
            srv.close()
            log.warning("signal port %s unavailable (%s) - a second launch cannot raise this window", self.port, e)
            return False
        self.port = srv.getsockname()[1]
        self._server = srv
        self._thread = threading.Thread(target=self._serve, args=(on_show,), daemon=True, name="qn-single-instance")
        self._thread.start()
        return True

    def _serve(self, on_show: Callable[[], None]) -> None:
        srv = self._server
        while not self._stop.is_set() and srv is not None:
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                conn.settimeout(1.0)
                if conn.recv(16).strip() == b"SHOW":
                    on_show()
            except Exception:
                log.exception("single-instance signal failed")
            finally:
                conn.close()

    def release(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self._server is not None:
            try:
                self._server.close()
            except OSError:
                pass
            self._server = None
        if self._mutex:
            try:
                self._k32.CloseHandle(self._mutex)
            except Exception:
                pass
            self._mutex = None


# ================================================================ upgrade safety
def backup_pre_v3_db() -> Optional[str]:
    """DB ก่อน v3 (ตาราง notes ยังไม่มีคอลัมน์ color) → สำเนาเก็บไว้ครั้งเดียวก่อน migrate

    migrate ของ v3 พับการ์ดทุกใบและเพิ่มคอลัมน์ ย้อนกลับไม่ได้ จึงเก็บต้นฉบับไว้ให้ผู้ใช้ลดรุ่นได้
    """
    db_file = db._get_db_file()
    if db_file == ":memory:" or not Path(db_file).is_file():
        return None
    target = db.get_app_dir() / "backups" / "notes_pre_v3.db"
    if target.exists():
        return None
    try:
        conn = sqlite3.connect(Path(db_file).resolve().as_uri() + "?mode=ro", uri=True)
        try:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(notes)")}
        finally:
            conn.close()
    except sqlite3.Error as e:
        log.warning("cannot inspect database before upgrade: %s", e)
        return None
    if not columns or "color" in columns:
        return None  # DB ว่าง/ไม่มีตาราง หรือเป็นของ v3 อยู่แล้ว
    if db.backup_database(str(target)):
        log.info("pre-v3 database saved to %s", target)
        return str(target)
    log.error("could not save the pre-v3 database copy")
    return None


# ================================================================ application
class App:
    """ประกอบ Board + tray + hotkey + เส้นทางปิดแอปจุดเดียว

    แยกเป็น class เพื่อให้เทสสร้างด้วย Tk จริงและฉีด tray/hotkey ปลอมได้ (ปลอมเฉพาะ pystray กับตัวลงทะเบียนคีย์ลัด)
    """

    def __init__(self, root: tk.Tk, settings: Settings, theme: Theme, toasts: ToastManager, board: Board,
                 hotkey_factory: Callable = start_hotkey_listener,
                 single: Optional[SingleInstance] = None) -> None:
        self.root, self.settings, self.theme, self.toasts, self.board = root, settings, theme, toasts, board
        self.tray = None
        self.hotkeys = None
        self.single = single
        self._hotkey_factory = hotkey_factory
        self._hotkey_reverting = False
        self._working_hotkeys: Optional[dict] = None   # ชุดคีย์ลัดล่าสุดที่ลงทะเบียนสำเร็จ (ไว้คืนค่าเมื่อชุดใหม่ใช้ไม่ได้)
        self._quitting = False
        self._persisted = False
        self._last_tip = ""

        board.on_quit = self.quit_app
        board.can_hide = self.tray_running
        root.protocol("WM_DELETE_WINDOW", self.on_close_request)  # override ค่า default ของ Board
        settings.subscribe(self.on_setting)
        board.scheduler.on_tick(self._on_tick)

    # ---------------------------------------------------------------- thread bridge
    def ui(self, fn: Callable[[], None]) -> None:
        """เรียกจาก thread อื่นได้ — วาง fn ลง main loop"""
        try:
            self.root.after(0, fn)
        except (tk.TclError, RuntimeError):
            # root ถูกทำลายแล้ว หรือ mainloop ยังไม่เริ่ม/จบไปแล้ว (ช่วงเปิด-ปิดแอป) — ไม่มี UI ให้ทำอะไรอยู่ดี
            log.debug("ui callback dropped (no running mainloop)")

    # ---------------------------------------------------------------- tray
    def tray_running(self) -> bool:
        return self.tray is not None and bool(getattr(self.tray, "is_running", False))

    def setup_tray(self, start: Optional[Callable] = None) -> None:
        """tray ขึ้นไม่ได้ต้องไม่ฆ่าแอป — close_to_tray จะถอยไปเป็น "ปิด = ออก" เอง"""
        try:
            if start is None:
                from src.platform.tray import start_tray_thread as start
            self.tray = start(
                on_toggle=lambda: self.ui(self.board.toggle_visibility),
                on_new_note=lambda: self.ui(self.new_note),
                on_settings=lambda: self.ui(self.open_settings),
                on_quit=lambda: self.ui(self.quit_app),
                tooltip=self.tray_tooltip)
        except Exception:
            log.exception("system tray unavailable — window close will quit the app")
            self.tray = None

    def tray_tooltip(self) -> str:
        try:
            nxt = db.get_next_reminder()
            if nxt:
                when, _ = format_reminder(nxt["reminder_datetime"], datetime.now(), strings.get_language())
                return t("tray.tooltip_next", time=when)
        except Exception:
            log.debug("tray tooltip fallback", exc_info=True)
        return t("tray.tooltip")

    def _on_tick(self) -> None:
        """ทุกรอบของ scheduler: อัปเดต tooltip ของ tray เฉพาะเมื่อข้อความเปลี่ยน (ไม่ยิง Shell_NotifyIcon ถี่ ๆ)"""
        if self.tray is None:
            return
        tip = self.tray_tooltip()
        if tip != self._last_tip:
            self._last_tip = tip
            self.tray.update_tooltip()

    # ---------------------------------------------------------------- actions
    def new_note(self) -> None:
        self.board.show()
        self.board.focus_quick_add()

    def open_settings(self) -> None:
        """H1: singleton เดียวอยู่ที่ Board — tray แค่ดึงหน้าต่างขึ้นแล้วเรียกตัวเดียวกับปุ่ม ⚙"""
        self.board.show()
        self.board.open_settings()

    def show_main(self) -> None:
        self.board.show()

    # ---------------------------------------------------------------- hotkeys
    def start_hotkeys(self) -> bool:
        self.stop_hotkeys()
        config = dict(self.settings.get("hotkeys", {}))
        listener = self._hotkey_factory(config, self._on_hotkey)
        self.hotkeys = listener
        if listener is not None:
            self._working_hotkeys = config
        return listener is not None

    def stop_hotkeys(self) -> None:
        listener, self.hotkeys = self.hotkeys, None
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                log.debug("hotkey stop failed", exc_info=True)

    def _on_hotkey(self, name: str) -> None:
        """รันบน thread ของ hotkey listener"""
        action = {"new_note": self.new_note, "toggle_show": self.board.toggle_visibility}.get(name)
        if action is not None:
            self.ui(action)

    # ---------------------------------------------------------------- settings listeners
    def on_setting(self, key: str, value: object) -> None:
        """Board/Theme จัดการคีย์ของตัวเองแล้ว — ที่นี่เหลือแค่ hotkey กับภาษาของ tray"""
        if key == "hotkeys":
            self._apply_hotkeys()
        elif key == "language" and self.tray is not None:
            self.tray.update_menu_language()
            self._last_tip = ""  # ภาษาใหม่ → ข้อความ tooltip เปลี่ยนแม้เวลาเตือนเท่าเดิม
            self.tray.update_tooltip()

    def _apply_hotkeys(self) -> None:
        """ผู้ใช้เปลี่ยนคีย์ลัด → หยุดตัวฟังเก่าแล้วเปิดใหม่; ลงทะเบียนไม่ได้ = แจ้งแล้วคืนชุดเดิมที่ใช้ได้"""
        previous = self._working_hotkeys
        if self.start_hotkeys():
            return
        messagebox.showwarning(t("app.name"), t("msg.hotkey_failed"), parent=self.root)
        if previous and not self._hotkey_reverting:
            # คืนค่า ไม่งั้นผู้ใช้เหลือแอปที่ไม่มีคีย์ลัดจนกว่าจะเปิดใหม่ (หน้า Settings sync ช่องบันทึกเองเมื่อค่าเปลี่ยน)
            self._hotkey_reverting = True
            try:
                self.settings.set("hotkeys", previous)
            finally:
                self._hotkey_reverting = False

    # ---------------------------------------------------------------- close / quit (C3)
    def on_close_request(self) -> None:
        """✕ ของ Windows: ซ่อนลงถาดเมื่อเปิด close_to_tray และ tray ทำงานจริง ไม่งั้นออกจากแอป"""
        if self.settings.get("close_to_tray", True) and self.tray_running():
            self.board.hide()
            if not self.settings.get("tray_hint_shown", False):
                self.toasts.show_info(t("toast.tray_hint"))
                self.settings.set("tray_hint_shown", True)
        else:
            self.quit_app()

    def _persist(self) -> None:
        """เก็บข้อมูลค้างทั้งหมดลงดิสก์ — ทุกขั้นกันพังแยกกัน เพื่อขั้นหนึ่งล้มแล้วขั้นอื่นยังทำ"""
        if self._persisted:
            return
        self._persisted = True
        steps = (
            ("flush cards", self.board.flush_all_cards),
            # แถบ Undo ที่ค้าง = โน้ตที่ soft-delete แล้ว → purge ตอนนี้เลย ผลเหมือนกันทุกครั้งที่ปิด
            ("flush undo bar", self.board.undo_bar.flush),
            ("save geometry", lambda: self.settings.set("geometry", self.board.get_persistable_geometry(), save=False)),
            ("save settings", self.settings.save),
            ("close toasts", self.toasts.close_all),
        )
        for name, step in steps:
            try:
                step()
            except Exception:
                log.exception("quit step failed: %s", name)

    def quit_app(self) -> None:
        """ทางออกเดียวของแอป — เรียกซ้ำได้ (tray Quit + ✕ พร้อมกัน) แต่ทำงานครั้งเดียว"""
        if self._quitting:
            return
        self._quitting = True
        try:
            self._persist()
        finally:
            self.root.quit()

    def shutdown(self) -> None:
        """หลัง mainloop จบ (ทุกกรณี รวม exception): หยุดทุก thread/listener แล้วทำลาย root"""
        self._persist()  # exception หลุดจาก mainloop ก็ยังได้เซฟ
        steps = (
            ("scheduler", self.board.scheduler.stop),
            ("hotkeys", self.stop_hotkeys),
            ("tray", lambda: self.tray.stop() if self.tray is not None else None),
            ("single instance", lambda: self.single.release() if self.single is not None else None),
        )
        for name, step in steps:
            try:
                step()
            except Exception:
                log.exception("shutdown step failed: %s", name)
        try:
            self.root.destroy()
        except tk.TclError:
            pass


# ================================================================ startup
def _fatal(message: str) -> None:
    """แจ้งผู้ใช้โดยไม่พึ่ง Tk (อาจยังสร้างไม่สำเร็จ) — .exe แบบ noconsole ไม่มีที่แสดง traceback"""
    try:
        ctypes.windll.user32.MessageBoxW(None, message, APP_NAME, 0x10)
    except Exception:
        print(message, file=sys.stderr)


def run_app(selftest: bool) -> int:
    single = SingleInstance("Local\\QuickNote.SelfTest" if selftest else MUTEX_NAME, 0 if selftest else SIGNAL_PORT)
    if not single.acquire():
        signaled = single.signal_existing()
        log.info("QuickNote is already running — %s", "asked it to show its window" if signaled else "could not signal it")
        return 0

    win11.set_app_user_model_id(APP_ID)  # คงที่ ไม่ผูกเวอร์ชัน (L12)
    backup_pre_v3_db()
    db.init_db()
    settings = Settings()
    settings.load()
    if settings.get("auto_backup", True) and db.auto_backup():
        settings.set("last_auto_backup", datetime.now().isoformat(timespec="seconds"))
    strings.set_language(str(settings.get("language", "th")))

    root = tk.Tk()
    root.report_callback_exception = lambda exc, val, tb: log.error("Tk callback exception", exc_info=(exc, val, tb))
    theme = Theme(root, settings)
    toasts = ToastManager(root, theme, settings)
    board = Board(root, settings, theme, toasts)
    app = App(root, settings, theme, toasts, board, single=single)
    try:
        app.setup_tray()
        if not app.start_hotkeys():
            toasts.show_info(t("msg.hotkey_failed"))
        single.start_listener(lambda: app.ui(app.show_main))
        if selftest:
            root.attributes("-alpha", 0.0)  # หน้าต่าง map จริงแต่มองไม่เห็น — ไม่กวนคนรันเทส
            root.after(int(SELFTEST_SECONDS * 1000), app.quit_app)
        log.info("QuickNote %s started", APP_VERSION)
        root.mainloop()
        return 0 if (not selftest or board.note_cards) else 1
    finally:
        app.shutdown()
        log.info("QuickNote stopped")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog=APP_NAME)
    parser.add_argument("--selftest", action="store_true",
                        help="เปิดแอปบนข้อมูลชั่วคราว ประมวลผล event ~2 วินาทีแล้วออกด้วย code 0 (ใช้ใน build/CI)")
    args = parser.parse_args(argv)

    temp_home = None
    if args.selftest:
        temp_home = tempfile.mkdtemp(prefix="qn_selftest_")
        os.environ["QUICKNOTE_HOME"] = temp_home  # ห้ามแตะข้อมูลจริงของผู้ใช้
        os.environ.pop("DB_PATH", None)
    setup_logging(db.get_app_dir())
    _install_exception_hooks()
    try:
        if args.selftest:
            db.init_db()
            db.create_note("selftest")  # ให้มีการ์ดอย่างน้อยหนึ่งใบเพื่อพิสูจน์ว่า Board โหลด DB ได้
        return run_app(args.selftest)
    except Exception:
        log.exception("fatal error")
        _fatal(f"{APP_NAME} {APP_VERSION}: {sys.exc_info()[1]}\n\nLog: {db.get_app_dir() / 'quicknote.log'}")
        return 1
    finally:
        if temp_home is not None:
            logging.shutdown()
            shutil.rmtree(temp_home, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
