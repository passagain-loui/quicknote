# QuickNote v2.9.46 — Bug Audit Report

> ขอบเขต: อ่านโค้ดทั้งหมดใน `main.py` + `src/**` (ไม่ได้แก้ไขอะไร)
> วิธีตรวจ: อ่านโค้ด และทดสอบพฤติกรรม Tk จริง 3 จุด (ทำเครื่องหมาย **[ยืนยันแล้ว]**) ด้วย Python 3.14 / Tk 9.0 บนเครื่องนี้
> ระดับความรุนแรง: 🔴 Critical (ข้อมูลหาย / ฟีเจอร์หลักพัง) · 🟠 High (ฟีเจอร์ไม่ทำงานตามที่อ้าง) · 🟡 Medium (UX / ความไม่สอดคล้อง) · ⚪ Low / Code health

---

## 🔴 CRITICAL

### C1. Priority ไม่เคยถูกบันทึกลง DB
- **ไฟล์:** `src/ui/note_card.py:583-613` → `src/ui/board.py:599-605`
- **อาการ:** เปลี่ยน priority (🚩) แล้ว refresh / ปิดเปิดแอป → priority กลับเป็น none
- **สาเหตุ:** `_set_priority()` เรียก `on_update(note)` → `Board._on_note_update()` เรียก `update_note(...)` โดย **ไม่ส่ง `priority=`** (grep ทั้ง `src/` ไม่มีที่ไหนส่ง `priority=` ให้ `update_note` เลย)
- **แนวทางแก้:** ส่ง `priority=note.priority` ใน `_on_note_update` หรือให้ `_set_priority` บันทึกตรง

### C2. Reminder scheduler loop เพิ่มเป็นสองเท่าทุกครั้งที่กด Dismiss/Snooze (exponential)
- **ไฟล์:** `src/ui/board.py:1021-1035` + `1115-1118`
- **สาเหตุ:** ทาง paused และทาง debounce เรียก `self.root.after(5000, self._check_reminders)` แล้ว `return` แต่ block `finally:` ก็เรียก `after(5000, ...)` ซ้ำอีกครั้ง จึงเกิด 2 chain ทุกครั้งที่เข้า path นี้
- **ผล:** การ action แต่ละครั้งตั้ง debounce 5 วินาที แต่ละ chain ที่มีอยู่จะเข้า path debounce 1 ครั้งแล้วแตกเป็น 2 → หลัง N actions จะมี ~2^N loops ซึ่งแต่ละ loop อ่าน DB ทั้งตารางทุก 5 วินาที → CPU/IO พุ่ง แอปช้าลงเรื่อย ๆ จนค้าง
- **แนวทางแก้:** ลบ `after()` ใน early-return (ให้ `finally` เป็นจุดเดียว) หรือใช้ handle เดียว + `after_cancel`

### C3. Settings (opacity, snooze, geometry) ไม่เคยถูกเขียนลงดิสก์
- **ไฟล์:** `src/ui/board.py:748-755`, `main.py:370-384`, `src/ui/settings_window.py:546-549`, `src/ui/board.py:1457-1485`
- **สาเหตุ:**
  1. ปุ่ม ✕ บน titlebar → `Board._on_close()` → `root.quit()` ตรง ๆ ข้าม `on_closing()` ที่เป็นจุดเดียวที่เรียก `settings.save()`
  2. `WM_DELETE_WINDOW` ไม่ถูกยิงสำหรับหน้าต่าง `overrideredirect(True)` (ไม่มี native close)
  3. ปุ่ม ⚙ เปิด Settings ผ่าน `Board._open_settings()` ซึ่ง `on_save_callback=self._on_settings_saved` → apply UI อย่างเดียว ไม่เรียก `settings.save()`
  4. Tray → Exit → `root.quit()` ไม่ save เช่นกัน; `finally` ใน `main()` ก็ไม่ save
- **ผล:** ปรับ opacity/snooze แล้วเปิดใหม่ ค่าหายหมด

### C4. ตำแหน่ง/ขนาดหน้าต่างที่บันทึกไว้ถูกเพิกเฉย
- **ไฟล์:** `src/ui/board.py:36, 65, 273-331`
- **สาเหตุ:** `Board.__init__` รับ `geometry` แต่ไม่ใช้เลย `_center_main_window()` บังคับ 420x600 กลางจอทุกครั้ง ส่วน `_get_safe_geometry()` / `_restore_geometry()` เป็น dead code
- **ผล:** ขัดกับ checklist "Drag window → close → reopen → same position/size" (รวมกับ C3 ก็ยังไม่มีอะไรถูกบันทึกอยู่ดี)

### C5. ลำดับการ์ดจาก DB ไม่ถูกนำไปใช้กับการ์ดที่มีอยู่แล้ว — **[ยืนยันแล้ว]**
- **ไฟล์:** `src/ui/board.py:469-497`
- **สาเหตุ:** `_load_notes()` เรียก `card.pack(fill="x", ...)` ซ้ำกับการ์ดที่ pack อยู่แล้ว ซึ่ง Tk **ไม่ย้ายตำแหน่ง** (ทดสอบแล้ว: pack ซ้ำในลำดับ c,b,a ผลยังเป็น a,b,c) การ์ดใหม่จึงไปต่อท้ายเสมอ
- **ผล:** การเรียงตาม pin / alarm / priority / created_at ใน SQL ไม่มีผลจริงบนจอ, unpin แล้วการ์ดยังค้างบนสุด, `repack_card_to_top()` เป็นแค่ band-aid ที่ทำให้บั๊ก "new task not at top" วนกลับมาหลายเวอร์ชัน (v2.9.39→v2.9.42)
- **แนวทางแก้:** ใน `_load_notes` ให้ `pack_forget()` การ์ดทั้งหมดก่อน แล้ว pack ใหม่ตามลำดับ `notes_data` (หรือใช้ `pack(after=prev)`)

### C6. Reminder popup ไม่แสดงเมื่อหน้าต่างหลักถูกซ่อนลง tray — **[ยืนยันแล้ว]**
- **ไฟล์:** `src/ui/unblockable_dialog.py:68-72`, `src/ui/board.py:675-680`
- **สาเหตุ:** dialog ใช้ `self.transient(parent)` และ Tk ให้ transient window **รับ state ของ master** ถ้า master ถูก `withdraw()` (ปุ่มเหลือง − หรือ Ctrl+Alt+S) dialog ก็จะ withdrawn ตาม (ทดสอบแล้ว: `winfo_ismapped()=0, state=withdrawn`)
- **ผล:** เวลาที่ผู้ใช้ซ่อนแอปไว้ ซึ่งเป็นกรณีที่ต้องการแจ้งเตือนมากที่สุด จะได้ยินแค่เสียง "ติ๊ง" ไม่เห็น popup ทั้ง note ถูก set `reminder_triggered=1` ไปแล้ว → การแจ้งเตือนหายเงียบ
- **แนวทางแก้:** ไม่ใช้ transient กับ root ที่อาจถูกซ่อน หรือ deiconify root ก่อนแสดง

### C7. เนื้อหาหายเมื่อพิมพ์แล้วกดพับ (▸) ภายใน 500ms
- **ไฟล์:** `src/ui/note_card.py:382-393, 484-494, 321-326`
- **สาเหตุ:** `_on_toggle_fold()` เรียก `_hide_content()` (destroy Text + set `content_text=None`) โดยไม่ flush ก่อน ส่วน `tk.Button` ไม่รับ focus เมื่อคลิก จึงไม่เกิด FocusOut ต่อมา debounce `save_content()` เรียก `None.winfo_exists()` → **AttributeError** (โค้ดจับแค่ `tk.TclError`)
- **ผล:** ตัวอักษรที่พิมพ์ช่วงสุดท้ายหาย + traceback ใน Tk callback

### C8. Title ที่พิมพ์ค้างไว้หายเมื่อปิด/ซ่อนแอป
- **ไฟล์:** `src/ui/note_card.py:151, 450-455`
- **สาเหตุ:** title บันทึกเฉพาะตอน `<FocusOut>` (ไม่มี debounce เหมือน content) ถ้าพิมพ์ title แล้วกด ✕ / tray Exit / hotkey hide → `root.quit()` ไม่ flush
- **เพิ่มเติม:** debounce timer ของ content ที่ค้างอยู่ (<500ms) ก็ถูกทิ้งเมื่อ `quit()` เช่นกัน ไม่มี "flush all cards on exit"

### C9. Backup/Restore ไม่ปลอดภัยกับ SQLite WAL
- **ไฟล์:** `src/core/database.py:440-495`, `src/ui/settings_window.py:614-649`
- **สาเหตุ:**
  - Backup ใช้ `shutil.copy2` คัดลอกเฉพาะ `notes.db` แต่ข้อมูลที่ commit แล้วอาจยังอยู่ใน `notes.db-wal` → ไฟล์ backup ขาดข้อมูลล่าสุด
  - Restore คัดลอกทับ `notes.db` ขณะที่ `-wal`/`-shm` เก่ายังอยู่ → SQLite อาจ replay WAL เก่าลงบน DB ที่ restore → ข้อมูลปนกันหรือ DB เสีย
  - ไม่ตรวจว่าไฟล์ที่เลือกเป็น SQLite/มีตาราง notes จริง (เลือกไฟล์ผิด → DB พัง → `init_db()` สร้างตารางว่างใหม่)
  - หลัง restore สำเร็จ UI **ไม่ reload notes** (`on_save` แค่ refresh theme) → การ์ดเก่ายังอยู่ แก้ไขการ์ดเก่าจะไปเขียนทับ row ที่ id ตรงกันใน DB ที่ restore มา
- **แนวทางแก้:** ใช้ `sqlite3.Connection.backup()` ทั้งสองทาง + `_load_notes()` หลัง restore

### C10. `cleanup_temp_artifacts()` ลบไฟล์ WAL/SHM ของ DB production
- **ไฟล์:** `main.py:186-197`
- **สาเหตุ:** ลบ `notes.db-wal` / `notes.db-shm` ที่อายุ > 1 วัน โดยไม่ตรวจว่ามี process อื่นเปิด DB อยู่ไหม (เช่น instance อื่น, test, DB browser) การลบ WAL ที่ยังไม่ checkpoint = ข้อมูลที่ commit แล้วหาย; การลบ `-shm` ขณะเปิดอยู่ = เสี่ยง corruption ส่วนการลบด้วยมือแบบนี้ไม่จำเป็นอยู่แล้ว เพราะ SQLite จัดการเอง

---

## 🟠 HIGH

### H1. Tray → "Settings" ใช้ไม่ได้ (AttributeError)
- **ไฟล์:** `main.py:285-290`
- **สาเหตุ:** ส่ง `settings.settings` แต่ class `Settings` มีแค่ `.data` → AttributeError ถูก catch แล้ว print เฉย ๆ
- **เพิ่มเติม:** มี singleton 2 ชุดแยกกัน (`main.settings_window` กับ `board.settings_window_instance`) ถ้าแก้ H1 แล้วจะเปิด Settings ได้ 2 หน้าต่างพร้อมกัน (จาก tray + จากปุ่ม ⚙)

### H2. ปุ่ม pin หน้าต่าง (📌/📍) ใช้ไม่ได้จริง
- **ไฟล์:** `src/ui/board.py:757-763`, `1435-1440`, `main.py:360-363`
- **สาเหตุ:** `_reapply_topmost()` บังคับ `-topmost True` ทุก 3 วินาทีโดยไม่ดู `titlebar.is_topmost` → กด unpin ไปแล้ว 3 วินาทีก็กลับเป็น topmost ขณะเดียวกัน `_force_main_window_foreground` / `_bring_to_front` ตั้ง `-topmost False` หลัง 0.8–1 วินาที → สถานะ topmost กระพริบไปมา
- **เพิ่มเติม:** การ re-raise main ทุก 3 วินาทีทำให้ main ทับ Settings/Reminder dialog ได้ ซึ่งเป็นต้นเหตุคลาสสิกของบั๊ก "dialog หายไปหลังหน้าต่างหลัก" (v2.5.x–v2.9.3x)

