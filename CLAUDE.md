# QuickNote v1.0.1 — Complete

แอปจดโน้ตเบา ๆ ที่ค้างบนหน้าจอตลอดเวลา — Python + tkinter + SQLite3 + macOS Pastel UI

**Status: ✅ COMPLETE & TESTED** — Ready for distribution

> v1.0.1 เพิ่มระบบ **Active/Completed Filter** ให้ดูงานตามสถานะ

> เอกสารนี้เขียนให้อ่านแล้วทำต่อได้ทันที อ้างอิง `docs/HISTORY.md` สำหรับ changelog

---

## ✨ Features (v1.0.1)

- ✅ **Always-on-top Window** — Borderless, drag-enabled, Windows 11 compatible
- ✅ **Outliner** — Fold/unfold notes + checklist inside each note
- ✅ **macOS Pastel UI** — Traffic light buttons (Red/Yellow/Green), soft colors
- ✅ **Active/Completed Filter** — Toggle between viewing active and completed notes (v1.0.1)
- ✅ **Version & Credit Display** — Footer credit line + About section (v1.0.1)
- ✅ **System Tray** — Minimize to tray, context menu
- ✅ **Global Hotkey** — `Ctrl+Alt+N` (new note), `Ctrl+Alt+S` (toggle show)
- ✅ **SQLite3 Local DB** — Atomic write + backup, no cloud sync
- ✅ **Settings Persist** — Window geometry, theme, opacity saved
- ✅ **Single-Instance Lock** — Prevents duplicate running

---

## 📦 Environment

- **Python:** 3.14.7 (Tk 9.0)
- **Windows:** 11 Home (tested)
- **Dependencies:** pystray, pynput, Pillow, pywin32, PyInstaller

All installed ✓

---

## 📁 Project Structure (Complete)

```
Noted Planing and Record/
├── CLAUDE.md                 ← You are here
├── PROJECT_BRIEF.md
├── README.md                 ← User guide
├── requirements.txt
├── build_windows.py          ← PyInstaller config
├── main.py                   ← Entry point + event loop
├── docs/HISTORY.md           ← Release notes
│
└── src/
    ├── core/
    │   ├── database.py       ✅ SQLite3 CRUD + init
    │   ├── models.py         ✅ Note dataclass
    │   └── settings.py       ✅ Settings manager + coercion
    ├── ui/
    │   ├── board.py          ✅ Main window (borderless, always-on-top)
    │   ├── titlebar.py       ✅ macOS traffic light buttons
    │   ├── note_card.py      ✅ Pastel card widget (strikethrough)
    │   ├── theme.py          ✅ Light/Dark + pastel palette
    │   └── settings_window.py ✅ Settings dialog
    └── platform/
        ├── tray.py           ✅ pystray icon + menu
        ├── hotkey.py         ✅ pynput global hotkey listener
        └── autostart.py      ✅ Windows startup shortcut

```

---

## 🔄 Data Model

```python
@dataclass
class Note:
    id: str                    # uuid4 hex
    title: str
    content: str
    status: str                # 'active' | 'completed'
    collapsed: bool = False
    created_at: str            # ISO format
    completed_at: str | None
```

**Storage:** `~/.quicknote/notes.db` (SQLite3) + `settings.json`

---

## ✅ Status: All Milestones Complete

| Milestone | Feature | Status |
|-----------|---------|--------|
| **M0** | Foundation (DB, paths, models) | ✅ Complete |
| **M1** | Window + UI skeleton | ✅ Complete |
| **M2** | Outliner (note cards, add/edit/delete) | ✅ Complete |
| **M3** | Polish (macOS Pastel theme, roll-up) | ✅ Complete |
| **M4** | System integration (tray, hotkey, autostart) | ✅ Complete |
| **M5** | Build + docs + final polish | ✅ Complete |

---

## 🚀 Build & Distribution

```bash
# Standard build (no console)
python build_windows.py

# Build with debug console (see errors)
python build_windows.py --debug

# Output: dist/QuickNote.exe (~35 MB, ~3 sec startup)
```

---

## 🧪 Testing Checklist (All Passed)

- [x] Window always-on-top even with Chrome/Excel fullscreen
- [x] Thai text input works (Segoe UI font)
- [x] Drag window → close → reopen → same position/size
- [x] Fold/unfold → close → reopen → state preserved
- [x] Ctrl+Alt+N from other app → QuickNote pops up focused
- [x] Minimize to tray → click tray icon → window returns
- [x] .exe works from any folder (no path assumptions)
- [x] No duplicate instances (single-instance lock)
- [x] Strikethrough title when completed (overstrike font)
- [x] Roll-up double-click titlebar (fold to 32px height)
- [x] Active/Completed filter toggle works (v1.0.1)
- [x] Mark note done → disappears from Active, appears in Completed (v1.0.1)
- [x] Unmark note → disappears from Completed, appears in Active (v1.0.1)
- [x] Footer credit line displays (v1.0.1)
- [x] Settings window has About tab (v1.0.1)
- [x] About section shows version and developer (v1.0.1)

---

## 🛠️ Code Conventions

- **Comments:** Thai, explain WHY not WHAT
- **Type hints:** Public methods only
- **core/ layer:** No tkinter imports (test-friendly)
- **Data validation:** Coerce + fallback all external inputs
- **Thread-safety:** Use `root.after(0, callback)` from daemon threads
- **Storage:** Atomic write (tmp → fsync → replace) + .bak fallback

---

## 🎨 Architecture Notes

**Three-Layer Design:**
- `core/` — Data + logic (tkinter-free, testable)
- `ui/` — All tkinter UI components
- `platform/` — OS-specific code (Windows: tray, hotkey, autostart)

**Windows Gotchas Solved:**
1. Borderless window focus → `<Button-1>` bind to `focus_force()`
2. `-alpha` fails before map → `update_idletasks()` first
3. `-topmost` slides behind fullscreen → re-apply every 3s
4. DPI scaling blur → `SetProcessDpiAwareness(1)` first line
5. Multi-screen geometry lost → clamp to virtual screen bounds
6. pynput/pystray threads → use `root.after(0, ...)` not direct widget access
7. Overrideredirect hidden → call `deiconify()` + `lift()` + `topmost`

---

## 📚 References

- User guide: `README.md`
- Technical roadmap: `PROJECT_BRIEF.md`
- Release history: `docs/HISTORY.md`
- Skill template: `~/.claude/skills/windows-python-desktop-app/`

---

## 🔮 Future Enhancements (v1.1+)

- Markdown rendering
- Reminders/due dates
- Category tags
- System theme auto-switch
- Keyboard-only navigation
- macOS support
- Export to Markdown/PDF

---

**Version:** 1.0.1  
**Last Updated:** 2026-08-20  
**Status:** ✅ RELEASED & STABLE

---

### What's New in v1.0.1

- **Active/Completed Filter Toggle** — Titlebar now shows two tabs to switch between Active and Completed notes
- **Automatic View Updates** — When you mark a note as done, it automatically disappears from Active view
- **Efficient Database Filtering** — New `get_notes_by_status()` function for better performance
- **Version & Credit Display** — Footer shows app version and developer name
- **About Section** — Settings window includes About tab with full app details and credits
- **Dynamic Version Management** — Version stored in `src/core/constants.py`, used throughout build system
