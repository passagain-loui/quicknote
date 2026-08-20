# QuickNote v2.2.3 — Notes Always on Top + Calendar Reminders + Desktop Notifications

โปรแกรมจดโน้ตเบา ๆ ที่ค้างอยู่บนหน้าจอตลอดเวลา — สไตล์ macOS Pastel สำหรับ Windows

**Status:** ✅ v2.2.3 RELEASED — SQLite Commits Fixed + Next Reminder Visual Debug

![QuickNote Screenshot](docs/screenshot.png)

---

## ✨ ฟีเจอร์ (v1.3.0)

- **ค้างบนหน้าจอ (Always-on-Top)** — เห็นโน้ตตลอดเวลาโดยไม่ต้องสลับหน้าต่าง
- **Reminder Alerts** — ตั้งเวลาแจ้งเตือนสำหรับแต่ละโน้ต (แบบ non-blocking, ไม่ติดขัด UI)
- **Priority Flags** — ทำเครื่องหมายเร่งด่วน (🚩 High / 🚩 Medium / 🚩 Low / 🏳 None) ด้วยสีเด่นชัด (v1.3.4)
- **Quick Filter Toggle** — สลับ Active/Completed notes โดยตรงจาก titlebar
- **Status Badge** — Done (สีเขียว) / Active (สีฟ้า) ดูสวยเรียบร้อย
- **Modern UI** — macOS Pastel Design System แถบหัวลากได้ ปุ่มควบคุมชัดเจน
- **System Tray** — ซ่อนลง tray แล้วเรียกกลับได้ง่าย ๆ
- **Global Hotkey** — `Ctrl+Alt+N` สร้างโน้ตใหม่ / `Ctrl+Alt+S` toggle show/hide
- **Dark Mode** — ธีมสีเข้ม ปรับได้แบบ Real-time
- **Version & Credit** — Footer แสดง v1.3.0 + Developer (About tab)
- **Local Database** — เก็บข้อมูลใน `~/.quicknote/` เท่านั้น ไม่มี cloud sync

---

## 📥 ติดตั้ง & รัน

### ✅ ตัวเลือก 1: Windows Installer (แนะนำ)

1. ดาวน์โหลด `QuickNote-Setup-v1.0.2.exe` จากโฟลเดอร์ `installer_output/`
2. ดับเบิลคลิกแล้วทำตามขั้นตอน
3. เลือกตัวเลือก (Desktop Icon / Auto-launch on Startup)
4. คลิก "Install"
5. เปิด QuickNote จาก Start Menu หรือ Desktop

**Uninstall:** Control Panel → Programs → Uninstall a Program → QuickNote → Remove

### ตัวเลือก 2: Portable .exe (ไม่ต้องติดตั้ง)

1. ดาวน์โหลด `QuickNote_v1.3.8.exe` จากโฟลเดอร์ `dist/`
2. ดับเบิลคลิก (ไม่ต้องติดตั้ง)
3. ข้อมูลเก็บไว้ที่ `~/.quicknote/` (หาย เมื่อลบ .exe)

### ตัวเลือก 3: รัน Python โดยตรง (สำหรับ Dev)

```bash
# ติดตั้ง dependency
pip install -r requirements.txt

# รัน
python main.py
```

---

## ⌨️ Keyboard Shortcuts

### Global Hotkeys (ทำงานจากแอปอื่น)

| ลัด | การกระทำ |
|-----|---------|
| `Ctrl+Alt+N` | สร้างโน้ตใหม่ + เด้งหน้าต่างขึ้นมา |
| `Ctrl+Alt+S` | Toggle show/hide หน้าต่าง |

### Titlebar Buttons

| ปุ่ม | ชื่อ | การกระทำ |
|-----|-----|---------|
| 🔴 | Close | ปิดโปรแกรม |
| 🟡 | Minimize | ซ่อนลง tray (หรือ restore ถ้า roll-up) |
| 🟢 | New Note | สร้างโน้ตใหม่ |

### Double-Click Titlebar

- **Double-click** ชื่อหรือแถบหัว → Roll-up (พับเหลือแถบหัวเดียว)
- Double-click อีกครั้ง → Restore (กางออก)

---

## 🎨 Appearance

### Theme

- **Light Mode** — พื้นขาว ข้อความดำ (เริ่มต้น)
- **Dark Mode** — พื้นดำ ข้อความขาว

ปรับ: (ยังไม่เสร็จในตัวโปรแกรม — แก้ใน settings.json ได้)

### Opacity (Transparency)

ปรับความโปร่งใส: `~/.quicknote/settings.json` → `"alpha": 0.3–1.0`

---

## 💾 ที่เก็บข้อมูล

```
~/.quicknote/
├── notes.db         # ฐานข้อมูล SQLite3 (โน้ตทั้งหมด)
└── settings.json    # ค่าตั้ง (geometry, theme, alpha, hotkeys)
```

**ปลอดภัย:** ข้อมูลเก็บในคอมพิวเตอร์ของคุณเท่านั้น ไม่ sync ไปที่ cloud

---

## 🛠️ Build .exe (PyInstaller)

```bash
# Build
python build_windows.py

# Build (พร้อม debug console — ดู error)
python build_windows.py --debug

# ผลลัพธ์: dist/QuickNote.exe
```

---

## 📝 ตัวอย่างการใช้งาน

1. **เปิดโปรแกรม** → หน้าต่างค้างมุมจอ
2. **กด Ctrl+Alt+N** จากแอปอื่น → QuickNote ขึ้นมา + ช่องโน้ตใหม่พร้อม
3. **พิมพ์เรื่อง** → แสดงอยู่ทันที
4. **กดปุ่ม ✓** → โน้ตเสร็จแล้ว (ขีดฆ่า)
5. **ปุ่ม ▸** → พับโน้ต (ซ่อนรายละเอียด)
6. **ปุ่ม 🟡** → ซ่อนลง tray (ยังทำงานในด้านหลัง)

---

## 🐛 Troubleshooting

**หน้าต่างไม่ขึ้นมา**
→ ตรวจ `settings.json` ว่า geometry ถูกต้อง หรือลบไฟล์นั้นให้ reset

**Hotkey ไม่ทำงาน**
→ อาจชนกับแอปอื่น ลองเปลี่ยน key combo ใน `settings.json`

**โน้ตหายไป**
→ ตรวจ `~/.quicknote/notes.db` ยังมีไหม (ไม่มี = ลบโดยไม่ตั้งใจ)

---

## 📚 Development

### โครงสร้างโปรเจกต์

```
src/
├── core/          # ตรรกะล้วน (database, models, settings)
├── ui/            # tkinter UI (board, note_card, theme, etc.)
└── platform/      # Windows-specific (tray, hotkey, autostart)
```

### Python Version

- **Python 3.14.7** (ตรวจสอบแล้ว)
- **Tk 9.0**

### Dependencies

- `pystray` — System tray icon
- `pynput` — Global hotkey listener
- `Pillow` — Image generation
- `pywin32` — Windows API
- `PyInstaller` — Build .exe

---

## 📄 License

Personal Project (ไม่ได้เขียนให้สาธารณะ)

---

## ✍️ Authors

Developed by QuickNote Team — 2026

---

**Enjoy your notes! 📝**
