# QuickNote v3.0.0 — Architecture Contract

> เอกสารนี้คือ "สัญญา" ระหว่างทุก module ของ v3 ทุก agent ต้องยึดตาม API ข้างล่าง
> ถ้าต้องเปลี่ยน signature ให้ระบุในรายงานกลับมา ห้ามเปลี่ยนเงียบ ๆ
> แหล่งอ้างอิง: `docs/v3/DESIGN_SPEC_WIN11.md` (หน้าตา/พฤติกรรม) และ `docs/v3/BUG_REPORT_v2.9.46.md` (บั๊กที่ต้องหายไป)

## 0. Decisions (ตัดสินแล้วโดยเจ้าของโปรเจกต์)

| เรื่อง | ตัดสิน |
|---|---|
| Release | v3.0.0 ครั้งเดียว: UI Windows 11 + แก้บั๊กทุกข้อใน BUG_REPORT ไปพร้อมกัน |
| การเรียงการ์ด | `is_pinned DESC` → alarm กำลังดัง → priority (high>medium>low>none) → `created_at DESC` ไม่มี band-aid `repack_card_to_top` |
| ภาษา | ไทย + อังกฤษ เลือกได้ใน Settings (ค่าเริ่มต้น ไทย) ทุกข้อความผ่าน `t()` |
| Alarm ตอนหน้าต่างซ่อน | แสดงแค่ toast ไม่ดึงหน้าต่างหลัก ("เปิด" ถึงจะดึง) |
| Toast | in-app toast (แนวทาง A) อย่างเดียว ไม่ทำ Windows toast |
| การ์ดกาง | ทีละใบ (กางใบใหม่ = ใบเก่า flush แล้วพับ) |
| Phase 4 ที่รวม | สีโน้ต, Export Markdown, Reminder ทำซ้ำ, มุมโค้ง + animation |
| Roll-up | ตัดออก → "โหมดกะทัดรัด" ใน Settings |
| Drag reorder | ไม่ทำ |
| ลบโน้ต | soft delete + UndoBar 5 วินาที |
| Google Tasks | ลบออกทั้งหมด (รวม client id/secret ปลอม) |
| โน้ตใหม่ | สร้างแบบพับ (Shift+Enter = สร้างแล้วกาง) |
| Test เก่า | ย้ายไป `tests/legacy/` (ไม่รัน) suite ใหม่อยู่ `tests/v3/` |

## 1. Module map

```
main.py                     entry, single-instance, hotkey, tray, close path เดียว, logging
src/core/  (ห้าม import tkinter)
  constants.py              APP_VERSION="3.0.0", MIN_ALPHA=0.3, APP_ID="PassagainP.QuickNote"
  models.py                 Note
  database.py               SQLite API (ข้อ 2)
  reminders.py              next_occurrence(), format_reminder(), parse/format datetime
  settings.py               Settings + subscribe (ข้อ 3)
  export.py                 export_markdown()
src/platform/
  tray.py                   ไอคอนเดียว (ข้อ 6)
  hotkey.py                 (คงเดิม)
  autostart.py              (คงเดิม + ใช้จาก Settings)
src/ui/
  strings.py                t(), set_language(), STRINGS{"th","en"}
  theme.py                  tokens, note colors, fonts, sv_ttk, system theme
  win11.py                  ctypes ทั้งหมด: DWM titlebar, accent, work area, high contrast
  icons.py                  ICONS = {"add": "", ...} (ตรวจ render แล้ว)
  widgets.py                IconButton, Tooltip, PlaceholderEntry, RoundedFrame, UndoBar, SettingsCard, animate helpers
  note_card.py              NoteCard
  board.py                  หน้าต่างหลัก
  scheduler.py              ReminderScheduler (after-handle เดียว)
  toast.py                  ToastManager
  reminder_dialog.py        ReminderDialog
  settings_window.py        SettingsWindow
assets/icon.ico             16/20/24/32/48/256
```

