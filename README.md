# Nate’s GitHub Analytics Project
<img width="1311" height="853" alt="Screenshot 2026-02-17 111112" src="https://github.com/user-attachments/assets/b0069ad8-3cf6-43f8-b826-3fbc4fae0086" />

A lightweight **PyQt5 desktop app** (plus optional CLI) that pulls **GitHub repo analytics** into a clean, sortable table — including **release download totals** and **commit counts**, with optional **traffic metrics** (views/clones) when your token permissions allow it.

> Built in the same “block-based” style you use (`blocks.py`, `gui.py`, `main.py`, `pipeline.py`).

---

## Features

### Repo Summary (per repo)
- **Commits** (total commit count)
- **Stars / Forks / Watchers / Open Issues**
- **Release downloads total** (sum of all release asset `download_count`)
- **Traffic (optional)**:
  - Views (last 14 days) + uniques
  - Clones (last 14 days) + uniques
  - Top referrers + top paths (available in raw JSON tab)

### Quality of Life
- **Dark theme** (readable, clean)
- **Resizable UI** with split panels
- **Sortable table** + draggable columns
- **Double-click a repo** to open it in your browser
- **Export JSON** report

### Presets
- Save and manage multiple repo lists:
  - Apply preset
  - Save As / Update
  - Rename / Delete
- Presets are stored locally in:
  - `~/.githubanalyticsProject/config.json`

---

## Why traffic metrics may show 403

GitHub’s traffic endpoints (views/clones/referrers/paths) are restricted.
If you see:

> `Resource not accessible by personal access token (403)`

it typically means:
- your token does not have the required access for that repo, **or**
- you are not an admin/maintainer on that repo, **or**
- the token type/permission model doesn’t allow that endpoint in your context.

The app will still work without traffic access — everything else (commits, releases, downloads, stars, etc.) is public-friendly.

---

## Requirements
- Python 3.10+ recommended
- PyQt5

Install dependencies:

```bash
pip install -r requirements.txt
