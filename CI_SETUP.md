# QuickNote CI/CD Setup Guide (GitHub Actions)

## Overview

This project uses **GitHub Actions** for continuous integration and automatic builds. The pipeline:
- ✅ Runs full test suite on every push
- ✅ Builds Windows executable (.exe)
- ✅ Creates GitHub Releases (on version tags)
- ✅ **Zero configuration needed** — works out of the box!

---

## Step 1: Push to GitHub (First Time)

If not already on GitHub:

```bash
git remote add origin https://github.com/YOUR_USERNAME/QuickNote.git
git branch -M main
git push -u origin main
```

---

## Step 2: Enable Actions

GitHub Actions are **enabled by default**. Nothing to configure! ✅

---

## Step 3: Verify Workflow

**Workflow file location:** `.github/workflows/ci-verify-build.yml`

To manually trigger workflow:
1. Push a commit to `main` branch
2. Go to GitHub → Actions tab
3. Watch "CI — Test, Verify & Build QuickNote" run
4. Check logs for each step

---

## Pipeline Stages

### Stage 1: Test & Verify
- Installs Python dependencies
- Runs pytest on all tests
- Generates test results log
- Uploads artifacts if failed (for debugging)

### Stage 2: Build Executable
- Runs PyInstaller to create `.exe`
- Verifies executable exists and size
- Uploads to GitHub Artifacts (30-day retention)
- **If tagged (v*.*.*):** Creates GitHub Release with executable attached

---

## Usage

### Normal Development
Just commit and push to `main`:
```bash
git add .
git commit -m "feat: new feature"
git push origin main
```
→ Workflow runs automatically ✅

### Create Release
Tag a commit:
```bash
git tag -a v2.9.47 -m "Release v2.9.47"
git push origin v2.9.47
```
→ Workflow builds + creates GitHub Release with .exe attached ✅

---

## Troubleshooting

### Tests fail
- Review test logs in GitHub Actions
- Check `test_results.log` artifact
- Fix issues locally and commit:
  ```bash
  python -m pytest tests/ -v
  ```

### Build fails
- Review build logs in GitHub Actions
- Check that `build_windows.py` works locally:
  ```bash
  python build_windows.py
  ```

---

## GitHub Actions Cost

**Free tier includes:**
- ✅ 2,000 workflow minutes/month
- ✅ Unlimited public repos
- ✅ 500 MB artifact storage (30 days)

This project uses ~5-10 minutes per workflow run, so plenty of headroom 🎉

---

## Quick Start

1. ✅ Push repo to GitHub
2. ✅ Make a test commit to `main`
3. ✅ Watch CI run in Actions tab
4. ✅ Create a release tag to publish .exe:
   ```bash
   git tag -a v2.9.47 -m "Release v2.9.47"
   git push origin v2.9.47
   ```
5. ✅ Find .exe in GitHub Releases

---

## Notes

- **Pull Requests:** Run tests only (no build/release)
- **Commits to main:** Run tests + build (artifact retained 30 days)
- **Version tags (v*.*.*):** Run tests + build + create GitHub Release with .exe
- GitHub Actions free tier: 2,000 min/month (plenty of headroom)

For details, see: `.github/workflows/ci-verify-build.yml`
