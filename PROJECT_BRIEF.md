# QuickNote — Project Brief

**Scope:** Lightweight note-taking app that stays on screen — Windows first, Python + tkinter + SQLite3

---

## Goals

1. **Quick note capture** — Global hotkey (Ctrl+Alt+N) → type → save → minimize to tray
2. **Outline view** — See all notes at once, fold/unfold by note
3. **Persist locally** — SQLite3 database, no cloud sync
4. **Always visible** — Stay on top when active, fade when idle (optional)

---

## Non-goals (v1)

- Sync to cloud
- Rich text/images
- Reminders
- Multiple notes open side-by-side
- Deep nested outlines
- Encryption

---

## Tech Stack

| Component | Tech |
|-----------|------|
| GUI | tkinter (Tk 9.0) |
| Persistence | SQLite3 |
| System tray | pystray |
| Global hotkey | pynput |
| Build | PyInstaller (--onefile) |
| Platform | Windows only (M1) |

---

## Data

**Table: notes**
```sql
CREATE TABLE notes (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT,              -- Markdown
    status TEXT CHECK(status IN ('active', 'completed')),
    collapsed BOOLEAN DEFAULT 0,
    created_at TIMESTAMP,
    completed_at TIMESTAMP
)
```

**Storage:** `%USERPROFILE%\.quicknote\notes.db`

---

## Milestones

### M0 — Foundation (Current)
- [x] Directory structure
- [x] requirements.txt
- [ ] database.py — SQLite3 init + schema
- [ ] main.py — test DB connection + print OK

### M1 — Window + UI skeleton
- [ ] board.py — borderless window, scroll area, always-on-top
- [ ] titlebar.py — custom titlebar (drag, minimize, close)
- [ ] theme.py — colors + light/dark
- [ ] DPI awareness, geometry persistence

### M2 — Outliner
- [ ] task_card.py / note_item.py — add/edit/delete notes
- [ ] Fold/unfold state persistence
- [ ] Keyboard shortcuts (Enter, Backspace, Tab, Ctrl+Enter)
- [ ] Checklist inside each note

### M3 — Settings
- [ ] settings_window.py — theme, alpha, hotkey config
- [ ] Fade on blur (optional)
- [ ] Roll-up (double-click titlebar)

### M4 — System integration
- [ ] tray.py — icon in system tray + menu
- [ ] hotkey.py — global Ctrl+Alt+N (new) + Ctrl+Alt+S (toggle)
- [ ] autostart.py — optional startup on boot

### M5 — Build + Polish
- [ ] build_windows.py — PyInstaller config
- [ ] README.md — user guide + keybinds
- [ ] .exe distribution

### M6 — macOS (future)
- [ ] Entry point + hotkey permission (Accessibility)
- [ ] Build for macOS

---

## Testing Checklist (per milestone)

1. Window stays on top even with other fullscreen apps
2. Thai text input works (set font to Segoe UI / Leelawadee UI)
3. Drag window → close → reopen → still at same position/size
4. Fold/unfold notes → close app → reopen → state preserved
5. Ctrl+Alt+N from another app → QuickNote pops up focused
6. Close to tray → click tray icon → window returns
7. Copy .exe to other folder → double-click → runs (no path assumptions)

---

## Known Gotchas (Windows borderless windows)

- **Focus:** Click in text field may not register — need to bind `<Button-1>` to `focus_force()`
- **Alpha:** `-alpha` attribute needs `update_idletasks()` before setting
- **Topmost:** Can slip behind fullscreen apps — re-apply every 3 seconds
- **DPI:** Call `SetProcessDpiAwareness(1)` in first line of main.py
- **Threaded callbacks:** pynput/pystray run on other threads — use `root.after(0, callback)` not direct widget access
- **Resize:** No OS chrome — implement corner drag manually
- **Multi-screen:** Save geometry must clamp to virtual screen bounds

---

## Stack Precedent

Pattern borrowed from successful project: `D:\AI\OpenCode\Capture Screen` (SuperCapture)
- Same folder structure (core/ui/platform)
- Same build pipeline (PyInstaller --onefile)
- Tested in production ✓

---

## References

- CLAUDE.md — project context + milestones
- `C:\Users\Passagain\.claude\skills\windows-python-desktop-app\` — reusable skill doc