**ลบทิ้ง:** `ui/titlebar.py`, `ui/custom_toast.py`, `ui/unblockable_dialog.py`, `ui/notification.py`,
`services/` ทั้งโฟลเดอร์, ไฟล์ซ้ำที่ root (`board.py`, `database.py`, `hotkey.py`)

## 2. `src/core/database.py`

คงไว้: `APP_DIR`, `DB_WRITE_LOCK`, `_get_db_file()` (env `DB_PATH`), `_get_db_connection()` (WAL), ทุก connection ปิดใน `finally`, ทุก write อยู่ใต้ `DB_WRITE_LOCK`

Schema เพิ่ม (migrate แบบ `_migrate_db_schema`): `color TEXT DEFAULT 'none'`, `reminder_repeat TEXT DEFAULT 'none'`, `deleted_at TEXT`
- color ∈ `none|yellow|green|pink|purple|blue|gray`
- reminder_repeat ∈ `none|daily|weekdays|weekly`
- datetime ทุกตัวเก็บเป็น local time string: reminder `"YYYY-MM-DD HH:MM"`, timestamp อื่น `datetime.now().isoformat(timespec="seconds")` ห้ามใช้ `datetime('now')` ของ SQLite (UTC)
- "alarm กำลังดัง" = `reminder_triggered=1 AND reminder_datetime IS NOT NULL`

```python
def init_db() -> None                       # create + migrate + purge_deleted() + sanitize
def create_note(title: str, content: str = "", collapsed: bool = True) -> str
def get_note(note_id: str) -> dict | None
def get_notes_by_status(status: str) -> list[dict]      # ไม่รวม deleted, เรียงตามข้อ 0
def count_by_status() -> dict[str, int]                 # {"active": n, "completed": n} ไม่รวม deleted
def update_fields(note_id: str, **fields) -> None
    # อนุญาตเฉพาะ: title, content, collapsed, priority, color, is_pinned
    # เขียนเฉพาะ key ที่ส่งมา (แก้ C1, H6) — key อื่น → ValueError
def set_status(note_id: str, status: str) -> None       # completed → set completed_at; active → completed_at=NULL (M5)
def set_reminder(note_id: str, when: str | None, repeat: str = "none") -> None
    # when=None → ล้าง datetime + repeat='none'; มีค่า → triggered=0
def mark_ringing(note_id: str) -> None                  # triggered=1 (datetime คงไว้)
def dismiss_reminder(note_id: str) -> None
    # repeat='none' → datetime=NULL, triggered=0 ; repeat อื่น → datetime=next_occurrence, triggered=0
def snooze_reminder(note_id: str, when: str) -> None    # datetime=when, triggered=0 (repeat คงเดิม)
def get_due_reminders(now: str) -> list[dict]           # active, ไม่ deleted, triggered=0, datetime<=now (L8)
def get_next_reminder() -> dict | None                  # active ที่ triggered=0 เร็วที่สุดในอนาคต {id,title,reminder_datetime}
def soft_delete(note_id: str) -> None
def undo_delete(note_id: str) -> None
def purge_deleted() -> None                             # hard delete ทุก row ที่ deleted_at ไม่ NULL
def delete_all_completed() -> int
def backup_database(target_path: str) -> bool           # sqlite3 backup API (C9)
def restore_database(backup_path: str) -> bool          # validate + pre-restore snapshot + backup API + init_db
def auto_backup(keep: int = 7) -> str | None            # APP_DIR/backups/notes_YYYYMMDD.db วันละครั้ง ลบเก่าเกิน keep
```
ฟังก์ชันเก่า (`update_note`, `update_note_status_only`, `delete_note`, `get_all_notes`, `get_next_due_reminder`, `sanitize_reminders`) ลบหรือเปลี่ยนเป็น private ได้ เพราะ UI เก่าถูกเขียนใหม่ทั้งหมด

