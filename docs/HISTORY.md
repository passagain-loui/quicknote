# QuickNote Release History

## v1.0.1 (2026-08-20)

### ✨ New Features

**Active/Completed Filter**
- [x] Filter toggle in titlebar (Active / Completed tabs)
- [x] Switch between views to see only active or completed notes
- [x] Automatic filtering when note status changes
- [x] When marking note as done in Active view, it disappears and appears in Completed view
- [x] When unmarking note in Completed view, it reappears in Active view
- [x] Database function `get_notes_by_status(status)` for efficient filtering

**Version & Credit Display**
- [x] App version (1.0.1) and author (Passagain P.) displayed in footer
- [x] About section in Settings window showing app info
- [x] Constants centralized in `src/core/constants.py`
- [x] Installer and build script use dynamic version from constants

### 🧪 Testing

- [x] Filter toggle buttons respond to clicks
- [x] Active/Completed views show correct notes
- [x] Status changes automatically filter UI
- [x] Database filtering logic verified
- [x] Footer credit line displays correctly
- [x] About section shows app info and developer credit
- [x] Version consistency across .exe build and installer

---

## v1.0.0 (2026-08-20)

### ✨ Major Features

**Core**
- [x] SQLite3 local database (`~/.quicknote/notes.db`)
- [x] Borderless, always-on-top window (Windows-specific)
- [x] Outliner — fold/unfold notes + checklist

**UI — macOS Pastel Theme**
- [x] Traffic light titlebar buttons (Red/Yellow/Green)
- [x] Pastel color palette for note cards
- [x] Light/Dark mode
- [x] Opacity control (0.3–1.0)
- [x] Roll-up support (double-click titlebar)

**System Integration**
- [x] System tray icon with menu
- [x] Global hotkeys (Ctrl+Alt+N, Ctrl+Alt+S)
- [x] Geometry & settings persistence
- [x] Single-instance lock (prevent duplicate running)

**Build & Distribution**
- [x] PyInstaller one-file `.exe` build
- [x] No external dependencies required (Python embedded)
- [x] README with full user guide

### 🔧 Technical Details

- **Framework:** tkinter (Python 3.14.7, Tk 9.0)
- **Database:** SQLite3 (local, no sync)
- **Tray/Hotkey:** pystray + pynput (daemon threads)
- **Build:** PyInstaller (--onefile --noconsole)
- **Platform:** Windows 11 (primary)

### 🧪 Testing

- [x] Geometry safety (clamp to virtual screen)
- [x] Alpha guard (0.3–1.0 enforcement)
- [x] Visibility verification (deiconify + lift + topmost)
- [x] Thread-safety (root.after for GUI callbacks from hotkey/tray)
- [x] Single-instance lock (prevent duplicate instances)

### 📦 Known Limitations (v1)

- macOS support not included (Windows only)
- No Markdown rendering (plain text in cards)
- No reminders or notifications
- No cloud sync (local only)
- No drag-and-drop reordering
- No deep nesting (only 1 level outliner)

### 🎁 Installer Support (v1.0.0+)

- [x] Windows Installer Wizard (Inno Setup)
  - Install to `%LOCALAPPDATA%\Programs\QuickNote\`
  - No admin rights required
  - Desktop icon + Startup shortcut options
  - Clean uninstall (removes all shortcuts)
- [x] Portable `.exe` (no install needed)
- [x] Build automation (PyInstaller + ISCC)

### 🚀 Future Roadmap (v1.1+)

- [ ] Markdown syntax highlighting
- [ ] Reminders/due dates
- [ ] Category tags
- [ ] Dark theme auto-switch (system preference)
- [ ] Keyboard-only mode (full outline navigation)
- [ ] macOS support
- [ ] Export to Markdown/PDF

---

## Development Notes

### Architecture

```
src/core/      Database + data models (no Tkinter)
src/ui/        All Tkinter UI components
src/platform/  Windows-specific (tray, hotkey, autostart)
```

### Key Files

| File | Purpose |
|------|---------|
| `main.py` | Entry point, event loop, single-instance lock |
| `src/core/database.py` | SQLite3 CRUD operations |
| `src/core/models.py` | Note dataclass |
| `src/core/settings.py` | Settings manager + coercion |
| `src/ui/board.py` | Main window (borderless, always-on-top) |
| `src/ui/note_card.py` | Individual note widget (pastel design) |
| `src/ui/titlebar.py` | macOS-style traffic light buttons |
| `src/platform/tray.py` | System tray icon + menu |
| `src/platform/hotkey.py` | Global hotkey listener |

### Gotchas Solved

1. **Borderless Window Focus** — Bind `<Button-1>` to `focus_force()`
2. **Alpha Not Working** — Call `update_idletasks()` before `attributes("-alpha", ...)`
3. **Topmost Sliding Back** — Re-apply every 3 seconds via `root.after(3000, ...)`
4. **DPI Scaling Blur** — `SetProcessDpiAwareness(1)` on first line
5. **Multi-screen Geometry** — Clamp to virtual screen bounds
6. **Thread-safety** — Use `root.after(0, callback)` from pynput/pystray threads
7. **Window Hidden** — Call `deiconify()` + `lift()` + `focus_force()` after `overrideredirect(True)`

### Build Command

```bash
python build_windows.py              # Standard build (no console)
python build_windows.py --debug      # Build with console window
```

Result: `dist/QuickNote.exe` (~30–40 MB, ~2–5 sec startup)

---

## Status: ✅ COMPLETE

Version 1.0.0 is feature-complete for initial release.

- UI: Polished and tested ✓
- Database: Atomic write + backup ✓
- System Integration: Tray + hotkey + single-instance ✓
- Build: One-file .exe distribution ✓
- Documentation: README + CLAUDE.md + HISTORY ✓

Ready for user testing.