### H3. Roll-up (ดับเบิลคลิก titlebar) พัง — **[ยืนยันแล้ว]**
- **ไฟล์:** `src/ui/board.py:62, 682-709, 380-384`
- **สาเหตุ:** `root.minsize(500, 400)` ทำให้ `geometry("Wx32")` ถูก clamp เป็น 400 (ทดสอบแล้ว: height=400) → body หายแต่หน้าต่างยังสูง 400 เหลือพื้นที่ว่าง; titlebar สูง 42 แต่ roll-up ตั้ง 32; resize handle อ้างขั้นต่ำ 260x180 แต่ถูก minsize ทับ

### H4. สถานะพับ/กาง (collapsed) ไม่เคยถูกเก็บ + state เพี้ยน
- **ไฟล์:** `src/core/models.py:31-42`, `src/ui/board.py:478, 489`
- **สาเหตุ:** `from_dict` บังคับ `collapsed=True` เสมอ และ `_load_notes` บังคับซ้ำ แต่การ์ดที่ reuse ยังแสดง content อยู่ (ไม่ได้ hide widget) → model บอก collapsed แต่จอแสดงกาง → ต้องกดปุ่มพับ 2 ครั้งถึงจะพับ, ไอคอน ▾/▸ ไม่ตรงสถานะ
- ทุก refresh (alarm, dismiss, pin, new) ก็ทำให้ model state ของการ์ดที่ผู้ใช้กางไว้ถูกรีเซ็ต

### H5. การ์ดที่ reuse ไม่อัปเดต widget ตามข้อมูลใหม่
- **ไฟล์:** `src/ui/board.py:474-485`
- **สาเหตุ:** แทน `card.note` ด้วย object ใหม่ แต่ไม่อัปเดต `title_var`, ข้อความใน Text, ไอคอน pin, สี flag/priority badge, ไอคอนนาฬิกา ⏰/⏱, กรอบแดง
- **ตัวอย่าง:** Snooze แล้วไอคอนยังเป็น ⏱ (ไม่ได้เรียก `update_reminder_state(True)`); กรอบแดงขึ้นกับ `set_alarm_highlight()` อย่างเดียว ไม่ได้ขึ้นกับข้อมูล

### H6. `_on_note_update` เขียน reminder fields จาก object ที่อาจ stale
- **ไฟล์:** `src/ui/board.py:599-605`
- **สาเหตุ:** ทุกครั้งที่บันทึก title/content/fold จะเขียน `reminder_datetime` และ `reminder_triggered` จาก `card.note` ด้วย ถ้า DB เพิ่งถูกเปลี่ยนโดย Dismiss/Snooze/scheduler แต่ debounced refresh (200ms) ยังไม่มา การพิมพ์ช่วงนั้นจะเขียนค่าเก่าทับ → reminder ที่ dismiss แล้วกลับมา / `triggered` ถูก reset → alarm ดังซ้ำ
- **แนวทางแก้:** แยก save เนื้อหาออกจาก save reminder (ส่งเฉพาะฟิลด์ที่เปลี่ยน)

### H7. ปิด Reminder popup ด้วยปุ่ม X → note ติดสถานะ "alarm" ถาวร
- **ไฟล์:** `src/ui/unblockable_dialog.py` (ไม่มี `protocol("WM_DELETE_WINDOW", ...)`)
- **สาเหตุ:** dialog มี native titlebar ผู้ใช้กด X ได้ → ไม่เรียก dismiss/snooze → DB ค้าง `triggered=1` + `reminder_datetime` → กรอบแดง + SQL ดันขึ้นบนสุดตลอดไป แก้ได้ทางเดียวคือเปิด reminder dialog แล้วกด Clear
- **แนวทางแก้:** ผูก X = Dismiss

### H8. Alarm ที่เลยเวลาไปเกิน 1 ชั่วโมงถูกทิ้งเงียบ ๆ
- **ไฟล์:** `src/ui/board.py:1078-1095`, `src/ui/reminder_dialog.py:312-370`
- **สาเหตุ:** เครื่อง sleep / ปิดแอป / ผู้ใช้ตั้งเวลาย้อนหลัง → mark triggered ทันทีโดยไม่มีการแจ้งเตือนหรือสัญลักษณ์ "missed" และ ReminderDialog ก็ไม่ validate เวลาย้อนหลัง

### H9. Search ถูกล้างทุกครั้งที่ refresh + ลำดับเพี้ยนหลังค้นหา
- **ไฟล์:** `src/ui/board.py:425-427, 520-545`
- **สาเหตุ:** `_load_notes()` set `search_var=""` ทุกครั้ง (ถูกเรียกจาก alarm, debounce refresh ฯลฯ) → ข้อความค้นหาหายกลางคันโดยที่ผู้ใช้ไม่ได้ทำอะไร; การ์ดที่ถูก `pack_forget` ระหว่างค้นหาจะถูก pack ต่อท้ายเมื่อล้างคำค้น (ดู C5)

### H10. Google Tasks เป็น placeholder แต่ UI บอกว่า "Connected"
- **ไฟล์:** `src/services/auth_service.py:23-24, 86-112, 136`, `src/ui/settings_window.py:720-826`, `src/services/google_tasks.py:20-38`
- **ปัญหา:**
  - Client ID/Secret เป็นค่าปลอมที่ hard-code ไว้ใน source → Google จะตอบ `invalid_client`
  - เปิด browser 2 ครั้ง (`settings_window.py:740` + `auth_service.py:104`)
  - `authenticate()` คืน `True` เสมอโดยไม่มี callback server/token exchange → UI แสดง "Connected as unknown@gmail.com" ซึ่งทำให้ผู้ใช้เข้าใจผิด
  - Connect ตั้งค่า flag ใน `GoogleOAuthService` แต่ Sync/Disconnect ดู `GoogleTasksService` (คนละ object) → "Sync Now" บอกว่า "Not connected" ทั้งที่เพิ่งขึ้นว่า connected
  - `google_tasks.py` ถือว่า authenticated แค่เพราะมีไฟล์ cache อยู่
- **แนะนำ:** ซ่อนแท็บนี้ หรือทำ OAuth จริง (installed-app flow + loopback)

### H11. ลบโน้ตทันทีโดยไม่ยืนยัน และไม่มี undo
- **ไฟล์:** `src/ui/note_card.py:505-507`, `src/ui/board.py:640-647`
- **ปัญหา:** ปุ่ม 🗑 อยู่ติดกับ ✓ และ ⏰ ขนาดเท่ากัน → กดพลาดง่าย และเป็น hard delete

---

## 🟡 MEDIUM

| # | ไฟล์ | ปัญหา |
|---|---|---|
| M1 | `board.py:159-168, 445-458` | เปิดแอปตอนไม่มีโน้ตจะเห็นข้อความ "ยังไม่มีโน้ต" **2 อัน** (สร้างใน `__init__` แล้ว `_load_notes` สร้างซ้ำเพราะยังไม่มี flag `_empty_state_created`) |
| M2 | `board.py:640-647, 617-638` | ลบ/complete โน้ตสุดท้ายแล้วไม่แสดง empty state (ไม่ได้เรียก `_load_notes`) |
| M3 | `database.py:209-212` | `last_dismissed_at` ไม่เคยถูกล้าง → โน้ตที่เคย dismiss **ครั้งเดียว** จะอยู่เหนือโน้ตอื่นตลอดไป |
| M4 | `database.py:212` | `reminder_datetime ASC`: SQLite เรียง NULL ก่อน → โน้ตที่ไม่มี reminder ขึ้นก่อนโน้ตที่มี reminder ใกล้ถึง (กลับกับที่ตั้งใจ) |
| M5 | `database.py:254-259` | เปลี่ยนกลับเป็น active แล้วไม่ล้าง `completed_at` |
| M6 | `reminder_dialog.py:141-212` | แก้ reminder เดิมแล้ว dialog ไม่ prefill วัน/เวลาเดิม (ขึ้นพรุ่งนี้ 09:00 เสมอ) → เผลอเขียนทับ |
| M7 | `reminder_dialog.py:318-336, 368-370` | input ไม่ถูกต้องแล้ว dialog ปิดเงียบ ๆ ไม่บอกผู้ใช้ |
| M8 | `reminder_dialog.py:349-370` | ถ้า `update_note` โยน `sqlite3.Error` (ไม่อยู่ใน tuple ที่ catch) → dialog ค้าง และหน้าต่างหลักติด `-disabled` + grab → แอปดูเหมือนค้าง |
| M9 | `reminder_dialog.py:99-101, 358-363` | การ pause scheduler ตั้งค่าบน Tk root (ไม่ใช่ Board) จึงไม่มีผล; `self.parent` เป็น NoteCard ทำให้ `_load_notes`/`_check_reminders` เป็น no-op |
| M10 | `settings_window.py:180-191` | Spinbox snooze: `command` ยิงเฉพาะตอนกดลูกศร ถ้าพิมพ์ตัวเลขเองค่าจะไม่ถูกเก็บ; พิมพ์ตัวอักษร → `IntVar.get()` error |
| M11 | `settings_window.py:123, 462`, `board.py:1470` vs `settings.py:61`, `main.py:241` | ขั้นต่ำ alpha ไม่ตรงกัน: UI ให้ 20% แต่ตอนโหลด clamp เป็น 30% |
| M12 | `settings_window.py:712-716` | `_show_deduped_error` สร้าง `tk.Tk()` ตัวใหม่ (Tcl interpreter ที่ 2) ทุกครั้งและไม่ destroy → leak + พฤติกรรม Tk แปลก |
| M13 | `settings_window.py:566` | `self.root.unbind_all()` ไม่ส่ง argument → TypeError (ถูก catch ไว้) และถ้าแก้ให้ทำงานได้จะลบ binding ทั้งแอป (เช่น global MouseWheel ของ Board) |
| M14 | `tray_service.py` + `platform/tray.py` | มี **tray icon 2 อัน** (สี่เหลี่ยมฟ้า + เหลือง) อันฟ้ามีเมนู Show/Hide/Exit ที่ไม่ทำอะไร (Show เรียก callback ที่เป็น None, Exit ปิดแค่ icon ตัวเอง) |
| M15 | `platform/tray.py:39-44` | ไม่มี default menu item → คลิกซ้ายที่ tray icon ไม่คืนหน้าต่าง (ขัดกับ checklist) |
| M16 | `board.py:675-680` | ย่อ (−) = `withdraw()` ซึ่งหน้าต่าง overrideredirect ไม่มีปุ่มบน taskbar ถ้า tray เริ่มไม่สำเร็จจะไม่มีทางเรียกหน้าต่างกลับ (นอกจาก hotkey) |
| M17 | `board.py:720-746` vs `1487-1552`, `note_card.py:653-692` | theme refresh มี 2 เส้นทางที่ไม่สอดคล้องกัน: ไม่ recolor `search_frame`, `heartbeat_label`, `resize_corner`, ปุ่ม pin/action, header/footer ของการ์ด; `content_text` ใช้ `bg` แทน `note_bg`; fallback ตั้งการ์ดเป็น `bg` (ผิด) — Dark mode ใช้ไม่ได้อยู่แล้ว เพราะไม่มี toggle (v1.7.0) |
| M18 | `note_card.py:22` | `hash(note.id)` ของ str ถูก randomize ทุก process (PYTHONHASHSEED) → สีแถบการ์ดเปลี่ยนทุกครั้งที่เปิดแอป |
| M19 | `note_card.py:450-455` | ลบ title จนว่างแล้วไม่บันทึก แต่ช่องยังแสดงว่าง (UI ≠ DB) |
| M20 | `unblockable_dialog.py:192-199` | DPI scale = `fpixels('1i')/72` → ที่ 96 DPI ได้ 1.33 ไม่ใช่ 1.0 ตามที่ comment อ้าง; ใช้ `winfo_screenwidth` (จอหลักเท่านั้น) |
| M21 | `board.py:1159`, `notification.py:105-116` | `root._current_reminder_note_id` เป็นค่าเดียว ถ้ามี alarm หลายอันพร้อมกัน จะ highlight การ์ดผิดตัว; popup หลายอันซ้อนทับตำแหน่งเดียวกันเป๊ะ |
| M22 | `main.py:341-343` | toggle_show เช็ก `state()=="normal"` ถ้าหน้าต่างถูกบังอยู่ (normal แต่ไม่ได้อยู่หน้า) การกด Ctrl+Alt+S จะซ่อนแทนที่จะดึงขึ้นมา |

---

## ⚪ LOW / CODE HEALTH / DEAD CODE