`src/core/reminders.py`:
```python
FMT = "%Y-%m-%d %H:%M"
def next_occurrence(when: str, repeat: str, now: datetime | None = None) -> str
    # ครั้งถัดไปที่ > now (ข้ามรอบที่พลาดไป) weekdays = จ–ศ
def format_reminder(when: str, now: datetime, lang: str) -> tuple[str, bool]
    # ("วันนี้ 14:30" | "พรุ่งนี้ 09:00" | "ศ. 31 ต.ค. 14:30" | "เลยกำหนด 14:30", is_overdue)
    # en: "Today 14:30" | "Tomorrow 09:00" | "Fri 31 Oct 14:30" | "Overdue 14:30"
def quick_times(now: datetime) -> dict[str, str]        # in15m, in1h, this_evening(17:00 ถ้ายังไม่ผ่าน ไม่งั้น None), tomorrow_9
```
ชื่อวัน/เดือนไทยเก็บใน `reminders.py` (core ห้าม import ui)

**Implemented notes (Wave A):** `reminders.py` มี `parse_dt(s)` / `format_dt(dt)` ด้วย; ฟังก์ชัน DB สาธารณะ raise `ValueError` เมื่อ input ผิด (priority/color/status/repeat/รูปแบบเวลา) — UI ต้อง validate ก่อนเรียก; overdue ข้ามวันแสดงวันที่ด้วย ("เลยกำหนด พ. 28 ต.ค. 09:15"); อัปเกรดจาก v2 ครั้งแรกจะพับการ์ดทุกใบ

`src/core/models.py`: `Note` เพิ่ม `color="none"`, `reminder_repeat="none"`, `deleted_at=None`; `from_dict` อ่าน `collapsed` ตามจริง (H4) ไม่บังคับ True

`src/core/export.py`: `export_markdown(path: str, lang: str) -> bool` — active ก่อน completed, หัวข้อ `## ` + checkbox `- [ ]/[x]`, เนื้อหา, เวลาเตือน

## 3. `src/core/settings.py`

```python
DEFAULTS = {
  "geometry": "380x600+120+120", "theme": "system",      # light|dark|system
  "language": "th", "font_size": "normal",               # small|normal|large
  "compact": False, "alpha": 1.0, "always_on_top": True,
  "close_to_tray": True, "tray_hint_shown": False,
  "sound": True, "snooze_default_minutes": 5,            # 5|10|15|30|60
  "auto_backup": True, "last_auto_backup": "",
  "hotkeys": {"new_note": "<ctrl>+<alt>+n", "toggle_show": "<ctrl>+<alt>+s"},
}
class Settings:
    data: dict                       # copy.deepcopy(DEFAULTS) (L7)
    def load(self) -> None           # JSON พัง → ลอง .bak → DEFAULTS; จากนั้น _coerce (alpha clamp MIN_ALPHA, enum ผิด → default)
    def save(self) -> None           # atomic: tmp → fsync → .bak → os.replace (L7)
    def get(self, key, default=None)
    def set(self, key, value, save: bool = True) -> None   # coerce + save + แจ้ง listener ถ้าค่าเปลี่ยน
    def subscribe(self, cb: Callable[[str, object], None]) -> None
```
autostart ไม่เก็บใน settings — อ่านสถานะจริงจาก `is_autostart_enabled()`

## 4. UI foundation

