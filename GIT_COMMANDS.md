# QuickNote v1.0.1 — Git Commit & Push Commands

## Summary of Changes
- ✅ Active/Completed filter toggle in titlebar
- ✅ Version (1.0.1) and author (Passagain P.) displayed in footer
- ✅ About section in Settings window
- ✅ Centralized version management in `src/core/constants.py`
- ✅ Dynamic version in build scripts and installer
- ✅ All tests pass, build successful

## Git Commands to Run

### 1. Configure Git (First Time Only)
```bash
git config user.name "Passagain P."
git config user.email "passagain@gmail.com"
```

### 2. Add All Files to Staging
```bash
git add -A
```

### 3. Commit with Detailed Message
```bash
git commit -m "feat: v1.0.1 - Add Active/Completed filter and version/credit display

- Add Active/Completed filter toggle in titlebar
- Auto-update UI when note status changes
- Get notes by status efficiently with get_notes_by_status()
- Display app version and author in footer
- Add About section in Settings window
- Centralize version in constants.py
- Update installer to v1.0.1 with author credit
- All tests pass, build successful

Features:
• Filter notes by Active/Completed status
• Footer shows: QuickNote v1.0.1 • By Passagain P.
• About tab displays app info and developer credit
• Dynamic version management across build system"
```

### 4. Verify Commit
```bash
git log --oneline -1
git show --stat
```

### 5. Add Remote Repository (Replace with Your GitHub URL)
```bash
git remote add origin https://github.com/your-username/quicknote.git
```

### 6. Push to GitHub
```bash
git branch -M main
git push -u origin main
```

## Alternative: Short Commit (Without Details)
```bash
git commit -m "v1.0.1: Add filter + version/credit display"
```

## Files Changed

### New Files (2)
- `src/core/constants.py` — App constants (version, author, description)
- `.gitignore` — Git ignore rules

### Modified Core (2)
- `src/core/database.py` — Added `get_notes_by_status()` function
- `main.py` — Import constants instead of hardcoding

### Modified UI (4)
- `src/ui/board.py` — Footer credit line
- `src/ui/titlebar.py` — Filter toggle buttons
- `src/ui/settings_window.py` — Notebook tabs + About section
- `src/ui/theme.py` — Added `fg_muted` color

### Modified Build/Config (3)
- `build_windows.py` — Use version from constants
- `installer.iss` — Version 1.0.1, author credit
- `main.py` — Import constants

### Modified Docs (2)
- `CLAUDE.md` — Updated to v1.0.1
- `docs/HISTORY.md` — v1.0.1 release notes

## Status Check
```bash
git status
git diff --cached
```

## Notes
- All files pass `python main.py --selftest`
- Build successful: `dist/QuickNote.exe` (20.4 MB)
- Version consistency verified across all files
- Ready for distribution