- **L1. Latent bug — Open-from-notification ทำให้ alarm ดังซ้ำ:** `board.py:1277` ส่ง `reminder_datetime=None` (ซึ่ง `update_note` ข้ามค่า None) + `reminder_triggered=False` → reminder ที่เลยเวลาแล้วกลับเป็น `triggered=0` แล้วดังซ้ำ ตอนนี้ยังไม่เกิด เพราะ dialog ไม่มีปุ่ม Open แต่ถ้าเพิ่มกลับมาจะเกิดทันที
- **L2.** `notification_queue` ไม่มีใครเรียก enqueue → `_check_notification_queue` (poll ทุก 500ms), `CustomToastNotification`, `<<NewNotification>>` เป็น dead code
- **L3.** `notification.py:80-124`: `show_reminder_notification` คืน True เสมอเมื่อมี `parent_root` → fallback chain (Win32 MessageBox / tray / toast / shell) ไม่มีวันทำงาน; ถ้า dialog สร้างไม่สำเร็จจะไม่มี fallback
- **L4.** `notification.py:269-273`: `RegisterClass` ซ้ำทุกครั้ง + `lpfnWndProc={}` → shell balloon ใช้ได้แค่ครั้งแรก
- **L5.** `board.py:982-1010`: `pywinctl` ไม่อยู่ใน `requirements.txt` → ImportError ทุกครั้ง และ `getWindowsWithTitle("QuickNote")` อาจไปจับหน้าต่างอื่น (เช่น Explorer ที่เปิดโฟลเดอร์ชื่อ QuickNote) เพราะ root ไม่ได้ตั้ง title
- **L6.** `unblockable_dialog.py:293-372`: เมธอด `_mark_reminder_triggered`, `_snooze_reminder_5m`, `_commit_reminder_triggered_sync`, `_force_main_window_to_foreground_win32`, `_force_ui_rerender` ไม่ถูกเรียก; `board.py`: `_show_toast_banner`, `_hide_toast_banner`, `_dismiss_and_open_note`, `_play_notification_alert`, `_highlight_and_scroll_to_note`, `toast_frame` เป็น dead code
- **L7.** `settings.py:27, 38`: `DEFAULTS.copy()` เป็น shallow copy → dict `hotkeys` ใช้ร่วมกับ DEFAULTS; `save()` ไม่ atomic (เขียนทับตรง ๆ ไฟดับตอนเขียน = settings.json เสีย) ขัดกับ convention "Atomic write (tmp → fsync → replace)" ใน CLAUDE.md
- **L8.** `database.py:116-146`: `_migrate_db_schema` ไม่ปิด connection ใน try/finally เดียวกับ cursor creation; `sanitize_reminders` ไม่ใช้ `DB_WRITE_LOCK`; เปิด/ปิด connection ใหม่ทุก query (scheduler อ่านทั้งตารางทุก 5 วินาที)
- **L9.** `main.py:85-94`: `connect()` ไม่มี timeout; ถ้ามีโปรแกรมอื่นใช้ port 29837 อยู่ QuickNote จะออกเงียบ ๆ โดยไม่แจ้ง (exit 0)
- **L10.** `main.py:17-21`: logging ระดับ DEBUG ออก stdout ตลอด (ใน .exe แบบ `--noconsole` ไม่มีที่แสดง และไม่มี log file ทั้งที่ error dialog บอกว่า "ตรวจสอบ Log file")
- **L11.** `board.py:68-71`: เรียก `SetProcessDpiAwareness(1)` หลังสร้าง Tk แล้ว (ไม่มีผล/ขัดกับ v2 ที่ตั้งใน main)
- **L12.** `board.py:800-802`: bare `except:`; `notification.py:25` AUMID ยังเป็น `v2.9.4`
- **L13.** `src/platform/autostart.py`: ไม่ได้เชื่อมกับ UI เลย (ฟีเจอร์ที่อ้างว่ามีแต่เปิดใช้ไม่ได้)
- **L14.** Repo hygiene: มีไฟล์ซ้ำนอก `src/` (`board.py`, `database.py`, `hotkey.py` ที่ root), track ไฟล์ `.exe` installer / `build_output.log` / `test_results.log` ใน git

---

## ลำดับการแก้ที่แนะนำ

1. **C2** (scheduler ทวีคูณ) — แก้บรรทัดเดียว แต่กระทบความเสถียรมากที่สุด
2. **C1, C7, C8, H6** — ข้อมูลผู้ใช้หาย/ถูกเขียนทับ
3. **C3, C4** — persistence ของ settings/geometry (รวม flush ทุกการ์ดก่อน quit ไว้ในจุดเดียว)
4. **C6, H7, H8** — ความน่าเชื่อถือของ reminder (แกนหลักของแอป)
5. **C5, H4, H5, H9** — เขียน `_load_notes` ใหม่ให้ order/state มาจาก DB จริง (แก้บั๊ก positioning ที่วนมาหลายเวอร์ชันได้ที่ต้นเหตุ)
6. **C9, C10** — backup/restore/cleanup ด้วย SQLite backup API
7. **H1, H2, H3, H10, H11** และ Medium ที่เหลือ

## หมายเหตุสำหรับ AI ที่จะแก้

- CLAUDE.md อ้างว่า test 334 ตัวผ่านหมด (รอบนี้ไม่ได้รันซ้ำ) แต่ test เหล่านั้นไม่ครอบคลุมบั๊กข้างบน ควรเขียน regression test ให้แต่ละข้อ **ก่อน**แก้ (ข้อที่ **[ยืนยันแล้ว]** reproduce ได้ด้วย Tk จริงไม่กี่บรรทัด)
- หลายบั๊ก (C5, H2, H4) เป็นต้นเหตุของบั๊กเดิมที่ "แก้ไปแล้ว" หลายรอบใน changelog ควรแก้ที่ต้นเหตุ ไม่ควรแปะ workaround เพิ่ม

---

# ภาคผนวก: วิธีแก้ไขโดยละเอียด

> โค้ดด้านล่างเป็นแนวทางที่เขียนให้เข้ากับโครงสร้างโค้ดปัจจุบัน เลขบรรทัดอ้างอิงจาก v2.9.46 ก่อนแก้
> วิธีแก้ที่ทำเครื่องหมาย **[ทดสอบกลไกแล้ว]** ได้ทดสอบพฤติกรรม Tk ที่ใช้แก้ด้วยสคริปต์จริงแล้ว (ยังไม่ได้ทดสอบในแอปทั้งตัว)
> ข้อที่ต้องตัดสินใจเชิง product ทำเครื่องหมาย **⚖️ ต้องเลือก**

## แก้ C1 — บันทึก priority

`src/ui/board.py` `_on_note_update()` (ทำพร้อม H6 ด้านล่าง):

```python
def _on_note_update(self, note: Note):
    """บันทึกเฉพาะฟิลด์เนื้อหา — reminder/status มี path ของตัวเอง (ดู H6)"""
    update_note(note.id, title=note.title, content=note.content,
                collapsed=note.collapsed, priority=note.priority)
    self.canvas.configure(scrollregion=self.canvas.bbox("all"))
```

**ทดสอบ:** ตั้ง priority High → เรียก `_load_notes()` → `get_note(id)["priority"] == "high"`

## แก้ C2 — scheduler ให้มี chain เดียวเสมอ

`src/ui/board.py` `__init__` เพิ่ม `self._reminder_job = None` แล้วแก้ `_check_reminders()`:

```python
def _check_reminders(self):
    try:
        if not getattr(self, '_scheduler_enabled', True):
            return  # finally จะ reschedule ให้ — ห้าม after() ซ้ำตรงนี้
        if self._last_action_timestamp and time.time() - self._last_action_timestamp < 5.0:
            return  # เช่นกัน
        ...  # logic เดิม
    finally:
        # ยกเลิก job เก่าก่อนเสมอ กันกรณีมีคนเรียก _check_reminders() ตรง ๆ แล้วเกิด chain ที่ 2
        if self._reminder_job is not None:
            try:
                self.root.after_cancel(self._reminder_job)
            except tk.TclError:
                pass
        self._reminder_job = self.root.after(5000, self._check_reminders)
```

ใช้ pattern เดียวกันกับ `_process_command_queue` (100ms) และ `_reapply_topmost` (3s) ด้วย เพื่อกันปัญหาซ้ำในอนาคต

**ทดสอบ:** ใส่ counter ใน `_check_reminders` ตั้ง `_last_action_timestamp=time.time()` แล้วรัน mainloop 20 วินาที จำนวนครั้งที่เรียกต้องอยู่ราว 4 (ไม่โตแบบทวีคูณ) และ `len(root.tk.call('after','info'))` ต้องคงที่

## แก้ C3 — จุดปิดแอปจุดเดียว + บันทึก settings

**1) `main.py`** ทำให้ทุกทางออกไปผ่าน `on_closing()`:

```python
_closing = False
def on_closing():
    nonlocal _closing
    if _closing:
        return
    _closing = True
    try:
        board.flush_all_cards()                      # ดู C8
        settings.set("geometry", board.get_persistable_geometry())  # ดู C4
        settings.save()
    finally:
        board.root.quit()

board.root.protocol("WM_DELETE_WINDOW", on_closing)
board.titlebar.on_close = on_closing                  # ปุ่ม ✕ เดิมเรียก root.quit() ตรง ๆ
def on_tray_quit():
    board.root.after(0, on_closing)
```

`graceful_shutdown()` + `lock.release()` ให้อยู่ใน `finally` หลัง mainloop ที่เดียว (เอาออกจาก `on_closing` เพราะตอนนี้ถูกเรียกซ้ำ 2 รอบ)

**2) `src/ui/board.py` `_on_settings_saved()`** เพิ่มตอนท้าย:

```python
if hasattr(self.settings, "save"):
    self.settings.save()
```

**ทดสอบ:** ปรับ opacity → ปิดด้วย ✕ → อ่าน `~/.quicknote/settings.json` ต้องเห็นค่าใหม่

## แก้ C4 — คืนตำแหน่งหน้าต่าง

`src/ui/board.py`:

```python
# __init__ หลัง self._center_main_window()
if geometry:
    self.root.geometry(self._get_safe_geometry(geometry))

def get_persistable_geometry(self) -> str:
    """ตอน roll-up ให้บันทึกความสูงก่อนพับ ไม่ใช่ 42px"""
    self.root.update_idletasks()
    w, h = self.root.winfo_width(), self.root.winfo_height()
    if self._rolled_up:
        h = self._saved_height
    return f"{w}x{h}+{self.root.winfo_x()}+{self.root.winfo_y()}"
```

ใน `_get_safe_geometry()` ให้ clamp `w, h` ไม่ต่ำกว่า minsize ด้วย (`w = max(w, MIN_W)`)

## แก้ C5 — `_load_notes` ต้องเรียงตาม DB จริง **[ทดสอบกลไกแล้ว]**

ทดสอบแล้วว่า `pack_forget()` ทุกตัวแล้ว `pack()` ใหม่ตามลำดับได้ลำดับที่ถูกต้อง

```python
def _load_notes(self):
    notes_data = get_notes_by_status(self.current_filter)
    current_ids = [row['id'] for row in notes_data]
    self._card_order = current_ids                 # ใช้กับ search (H9)

    for nid in [n for n in self.note_cards if n not in set(current_ids)]:
        card = self.note_cards.pop(nid)
        card.flush_pending()                       # ดู C8 — กันข้อความหายก่อน destroy
        card.destroy()

    for card in self.note_cards.values():          # ← จุดสำคัญ: ถอดทั้งหมดก่อน
        card.pack_forget()

    self._update_empty_state(bool(notes_data))     # ดู M1/M2

    for row in notes_data:
        note = Note.from_dict(row)
        card = self.note_cards.get(note.id)
        if card is None:
            card = self._create_card(note)         # ย้ายโค้ดสร้าง + bind callbacks ออกมาเป็นเมธอด
            self.note_cards[note.id] = card
        else:
            card.refresh_from(note)                # ดู H5
        card.pack(fill="x", padx=4, pady=4)

    self._apply_search()                           # ดู H9 — ห้ามล้าง search_var
    self.root.after(100, lambda: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
```

**⚖️ ต้องเลือก: ลำดับการเรียง** ใน `database.py` `get_notes_by_status()` ตอนนี้โน้ตใหม่จะไม่ขึ้นบนสุดถ้ามีโน้ตที่เคย dismiss หรือมี priority อยู่แล้ว ข้อเสนอที่ตรงกับพฤติกรรมที่ผู้ใช้ขอมาตลอด:

