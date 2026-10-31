# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Spendly: a Flask expense tracker built as a step-by-step student project. Only the landing, auth pages, and legal pages are real so far. Most of the backend is still a stub.

## Commands

Windows/PowerShell, using the committed-out `venv/` at the repo root:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py          # dev server with debug on, http://localhost:5001
pytest                 # pytest + pytest-flask are in requirements.txt; no tests exist yet
pytest path/to/test_file.py::test_name   # run a single test
```

There is no linter or build step configured.

## Architecture

- `app.py` is a single-file Flask app. All routes live there, and each one renders a template from `templates/`.
- Implemented routes: `/` (landing), `/register`, `/login`, `/terms`, `/privacy`. These only render templates (no form handling yet).
- Placeholder routes return plain strings that name the tutorial step that will implement them (`/logout`, `/profile`, `/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete`). Replace these in place when implementing the step. Keep the route function names, because templates use `url_for('landing')`, `url_for('login')`, etc.
- `database/db.py` is intentionally empty apart from a comment spec. Step 1 is to implement `get_db()` (SQLite connection with `row_factory` and foreign keys on), `init_db()` (`CREATE TABLE IF NOT EXISTS`), and `seed_db()` (sample data).
- Templates all extend `templates/base.html`, which provides the navbar, `title`/`head`/`content` blocks, and loads Google Fonts (DM Serif Display, DM Sans) plus `static/css/style.css`.
- `static/css/style.css` is a single stylesheet (~700 lines) shared by all pages. `static/js/main.js` is essentially empty.
- Recent work is landing-page UI (hero redesign, YouTube modal, footer links to terms and privacy). `docs/Hero_image.png` is currently deleted in the working tree.
