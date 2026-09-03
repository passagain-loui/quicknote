# QuickNote — GitHub + CI/CD Workflow Summary

ขั้นตอนการทำงาน Git → GitHub → GitHub Actions CI

---

## 📋 ขั้นตอนทั้งหมด

### 1️⃣ Commit การเปลี่ยนแปลง (บนเครื่อง)

```bash
# ระบุไฟล์ที่แก้
git add src/ui/board.py tests/test_e2e_v2943.py

# Commit พร้อมข้อความอธิบาย
git commit -m "feat: Add content persistence with KeyRelease debounce

- Implement 500ms debounce on KeyRelease event
- Maintain immediate FocusOut save (no delay)
- Prevent DB thrashing during rapid typing
- Update version to 2.9.43"
```

---

### 2️⃣ Push ขึ้น GitHub

```bash
git push origin main
```

**Repository:** `https://github.com/Passagain-P/QuickNote`  
**Branch:** `main` (หรือ PR branch สำหรับ feature)

พอ push เสร็จ → GitHub Actions ทริกเกอร์อัตโนมัติในทันที ไม่ต้องสั่งอะไรเพิ่ม

---

### 3️⃣ GitHub Actions CI รันอัตโนมัติ

**Workflow file:** `.github/workflows/ci-verify-build.yml`

GitHub เปิดเครื่องเสมือน (Windows VM) ใหม่ แล้วรันตามลำดับ:

#### Stage 1: Test & Verify
1. ✅ Checkout โค้ด (clone repo สดๆ)
2. ✅ ติดตั้ง Python 3.11
3. ✅ ติดตั้ง dependencies จาก `requirements.txt`
4. ✅ รัน `pytest tests/` (full test suite)
5. ✅ สร้าง `test_results.log`
6. ✅ Upload artifact (ถ้า test fail)

#### Stage 2: Build Executable
1. ✅ ติดตั้ง PyInstaller
2. ✅ ดึง version จาก `src/core/constants.py`
3. ✅ รัน `python build_windows.py` → สร้าง `dist/QuickNote_v*.exe`
4. ✅ ตรวจสอบไฟล์ .exe มีอยู่จริง
5. ✅ Upload executable ไป GitHub Artifacts (retention 30 days)
6. ✅ **ถ้า push to main:** Build สำเร็จ
7. ✅ **ถ้า tag version (git tag v2.9.47):** สร้าง GitHub Release พร้อม .exe

---

### 4️⃣ เช็คผลลัพธ์

#### ทดสอบแบบ interactive (ต้องติดตั้ง GitHub CLI)

```bash
# ดูรายการ run ล่าสุด
gh run list --limit 5

# ดูรายละเอียด/สถานะแต่ละ step
gh run view <run-id>

# ดูตัวอักษร log ทั้งหมด
gh run view <run-id> --log
```

#### ตรวจสอบใน GitHub Web
1. ไปที่ repository
2. **Actions** tab
3. คลิก workflow ล่าสุด
4. ดูแต่ละ step (ขยายได้)

---

## 📊 ผลลัพธ์ CI

| ผลลัพธ์ | หมายความ | ต้องแก้ไข? |
|---|---|---|
| ✅ **Success (สีเขียว)** | Tests pass + Build success | ไม่ต้อง |
| ❌ **Failure (สีแดง)** | Test fail หรือ Build fail | ✅ ต้องแก้ก่อน push ซ้ำ |
| ⏸️ **In Progress** | CI ยังกำลังรันอยู่ | รอก่อน |

---

## ⏱️ ระยะเวลา

- **Test stage:** ~2-3 นาที
- **Build stage:** ~5-7 นาที
- **รวมทั้งหมด:** ~10 นาที

---

## 🚀 สร้าง Release (สำหรับ Deploy)

```bash
# สร้าง version tag
git tag -a v2.9.47 -m "Release v2.9.47: Content Persistence Fix"

# Push tag ขึ้น GitHub
git push origin v2.9.47
```

**ผลลัพธ์:**
1. GitHub Actions ทำงาน (build .exe)
2. สร้าง GitHub Release โดยอัตโนมัติ
3. .exe แนบใน Release → ผู้อื่นสามารถ download ได้เลย

ตรวจสอบ: **Repository** → **Releases** tab

---

## 📝 หมายเหตุสำคัญ

| สถานการณ์ | CI ทำอะไร |
|---|---|
| Push to `main` | ✅ Run tests + Build .exe (สะสม artifact) |
| Create Pull Request | ✅ Run tests (build optional) |
| Tag version (`v*.*.* `) | ✅ Run tests + Build + Create Release |
| Push to other branch | ✅ Run tests (if configured) |

---

## 🔧 ไฟล์ที่สำคัญ

| ไฟล์ | ความหมาย |
|---|---|
| `.github/workflows/ci-verify-build.yml` | Workflow definition (รับคำสั่ง CI) |
| `requirements.txt` | Python dependencies |
| `build_windows.py` | PyInstaller config → สร้าง .exe |
| `src/core/constants.py` | APP_VERSION (CI อ่านค่านี้) |
| `tests/` | Test suite (CI รัน pytest) |

---

## ❓ Troubleshooting

### ❌ Tests fail
```bash
# ทดสอบในเครื่องก่อน
python -m pytest tests/ -v

# แก้ issue แล้ว commit ใหม่
```

### ❌ Build fail
```bash
# ทดสอบ build ในเครื่อง
python build_windows.py

# ตรวจสอบ dist/QuickNote_*.exe มีอยู่
```

### ❌ Artifact ไม่พบ
- Artifact อยู่ 30 วัน แล้วลบเอง
- ดาวน์โหลดจาก GitHub Releases ถ้าอยากเก็บถาวร

---

## 📌 สรุป Workflow

```
Code Change (เครื่อง)
    ↓
git add + git commit
    ↓
git push origin main
    ↓
GitHub Actions Triggered (อัตโนมัติ)
    ↓
[Stage 1] Run pytest
    ↓
[Stage 2] Build .exe
    ↓
Result: ✅ Success หรือ ❌ Failure
    ↓
(ถ้า tag version) → สร้าง Release + upload .exe
```

---

**สำหรับ AI ตัวอื่นที่ต้องทำงานในโปรเจกต์นี้:**
- 🔍 ตรวจสอบ Actions tab หลังทุก push
- 📋 อ่าน test results จาก artifacts
- 🔧 ใช้ commit message ที่บอกรายละเอียด (สำหรับ CHANGELOG)
- 🎯 ไม่ต้อง manual trigger CI — push = trigger อัตโนมัติ