```sql
ORDER BY is_pinned DESC,
         CASE WHEN reminder_triggered = 1 AND reminder_datetime IS NOT NULL THEN 0 ELSE 1 END,
         created_at DESC
```

ถ้าต้องการให้ priority มีผลกับการเรียงด้วย ให้ใส่ priority ก่อน `created_at` แต่โน้ตใหม่ (priority none) จะไม่อยู่บนสุดอีก ถ้าเลือกแบบนั้นต้องเก็บ `repack_card_to_top()` ไว้สำหรับโน้ตที่เพิ่งสร้างใน session นี้ เมื่อเรียงจาก DB ถูกแล้ว ให้ลบการเรียก `repack_card_to_top()` ใน `_on_pin_changed` และ `_trigger_reminder` ออก

## แก้ C6 — popup ต้องขึ้นแม้หน้าต่างหลักถูกซ่อน **[ทดสอบกลไกแล้ว]**

ทดสอบแล้วว่า Toplevel ที่ไม่ผูก transient แต่ตั้ง `-topmost` จะ map ได้ (`state=normal`) แม้ root ถูก withdraw

`src/ui/unblockable_dialog.py:68-72` ลบ `self.transient(parent)` ออก และเก็บ `self.attributes("-topmost", True)` ไว้

**⚖️ ต้องเลือก:** ถ้าอยากให้แจ้งเตือนดึงหน้าต่างหลักกลับมาด้วย (เพื่อให้เห็นการ์ดแดง) ให้เรียก `board.root.deiconify()` ใน `_trigger_reminder` ก่อนแสดง dialog แทน

**ทดสอบ:** `board.root.withdraw()` → trigger reminder → `dialog.winfo_ismapped() == 1`

## แก้ C7 + C8 — flush ข้อมูลก่อนซ่อน/ทำลาย/ปิด

`src/ui/note_card.py` เพิ่มเมธอดกลาง:

```python
def flush_pending(self) -> None:
    """ดึงค่าจาก widget ทั้งหมดที่ยังไม่ได้บันทึก — เรียกก่อน hide/destroy/quit"""
    self._cancel_timer("_content_save_timer")
    self._cancel_timer("_title_save_timer")
    changed = False
    try:
        if self.content_text is not None and self.content_text.winfo_exists():
            c = self.content_text.get("1.0", "end-1c")
            if c != self.note.content:
                self.note.content, changed = c, True
        t = self.title_var.get().strip()
        if t and t != self.note.title:
            self.note.title, changed = t, True
    except tk.TclError:
        return
    if changed:
        self.on_update(self.note)

def _cancel_timer(self, attr):
    job = getattr(self, attr, None)
    if job is not None:
        try:
            self.after_cancel(job)
        except tk.TclError:
            pass
        setattr(self, attr, None)
```

แก้จุดที่เกี่ยวข้อง:
- `_on_toggle_fold()`: ถ้ากำลังจะพับ ให้เรียก `self.flush_pending()` **ก่อน** `self._hide_content()`
- `_hide_content()`: เรียก `self._cancel_timer("_content_save_timer")`
- `save_content()` (closure ใน `_on_content_debounced`): guard เป็น `if self.content_text is not None and self.content_text.winfo_exists():` และ catch `(tk.TclError, AttributeError)`
- title: เพิ่ม `self._title_save_timer = None` ใน `__init__` แล้วผูก `self.title_entry.bind("<KeyRelease>", self._on_title_debounced)` (debounce 500ms รูปแบบเดียวกับ content)
- `src/ui/board.py` เพิ่ม:

```python
def flush_all_cards(self):
    for card in list(self.note_cards.values()):
        try:
            card.flush_pending()
        except Exception as e:
            log.warning(f"[Board] flush failed: {e}")
```

เรียก `flush_all_cards()` ใน `on_closing` (C3), ก่อน `_on_minimize` / hotkey hide, และใน `_on_filter_changed` ก่อน `_load_notes()`

**ทดสอบ:** พิมพ์ content → เรียก `_on_toggle_fold()` ทันที (ไม่รอ 500ms) → DB ต้องมีข้อความครบ และไม่มี exception

## แก้ C9 — Backup/Restore ด้วย SQLite backup API

`src/core/database.py`:

```python
def backup_database(target_path: str) -> bool:
    try:
        src = _get_db_connection()
        try:
            dst = sqlite3.connect(target_path)
            try:
                with DB_WRITE_LOCK:
                    src.backup(dst)          # รวมข้อมูลใน WAL ด้วย
            finally:
                dst.close()
        finally:
            src.close()
        return True
    except Exception as e:
        print(f"[Backup Error] {e}")
        return False


def restore_database(backup_path: str) -> bool:
    try:
        uri = Path(backup_path).resolve().as_uri() + "?mode=ro"
        src = sqlite3.connect(uri, uri=True)
        try:
            if src.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                return False
            cols = {r[1] for r in src.execute("PRAGMA table_info(notes)")}
            if not {"id", "title", "status"} <= cols:
                return False                 # ไม่ใช่ไฟล์ QuickNote
            # กันพลาด: เก็บสำเนาข้อมูลปัจจุบันไว้ก่อน
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_database(str(APP_DIR / f"notes_before_restore_{stamp}.db"))
            dst = _get_db_connection()
            try:
                with DB_WRITE_LOCK:
                    src.backup(dst)          # เขียนผ่าน SQLite → WAL/SHM สอดคล้องกันเอง
            finally:
                dst.close()
        finally:
            src.close()
        init_db()                            # migrate คอลัมน์ให้ไฟล์ backup เก่า
        return True
    except Exception as e:
        print(f"[Restore Error] {e}")
        return False
```

`src/ui/settings_window.py` `_on_restore()` หลัง restore สำเร็จ ให้ rebuild การ์ดทั้งหมด (ห้าม reuse การ์ดเก่า):

```python
board = getattr(self.main_root, "_board", None)
if board is not None:
    for card in list(board.note_cards.values()):
        card.destroy()                       # ไม่ flush — ข้อมูลเก่าต้องทิ้ง
    board.note_cards.clear()
    board._load_notes()
```

## แก้ C10 — เลิกลบ WAL/SHM

`main.py:186-197` ลบ block ที่ 2 (WAL/SHM sidecars) ทิ้งทั้งหมด เพราะ SQLite จัดการไฟล์เหล่านี้เอง ส่วน block ที่ 1 (`qn_test_*`) ควรย้ายไปไว้ใน `tearDown`/`tearDownClass` ของ test แทนการให้แอป production ไปลบ temp

## แก้ H1 — Tray Settings ใช้ singleton เดียว

`main.py` ลบ `open_settings_window()` และตัวแปร `settings_window` ทิ้ง:

```python
def on_tray_settings():
    board.root.after(0, lambda: (board.root.deiconify(), board.root.lift()))
    board.root.after(200, board._open_settings)

board.on_open_settings = lambda: board.root.after(0, board._open_settings)
```

## แก้ H2 — เคารพสถานะ pin

**⚖️ ต้องเลือก:** ค่าเริ่มต้นตอนเปิดแอปเป็น pin หรือไม่ ให้ใช้ `settings["always_on_top"]` (มีอยู่ใน DEFAULTS แล้วแต่ไม่ได้ใช้) และบันทึกเมื่อ toggle

`src/ui/board.py`:

```python
def _reapply_topmost(self):
    try:
        if self.titlebar.is_topmost and not self._has_open_dialog():
            self.root.attributes("-topmost", True)
    except tk.TclError:
        pass
    self._topmost_job = self.root.after(3000, self._reapply_topmost)

def _has_open_dialog(self) -> bool:
    """อย่าดัน main ขึ้นทับ Settings / Reminder / alarm popup"""
    return any(isinstance(w, tk.Toplevel) and w.winfo_viewable()
               for w in self.root.winfo_children())
```

- ใน `__init__` ลบ `attributes("-topmost", True)` บรรทัด 238 และ 248 แล้วตั้งค่าจาก settings ครั้งเดียว ให้ตรงกับไอคอน
- `_force_main_window_foreground` (บรรทัด 1440) และ `main._bring_to_front` (บรรทัด 363): หลังหน่วงเวลาให้คืนค่าเป็น `self.titlebar.is_topmost` แทน `False`
- `_on_toggle_topmost`: บันทึก `self.settings.set("always_on_top", is_topmost)`
- **⚖️** ตอนนี้ pin = ล็อกไม่ให้ลากด้วย (`titlebar.py:191`) ผู้ใช้ส่วนใหญ่คาดว่า pin = always-on-top อย่างเดียว ควรพิจารณาแยกสองอย่างนี้

## แก้ H3 — Roll-up **[ทดสอบกลไกแล้ว]**

ทดสอบแล้วว่า `minsize(1,1)` แล้ว `geometry("500x42")` ได้ความสูง 42 จริง

```python
MIN_W, MIN_H = 500, 400   # ใช้ค่าเดียวกันทั้ง minsize และ _on_resize

def _on_roll_up(self):
    x, y, w = self.root.winfo_x(), self.root.winfo_y(), self.root.winfo_width()
    if self._rolled_up:
        self.root.minsize(MIN_W, MIN_H)
        for f in (self.search_frame, self.body_frame):   # pack กลับตามลำดับเดิม
            f.pack(side="top", fill="both" if f is self.body_frame else "x",
                   expand=f is self.body_frame, after=self.titlebar)
        self.root.geometry(f"{w}x{self._saved_height}+{x}+{y}")
        self._rolled_up = False
    else:
        self._saved_height = self.root.winfo_height()
        self.search_frame.pack_forget()
        self.body_frame.pack_forget()
        self.root.minsize(1, 1)
        self.root.geometry(f"{w}x{self.titlebar.winfo_height()}+{x}+{y}")
        self._rolled_up = True
```

หมายเหตุ: การใช้ `pack(after=...)` ต้องเรียงให้ search อยู่ก่อน body (pack search หลัง titlebar แล้ว body หลัง search) ระวังลำดับ ส่วน `_on_resize` ให้ใช้ `max(MIN_W, ...)` / `max(MIN_H, ...)` แทน 260/180

## แก้ H4 — เก็บสถานะพับ/กาง

- `src/core/models.py:31-42`: `collapsed=bool(data.get("collapsed", True))` (ลบ logic ที่บังคับ True)
- `src/core/database.py` `create_note`: INSERT `collapsed=1` ถ้าต้องการให้โน้ตใหม่พับไว้ก่อน (ตามที่ตัดสินใจใน v2.8.2) **⚖️** หรือ `0` ถ้าอยากให้กางเพื่อพิมพ์ได้ทันที
- `src/ui/board.py:478, 489`: ลบ `note.collapsed = True` / `card.note.collapsed or True`
- การ์ดที่ reuse ให้ sync widget ผ่าน `refresh_from()` (H5)

## แก้ H5 — `NoteCard.refresh_from(note)`

```python
def refresh_from(self, note: Note) -> None:
    """sync widget ทุกตัวกับข้อมูลจาก DB (ไม่ทับช่องที่ผู้ใช้กำลังพิมพ์)"""
    self.note = note
    focus = self.focus_get()
    if focus is not self.title_entry and self.title_var.get() != note.title:
        self.title_var.set(note.title)
    # fold
    if note.collapsed and self.content_frame is not None:
        self.flush_pending(); self._hide_content()
    elif not note.collapsed and self.content_frame is None:
        self._show_content()
    elif self.content_text is not None and focus is not self.content_text:
        if self.content_text.get("1.0", "end-1c") != note.content:
            self.content_text.delete("1.0", "end"); self.content_text.insert("1.0", note.content)
    self.btn_fold.config(text="▸" if note.collapsed else "▾")
    # pin
    self.btn_pin.config(text="📌" if note.is_pinned else "📍",
                        fg="#FF6B6B" if note.is_pinned else self.theme.c("fg_muted"))
    # priority
    icon, color = self.priority_icon_map.get(note.priority, ("🚩", "#B0B0B0"))
    self.btn_priority.config(text=icon, fg=color, activeforeground=color)
    if note.priority != "none":
        self._create_priority_badge(self.status_badge.master, self.theme)
    elif self.priority_badge:
        self.priority_badge.destroy(); self.priority_badge = None
    # reminder icon + red border (ใช้นิยามเดียวกับ __init__)
    self.update_reminder_state(bool(note.reminder_datetime) and not note.reminder_triggered)
    self.set_alarm_highlight(bool(note.reminder_triggered and note.reminder_datetime))
    self._update_action_button()
    self._update_strikethrough()
```