`strings.py`
```python
def set_language(lang: str) -> None
def get_language() -> str
def t(key: str, **kw) -> str        # key ไม่เจอ → คืน key (ไม่ crash); .format(**kw)
STRINGS = {"th": {...}, "en": {...}}   # key แบบ "board.search_placeholder", "card.menu.delete"
```
`theme.py`
```python
class Theme:
    def __init__(self, root, settings)  # สร้าง fonts, อ่าน accent, resolve โหมด, sv_ttk.set_theme, ttk styles
    mode: str                           # "light"|"dark" ที่ resolve แล้ว
    def c(self, token: str) -> str      # token ตาม spec 2.1 (+ accent จาก registry)
    def note_bg(self, color: str) -> str
    def note_dot(self, color: str) -> str
    def font(self, style: str)          # "caption"|"body"|"body_strong"|"subtitle"|"title"|"icon10"|"icon12"|"icon14"|"icon32"
    def set_font_size(self, size: str)  # configure ทุก font ทีเดียว
    def refresh(self) -> bool           # อ่านธีมระบบใหม่ (ถ้า settings theme=system) คืน True ถ้าเปลี่ยน
    def subscribe(self, cb: Callable[[], None]) -> None    # แจ้งเมื่อ mode/accent/font เปลี่ยน
    def apply_window(self, window) -> None                 # win11.apply_titlebar ตาม mode + caption color
```
ttk styles ที่ต้องมี: `Accent.TButton` (จาก sv_ttk), `Subtle.TButton`, `Link.TButton`, `Placeholder.TEntry`, `Switch.TCheckbutton`

`win11.py` (ทุกฟังก์ชันห้าม raise — fallback เงียบ)
```python
def apply_titlebar(window, dark: bool, caption_hex: str | None = None) -> None   # attr 20, 33, 35
def get_accent_color() -> str | None
def is_system_dark() -> bool
def is_high_contrast() -> bool
def get_work_area(window) -> tuple[int, int, int, int]    # (left, top, right, bottom) ของจอที่ window อยู่ (MonitorFromWindow)
def icon_font_family() -> str                              # "Segoe Fluent Icons" | "Segoe MDL2 Assets"
def set_app_user_model_id(app_id: str) -> None
```
`widgets.py`
```python
class IconButton(tk.Label):  __init__(parent, theme, icon: str, command, tooltip: str = "", size: int = 32, toggle: bool = False)
                             set_active(bool), set_icon(str); รองรับ hover/pressed/focus ring, <space>/<Return>
class Tooltip:               __init__(widget, text: str | Callable[[], str], delay_ms=500)
class PlaceholderEntry(ttk.Entry): __init__(parent, placeholder: str, textvariable=None, **kw); get_value() -> str (ไม่คืน placeholder)
class RoundedFrame(tk.Canvas): __init__(parent, theme, radius=8, bg_token|bg_hex, border_hex, border_width=1); .body = tk.Frame ข้างใน; set_colors(bg, border, width)
class UndoBar(tk.Frame):     show(message: str, on_undo: Callable, on_expire: Callable | None, seconds=5); เรียก on_expire ของอันก่อนทันทีถ้ามีอันใหม่มาแทน
class SettingsCard(tk.Frame): add_row(title: str, description: str | None, control_factory: Callable[[tk.Widget], tk.Widget]) -> tk.Widget
def fade_in(window, ms=150) / fade_out(window, ms=100, then=None) / slide_y(window, dy, ms)
def is_pointer_inside(widget) -> bool   # ใช้ winfo_containing (hover ไม่กระพริบ)
```

## 5. Main window

`note_card.py`
```python
@dataclass
class CardCallbacks:
    on_toggle_complete: Callable[[str], None]
    on_save: Callable[[str, dict], None]          # (note_id, {"title":..., "content":..., "collapsed":...})
    on_request_expand: Callable[[str], None]      # board พับใบอื่นก่อน แล้วเรียก card.expand()
    on_reminder: Callable[[str], None]            # เปิด ReminderDialog
    on_clear_reminder: Callable[[str], None]
    on_pin: Callable[[str, bool], None]
    on_priority: Callable[[str, str], None]
    on_color: Callable[[str, str], None]
    on_delete: Callable[[str], None]
    on_alarm_done: Callable[[str], None]          # chip "เสร็จแล้ว" ตอน alarm ดัง
    on_alarm_snooze: Callable[[str], None]        # chip "เลื่อน N นาที"
class NoteCard(RoundedFrame):
    def __init__(self, parent, note: Note, theme, callbacks: CardCallbacks, compact: bool = False)
    def refresh_from(self, note: Note) -> None    # sync ทุก widget จาก DB (H5) ไม่ทับช่องที่กำลังพิมพ์
    def flush_pending(self) -> None               # C7/C8 ยกเลิก timer + บันทึกค่าค้าง
    def expand(self) / collapse(self)
    def set_compact(self, compact: bool)
    def apply_theme(self)
    def focus_card(self)
```
ลำดับภายในการ์ดคงที่: header → content → chip row (`pack(before=...)`)
Title/content: debounce 500ms ผ่าน `on_save` + flush ตอน collapse/destroy/quit (ห้ามมี path save อื่น)

