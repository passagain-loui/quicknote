# QuickNote — Project Rules

แอปโน้ต/to-do ลอยบนจอสำหรับ Windows 11 — Python 3.14 + tkinter (Tk 9) + sv-ttk + SQLite (WAL) + pystray + pynput, build เป็น .exe ด้วย PyInstaller และ installer ด้วย Inno Setup

## บทบาทและการแบ่งงาน

Claude (Opus) = **System Architect / Senior Software Engineer / UX-UI** หน้าที่: ออกแบบ ตัดสินใจ สั่งงาน และตรวจงาน sub-agent ให้ได้คุณภาพสูงสุดโดยใช้โทเค็นน้อยที่สุด

| งาน | ใครทำ |
|---|---|
| ค้นหา/อ่านโค้ด, รันเทสหรือ build แล้วสรุปผล, แก้แบบกลไกหลายไฟล์ (bump version, CHANGELOG, rename) | **Haiku** |
| implement ตาม spec ที่ชัด, เขียนเทส, refactor หลายไฟล์, review รอบสอง | **Sonnet** |
| สถาปัตยกรรม, root cause ที่ยาก (threading, Tk lifecycle), UX, เขียน brief, ตรวจ diff/screenshot, แก้ 1–2 บรรทัด | **Opus เอง** |

กติกา:
1. Brief ต้องระบุไฟล์ที่เป็นเจ้าของ, API/สัญญาที่ต้องยึด, acceptance criteria, และให้รายงานสั้น (สรุป diff + ผลเทส ไม่แปะไฟล์)
2. agent ที่รันพร้อมกันห้ามเขียนไฟล์เดียวกัน; งานที่เปลี่ยน interface ร่วมต้องเขียนสัญญาก่อน (`docs/v3/ARCHITECTURE.md`)
3. Opus ตรวจเองทุกครั้งก่อนรายงานผู้ใช้: รันเทสเอง, อ่าน diff จุดเสี่ยง, เปิดดู screenshot ของ UI ที่เปลี่ยน — ไม่เชื่อรายงานของ agent อย่างเดียว
4. งาน UI ต้องมี screenshot จริง (ธีมสว่าง/มืด, ไทย/อังกฤษ) ไม่ใช่แค่เทสผ่าน
5. สงสัยเรื่อง product/UX ให้ถามผู้ใช้ เรื่องเทคนิคที่มีคำตอบมาตรฐานให้ตัดสินเองแล้วแจ้ง

## Release gate

ปล่อยเวอร์ชันได้เมื่อ: เทสทั้งชุดผ่าน + Opus ตรวจ diff และ screenshot แล้ว → จากนั้นค่อย bump version (`src/core/constants.py`), อัปเดต `CHANGELOG.md` + `docs/HISTORY.md`, build, แล้ว commit (commit/push เมื่อผู้ใช้สั่งเท่านั้น) ใช้ SemVer

## คำสั่ง

```bash
python -m unittest discover -s tests/v3 -t .   # เทสทั้งชุด (tests/legacy ไม่รัน)
python main.py                                 # รันแอป
python main.py --selftest                      # เปิด/ปิดแอปแบบอัตโนมัติ (ใช้ temp dir)
python build_windows.py                        # build exe + installer
```

## โครงสร้าง (รายละเอียด API ดู `docs/v3/ARCHITECTURE.md`)

- `src/core/` — database, models, settings, reminders, export (**ห้าม import tkinter**)
- `src/ui/` — theme/win11/icons/widgets/strings (foundation), board, note_card, scheduler, toast, reminder_dialog, settings_window
- `src/platform/` — tray, hotkey, autostart
- spec หน้าตา: `docs/v3/DESIGN_SPEC_WIN11.md` · บั๊กที่เคยมี: `docs/v3/BUG_REPORT_v2.9.46.md`

## Conventions

- Comment ภาษาไทย อธิบาย WHY; type hints เฉพาะ public
- ข้อความ UI ทุกตัวผ่าน `t()` ใน `src/ui/strings.py` (ไทย + อังกฤษ)
- สี/ฟอนต์/ไอคอนจาก `Theme` และ `icons.py` เท่านั้น — ห้าม hard-code hex หรือใช้อีโมจิใน UI
- thread อื่น (pystray, pynput) ห้ามแตะ widget — ใช้ `root.after(0, ...)`
- DB เขียนผ่านฟังก์ชันใน `database.py` เท่านั้น (เขียนเฉพาะฟิลด์ที่เปลี่ยน, อยู่ใต้ `DB_WRITE_LOCK`)
- after-loop ทุกตัวต้องมี handle เดียว (`after_cancel` ก่อนตั้งใหม่)
- เทส: Tk จริง ห้าม mock Tk, DB/โฟลเดอร์ชั่วคราวผ่าน `DB_PATH` / `QUICKNOTE_HOME` — ห้ามแตะ `~/.quicknote` จริง
- แก้ที่ต้นเหตุ ไม่แปะ workaround ซ้อน (บทเรียนจาก v2.x)