จากนั้นเลิกเรียก `set_alarm_highlight` / `update_reminder_state` แยกใน `_process_command_queue` และ `notification.py:105-116` ปล่อยให้ refresh จาก DB เป็นแหล่งข้อมูลเดียว

## แก้ H6 — แยก save เนื้อหาออกจาก reminder/status

ใช้ `_on_note_update` แบบในหัวข้อ C1 (ไม่ส่ง `status`, `reminder_datetime`, `reminder_triggered`) ซึ่งปลอดภัย เพราะ:
- status มี `on_status_update` → `update_note_status_only` อยู่แล้ว
- ReminderDialog เขียน DB ตรงอยู่แล้ว (`reminder_dialog.py:349, 377`) ส่วน `on_save`/`on_clear` callback ให้เหลือแค่อัปเดตไอคอน ไม่ต้องเรียก `on_update`

## แก้ H7 — ปุ่ม X ของ popup = Dismiss

`src/ui/unblockable_dialog.py` ใน `__init__`:

```python
self.protocol("WM_DELETE_WINDOW", self._on_dismiss_click)
self.bind("<Escape>", lambda e: self._on_dismiss_click())
```

## แก้ H8 — ไม่ทิ้ง alarm ที่พลาด

`src/ui/board.py:1078-1095` แทนที่การ mark triggered เงียบ ๆ:

```python
missed = []   # เก็บไว้นอก loop
...
if time_diff > 3600:
    update_note(note_data["id"], reminder_triggered=True)   # กันดังซ้ำ
    missed.append(note_data)
    continue
...
# หลัง loop: แจ้งครั้งเดียว ไม่ว่าจะพลาดกี่อัน (กัน alarm storm)
if missed:
    titles = "\n".join(f"• {n['title']} ({n['reminder_datetime']})" for n in missed[:10])
    self.root.after(0, lambda: messagebox.showinfo(
        "QuickNote — การแจ้งเตือนที่พลาดไป", titles, parent=self.root))
```

`src/ui/reminder_dialog.py` `_save_reminder()` ก่อน `update_note`:

```python
if datetime.strptime(reminder_str, "%Y-%m-%d %H:%M") <= datetime.now():
    if not messagebox.askyesno("เวลาผ่านไปแล้ว",
                               "เวลานี้ผ่านไปแล้ว ต้องการแจ้งเตือนทันทีหรือไม่?",
                               parent=self.dialog):
        return   # ไม่ปิด dialog ให้ผู้ใช้แก้เวลา
```

## แก้ H9 — Search ไม่ถูกล้าง และไม่ทำลายลำดับ

```python
def _on_search(self, event=None):
    self._apply_search()

def _apply_search(self):
    kw = self.search_var.get().lower().strip()
    for card in self.note_cards.values():
        card.pack_forget()
    for nid in getattr(self, "_card_order", []):
        card = self.note_cards.get(nid)
        if card and (not kw or kw in card.note.title.lower() or kw in card.note.content.lower()):
            card.pack(fill="x", padx=4, pady=4)
    self.canvas.configure(scrollregion=self.canvas.bbox("all"))
```

- ลบ `self.search_var.set("")` ออกจาก `_load_notes()` ให้ไปล้างใน `_on_filter_changed()` แทน
- Escape binding (`board.py:129`) ให้เรียก `self._apply_search()`

## แก้ H10 — Google Tasks

**⚖️ ต้องเลือก:**
- **ทางเลือก A (แนะนำตอนนี้):** ซ่อนแท็บ Google Tasks (ไม่ `notebook.add`) และลบ `EMBEDDED_CLIENT_ID/SECRET` ปลอมออกจาก source จนกว่าจะทำจริง
- **ทางเลือก B (ทำจริง):** ใช้ `google-auth-oauthlib` แบบ `InstalledAppFlow.from_client_secrets_file(...).run_local_server(port=0)` ใน background thread แล้วส่งผลกลับผ่าน `root.after`, เก็บ token ที่ `~/.quicknote/token.json`, ดึง email จาก userinfo จริง, รวม `GoogleOAuthService` กับ `GoogleTasksService` เป็น object เดียว และให้ UI แสดง Connected **หลัง**ได้ token แล้วเท่านั้น

## แก้ H11 — ยืนยันก่อนลบ

`src/ui/note_card.py`:

```python
def _on_delete(self):
    from tkinter import messagebox
    title = self.note.title or "โน้ตนี้"
    if messagebox.askyesno("ลบโน้ต", f"ลบ \"{title[:40]}\" ถาวร?", parent=self.winfo_toplevel()):
        self.on_delete_note()
```

**⚖️ ทางเลือกที่ UX ดีกว่า:** soft delete (คอลัมน์ `deleted_at`) + แถบ "ลบแล้ว · Undo" 5 วินาที แล้วค่อย hard delete

---

## วิธีแก้ Medium

| # | วิธีแก้ |
|---|---|
| M1 | ใช้ `_update_empty_state(has_notes)` เมธอดเดียวที่สร้าง label ครั้งเดียวแล้ว `pack()` / `pack_forget()` (ไม่ destroy/สร้างใหม่) และตั้ง `self._empty_state_created = True` ใน `__init__` หลังสร้าง label |
| M2 | หลัง `_on_note_delete` / `_on_note_status_update` ที่เอาการ์ดออก ให้เรียก `self._update_empty_state(bool(self.note_cards))` |
| M3 | ถ้าใช้ ORDER BY ใหม่ใน C5 ปัญหานี้หายไปเอง ถ้าจะเก็บไว้ ให้กำหนดอายุ เช่น `CASE WHEN last_dismissed_at > ? THEN 0 ELSE 1 END` โดยส่งค่า `(datetime.now()-timedelta(hours=1)).isoformat()` จาก Python **ห้ามใช้ `datetime('now')`** เพราะเป็น UTC และรูปแบบไม่มี `T` จึงเทียบ string กับค่าที่เก็บด้วย `isoformat()` ไม่ได้ |
| M4 | `reminder_datetime IS NULL, reminder_datetime ASC` (เอา NULL ไปท้าย) |
| M5 | ใน `update_note` และ `update_note_status_only`: `elif status == "active": updates.append("completed_at = NULL")` |
| M6 | ใน `ReminderDialog.__init__`: ถ้า `note.reminder_datetime` มีค่า ให้ parse แล้ว `date_entry.set_date(dt.date())`, `hour_combo.set(f"{dt.hour:02d}")`, `minute_combo.set(f"{dt.minute:02d}")` |
| M7 | path ที่ input ผิด: `messagebox.showwarning(..., parent=self.dialog)` แล้ว `return` โดยไม่ปิด dialog |
| M8 | ห่อ `_save_reminder` / `_clear_reminder` ด้วย `try: ... except Exception as e: messagebox.showerror(...)` และเรียก `_close_dialog()` ใน `finally` (ยกเว้นกรณี validation ที่ตั้งใจให้ค้างไว้) เพื่อให้ `-disabled` ถูกปลดเสมอ |
| M9 | ลบ logic pause scheduler (`reminder_dialog.py:96-101, 287-292`) เพราะไม่มีผลอยู่แล้ว หา board ด้วย `board = getattr(self.parent_root, "_board", None)` แล้วเรียก `board._request_ui_refresh()` แทน `self.parent._load_notes()`; **ห้าม**เรียก `board._check_reminders()` ตรง ๆ ถ้ายังไม่ได้แก้ C2 |
| M10 | ใช้ `self.snooze_var.trace_add("write", lambda *a: self._on_snooze_change())` และใน `_on_snooze_change` ให้ catch `tk.TclError` (ช่องว่าง/ตัวอักษร) แล้วไม่บันทึก และ `<FocusOut>` ให้ clamp + set กลับ |
| M11 | เพิ่ม `MIN_ALPHA = 0.3` ใน `constants.py` ใช้ทั้ง `settings._coerce`, `main.py:241`, slider `from_=MIN_ALPHA`, `_on_alpha_change`, `board._on_settings_saved` |
| M12 | `_show_deduped_error`: ลบ `tk.Tk()` ใช้ `messagebox.showerror(title, message, parent=self.root)` ตรง ๆ และกันซ้ำด้วย flag `self._error_open` (messagebox เป็น modal จะ block อยู่แล้ว) |
| M13 | ลบ `self.root.unbind_all()` (`settings_window.py:566`) เพราะ `destroy()` ล้าง binding ของหน้าต่างเองอยู่แล้ว |
| M14 | ใช้ tray icon เดียว: ลบ `initialize_tray_service()` ใน `main.py:220-227` และการ stop ใน `graceful_shutdown` ถ้าต้องการ tray balloon ให้ใช้ `tray.icon.notify(msg, title)` จาก `platform/tray.py` แทน |
| M15 | `pystray.MenuItem("Show QuickNote", lambda: self.on_show(), default=True)` |
| M16 | ถ้า `tray.icon is None` (tray ไม่ทำงาน) ให้ปุ่ม − ทำ roll-up แทน `withdraw()` เพื่อไม่ให้หน้าต่างหายถาวร |
| M17 | รวม theme refresh เหลือทางเดียว (`_on_theme_changed`) ลบ `_refresh_ui_colors` และให้ `NoteCard.apply_theme` ครอบคลุม frame/ปุ่มทุกตัว (เก็บ ref `header`, `footer`, `left_frame`, `right_frame`, `spacer`, `btn_pin`, `btn_action`); `content_text` ใช้ `note_bg` **⚖️** หรือถ้าตัด dark mode ไปแล้ว (v1.7.0) ให้ลบโค้ด dark ทั้งชุดแทน |
| M18 | `self.color_idx = int(note.id[:8], 16) % len(color_list)` (id เป็น uuid hex) ถ้า parse ไม่ได้ให้ fallback เป็น `zlib.crc32(note.id.encode())` |
| M19 | `_on_title_change`: ถ้า `new_title` ว่าง ให้ `self.title_var.set(self.note.title)` คืนค่าเดิม |
| M20 | `scale = self.winfo_fpixels('1i') / 96.0` และคำนวณตำแหน่งจาก work area (`SystemParametersInfoW(SPI_GETWORKAREA=0x30, ...)`) แทน `screen_height - 160` |
| M21 | ส่ง `note_id` เข้า `UnblockableCustomDialog` โดยตรงแทน `root._current_reminder_note_id`, ให้ Board เก็บ `self._open_alarm_dialogs: dict[note_id, dialog]` เพื่อกันเปิดซ้ำสำหรับโน้ตเดียวกัน และเลื่อนตำแหน่งแต่ละอันขึ้น `index * (height + 10)` |
| M22 | toggle: `if board.root.state() == "normal" and board.root.focus_displayof() is not None: withdraw() else: show()` (ถ้าหน้าต่างเปิดอยู่แต่ไม่มี focus ให้ดึงขึ้นมาแทนการซ่อน) |

## วิธีแก้ Low / Code health