`board.py`
```python
class Board:
    def __init__(self, root, settings, theme, toasts: "ToastManager")
    root
    on_quit: Callable[[], None] | None        # main.py ตั้ง
    def refresh(self) -> None                 # debounce 150ms → _load_notes()
    def rebuild(self) -> None                 # ทำลายการ์ดทั้งหมด (ไม่ flush) แล้วโหลดใหม่ — ใช้หลัง restore
    def flush_all_cards(self) -> None
    def show(self) / hide(self) / toggle_visibility(self)   # toggle: ถ้ามองเห็นแต่ไม่มี focus → ดึงขึ้นมา (M22)
    def focus_quick_add(self) / focus_search(self)
    def reveal_note(self, note_id: str) -> None             # show + สลับแท็บถ้าจำเป็น + เลื่อน + กาง
    def open_settings(self) -> None                         # singleton เดียวทั้งแอป (H1)
    def get_persistable_geometry(self) -> str
```
`_load_notes()` ตามแบบ C5 ในรายงาน: pack_forget ทุกใบ → pack ใหม่ตามลำดับ DB, reuse ด้วย `refresh_from`, ไม่ล้าง search (H9), empty state label เดียว (M1/M2)
หน้าต่าง: native frame, `root.title("QuickNote")`, `iconbitmap(assets/icon.ico)`, `minsize(300,360)`, topmost จาก settings เท่านั้น (ห้าม re-apply loop ที่ไม่ดู setting และห้ามดันทับ dialog — H2)

`scheduler.py`
```python
class ReminderScheduler:
    def __init__(self, root, on_due: Callable[[list[dict]], None], on_missed: Callable[[list[dict]], None], interval_ms=5000)
    def start(self) / stop(self)
    def check_now(self) -> None      # after_cancel handle เดิม → ตรวจ → after ใหม่ (C2: มี chain เดียวเสมอ)
    def on_tick(self, cb)            # hook ให้ board ใช้ refresh ธีมระบบ / status bar ทุกรอบ
```
- due ที่เลยเวลาไม่เกิน 60 นาที → `on_due`; เกิน 60 นาที → `on_missed` (รวมเป็นรายการเดียว H8) — ทั้งสองกรณี `mark_ringing` ก่อน callback กันดังซ้ำ
- missed: repeat='none' → ทำให้ไม่ดัง (dismiss) แต่ยังแสดงใน toast missed; repeat อื่น → advance

## 6. Secondary windows

`toast.py`
```python
class ToastManager:
    def __init__(self, root, theme, settings)
    def show_reminder(self, note: dict, on_done, on_snooze: Callable[[str], None], on_open, on_dismiss) -> None
        # on_snooze รับ when-string ที่คำนวณแล้ว; เมนูเลื่อน 5/15/60 นาที/พรุ่งนี้ 09:00
        # โน้ตเดียวกันห้ามมี toast ซ้อน 2 อัน (M21)
    def show_missed(self, notes: list[dict], on_view: Callable[[], None]) -> None
    def show_info(self, message: str, seconds: int = 6) -> None   # เช่น hint "ยังทำงานอยู่ในถาด"
    def close_for(self, note_id: str) -> None
```
ไม่ใช้ transient (C6), overrideredirect + topmost, วางที่ work area ของจอที่ root อยู่ ซ้อนขึ้นด้านบนห่าง 8px, ✕/Esc = dismiss (H7), เสียงตาม `settings["sound"]`

