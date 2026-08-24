# QuickNote Installer Builder Guide

สำหรับสร้าง Windows Installer ของ QuickNote v2.9.41

---

## 📋 ข้อกำหนด

- **Inno Setup 6.0 or later** — Download from [jrsoftware.org](https://jrsoftware.org/isdl.php)
- **Windows 7+**
- **QuickNote_v2.9.41.exe** — ต้องอยู่ใน `dist/` folder (มีอยู่แล้ว ✓)

---

## 🚀 วิธีสร้าง Installer

### Step 1: ติดตั้ง Inno Setup
1. ไปที่ https://jrsoftware.org/isdl.php
2. ดาวน์โหลด **Inno Setup 6.3.0** (หรือเวอร์ชันล่าสุด)
3. รัน Installer และทำตามขั้นตอน
4. ติดตั้งลงใน `C:\Program Files (x86)\Inno Setup 6` (ค่าเริ่มต้น)

### Step 2: สร้าง Installer
**วิธีที่ 1: ใช้ Batch Script (ง่ายที่สุด)**
```batch
build_installer.bat
```
- Script จะตรวจสอบว่า Inno Setup ติดตั้งถูกต้อง
- สร้าง Installer โดยอัตโนมัติ
- Output: `installer_output\QuickNote_v2.9.41_Setup.exe`

**วิธีที่ 2: ใช้ Inno Setup GUI (Manual)**
1. เปิด **Inno Setup Compiler**
2. File → Open `installer.iss`
3. Build → Compile
4. Output จะออกมาใน `installer_output\`

**วิธีที่ 3: Command Line**
```cmd
iscc.exe installer.iss
```

---

## 📦 ไฟล์ Installer

- **Filename:** `QuickNote_v2.9.41_Setup.exe`
- **Size:** ~15-20 MB (compressed with LZMA)
- **Location:** `installer_output/`

---

## ✨ Installer Features

✅ One-click Installation
✅ Desktop Icon Option
✅ Start Menu Shortcuts
✅ Auto-launch on Startup Option (opt-in)
✅ Uninstall Support
✅ Include README & Documentation

---

## 🧪 ทดสอบ Installer

1. เปิด `installer_output\QuickNote_v2.9.41_Setup.exe`
2. เลือกตัวเลือก:
   - ✓ Desktop icon (optional)
   - ✓ Startup folder (optional)
3. คลิก "Install"
4. เลือก "Launch QuickNote" (optional)
5. ตรวจสอบ:
   - ✓ Start Menu มี QuickNote
   - ✓ Desktop มี shortcut (ถ้าเลือก)
   - ✓ โปรแกรมรันได้
   - ✓ Data ถูกเก็บใน `~/.quicknote/`

---

## 🧹 Cleanup

```bash
# ลบไฟล์ temp ของ Inno Setup (ถ้ามี)
rm -rf "Output"
```

---

## 📝 Installer Configuration

ตั้งค่า Installer ใน `installer.iss`:

| Setting | ค่าปัจจุบัน | คำอธิบาย |
|---------|------------|--------|
| AppVersion | 2.9.41 | เวอร์ชั่น |
| DefaultDirName | {autopf}\QuickNote | ตำแหน่งติดตั้ง (Program Files) |
| OutputDir | installer_output | Output folder |
| Compression | lzma | เอาบีบอัดให้เล็ก |

---

## 🐛 Troubleshooting

**Error: "iscc.exe not found"**
- ✓ ติดตั้ง Inno Setup ใหม่
- ✓ ตรวจสอบ PATH: `where iscc.exe`
- ✓ Try: `C:\Program Files (x86)\Inno Setup 6\iscc.exe` (full path)

**Error: "dist\QuickNote_v2.9.41.exe not found"**
- ✓ Rebuild .exe: `python build_windows.py`
- ✓ Check: `ls dist/QuickNote_v2.9.41.exe`

**Installer too large?**
- ✓ LZMA compression active (normal: 15-20 MB)
- ✓ Can reduce by excluding docs: edit `installer.iss`

---

## 📧 Next Steps

หลังจากสร้าง Installer แล้ว:

1. **Share with Users:**
   - Upload `QuickNote_v2.9.41_Setup.exe` ให้ผู้ใช้
   - Users double-click เพื่อ install

2. **Distribution:**
   - GitHub Releases
   - Google Drive
   - DropBox
   - Personal Website

3. **Auto-Update (Future):**
   - Inno Setup รองรับ auto-update via Sparkle
   - Plan for v2.9.42+

---

**Version:** QuickNote v2.9.41
**Updated:** 2026-08-24
**Maintainer:** Passagain P.