| # | วิธีแก้ |
|---|---|
| L1 | `_on_note_reminder_open`: ใช้ `update_note(note.id, clear_reminder=True)` แทนการส่ง `reminder_datetime=None` |
| L2 | ลบ `services/notification_queue.py`, `ui/custom_toast.py`, `_check_notification_queue`, `_on_new_notification_event`, binding `<<NewNotification>>` และ `active_toasts` |
| L3 | ใน `show_reminder_notification` เรียก `show_dialog_safely()` ตรง ๆ (ตอนนี้รันบน main thread อยู่แล้วผ่าน `root.after` ใน board) ใน `try` ถ้าสำเร็จคืน `True` ถ้า exception ให้ไหลต่อไป fallback จริง |
| L4 | ลบ `_show_shell_notification` (ใช้ `tray.icon.notify` แทนตาม M14) |
| L5 | ลบ `_force_window_to_foreground_v2916` (pywinctl) ให้ใช้ `deiconify` + `-topmost` ชั่วคราว + `lift` + `focus_force` และตั้ง `self.root.title("QuickNote")` |
| L6 | ลบเมธอด dead code ใน `unblockable_dialog.py:293-372` และ `board.py` (`_show_toast_banner`, `_hide_toast_banner`, `_dismiss_and_open_note`, `_play_notification_alert`, `_highlight_and_scroll_to_note`, `toast_frame`, `toast_content`) — ตรวจ test ที่อ้างถึงเมธอดเหล่านี้ด้วย `grep` ก่อนลบ |
| L7 | `self.data = copy.deepcopy(DEFAULTS)` (ทั้ง 2 จุด) และ atomic save: เขียน `settings.json.tmp` → `f.flush(); os.fsync(f.fileno())` → copy ไฟล์เดิมเป็น `.bak` → `os.replace(tmp, SETTINGS_FILE)`; ตอน `load()` ถ้า JSON พังให้ลองอ่าน `.bak` |
| L8 | `_migrate_db_schema`: ย้าย `conn.cursor()` เข้า `try`; `sanitize_reminders` ห่อ `with DB_WRITE_LOCK`; scheduler query เฉพาะที่ถึงเวลา: `SELECT * FROM notes WHERE reminder_datetime IS NOT NULL AND reminder_triggered = 0 AND reminder_datetime <= ?` แทน `get_all_notes()` |
| L9 | ใช้ Windows named mutex (`CreateMutexW(None, False, "Local\\QuickNote.SingleInstance")` + เช็ก `GetLastError() == 183`) เป็นตัวล็อก และใช้ socket เฉพาะส่งสัญญาณ; client ใส่ `sock.settimeout(1.0)`; ถ้าล็อกได้แต่ bind port ไม่ได้ ให้แสดงข้อความแทนการออกเงียบ |
| L10 | เพิ่ม `RotatingFileHandler(APP_DIR / "quicknote.log", maxBytes=1_000_000, backupCount=3)` ที่ระดับ INFO และใส่ stdout handler เฉพาะเมื่อ `sys.stdout` มีอยู่ (ใน `--noconsole` จะเป็น `None`) |
| L11 | ลบ `SetProcessDpiAwareness(1)` ใน `board.py:68-71` |
| L12 | `except queue.Empty:` แทน bare except; AUMID ใช้ค่าคงที่ที่ไม่มีเลขเวอร์ชัน เช่น `"PassagainP.QuickNote"` (ถ้าเปลี่ยน AUMID ทุกเวอร์ชัน การตั้งค่าแจ้งเตือนของ Windows จะรีเซ็ต) |
| L13 | เพิ่ม checkbox "Start with Windows" ใน Settings ที่เรียก `enable_autostart()`/`disable_autostart()` และแสดงสถานะจาก `is_autostart_enabled()` หรือลบ module ถ้าไม่ใช้ |
| L14 | ตรวจด้วย `grep` ก่อนว่าไม่มีอะไร import `board.py`/`database.py`/`hotkey.py` ที่ root แล้ว `git rm` ออก; `git rm --cached` ไฟล์ `installer_output/*.exe`, `*.log` และเพิ่มใน `.gitignore` |

---

## Regression tests ขั้นต่ำที่ควรเพิ่ม

ใช้ Tk จริง (`tk.Tk()` + `withdraw()`) และ DB ชั่วคราวผ่าน `os.environ["DB_PATH"]` ตามแบบ test เดิม

1. **C1:** `_set_priority("high")` → `get_note(id)["priority"] == "high"`
2. **C2:** หลังตั้ง debounce แล้ว `update()` วน 20 วินาที → จำนวน `after info` ที่ชี้ไป `_check_reminders` == 1
3. **C3:** เรียก `board.titlebar.on_close()` → ไฟล์ settings.json มีค่า alpha ใหม่
4. **C5:** สร้าง 3 โน้ต → pin โน้ตล่างสุด → `inner_frame.pack_slaves()[0]` เป็นการ์ดนั้น → unpin → กลับไปตำแหน่งตาม created_at
5. **C6:** `root.withdraw()` → สร้าง `UnblockableCustomDialog` → `winfo_ismapped() == 1`
6. **C7:** insert ข้อความใน `content_text` → `_on_toggle_fold()` ทันที → DB มีข้อความ, ไม่มี exception หลัง 600ms
7. **C9:** เขียนโน้ต (อยู่ใน WAL) → backup → เปิดไฟล์ backup ต้องเห็นโน้ตนั้น; restore ไฟล์ที่ไม่ใช่ SQLite → คืน `False` และ DB เดิมไม่เปลี่ยน
8. **H3:** `_on_roll_up()` → `winfo_height() == titlebar.winfo_height()` → `_on_roll_up()` → ความสูงเดิม
9. **H7:** เรียก protocol `WM_DELETE_WINDOW` ของ dialog → `on_dismiss` ถูกเรียก 1 ครั้ง

---

# ภาคผนวก: มุมมองจากผู้ใช้งานจริง

## คำตอบสั้น ๆ: ดีหรือยัง?

**ยังไม่พร้อมให้ใช้เป็นที่เก็บโน้ตประจำวัน** ถึงแนวคิดจะดีและหน้าตาสวยแล้วก็ตาม

ถ้าผมเป็นผู้ใช้ ภายในสัปดาห์แรกน่าจะเจอเรื่องเหล่านี้แล้วเลิกใช้:
- ตั้ง priority ไว้ เปิดแอปวันรุ่งขึ้นหายหมด (C1)
- ปรับความโปร่งใสและย้ายหน้าต่างไว้มุมจอ เปิดใหม่กลับมากลางจอทึบเหมือนเดิมทุกครั้ง (C3, C4)
- ตั้งเตือนประชุมแล้วซ่อนแอปไว้ ได้ยินแค่เสียง "ติ๊ง" ไม่เห็นว่าเตือนเรื่องอะไร (C6) ส่วนถ้าเครื่อง sleep ก็ไม่เตือนเลย (H8)
- ใช้ไปครึ่งวันแอปเริ่มหน่วงโดยไม่รู้สาเหตุ (C2)
- กดถังขยะพลาดเพราะอยู่ติดปุ่ม ✓ โน้ตหายถาวร (H11)
- การ์ดสลับตำแหน่ง/พับเองทุกครั้งที่มีการแจ้งเตือน (C5, H4)

แอปโน้ตมีสัญญาข้อเดียวที่ห้ามผิด คือ **"สิ่งที่ฉันเขียนและตั้งค่าไว้จะยังอยู่"** และแอปเตือนความจำก็มีสัญญาข้อเดียวเหมือนกัน คือ **"ถึงเวลาแล้วฉันจะเห็นแน่นอน"** ตอนนี้ทั้งสองข้อยังทำได้ไม่ครบ

## สิ่งที่ทำได้ดีแล้ว (ควรเก็บไว้)

- **แนวคิดชัด:** sticky note ลอยบนจอ + checklist งาน + เตือนความจำในตัวเดียว เบา ไม่ต้องใช้ cloud
- **หน้าตา:** โทนพาสเทล การ์ดสะอาด ปุ่มน้อย ดูเป็นมิตร
- **Hotkey** `Ctrl+Alt+N` จดโน้ตได้ทันทีจากแอปไหนก็ได้ ถือเป็นฟีเจอร์ที่คุ้มที่สุดของแอป
- **ข้อมูลอยู่ในเครื่อง** (SQLite) เป็นส่วนตัว ทำงานได้แบบ offline
- **แยก Active / Completed** และค้นหาแบบ real-time ซึ่งตรงกับวิธีใช้งานจริง

## สิ่งที่ต้องปรับปรุง (เรียงตามความสำคัญในมุมผู้ใช้)

### 1. ต้องเชื่อถือได้ก่อน — แก้บั๊ก C/H ให้หมด
ก่อนจะเพิ่มฟีเจอร์ใหม่ใด ๆ ทุกการเปลี่ยนแปลงต้องถูกบันทึก ทุกการเตือนต้องเห็น ทุกการตั้งค่าต้องจำได้ แค่นี้ก็ทำให้แอปดีขึ้นกว่าการเพิ่มฟีเจอร์ 10 อย่าง

### 2. ความรู้สึก "ปลอดภัย" กับข้อมูล
- **Undo / ถังขยะ:** ลบแล้วกู้คืนได้ภายในระยะเวลาหนึ่ง (เช่น แท็บ "Trash" 30 วัน)
- **Auto-backup** รายวันเก็บไว้ 7 ชุดใน `~/.quicknote/backups/` อัตโนมัติ ไม่ต้องรอให้ผู้ใช้กดเอง
- **สัญญาณ "บันทึกแล้ว"** เล็ก ๆ (เช่น ✓ จาง ๆ ที่มุมการ์ด) เพื่อให้มั่นใจว่าพิมพ์แล้วไม่หาย

### 3. การเตือนความจำที่ใช้ได้จริง
- เตือนแม้แอปถูกซ่อน/อยู่ใน tray และแสดงรายการ "เตือนที่พลาดไป" หลังเครื่องตื่น
- **Reminder ซ้ำ:** ทุกวัน / ทุกวันทำงาน / ทุกสัปดาห์ (งานประจำเป็นเหตุผลหลักที่คนตั้งเตือน)
- **ตั้งเวลาเร็ว:** ปุ่ม "+15 นาที", "+1 ชม.", "พรุ่งนี้เช้า 9:00", "เย็นนี้ 17:00" แทนการเลือกวัน/ชั่วโมง/นาทีทีละช่อง
- Snooze เลือกได้ตอนเตือน (5 / 15 / 60 นาที) ไม่ต้องเข้า Settings
- แสดงเวลาที่ตั้งไว้บนการ์ด (เช่น "⏰ วันนี้ 14:30") ตอนนี้ต้องเปิด dialog ถึงจะรู้
- เมื่อแก้ reminder ให้ dialog แสดงค่าเดิม (M6)

### 4. ลดความสับสนใน UI
- **ปุ่มเยอะเกินไปบนการ์ดเล็ก ๆ:** ▸ 🚩 📍 ✓ ⏰ 🗑 + badge Active + badge priority = ไอคอน 6–8 ตัวต่อการ์ด แนะนำให้เหลือ ✓ กับ ⏰ ที่เห็นตลอด ส่วนที่เหลือย้ายไปเมนู "⋯" หรือคลิกขวา
- **ไอคอน pin ซ้ำความหมาย:** 📌/📍 ใช้ทั้งปักหมุดโน้ตและปักหมุดหน้าต่าง ควรใช้ไอคอนต่างกัน
- **badge "Active" บนทุกการ์ดในแท็บ Active** ซ้ำซ้อน ไม่ให้ข้อมูลเพิ่ม ควรแสดงเฉพาะในแท็บ Completed หรือไม่แสดงเลย
- **ปุ่มสามสี (✕ − +) ดูเหมือน macOS แต่ความหมายไม่ตรง:** สีเขียวของ macOS คือขยายหน้าต่าง แต่ที่นี่คือสร้างโน้ต ผู้ใช้ Windows จะไม่คุ้น ควรแยกปุ่ม "+ โน้ตใหม่" ออกมาให้ชัด และตัดสินใจว่า ✕ = ซ่อนลง tray หรือ ออกจากแอป (ส่วนใหญ่ app แบบนี้ ✕ = ซ่อน แล้ว Exit อยู่ใน tray)
- **โน้ตใหม่ชื่อ "New Note"** ให้เป็นช่องว่างพร้อม placeholder "พิมพ์หัวข้อ..." แทน จะได้ไม่ต้องลบก่อนพิมพ์
- **Footer "● Scheduler: 14:32:05 | Next: 15:00"** เป็นข้อมูล debug ผู้ใช้ไม่ต้องรู้ว่ามี scheduler ให้เปลี่ยนเป็น "การเตือนถัดไป 15:00 · ประชุมทีม" หรือซ่อนไป
- **Empty state** ใช้ข้อความไทย แต่ปุ่ม/เมนูทั้งหมดเป็นอังกฤษ ควรเลือกภาษาเดียว หรือทำ i18n

### 5. Checklist ในโน้ต (ตามที่ README อ้าง)
README บอกว่ามี "checklist inside each note" แต่ในโค้ดเป็น Text ธรรมดา แนะนำให้รองรับ `- [ ]` / `- [x]` ที่คลิกติ๊กได้ จะเหมาะกับการใช้เป็น to-do มาก