`reminder_dialog.py`
```python
class ReminderDialog:
    def __init__(self, root, note: Note, theme, on_save: Callable[[str | None, str], None])
        # on_save(when_or_None, repeat) — dialog ไม่เขียน DB เอง; None = ลบการแจ้งเตือน
```
modal: `transient(root)` เฉพาะเมื่อ root มองเห็นอยู่ + `grab_set`, ปลด grab ทุกทางออก (M8), prefill (M6), validation inline (M7), ⚠ เวลาผ่านไปแล้ว (บันทึกได้ = ดังทันที)

`settings_window.py`
```python
@dataclass
class SettingsActions:
    backup: Callable[[], None]; restore: Callable[[], None]; export_markdown: Callable[[], None]
    open_data_folder: Callable[[], None]
class SettingsWindow:
    def __init__(self, root, settings, theme, actions: SettingsActions, on_close: Callable[[], None])
    def lift(self)
```
ทุก control → `settings.set(...)` ทันที (บันทึก + แจ้ง listener) ผู้ฟัง (board/theme/main) เป็นคน apply ผล ไม่มีปุ่ม Save/Close

`platform/tray.py`
```python
class TrayIcon:
    def __init__(self, on_toggle, on_new_note, on_settings, on_quit, tooltip: Callable[[], str])
    def run(self) / stop(self) / update_tooltip(self) / update_menu_language(self)
def start_tray_thread(...) -> TrayIcon
```
ไอคอนจาก `assets/icon.ico`, คลิกซ้าย = toggle (`default=True`), callback ทุกตัวถูกเรียกจาก thread ของ pystray → main.py ห่อด้วย `root.after(0, ...)`

## 7. main.py flow

1. `SetProcessDpiAwareness(2)` บรรทัดแรก ๆ, logging → `APP_DIR/quicknote.log` (Rotating, INFO) + stdout เฉพาะเมื่อมี (L10)
2. single instance: named mutex `Local\QuickNote.SingleInstance` + socket signal "SHOW" (timeout 1s) (L9)
3. `init_db()`, `auto_backup()` ถ้าเปิดไว้, settings.load(), `set_language`, `Theme`, `ToastManager`, `Board`, `ReminderScheduler`, tray, hotkey
4. ปิดหน้าต่าง (✕): ถ้า `close_to_tray` และ tray ทำงาน → `board.hide()` (+ hint ครั้งแรก) ไม่งั้น → `quit_app()`
5. `quit_app()` จุดเดียว (กันเรียกซ้ำ): flush_all_cards → settings geometry → save → `root.quit()`; cleanup listener/tray/lock ใน `finally` หลัง mainloop
6. ห้ามลบ `notes.db-wal/-shm` (C10)

## 8. Rules for every agent

- ทำเฉพาะไฟล์ที่ได้รับมอบหมาย ห้าม commit / switch branch / push
- core ห้าม import tkinter; thread อื่นห้ามแตะ widget (ใช้ `root.after(0, ...)`)
- Comment ภาษาไทย อธิบาย WHY, type hints เฉพาะ public method
- test ใหม่อยู่ `tests/v3/test_<area>.py` ใช้ `unittest`, Tk จริง (`withdraw()`), DB ชั่วคราวผ่าน `os.environ["DB_PATH"]` (save/restore ใน setUp/tearDown) ห้ามแตะ `~/.quicknote` จริง ห้าม mock Tk
- คำสั่งรัน: `python -m unittest discover -s tests/v3 -t .`
- รายงานกลับ: ไฟล์ที่แก้, API ที่เปลี่ยนจากสัญญา (ถ้ามี), ผลเทส (จำนวนผ่าน/ไม่ผ่าน), สิ่งที่ยังไม่ได้ทำ — ไม่ต้องแปะโค้ดทั้งไฟล์
