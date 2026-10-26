"""ข้อความ UI ทั้งหมด (ไทย/อังกฤษ) — ทุกที่ต้องเรียกผ่าน t("key", **kw)

โครงสร้าง: _TABLE เก็บ "key": (ไทย, อังกฤษ) บรรทัดเดียวต่อ key เพื่อให้สองภาษามี key ตรงกันเสมอ
(STRINGS สร้างจากตารางนี้ จึงลืมแปลภาษาใดภาษาหนึ่งไม่ได้) key แบบ "area.sub.name"
หา key ได้จากหัวข้อกลุ่ม "# ===== area =====" ด้านล่าง
"""

from __future__ import annotations

_LANGS = ("th", "en")
_lang = "th"

_TABLE: dict[str, tuple[str, str]] = {
    # ===== common — ปุ่ม/คำทั่วไป =====
    "common.ok": ("ตกลง", "OK"),
    "common.cancel": ("ยกเลิก", "Cancel"),
    "common.close": ("ปิด", "Close"),
    "common.save": ("บันทึก", "Save"),
    "common.delete": ("ลบ", "Delete"),
    "common.error_title": ("เกิดข้อผิดพลาด", "Something went wrong"),
    "common.untitled": ("(ไม่มีชื่อ)", "(Untitled)"),
    "app.name": ("QuickNote", "QuickNote"),

    # ===== board — หน้าต่างหลัก: toolbar / แท็บ / quick-add / status bar =====
    "board.search_placeholder": ("ค้นหาโน้ต (Ctrl+F)", "Search notes (Ctrl+F)"),
    "board.search_icon_tip": ("ค้นหาโน้ต (Ctrl+F)", "Search notes (Ctrl+F)"),
    "board.search_clear_tip": ("ล้างการค้นหา (Esc)", "Clear search (Esc)"),
    "board.topmost_tip": ("ปักหน้าต่างไว้บนสุด (Ctrl+T)", "Keep window on top (Ctrl+T)"),
    "board.settings_tip": ("ตั้งค่า", "Settings"),
    "board.tab_active": ("งานที่ทำอยู่ ({n})", "Active ({n})"),
    "board.tab_completed": ("เสร็จแล้ว ({n})", "Completed ({n})"),
    "board.tab_active_tip": ("งานที่ทำอยู่ (Ctrl+1)", "Active notes (Ctrl+1)"),
    "board.tab_completed_tip": ("งานที่เสร็จแล้ว (Ctrl+2)", "Completed notes (Ctrl+2)"),
    "board.quick_add_placeholder": ("＋  เพิ่มโน้ต แล้วกด Enter", "＋  Add a note and press Enter"),
    "board.quick_add_tip": ("Enter = เพิ่มโน้ต · Shift+Enter = เพิ่มแล้วกางเพื่อพิมพ์รายละเอียด (Ctrl+N)",
                            "Enter = add note · Shift+Enter = add and expand for details (Ctrl+N)"),
    "board.empty_title": ("ยังไม่มีโน้ต", "No notes yet"),
    "board.empty_hint": ("พิมพ์ในช่องด้านบนเพื่อเพิ่มโน้ตแรก", "Type in the box above to add your first note"),
    "board.empty_completed": ("ยังไม่มีงานที่เสร็จ", "No completed notes yet"),
    "board.empty_search": ("ไม่พบโน้ตที่ตรงกับ “{query}”", "No notes match “{query}”"),
    "board.empty_search_clear": ("ล้างการค้นหา", "Clear search"),
    "board.delete_all_completed": ("ลบงานที่เสร็จแล้วทั้งหมด", "Delete all completed notes"),
    "board.status_next": ("แจ้งเตือนถัดไป {time} · {title}", "Next reminder {time} · {title}"),
    "board.window_title": ("QuickNote", "QuickNote"),

    # ===== card — การ์ดโน้ต: tooltip / meta / เมนู ⋯ =====
    "card.title_placeholder": ("ตั้งชื่อโน้ต", "Note title"),
    "card.content_placeholder": ("เพิ่มรายละเอียด…", "Add details…"),
    "card.complete_tip": ("ทำเครื่องหมายว่าเสร็จแล้ว", "Mark as completed"),
    "card.restore_tip": ("คืนเป็นงานที่ทำอยู่", "Mark as active"),
    "card.reminder_tip": ("ตั้งการแจ้งเตือน (Ctrl+R)", "Set reminder (Ctrl+R)"),
    "card.more_tip": ("เพิ่มเติม", "More"),
    "card.pinned_tip": ("ปักหมุดไว้ด้านบน", "Pinned to top"),
    "card.saved": ("บันทึกแล้ว", "Saved"),
    "card.completed_meta": ("เสร็จเมื่อ {when}", "Completed {when}"),
    "card.menu.complete": ("ทำเครื่องหมายว่าเสร็จแล้ว", "Mark as completed"),
    "card.menu.restore": ("คืนเป็นงานที่ทำอยู่", "Mark as active"),
    "card.menu.pin": ("ปักหมุดไว้ด้านบน", "Pin to top"),
    "card.menu.unpin": ("เลิกปักหมุด", "Unpin"),
    "card.menu.reminder": ("ตั้งการแจ้งเตือน…", "Set reminder…"),
    "card.menu.priority": ("ความสำคัญ", "Priority"),
    "card.menu.color": ("สี", "Color"),
    "card.menu.delete": ("ลบ", "Delete"),
    "card.chip.reminder_tip": ("แก้ไขการแจ้งเตือน", "Edit reminder"),
    "card.chip.reminder_clear_tip": ("ลบการแจ้งเตือน", "Remove reminder"),
    "card.chip.priority_tip": ("เปลี่ยนความสำคัญ", "Change priority"),
    "card.chip.add_reminder": ("เพิ่มการแจ้งเตือน", "Add reminder"),
    "card.alarm_done": ("เสร็จแล้ว", "Done"),
    "card.alarm_snooze": ("เลื่อน {n} นาที", "Snooze {n} min"),
    "card.alarm_ringing": ("ถึงเวลาแล้ว", "It's time"),
    "card.when_today": ("วันนี้ {hm}", "today {hm}"),          # ใช้กับ "เสร็จเมื่อ {when}" (เวลาอดีต)
    "card.when_yesterday": ("เมื่อวาน {hm}", "yesterday {hm}"),
    "card.ringing_at": ("ถึงเวลาแล้ว {hm}", "Due now {hm}"),

    # ===== priority / color — ชื่อระดับความสำคัญและสีโน้ต =====
    "priority.high": ("สูง", "High"),
    "priority.medium": ("ปานกลาง", "Medium"),
    "priority.low": ("ต่ำ", "Low"),
    "priority.none": ("ไม่มี", "None"),
    "color.none": ("ไม่มี", "None"),
    "color.yellow": ("เหลือง", "Yellow"),
    "color.green": ("เขียว", "Green"),
    "color.pink": ("ชมพู", "Pink"),
    "color.purple": ("ม่วง", "Purple"),
    "color.blue": ("ฟ้า", "Blue"),
    "color.gray": ("เทา", "Gray"),

    # ===== undo — แถบเลิกทำที่ล่างหน้าต่าง =====
    "undo.action": ("เลิกทำ", "Undo"),
    "undo.completed": ("ทำเครื่องหมายว่าเสร็จแล้ว", "Marked as completed"),
    "undo.restored": ("คืนเป็นงานที่ทำอยู่แล้ว", "Marked as active"),
    "undo.deleted": ("ลบโน้ตแล้ว", "Note deleted"),

    # ===== reminder — หน้าต่างตั้งการแจ้งเตือน =====
    "reminder.title": ("ตั้งการแจ้งเตือน", "Set reminder"),
    "reminder.quick_15m": ("อีก 15 นาที", "In 15 minutes"),
    "reminder.quick_1h": ("อีก 1 ชั่วโมง", "In 1 hour"),
    "reminder.quick_evening": ("เย็นนี้ 17:00", "This evening 17:00"),
    "reminder.quick_tomorrow": ("พรุ่งนี้ 09:00", "Tomorrow 09:00"),
    "reminder.date": ("วันที่", "Date"),
    "reminder.time": ("เวลา", "Time"),
    "reminder.repeat": ("ทำซ้ำ", "Repeat"),
    "reminder.repeat.none": ("ไม่ทำซ้ำ", "Does not repeat"),
    "reminder.repeat.daily": ("ทุกวัน", "Every day"),
    "reminder.repeat.weekdays": ("วันทำงาน (จ–ศ)", "Weekdays (Mon–Fri)"),
    "reminder.repeat.weekly": ("ทุกสัปดาห์", "Every week"),
    "reminder.past_warning": ("เวลานี้ผ่านไปแล้ว — จะแจ้งเตือนทันทีที่บันทึก", "This time has passed — it will alert as soon as you save"),
    "reminder.err_date": ("วันที่ไม่ถูกต้อง (วว/ดด/ปปปป)", "Invalid date (dd/mm/yyyy)"),
    "reminder.err_hour": ("ชั่วโมงต้องอยู่ระหว่าง 0–23", "Hour must be 0–23"),
    "reminder.err_minute": ("นาทีต้องอยู่ระหว่าง 0–59", "Minute must be 0–59"),
    "reminder.delete": ("ลบการแจ้งเตือน", "Remove reminder"),
    "reminder.calendar_tip": ("เลือกจากปฏิทิน", "Pick from calendar"),

    # ===== toast — popup แจ้งเตือนมุมขวาล่าง =====
    "toast.header": ("QuickNote · {time}", "QuickNote · {time}"),
    "toast.done": ("เสร็จแล้ว", "Done"),
    "toast.snooze": ("เลื่อน", "Snooze"),
    "toast.open": ("เปิด", "Open"),
    "toast.dismiss_tip": ("ปิดการแจ้งเตือน (Esc)", "Dismiss (Esc)"),
    "toast.snooze_5": ("5 นาที", "5 minutes"),
    "toast.snooze_15": ("15 นาที", "15 minutes"),
    "toast.snooze_60": ("1 ชั่วโมง", "1 hour"),
    "toast.snooze_tomorrow": ("พรุ่งนี้ 09:00", "Tomorrow 09:00"),
    "toast.missed": ("พลาดการแจ้งเตือน {n} รายการ", "Missed {n} reminders"),
    "toast.missed_view": ("ดู", "View"),
    "toast.missed_more": ("และอีก {n} รายการ", "and {n} more"),
    "toast.tray_hint": ("QuickNote ยังทำงานอยู่ในถาดระบบ เพื่อแจ้งเตือนคุณ", "QuickNote is still running in the system tray so it can remind you"),

    # ===== settings — หน้าต่างตั้งค่า (กลุ่ม → แถว: ชื่อ + คำอธิบาย) =====
    "settings.title": ("ตั้งค่า", "Settings"),
    "settings.group.appearance": ("ลักษณะ", "Appearance"),
    "settings.group.behavior": ("การทำงาน", "Behavior"),
    "settings.group.notifications": ("การแจ้งเตือน", "Notifications"),
    "settings.group.data": ("ข้อมูล", "Data"),
    "settings.group.about": ("เกี่ยวกับ", "About"),
    "settings.theme": ("ธีม", "Theme"),
    "settings.theme.desc": ("เลือกโหมดสว่าง มืด หรือตามระบบ", "Choose light, dark or follow the system"),
    "settings.theme.light": ("สว่าง", "Light"),
    "settings.theme.dark": ("มืด", "Dark"),
    "settings.theme.system": ("ตามระบบ", "Use system setting"),
    "settings.language": ("ภาษา", "Language"),
    "settings.language.desc": ("ภาษาของเมนูและข้อความทั้งหมด", "Language for all menus and text"),
    "settings.language.th": ("ไทย", "ไทย"),
    "settings.language.en": ("English", "English"),
    "settings.alpha": ("ความโปร่งใสของหน้าต่าง", "Window opacity"),
    "settings.alpha.desc": ("ปรับให้มองทะลุหน้าต่างได้ (ต่ำสุด 30%)", "See through the window (minimum 30%)"),
    "settings.font_size": ("ขนาดตัวอักษร", "Text size"),
    "settings.font_size.desc": ("ปรับขนาดตัวอักษรทั้งแอป", "Change text size across the app"),
    "settings.font_size.small": ("เล็ก", "Small"),
    "settings.font_size.normal": ("ปกติ", "Normal"),
    "settings.font_size.large": ("ใหญ่", "Large"),
    "settings.compact": ("โหมดกะทัดรัด", "Compact mode"),
    "settings.compact.desc": ("การ์ดแสดงแค่หัวข้อ ประหยัดพื้นที่", "Cards show only the title to save space"),
    "settings.autostart": ("เปิดพร้อม Windows", "Start with Windows"),
    "settings.autostart.desc": ("เปิด QuickNote อัตโนมัติเมื่อเข้าสู่ระบบ", "Open QuickNote automatically when you sign in"),
    "settings.autostart.error": ("ตั้งค่าเปิดพร้อม Windows ไม่สำเร็จ", "Couldn't change the Start with Windows setting"),
    "settings.always_on_top": ("อยู่บนสุดเสมอ", "Always on top"),
    "settings.always_on_top.desc": ("หน้าต่างลอยอยู่เหนือแอปอื่น", "Keep the window above other apps"),
    "settings.close_to_tray": ("ปิดหน้าต่างแล้วซ่อนไว้ในถาด", "Hide to tray when closed"),
    "settings.close_to_tray.desc": ("QuickNote ยังทำงานเพื่อแจ้งเตือนหลังปิดหน้าต่าง", "QuickNote keeps running to send reminders after you close the window"),
    "settings.hotkey_new": ("คีย์ลัดโน้ตใหม่", "New note shortcut"),
    "settings.hotkey_toggle": ("คีย์ลัดแสดง/ซ่อน", "Show/hide shortcut"),
    "settings.hotkey.desc": ("คลิกแล้วกดคีย์ใหม่เพื่อบันทึก", "Click, then press the new keys to save"),
    "settings.hotkey.recording": ("กดคีย์ลัด…", "Press keys…"),
    "settings.hotkey.invalid": ("ต้องมี Ctrl, Alt หรือ Win ร่วมด้วย", "Must include Ctrl, Alt or Win"),
    "settings.hotkey.duplicate": ("ซ้ำกับคีย์ลัดอีกอัน", "Already used by the other shortcut"),
    "settings.sound": ("เล่นเสียง", "Play sound"),
    "settings.sound.desc": ("เล่นเสียงเมื่อมีการแจ้งเตือน", "Play a sound when a reminder fires"),
    "settings.snooze": ("เลื่อนเตือนเริ่มต้น", "Default snooze"),
    "settings.snooze.desc": ("เวลาเลื่อนเตือนเมื่อกดปุ่มเลื่อนบนการ์ด", "Used by the snooze button on cards"),
    "settings.snooze.minutes": ("{n} นาที", "{n} min"),
    "settings.snooze.hour": ("1 ชั่วโมง", "1 hour"),
    "settings.auto_backup": ("สำรองข้อมูลอัตโนมัติทุกวัน", "Back up automatically every day"),
    "settings.auto_backup.desc": ("เก็บไว้ 7 ชุดล่าสุด", "Keeps the 7 most recent backups"),
    "settings.backup": ("สำรองข้อมูลตอนนี้", "Back up now"),
    "settings.backup.desc": ("บันทึกสำเนาโน้ตทั้งหมดเป็นไฟล์", "Save a copy of all notes to a file"),
    "settings.backup.button": ("สำรอง…", "Back up…"),
    "settings.restore": ("กู้คืนจากไฟล์สำรอง", "Restore from backup"),
    "settings.restore.desc": ("แทนที่โน้ตปัจจุบันด้วยไฟล์สำรอง", "Replace current notes with a backup file"),
    "settings.restore.button": ("กู้คืน…", "Restore…"),
    "settings.export": ("ส่งออกเป็น Markdown", "Export as Markdown"),
    "settings.export.desc": ("ส่งออกโน้ตทั้งหมดเป็นไฟล์ .md", "Export all notes to a .md file"),
    "settings.export.button": ("ส่งออก…", "Export…"),
    "settings.open_folder": ("เปิดโฟลเดอร์ข้อมูล", "Open data folder"),
    "settings.open_folder.button": ("เปิด", "Open"),
    "settings.about": ("QuickNote {version} · สร้างโดย {author}", "QuickNote {version} · by {author}"),

    # ===== tray — ไอคอนถาดระบบ =====
    "tray.show": ("แสดง QuickNote", "Show QuickNote"),
    "tray.new_note": ("โน้ตใหม่", "New note"),
    "tray.settings": ("ตั้งค่า", "Settings"),
    "tray.quit": ("ออก", "Quit"),
    "tray.tooltip": ("QuickNote", "QuickNote"),
    "tray.tooltip_next": ("QuickNote · แจ้งเตือนถัดไป {time}", "QuickNote · next reminder {time}"),

    # ===== dialog — ยืนยัน / file dialog / ข้อความผลลัพธ์ =====
    "dialog.delete_completed.title": ("ลบงานที่เสร็จแล้วทั้งหมด?", "Delete all completed notes?"),
    "dialog.delete_completed.body": ("จะลบ {n} รายการอย่างถาวร ไม่สามารถเลิกทำได้", "{n} notes will be permanently deleted. This can't be undone."),
    "dialog.delete_completed.confirm": ("ลบทั้งหมด", "Delete all"),
    "dialog.restore.title": ("กู้คืนข้อมูล?", "Restore data?"),
    "dialog.restore.body": ("โน้ตปัจจุบันจะถูกแทนที่ด้วยไฟล์สำรอง (ระบบจะเก็บสำเนาข้อมูลปัจจุบันไว้ให้ก่อน)",
                            "Your current notes will be replaced by the backup (a copy of the current data is kept first)."),
    "dialog.restore.confirm": ("กู้คืน", "Restore"),
    "dialog.backup.title": ("บันทึกไฟล์สำรอง", "Save backup"),
    "dialog.restore.pick": ("เลือกไฟล์สำรอง", "Choose backup file"),
    "dialog.export.title": ("ส่งออกเป็น Markdown", "Export as Markdown"),
    "dialog.filetype.db": ("ไฟล์สำรอง QuickNote", "QuickNote backup"),
    "dialog.filetype.md": ("ไฟล์ Markdown", "Markdown file"),
    "dialog.filetype.all": ("ทุกไฟล์", "All files"),
    "msg.backup_ok": ("สำรองข้อมูลแล้ว", "Backup saved"),
    "msg.backup_fail": ("สำรองข้อมูลไม่สำเร็จ", "Backup failed"),
    "msg.restore_ok": ("กู้คืนข้อมูลแล้ว", "Data restored"),
    "msg.restore_fail": ("กู้คืนไม่สำเร็จ — ไฟล์ไม่ถูกต้อง ข้อมูลเดิมไม่ถูกเปลี่ยน", "Restore failed — invalid file. Your data was not changed."),
    "msg.export_ok": ("ส่งออกแล้ว", "Exported"),
    "msg.export_fail": ("ส่งออกไม่สำเร็จ", "Export failed"),
    "msg.reminder_save_fail": ("บันทึกการแจ้งเตือนไม่สำเร็จ", "Couldn't save the reminder"),
    "msg.open_folder_fail": ("เปิดโฟลเดอร์ไม่ได้", "Couldn't open the folder"),
    "msg.hotkey_failed": ("ลงทะเบียนคีย์ลัดไม่ได้ อาจถูกโปรแกรมอื่นใช้อยู่", "Couldn't register the shortcut. Another app may be using it."),
}

STRINGS: dict[str, dict[str, str]] = {
    "th": {k: v[0] for k, v in _TABLE.items()},
    "en": {k: v[1] for k, v in _TABLE.items()},
}


def set_language(lang: str) -> None:
    """ภาษาที่ไม่รู้จักถูกเมินเงียบ ๆ (ค่าเก่าใน settings.json อาจผิด)"""
    global _lang
    if lang in _LANGS:
        _lang = lang


def get_language() -> str:
    return _lang


def t(key: str, **kw) -> str:
    """แปลข้อความ — key ไม่เจอคืน key เอง (เห็นชัดตอน dev แต่ไม่ crash) / format พลาดคืนข้อความดิบ"""
    text = STRINGS[_lang].get(key)
    if text is None:
        return key
    if kw:
        try:
            return text.format(**kw)
        except (KeyError, IndexError, ValueError):
            return text
    return text