### 6. การใช้คีย์บอร์ด
- `Ctrl+F` โฟกัสช่องค้นหา, `Ctrl+N` โน้ตใหม่ (เมื่อแอป active), `Ctrl+Enter` mark done, `Delete` ลบ (พร้อมยืนยัน), `Esc` ซ่อนหน้าต่าง
- เปลี่ยน hotkey ได้ใน Settings (`Ctrl+Alt+N` ชนกับแอปอื่นบ่อย และบนคีย์บอร์ดบางแบบคือ AltGr)

### 7. Settings ที่ผู้ใช้คาดว่าจะมี
- **Start with Windows** (โค้ดมีอยู่แล้วใน `autostart.py` แต่ไม่มีปุ่ม)
- **Dark mode** (โค้ดยังอยู่ แต่ถูกเอา toggle ออกไป) ควรมี หรือให้ตาม Windows theme อัตโนมัติ
- **ขนาดตัวอักษร** (ตอนนี้ 9pt ค่อนข้างเล็กบนจอ 4K / สำหรับผู้สูงอายุ)
- **ซ่อนแท็บ Google Tasks** จนกว่าจะใช้ได้จริง (ตอนนี้ทำให้เข้าใจผิดว่า connect แล้ว)

### 8. Export / ย้ายเครื่อง
- Export เป็น Markdown / CSV (ข้อมูลไม่ควรถูกขังอยู่ในไฟล์ .db)
- Import จาก backup แบบ merge (ไม่ใช่เขียนทับทั้งหมดอย่างเดียว)

### 9. การติดตั้งและความน่าเชื่อถือของไฟล์ .exe
- ไฟล์ .exe ไม่ได้ sign → Windows SmartScreen จะเตือน "Unknown publisher" ซึ่งทำให้ผู้ใช้ทั่วไปกลัว ควรพิจารณา code signing หรืออย่างน้อยใส่คำอธิบายในหน้าดาวน์โหลด
- ไอคอนแอป/tray ควรเป็นไอคอนจริง (ตอนนี้เป็นสี่เหลี่ยมสีพื้น 2 อัน)
- เพิ่ม log file และเมนู "เปิดโฟลเดอร์ข้อมูล" ใน Settings เพื่อให้รายงานปัญหาได้ง่าย

### 10. สำหรับนักพัฒนา (กระทบผู้ใช้ทางอ้อม)
- โค้ดสะสม workaround และ dead code จากหลายเวอร์ชัน (เช่น การแจ้งเตือนมี 6 ช่องทาง แต่ใช้จริงช่องเดียว) ทำให้แก้จุดหนึ่งแล้วไปพังอีกจุด ควรเก็บกวาด (L2–L6) ก่อนเพิ่มฟีเจอร์
- ตัวเลขเวอร์ชันขึ้นเร็วมาก (v2.9.0 → v2.9.46) โดยบั๊กหลักยังวนกลับมา ควรมี test ที่จำลองการใช้งานจริง (เปิด → แก้ → ปิด → เปิดใหม่ → ตรวจว่าข้อมูลยังอยู่) เป็นด่านก่อน release

## สรุปแผนที่แนะนำ

| ระยะ | เป้าหมาย | งาน |
|---|---|---|
| **1. ทำให้ไว้ใจได้** | ข้อมูลไม่หาย, เตือนแน่นอน | บั๊ก C1–C10, H6–H8, H11 + auto-backup |
| **2. ทำให้ใช้ลื่น** | ไม่สับสน, ไม่ขัดใจ | C5/H4/H5/H9, H1–H3, ลดปุ่มบนการ์ด, quick-time reminder, แสดงเวลาบนการ์ด |
| **3. ทำให้น่าใช้ต่อ** | ฟีเจอร์ที่คนคาดหวัง | reminder ซ้ำ, checklist, Start with Windows, dark mode, export, shortcuts |
| **4. ค่อยทำทีหลัง** | ส่วนเสริม | Google Tasks ของจริง, sync |

---

# ภาคผนวก: รีวิวหน้าตา (UI/UX Visual Review)

> **อัปเดต — ตัดสินใจแล้ว:** เปลี่ยน UI เป็นสไตล์ **Windows 11** ดูแบบละเอียดใน [`DESIGN_SPEC_WIN11.md`](DESIGN_SPEC_WIN11.md)
> ถ้าข้อเสนอในภาคผนวกนี้ขัดกับ DESIGN_SPEC (เช่น ปุ่มสามสีแบบ macOS หรือ roll-up) **ให้ยึด DESIGN_SPEC**

> เปิดโปรแกรมจริงด้วยฐานข้อมูลชั่วคราว (ไม่แตะข้อมูลจริง) ใส่โน้ตตัวอย่าง 4 อัน แล้วถ่ายภาพหน้าจอไว้ในโฟลเดอร์ `ui_review/`
> - `ui_review/01_main_collapsed.png` — หน้าหลัก (การ์ดพับ)
> - `ui_review/02_main_expanded.png` — หน้าหลัก (กางการ์ดแรก)
> - `ui_review/03_settings.png` — หน้าต่าง Settings
> - `ui_review/05_alarm_popup.png` — popup แจ้งเตือน
>
> หน้าต่างตั้งเวลาเตือน (ReminderDialog) ถ่ายภาพอัตโนมัติไม่สำเร็จ ส่วนนั้นจึงประเมินจากโค้ด

## คำตอบสั้น ๆ: น่าใช้ไหม?

**ดูสะอาดและเป็นมิตร ได้ประมาณ 6/10** โทนสว่าง ตัวอักษรไทยคมชัด และ filter แบบ pill ด้านบนดูดี แต่ยังมีปัญหาที่ทำให้ไม่รู้สึกว่าเป็นแอปที่ขัดเกลามาแล้ว:

1. **ไม่เหมือน sticky note:** ชื่อบอกว่า "macOS Pastel" แต่การ์ดเป็นสีขาวกรอบเทาทั้งหมด สีพาสเทลเหลือแค่เส้นบาง 4px ทางซ้ายที่แทบมองไม่เห็น
2. **ใช้พื้นที่เปลือง:** หน้าต่าง 500x600 เห็นโน้ตแค่ 3.5 ใบ เพราะการ์ดแต่ละใบสูง ~125px ทั้งที่มีแค่หัวข้อบรรทัดเดียว (padding ซ้อน 3 ชั้น + แถวไอคอนแยกอีกแถว) แอปที่ "ลอยบนจอตลอด" ควรเล็กและแน่น
3. **ไอคอนปนกันหลายสไตล์:** ธงอีโมจิสี, หมุดอีโมจิ, ✓ ตัวอักษร, ⏱ เส้นบาง, 🗑 ที่ render เป็นถังขยะหยัก ๆ, ✕ − + ตัวหนาสีสด และ ⌕ ที่เล็กจนแทบไม่เห็น ทั้งหมดมีน้ำหนักและขนาดไม่เท่ากัน
4. **ส่วนประกอบของ Windows รุ่นเก่า:** scrollbar สีเทาหนา, slider `tk.Scale` ที่มีตัวเลข "1.00" ซ้อนกับ "100%", แท็บ `ttk.Notebook` แบบ Windows classic และ Spinbox แบบเก่า ตัดกับส่วนอื่นที่พยายามดูโมเดิร์น

## ปัญหาที่เห็นจากภาพหน้าจอ

### หน้าหลัก (`01`, `02`)

| # | ปัญหา | ผลต่อผู้ใช้ |
|---|---|---|
| V1 | **ลำดับการ์ดผิดให้เห็นจริง:** "ซื้อของเข้าบ้าน" (priority Medium + มีเตือนในอีก 2 ชม.) ไปอยู่ล่างสุด ต่ำกว่าโน้ตที่ไม่มีอะไรเลย (สาเหตุคือ M4: NULL ขึ้นก่อน) | งานที่ใกล้ถึงเวลาจมอยู่ล่างสุด |
| V2 | badge **"Active"** บนทุกการ์ดในแท็บ Active | รก, ไม่ให้ข้อมูลเพิ่ม |
| V3 | การ์ดมี 2 แถวเสมอ: แถวหัวข้อ + แถวไอคอน (✓ ⏱ 🗑 + badge) ทั้งที่ไอคอนเหล่านี้ไม่จำเป็นต้องเห็นตลอด | ความสูงการ์ดเพิ่มเกือบเท่าตัว |
| V4 | **เนื้อหาที่กางออกอยู่ใต้แถวปุ่ม** (ภาพ `02`) ลำดับที่อ่านเลยเป็น หัวข้อ → ปุ่ม → เนื้อหา ซึ่งผิดธรรมชาติ และถ้าการ์ดถูกสร้างตอนกางอยู่ เนื้อหาจะไปอยู่ระหว่างหัวข้อกับปุ่ม **ตำแหน่งเปลี่ยนไปตามวิธีที่กาง** (บั๊ก layout: `_show_content()` pack ต่อท้าย `main_frame` หลัง footer) | สับสน |
| V5 | ช่องเนื้อหาไม่มีขอบหรือพื้นหลังต่างจากการ์ด | ไม่รู้ว่าคลิกแล้วพิมพ์ได้ |
| V6 | ปุ่มพับ ▸ เล็กมาก (~8px) อยู่ชิดขอบ | กดยาก |
| V7 | การ์ดที่มี reminder ไม่บอกเวลาบนการ์ด (มีแค่ไอคอนนาฬิกา) | ต้องเปิด dialog ถึงจะรู้ |
| V8 | 📍 (ไม่ปักหมุด) ดูเหมือน "หมุดแผนที่/ตำแหน่ง" สีเทาอยู่ทุกการ์ด และ 📍 ตัวดำที่มุมขวาบน (ปักหมุดหน้าต่าง) ใช้ไอคอนเดียวกัน | ไม่รู้ว่าอันไหนทำอะไร |
| V9 | ช่องค้นหาไม่มี placeholder ไอคอน ⌕ เล็กและจางมาก กรอบช่องเป็นสี่เหลี่ยมเหลี่ยมคม | ไม่รู้ว่าเป็นช่องค้นหา |
| V10 | Footer: ข้อความสีเขียว "● Scheduler: 23:32:00 \| Next: 01:31" ดูเหมือน log ส่วนปุ่ม ⚙ ลอยอยู่กลาง ๆ ระหว่างชื่อแอปกับข้อความนั้น | ดูไม่เสร็จ, หา Settings ยาก |
| V11 | มุม resize ◢ เป็นสามเหลี่ยมดำทึบ | ดูหนัก/ไม่เข้าธีม |
| V12 | Titlebar: ✕ − + เป็นตัวอักษรสีสด ไม่ใช่วงกลม traffic light, ปุ่ม "+" (สร้างโน้ต ซึ่งเป็น action หลักของแอป) ดูเหมือนปุ่มควบคุมหน้าต่าง | action หลักถูกซ่อน |
| V13 | ขอบการ์ด 2px สีเทา + เงาไม่มี + ช่องว่างระหว่างการ์ด 8px | ดูเป็นกล่องแข็ง ๆ เรียงกัน |

### Settings (`03`)

| # | ปัญหา |
|---|---|
| V14 | แท็บ `ttk.Notebook` สไตล์ Windows classic ชิดขอบซ้ายบน ไม่มี padding |
| V15 | Slider แสดงค่าซ้ำ 2 ที่ ("1.00" บน slider + "100%" ด้านข้าง) และ track สีเทาเข้ม |
| V16 | ปุ่ม "Close" สีฟ้าเหลี่ยม ลอยขวา ใต้นั้นเป็นพื้นที่ว่างเกือบ 1/3 ของหน้าต่าง; ผู้ใช้ไม่แน่ใจว่าต้องกด Save ไหม (จริง ๆ แล้วเปลี่ยนทันที แต่ไม่บันทึกลงดิสก์ — ดู C3) |
| V17 | หน้าต่าง Settings ไม่มีส่วนตั้งค่าที่ผู้ใช้หา: hotkey, เปิดพร้อม Windows, ธีม, ขนาดตัวอักษร |
| V18 | ป้ายภาษาอังกฤษล้วน ขณะที่หน้าหลักมีข้อความไทย |

### Popup แจ้งเตือน (`05`)

