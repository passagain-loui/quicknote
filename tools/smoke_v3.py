"""Smoke test end-to-end ของ QuickNote v3 — รัน `python main.py` ตัวจริงเป็น process แล้วขับด้วย Win32 input จริง

รัน:  python tools/smoke_v3.py [--out โฟลเดอร์ภาพ] [--home โฟลเดอร์ข้อมูลชั่วคราว]

ลำดับ: เปิดแอป → hotkey Ctrl+Alt+N + พิมพ์ quick-add 3 ใบ → ตั้ง reminder +1 นาที → รอ toast จริง → ✕ (WM_CLOSE) ซ่อนลงถาด
       → เปิดแอปซ้ำ (ต้อง exit 0 และหน้าต่างแรกกลับมา) → ย้าย/ย่อขนาด → Quit ผ่านเมนู tray จริง
       → เปิดใหม่ตรวจว่าโน้ต/geometry/settings ยังอยู่ → Quit อีกรอบ → ตรวจ quicknote.log

ความปลอดภัย: ข้อมูลอยู่ใน QUICKNOTE_HOME ชั่วคราวเสมอ (ไม่แตะ ~/.quicknote) และ "ไม่พิมพ์/กดคีย์ใด ๆ" ถ้า
หน้าต่าง foreground ไม่ใช่ของ QuickNote หรือหน้าต่าง sink ของสคริปต์นี้ (กันพิมพ์ใส่แอปของผู้ใช้)
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
import tkinter as tk
from ctypes import wintypes
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # พิกัดต้องตรงกับแอป (physical px)
except Exception:
    pass

from PIL import ImageGrab  # noqa: E402

user32 = ctypes.WinDLL("user32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.GetParent.argtypes = [wintypes.HWND]
user32.GetParent.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                wintypes.UINT]
dwmapi.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]

WM_CLOSE, WM_NOTIFY_TRAY, WM_LBUTTONUP, WM_RBUTTONUP = 0x0010, 0x040B, 0x0202, 0x0205
VK = {"ctrl": 0xA2, "alt": 0xA4, "shift": 0xA0, "enter": 0x0D, "up": 0x26, "esc": 0x1B, "n": 0x4E, "s": 0x53}
KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 0x0002, 0x0004
SWP_NOZORDER, SWP_NOACTIVATE = 0x0004, 0x0010

DEFAULT_OUT = Path(r"C:\Users\PASSAG~1\AppData\Local\Temp\claude\D--AI-OpenCode-Noted-Planing-and-Record"
                   r"\5942156e-1758-4add-8e22-4048da503076\scratchpad")


# ================================================================ win32 helpers
class _KB(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _MS(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _HW(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class _IN(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", _KB), ("mi", _MS), ("hi", _HW)]
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


def _send(events: list[tuple[int, int, int]]) -> None:
    arr = (_IN * len(events))()
    for i, (vk, scan, flags) in enumerate(events):
        arr[i].type = 1
        arr[i].ki = _KB(vk, scan, flags, 0, 0)
    user32.SendInput(len(events), arr, ctypes.sizeof(_IN))
    time.sleep(0.05)


def _mouse(x: int, y: int) -> None:
    """คลิกซ้ายที่ตำแหน่งปัจจุบันของเคอร์เซอร์ (ตั้งตำแหน่งด้วย SetCursorPos ก่อน)"""
    for flag in (0x0002, 0x0004):   # LEFTDOWN, LEFTUP
        arr = (_IN * 1)()
        arr[0].type = 0
        arr[0].mi = _MS(0, 0, 0, flag, 0, 0)
        user32.SendInput(1, arr, ctypes.sizeof(_IN))
        time.sleep(0.05)


def chord(*names: str) -> None:
    codes = [VK[n] for n in names]
    _send([(c, 0, 0) for c in codes] + [(c, 0, KEYEVENTF_KEYUP) for c in reversed(codes)])


def type_text(text: str) -> None:
    for ch in text:
        _send([(0, ord(ch), KEYEVENTF_UNICODE), (0, ord(ch), KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)])


def pid_of(hwnd: int) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def class_of(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def title_of(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    return buf.value


def windows_of(pid: int) -> list[int]:
    found: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _lp):
        if pid_of(hwnd) == pid:
            found.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return found


def frame_rect(hwnd: int) -> tuple[int, int, int, int]:
    """กรอบจริงจาก DWM (ไม่รวมเงา) — ใช้เป็น bbox แคปภาพ"""
    r = wintypes.RECT()
    dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(r), ctypes.sizeof(r))
    return r.left, r.top, r.right, r.bottom


def has_caption(hwnd: int) -> bool:
    """หน้าต่างหลักมี titlebar (WS_CAPTION) ส่วน toast เป็น overrideredirect — ใช้แยกสองอย่างนี้ (ชื่อซ้ำกัน)"""
    return bool(user32.GetWindowLongW(hwnd, -16) & 0xC00000)


def force_foreground(hwnd: int) -> bool:
    """ดึงหน้าต่างขึ้น foreground โดยผูก input queue กับ thread ของ foreground เดิมชั่วคราว

    ห้ามใช้ทริก "แตะ Alt" — Alt keyup ที่ไม่มีเมนูทำให้ Windows เข้า modal menu loop ใน wndproc ของ Tk ซึ่งทำให้ update() ค้าง
    """
    kernel32 = ctypes.WinDLL("kernel32")
    fg = user32.GetForegroundWindow()
    if fg != hwnd:
        fg_tid = user32.GetWindowThreadProcessId(fg, None) if fg else 0
        my_tid = kernel32.GetCurrentThreadId()
        attached = bool(fg_tid) and fg_tid != my_tid and user32.AttachThreadInput(my_tid, fg_tid, True)
        try:
            user32.SetForegroundWindow(hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(my_tid, fg_tid, False)
    time.sleep(0.3)
    return user32.GetForegroundWindow() == hwnd


# ================================================================ harness
class Smoke:
    def __init__(self, out: Path, home: Path) -> None:
        self.out, self.home = out, home
        self.env = {k: v for k, v in os.environ.items() if k not in ("DB_PATH",)}
        self.env["QUICKNOTE_HOME"] = str(home)
        self.env["PYTHONIOENCODING"] = "utf-8"
        self.proc: subprocess.Popen | None = None
        self.spawned: list[subprocess.Popen] = []   # ทุก process ที่เปิด — ต้องไม่ทิ้งค้างหลังจบ (แม้เทสพังกลางทาง)
        self.results: list[tuple[str, bool, str]] = []
        self.sink = tk.Tk()  # หน้าต่างรับคีย์แทนแอปของผู้ใช้ตอนกด hotkey ระดับ global
        self.sink.title("smoke-sink")
        self.sink.geometry("240x60+10+10")
        self.sink.attributes("-topmost", True)
        tk.Label(self.sink, text="QuickNote smoke test - keys go here").pack()
        self.sink.update()

    # ---------------------------------------------------------- bookkeeping
    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        self.results.append((name, bool(ok), detail))
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""), flush=True)
        return bool(ok)

    def pump(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.sink.update()
            time.sleep(0.02)

    def wait(self, cond, timeout: float, step: float = 0.2):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            value = cond()
            if value:
                return value
            self.pump(step)
        return cond()

    # ---------------------------------------------------------- process / windows
    def launch(self) -> subprocess.Popen:
        proc = subprocess.Popen([sys.executable, str(ROOT / "main.py")], cwd=ROOT, env=self.env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.spawned.append(proc)
        return proc

    def main_window(self, visible: bool | None = True) -> int | None:
        """หน้าต่างหลัก: Tk toplevel ชื่อ QuickNote ที่ไม่ใช่ toast (toast ไม่มี title)"""
        if self.proc is None:
            return None
        for h in windows_of(self.proc.pid):
            if class_of(h) == "TkTopLevel" and title_of(h) == "QuickNote" and has_caption(h):
                if visible is None or bool(user32.IsWindowVisible(h)) == visible:
                    return h
        return None

    def toasts(self) -> list[int]:
        if self.proc is None:
            return []
        return [h for h in windows_of(self.proc.pid)
                if class_of(h) == "TkTopLevel" and not has_caption(h) and user32.IsWindowVisible(h)
                and frame_rect(h)[2] - frame_rect(h)[0] > 150]

    def tray_hwnds(self) -> list[int]:
        """pystray สร้างหน้าต่างคลาสเดียวกันสองใบ (ตัวรับ notify + ตัวเป็นเจ้าของเมนู) — มีแค่ใบเดียวที่รับ WM_NOTIFY"""
        return [h for h in (windows_of(self.proc.pid) if self.proc else []) if class_of(h).endswith("SystemTrayIcon")]

    def tray_hwnd(self) -> int | None:
        found = self.tray_hwnds()
        return found[0] if found else None

    def shot(self, name: str, hwnd: int | None, pad: int = 0) -> Path | None:
        if not hwnd:
            return None
        l, t, r, b = frame_rect(hwnd)
        img = ImageGrab.grab(bbox=(l - pad, t - pad, r + pad, b + pad), all_screens=True)
        path = self.out / f"smoke_{name}.png"
        img.save(path)
        print(f"      screenshot -> {path}", flush=True)
        return path

    def focus_ok(self) -> bool:
        """foreground ต้องเป็นของ QuickNote หรือ sink ของเราเท่านั้น ก่อนส่งคีย์ใด ๆ"""
        fg = user32.GetForegroundWindow()
        return bool(fg) and (pid_of(fg) in ({self.proc.pid if self.proc else -1, os.getpid()}))

    def to_sink(self) -> None:
        hwnd = user32.GetParent(self.sink.winfo_id()) or self.sink.winfo_id()  # winfo_id ของ Tk คือหน้าต่างลูก
        force_foreground(hwnd)
        self.sink.focus_force()
        self.pump(0.3)

    def safe_chord(self, *names: str) -> bool:
        if not self.focus_ok():
            self.check(f"safety: foreground is ours before {'+'.join(names)}", False, "skipped sending keys")
            return False
        chord(*names)
        return True

    def stop(self, timeout: float = 10.0) -> int | None:
        if self.proc is None:
            return None
        try:
            return self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return None

    # ---------------------------------------------------------- data
    def db_rows(self) -> list[sqlite3.Row]:
        path = self.home / "notes.db"
        if not path.exists():
            return []
        conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            return conn.execute("SELECT * FROM notes WHERE deleted_at IS NULL ORDER BY created_at").fetchall()
        finally:
            conn.close()

    def settings(self) -> dict:
        try:
            return json.loads((self.home / "settings.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    # ---------------------------------------------------------- tray (ส่ง message ให้หน้าต่าง pystray จริง)
    def popup_menu(self) -> int | None:
        """หน้าต่างเมนู popup (#32768) ที่เป็นของ process แอป — เมนูของ tray ที่เปิดอยู่"""
        for h in windows_of(self.proc.pid) if self.proc else []:
            if class_of(h) == "#32768" and user32.IsWindowVisible(h):
                return h
        return None

    def tray_menu_quit(self) -> bool:
        """เปิดเมนู tray จริง (ส่ง WM_RBUTTONUP แบบเดียวกับที่ shell ส่ง) แล้วคลิกรายการสุดท้าย "ออก" ด้วยเมาส์

        คลิกเฉพาะเมื่อเจอหน้าต่างเมนูของแอปจริง ๆ เท่านั้น (ไม่คลิกเลื่อนลอยลงบนแอปอื่นของผู้ใช้)
        """
        menu = self.popup_menu()
        for h in ([] if menu else self.tray_hwnds()):
            user32.PostMessageW(h, WM_NOTIFY_TRAY, 0, WM_RBUTTONUP)
            menu = self.wait(self.popup_menu, 1.5)
            if menu:
                break
        if not menu:
            return False
        self.pump(0.3)
        l, t, r, b = frame_rect(menu)
        x, y = (l + r) // 2, b - max(14, (b - t) // 9)          # แถวสุดท้ายของเมนู (ออก)
        user32.SetCursorPos(x, y)
        self.pump(0.2)
        _mouse(x, y)
        return True

    def tray_left_click(self) -> bool:
        for h in self.tray_hwnds():
            user32.PostMessageW(h, WM_NOTIFY_TRAY, 0, WM_LBUTTONUP)
        return bool(self.tray_hwnds())

    # ---------------------------------------------------------- scenario
    def run(self) -> int:
        try:
            self.scenario()
        finally:
            for proc in self.spawned:
                if proc.poll() is None:
                    print(f"[cleanup] pid {proc.pid} still running -> terminate", flush=True)
                    proc.terminate()
            self.sink.destroy()
        fails = [r for r in self.results if not r[1]]
        print(f"\n=== {len(self.results) - len(fails)}/{len(self.results)} checks passed ===", flush=True)
        return 1 if fails else 0

    def scenario(self) -> None:
        # ---- 1 launch
        self.proc = self.launch()
        win = self.wait(lambda: self.main_window(True), 25)
        self.check("1 launch: main window visible", win, f"hwnd={win}")
        if not win:
            return
        self.pump(1.0)
        self.shot("01_board_empty", win)
        self.check("1 launch: tray icon window exists", self.wait(self.tray_hwnd, 5) is not None)

        # ---- 2 hotkey + quick-add (ผู้ใช้อาจแย่ง foreground ระหว่างรัน → ทำทีละใบ ลองซ้ำ และพิมพ์เฉพาะตอน foreground เป็นของเรา)
        first_fg = None
        for title in ("ซื้อของเข้าออฟฟิศ", "Smoke note two", "ประชุมทีม 14:00"):
            before = len(self.db_rows())
            for _attempt in range(4):
                self.to_sink()
                self.safe_chord("ctrl", "alt", "n")
                self.pump(0.8)
                fg_ok = user32.GetForegroundWindow() == win
                if first_fg is None:
                    first_fg = fg_ok
                if fg_ok and self.focus_ok():
                    type_text(title)
                    chord("enter")
                    self.pump(0.5)
                if len(self.db_rows()) > before:
                    break
        self.check("2 hotkey Ctrl+Alt+N brings QuickNote to foreground (first try)", first_fg)
        rows = self.wait(lambda: self.db_rows() if len(self.db_rows()) >= 3 else None, 5) or self.db_rows()
        titles = [r["title"] for r in rows]
        self.check("2 quick-add created 3 notes via real typing", len(rows) == 3, str(titles))
        self.shot("02_board_three_notes", win)

        # ---- 3 reminder → toast
        toast = None
        if rows:
            target = rows[-1]["id"]
            when = (datetime.now() + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M")
            conn = sqlite3.connect(self.home / "notes.db")
            conn.execute("UPDATE notes SET reminder_datetime = ?, reminder_triggered = 0 WHERE id = ?", (when, target))
            conn.commit()
            conn.close()
            print(f"      reminder set for {when}; waiting for toast (<= 100 s)", flush=True)
            toast = self.wait(lambda: self.toasts()[:1] or None, 100, 0.5)
            self.check("3 reminder toast appears at due time", toast is not None)
            if toast:
                self.pump(0.6)
                self.shot("03_toast", toast[0])
                self.shot("03_board_alarm", win)
                row = next(r for r in self.db_rows() if r["id"] == target)
                self.check("3 note is ringing in DB (triggered=1)", row["reminder_triggered"] == 1)

        # ---- 4 close -> hide to tray + hint
        self.pump(0.5)
        user32.PostMessageW(win, WM_CLOSE, 0, 0)
        hidden = self.wait(lambda: not user32.IsWindowVisible(win), 5)
        self.check("4 close(X) hides window to tray (process stays alive)", hidden and self.proc.poll() is None)
        hint = self.wait(lambda: [h for h in self.toasts() if h != (toast[0] if toast else 0)][:1] or None, 6) \
            if hidden else None
        self.pump(0.5)
        self.check("4 first-hide hint toast shown, tray_hint_shown saved",
                   hint is not None and self.wait(lambda: self.settings().get("tray_hint_shown") is True, 3))
        if hint:
            self.shot("04_tray_hint", hint[0])

        # ---- 5 second instance
        second = self.launch()
        code = None
        try:
            code = second.wait(timeout=15)
        except subprocess.TimeoutExpired:
            second.terminate()
        self.check("5 second launch exits with code 0", code == 0, f"code={code}")
        shown = self.wait(lambda: user32.IsWindowVisible(win), 5)
        self.check("5 first window reappears after the second launch (SHOW signal)", shown)
        self.pump(0.5)
        self.shot("05_after_second_launch", win)
        self.check("5 still exactly one main window / one process alive", self.proc.poll() is None)

        # ---- 6 hotkey toggle: ยังไม่มี focus → ดึงขึ้น (M22) · มี focus → ซ่อนลงถาด · กดอีกครั้ง → กลับมา
        states = []
        for _attempt in range(4):
            self.to_sink()
            self.safe_chord("ctrl", "alt", "s")
            self.pump(0.8)
            if user32.GetForegroundWindow() != win:
                continue                      # ถูกแย่ง foreground — เริ่มลำดับใหม่
            states = [bool(user32.IsWindowVisible(win))]
            self.safe_chord("ctrl", "alt", "s")   # QuickNote เป็น foreground แล้ว → ต้องซ่อน
            self.pump(0.8)
            states.append(bool(user32.IsWindowVisible(win)))
            self.to_sink()
            self.safe_chord("ctrl", "alt", "s")   # ซ่อนอยู่ → ต้องกลับมา
            self.pump(0.8)
            states.append(bool(user32.IsWindowVisible(win)))
            break
        self.check("6 Ctrl+Alt+S: raise/stay visible -> hide -> show", states == [True, False, True], str(states))
        if not states or not states[-1]:
            self.tray_left_click()
            self.wait(lambda: user32.IsWindowVisible(win), 3)

        # ---- 7 move + resize, then Quit via the real tray menu
        user32.SetWindowPos(win, 0, 210, 140, 460, 540, SWP_NOZORDER | SWP_NOACTIVATE)
        self.pump(1.0)
        rect_before = frame_rect(win)
        self.shot("06_moved_resized", win)
        clicked = self.tray_menu_quit()
        code = self.stop(15) if clicked else None
        self.check("7 Quit from the real tray menu exits the process with code 0", clicked and code == 0,
                   f"menu={'sent' if clicked else 'no tray window'} exit={code}")
        st = self.settings()
        self.check("7 settings.json written on quit (geometry moved off default)",
                   st.get("geometry") not in (None, "380x600+120+120"), str(st.get("geometry")))
        self.check("7 DB intact after quit (3 notes)", len(self.db_rows()) == 3)

        # ---- 8 relaunch -> persistence
        self.proc = self.launch()
        win2 = self.wait(lambda: self.main_window(True), 25)
        self.check("8 relaunch: window visible", win2)
        if win2:
            self.pump(1.0)
            rect_after = frame_rect(win2)
            drift = max(abs(a - b) for a, b in zip(rect_before, rect_after))
            self.check("8 relaunch: window position/size restored", drift <= 3, f"{rect_before} -> {rect_after}")
            self.shot("07_relaunch", win2)
            self.check("8 relaunch: notes still there", len(self.db_rows()) == 3)
            self.to_sink()
            self.tray_menu_quit()
            code = self.stop(15)
            self.check("8 final Quit via tray exits 0", code == 0, f"exit={code}")

        # ---- 9 log review
        log_path = self.home / "quicknote.log"
        text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
        bad = [ln for ln in text.splitlines() if re.search(r"\[(ERROR|CRITICAL)\]|Traceback", ln)]
        self.check("9 quicknote.log has no ERROR/Traceback", not bad, f"{len(bad)} bad lines")
        for ln in bad[:10]:
            print("      ", ln)
        warn = [ln for ln in text.splitlines() if "[WARNING]" in ln]
        print(f"      log: {len(text.splitlines())} lines, {len(warn)} warnings", flush=True)
        for ln in warn[:10]:
            print("      ", ln)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--home", default="")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    home = Path(args.home) if args.home else Path(tempfile.mkdtemp(prefix="qn_smoke_"))
    home.mkdir(parents=True, exist_ok=True)
    print(f"QUICKNOTE_HOME={home}\nscreenshots -> {out}", flush=True)
    return Smoke(out, home).run()


if __name__ == "__main__":
    sys.exit(main())