| # | ปัญหา |
|---|---|
| V19 | ไม่บอกว่าเป็นการแจ้งเตือนจาก QuickNote และไม่บอกเวลาที่ตั้งไว้ ไม่มีไอคอน ⏰ |
| V20 | ปุ่มแค่ Dismiss / Snooze 5m ไม่มี "เปิดโน้ต" หรือ "เสร็จแล้ว ✓" ซึ่งเป็น action ที่ใช้บ่อยที่สุดหลังถูกเตือน |
| V21 | ปุ่ม Dismiss สีแดงอ่อนดูเหมือนปุ่มอันตราย (ลบ) ทั้งที่แค่ปิดการเตือน |
| V22 | มี native titlebar (ซึ่งมีปุ่ม X ที่ทำให้เกิดบั๊ก H7) ทำให้ไม่ดูเป็น toast |

### หน้าต่างตั้งเวลาเตือน (ประเมินจากโค้ด `reminder_dialog.py`)

| # | ปัญหา |
|---|---|
| V23 | สีแบบ hard-code (`#F5F5F7`, ปฏิทิน `darkblue`) ไม่ใช้ theme และหัวปฏิทินสีน้ำเงินเข้มตัดกับแอปที่เป็นพาสเทล |
| V24 | ต้องเลือก 3 ช่อง (วัน + ชั่วโมง dropdown 24 ค่า + นาที dropdown 60 ค่า) สำหรับงานที่ส่วนใหญ่คือ "อีก 1 ชม." หรือ "พรุ่งนี้เช้า" |
| V25 | ปุ่ม Set / Clear / Cancel ขนาดใกล้เคียงกัน โดย Clear (ลบการเตือน) อยู่ติด Set |

## ข้อเสนอการปรับหน้าตา

### 1. ทำให้เป็น "sticky note" จริง — ให้สีเป็นตัวการ์ด

```
ปัจจุบัน                                   ข้อเสนอ
┌──────────────────────────────┐          ╭──────────────────────────────╮
│▌ ▸ 🚩 📌 ประชุมทีม Marketing  │          │ ○ ประชุมทีม Marketing     📌 │  ← พื้นการ์ดเป็นสีพาสเทล
│▌                             │          │   ⏰ วันนี้ 14:30 · High     │  ← บรรทัด meta (มีเมื่อมีข้อมูล)
│▌ ✓  ⏱  🗑        Active High │          ╰──────────────────────────────╯
└──────────────────────────────┘           (hover → ⏰ ⋯ ปรากฏด้านขวา)
   ~125px                                     ~56px
```

- **พื้นการ์ด = สีพาสเทล** (`PASTEL_PALETTE` ที่มีอยู่แล้ว) ตัดขอบเทาทิ้ง ใช้มุมโค้งด้วย Canvas หรือ `ttk` style หรือแค่ขอบ 1px สีเข้มกว่าพื้น 8%
- **ให้ผู้ใช้เลือกสีการ์ดได้** (คลิกขวา → สี) แทนการสุ่มด้วย hash ซึ่งตอนนี้เปลี่ยนทุกครั้งที่เปิดแอป (M18)
- **วงกลม ○ ด้านหน้า = ปุ่ม Complete** (รูปแบบเดียวกับ Microsoft To Do / Apple Reminders) ผู้ใช้เข้าใจทันที
- **Priority แสดงเป็นแถบสี/จุดสี** หรือคำใน meta line แทนธง + badge ซ้ำกัน 2 ที่
- **ซ่อน ⏰ 🗑 ⋯ จนกว่าจะ hover** (`<Enter>`/`<Leave>` บนการ์ด) และย้ายลบ, สี, priority ไปไว้ในเมนู ⋯ / คลิกขวา
- **ตัด badge "Active"** ทิ้ง แสดงสถานะเฉพาะในแท็บ Completed (ขีดฆ่า/จางลง)
- **ความสูงการ์ดพับ ~56px** → หน้าต่างเดิมเห็นโน้ตได้ ~8 ใบแทน 3.5 ใบ

### 2. ลำดับภายในการ์ดเมื่อกาง

`หัวข้อ → เนื้อหา → (meta/ปุ่ม)` เสมอ ใช้ `content_frame.pack(after=header)` หรือ `before=footer` ให้ตำแหน่งไม่ขึ้นกับวิธีกาง (แก้ V4) และให้ช่องเนื้อหามีพื้นหลังต่างเล็กน้อย (เช่น สีพาสเทลที่สว่างกว่า 4%) พร้อม placeholder "เพิ่มรายละเอียด..."

### 3. Titlebar และปุ่มหลัก

- **ตัดสินใจเลือกทางเดียว:** ถ้าจะคงสไตล์ macOS ให้ใช้วงกลม 12px จริง (วาดด้วย Canvas) และแสดงสัญลักษณ์เฉพาะตอน hover แต่แอปนี้ทำมาสำหรับ Windows จึงแนะนำ **ปุ่มสไตล์ Windows 11 ด้านขวา** (− □ ✕ แบบเส้นบาง สีเทา, ✕ เป็นแดงตอน hover)
- **ปุ่ม "+ โน้ตใหม่"** แยกออกมาให้ชัด เช่น ปุ่มเต็มความกว้างใต้ช่องค้นหา หรือช่อง "พิมพ์โน้ตใหม่แล้วกด Enter" ด้านบนรายการ (quick-add แบบ To Do) ซึ่งเร็วกว่าการกด + แล้วลบคำว่า "New Note"
- ไอคอนปักหมุดหน้าต่างใช้ 📌 ↔ outline หรือคำ "On top" แบบ toggle ไม่ใช้ไอคอนเดียวกับปักหมุดโน้ต

### 4. ช่องค้นหา

ใส่ placeholder "ค้นหาโน้ต... (Ctrl+F)", ไอคอนแว่นขยายขนาดอ่านได้ (12–14px), ปุ่ม ✕ ล้างคำค้นเมื่อมีข้อความ, และพื้นช่องสีเดียวกับพื้นหลัง + ขอบมน **⚖️** หรือซ่อนช่องค้นหาไว้หลังไอคอน 🔍 ใน titlebar เพื่อประหยัดความสูง

### 5. Footer

- ตัด "Scheduler: HH:MM:SS" ทิ้ง เปลี่ยนเป็น "⏰ ถัดไป 14:30 · ประชุมทีม" (คลิกแล้วเลื่อนไปการ์ดนั้น) หรือไม่แสดงอะไรเลยเมื่อไม่มีการเตือน
- ย้าย ⚙ ไปไว้ใน titlebar ข้างปุ่ม pin, เอา "By Passagain P." ไปไว้ในหน้า About อย่างเดียว
- มุม resize ใช้จุด ⋰ สีเทาอ่อน หรือให้ resize ได้จากขอบทั้ง 4 ด้าน

### 6. Scrollbar

ใช้ `ttk.Scrollbar` พร้อม style แบบบาง (6–8px) สีกลืนพื้นหลัง และซ่อนเมื่อโน้ตไม่ล้นหน้าต่าง

### 7. Settings

- จัดเป็นรายการแถวละ 1 ตัวเลือก: ชื่อทางซ้าย, control ทางขวา (แบบ Windows 11 Settings) แบ่งกลุ่ม "ทั่วไป / การแจ้งเตือน / ข้อมูล / เกี่ยวกับ"
- Opacity ใช้ `ttk.Scale` + ป้าย % เดียว (`showvalue=0` ถ้าใช้ `tk.Scale`)
- ตัดปุ่ม Close (มี X ของหน้าต่างแล้ว) และแสดงข้อความ "บันทึกอัตโนมัติ" เล็ก ๆ หรือถ้าจะเก็บปุ่ม ให้มีปุ่มเดียวว่า "เสร็จ"
- เพิ่ม: ธีม (สว่าง/มืด/ตามระบบ), ขนาดตัวอักษร, hotkey, เปิดพร้อม Windows, เปิดโฟลเดอร์ข้อมูล
- ซ่อนแท็บ Google Tasks (H10)

### 8. Popup แจ้งเตือน

```
╭───────────────────────────────────────╮
│ ⏰ QuickNote · 14:30                 ✕ │
│ ประชุมทีม Marketing                    │
│ เตรียมสไลด์ยอดขาย Q3                   │
│                                       │
│ [ ✓ เสร็จแล้ว ] [ เลื่อน ▾ ] [ เปิด ]  │
╰───────────────────────────────────────╯
```

- frameless (`overrideredirect`) + ขอบมน + เงา ให้เหมือน toast ของ Windows 11 และให้ ✕ = Dismiss (H7)
- ปุ่มหลัก "เสร็จแล้ว" (mark complete + dismiss), "เลื่อน ▾" มีตัวเลือก 5 / 15 / 60 นาที / พรุ่งนี้, "เปิด" (deiconify + เลื่อนไปที่การ์ด)
- สีปุ่มเป็นกลาง (เทา/ฟ้า) ไม่ใช้แดงกับปุ่มที่ไม่อันตราย

### 9. หน้าต่างตั้งเวลาเตือน

```
ตั้งเวลาเตือน
[ +15 นาที ] [ +1 ชม. ] [ เย็นนี้ 17:00 ] [ พรุ่งนี้ 09:00 ]
── หรือกำหนดเอง ──
วันที่ [ 26-10-2026 📅 ]   เวลา [ 14 ]:[ 30 ]
ทำซ้ำ  [ ไม่ทำซ้ำ ▾ ]
                         [ ลบการเตือน ]      [ ยกเลิก ] [ ตั้งเวลา ]
```

- ใช้สีจาก theme และตั้ง `DateEntry(background=accent, ...)` ให้เข้าชุด
- ช่องนาทีเป็น Spinbox step 5 หรือพิมพ์ได้ แทน dropdown 60 รายการ
- แยก "ลบการเตือน" ไปไว้ซ้ายสุดเป็นปุ่มข้อความ (link style) ให้ห่างจากปุ่มหลัก

### 10. Design tokens ที่แนะนำ (รวมไว้ใน `theme.py`)

| Token | ค่า | ใช้กับ |
|---|---|---|
| ขนาดตัวอักษร | หัวข้อ 10pt semibold, เนื้อหา 10pt, meta 8.5pt | ตอนนี้ 9pt bold ทั้งหมด เล็กไปบนจอ high-DPI |
| ระยะห่าง | 4 / 8 / 12 / 16 px เท่านั้น | ตอนนี้ปน 2, 3, 4, 6, 8, 10, 12, 16 |
| ขนาดปุ่มไอคอน | 24x24 px, ไอคอน 14px | ทุกปุ่มบนการ์ด/titlebar ให้เท่ากัน |
| ชุดไอคอน | เลือกชุดเดียว: Segoe Fluent Icons (`"Segoe Fluent Icons"`/`"Segoe MDL2 Assets"` มีใน Windows 10/11) | แทนอีโมจิที่ render ไม่เท่ากัน |
| สีเน้น | ฟ้า `#007AFF` สำหรับ action หลักเท่านั้น, แดงเฉพาะ alarm/ลบ | ตอนนี้มีแดง 3 เฉด (`#FF3B30`, `#FF605C`, `#EF4444`, `#C62828`) |
| Contrast | ข้อความรองอย่างน้อย `#6B6B6B` บนพื้นขาว (WCAG AA 4.5:1) | `fg_muted #999999` บนขาวได้แค่ ~2.8:1 อ่านยาก |

### 11. Accessibility

- ทุกปุ่มที่เป็นไอคอนต้องมี tooltip (ตอนนี้ไม่มีเลย ผู้ใช้ใหม่ต้องเดาว่า ⏱ 🚩 📍 คืออะไร)
- ใช้คีย์บอร์ดได้: Tab ไล่ระหว่างการ์ด, Space = complete, Enter = แก้ไข
- รองรับ Windows High Contrast / ธีมมืดตามระบบ

## ลำดับการปรับหน้าตาที่แนะนำ

1. **เร็วและเห็นผลทันที (ครึ่งวัน):** ตัด badge Active, ใส่ tooltip, placeholder ช่องค้นหา, ล้าง footer, ตั้ง `fg_muted` ให้เข้มขึ้น, ใช้ ttk.Scrollbar แบบบาง, แก้ลำดับเนื้อหาในการ์ด (V4)
2. **เปลี่ยนหน้าการ์ด (1–2 วัน):** การ์ดสีพาสเทล 1 แถว + meta line + ปุ่มตอน hover + วงกลม complete + แสดงเวลาเตือนบนการ์ด
3. **หน้าต่างรอง (1 วัน):** popup แจ้งเตือนแบบ toast + quick-time reminder dialog + Settings แบบแถวรายการ
4. **ภาพรวม:** ชุดไอคอนเดียว, design tokens, dark mode ตามระบบ
