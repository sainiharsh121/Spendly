<div align="center">

# Spendly

**A simple, fast expense tracker built with Flask and SQLite.**

![Python](https://img.shields.io/badge/python-3.13-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/flask-3.1-000000?logo=flask&logoColor=white)
![SQLite](https://img.shields.io/badge/sqlite-003B57?logo=sqlite&logoColor=white)
![Tests](https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)

</div>

Spendly lets you record what you spend, see where the money goes, and filter your history by date. It is server-rendered with Jinja templates, uses plain `sqlite3` with no ORM, and was built one step at a time: every feature started as a written spec, got its own branch and tests, and was merged through a pull request.

## Table of contents

- [Features](#features)
- [Tech stack](#tech-stack)
- [Getting started](#getting-started)
- [Configuration](#configuration)
- [Usage](#usage)
- [Data model](#data-model)
- [Routes](#routes)
- [Project structure](#project-structure)
- [Testing](#testing)
- [Deployment](#deployment)
- [Security notes](#security-notes)
- [Roadmap](#roadmap)
- [Development workflow](#development-workflow)
- [License](#license)

## Features

- **Accounts:** register, log in and log out. Passwords are stored as hashes, never in plain text.
- **Profile dashboard:** total spent, transaction count, this month's total, top category, a spending breakdown by category and recent transactions.
- **Date filtering:** presets for This Month, Last 3 Months, Last 6 Months and All Time, plus a custom date range.
- **Expense management:** add, edit and delete expenses. Deleting asks for confirmation and only works on your own records.
- **Seven categories:** Food, Transport, Bills, Health, Entertainment, Shopping and Other.
- **Analytics:** a placeholder page for logged-in users (see the [roadmap](#roadmap)).
- **Currency:** all amounts are shown in ₹.

## Tech stack

| Layer | Technology |
|---|---|
| Language | Python 3.13 |
| Web framework | Flask 3.1, Werkzeug |
| Templates | Jinja2, one shared stylesheet, no frontend framework |
| Database | SQLite via the standard `sqlite3` module |
| Testing | pytest, pytest-flask |
| Production server | gunicorn |

## Getting started

### Prerequisites

- Python 3.13 (earlier 3.x versions are untested)
- `pip`

### Install and run

**Windows (PowerShell)**

```powershell
git clone https://github.com/sainiharsh121/Spendly.git
cd Spendly
python -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

**macOS / Linux**

```bash
git clone https://github.com/sainiharsh121/Spendly.git
cd Spendly
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

The app runs at <http://localhost:5001> with debug mode on. The database file (`spendly.db`) and some sample data are created automatically the first time the app starts.

## Configuration

Spendly reads two optional environment variables.

| Variable | Purpose | Default |
|---|---|---|
| `SECRET_KEY` | Signs the session cookie. **Always set this in production.** | An insecure, development-only value |
| `DB_PATH` | Location of the SQLite database file. | `spendly.db` in the project root |

## Usage

1. Open the app and choose **Register** to create an account (password must be at least 8 characters).
2. Log in. You land on your **profile**, which shows your totals, category breakdown and recent expenses.
3. Use **Add expense** to record an amount, category, date and optional description (up to 200 characters).
4. Use **Edit** or **Delete** on any row in the transaction table. Delete asks you to confirm first.
5. Use the filter chips above the table to narrow everything to a date range.

## Data model

```
users                              expenses
-----                              --------
id            INTEGER  PK          id           INTEGER  PK
name          TEXT                 user_id      INTEGER  FK -> users.id
email         TEXT     UNIQUE      amount       REAL
password_hash TEXT                 category     TEXT
created_at    TEXT                 date         TEXT  (YYYY-MM-DD)
                                   description  TEXT  (optional)
                                   created_at   TEXT
```

Foreign keys are enforced on every connection, and every query is parameterised.

## Routes

| Route | Methods | Login required | Description |
|---|---|---|---|
| `/` | GET | No | Landing page |
| `/register` | GET, POST | No | Create an account |
| `/login` | GET, POST | No | Log in |
| `/logout` | GET | No | Clear the session |
| `/terms`, `/privacy` | GET | No | Legal pages |
| `/profile` | GET | Yes | Stats, category breakdown, recent expenses and the date filter |
| `/analytics` | GET | Yes | Analytics placeholder |
| `/expenses/add` | GET, POST | Yes | Add an expense |
| `/expenses/<id>/edit` | GET, POST | Yes | Edit one of your expenses |
| `/expenses/<id>/delete` | POST | Yes | Delete one of your expenses |

Logged-out visitors to a protected route are redirected to `/login`. Requesting another user's expense returns `404`.

## Project structure

```
Spendly/
├── app.py                 Flask app: routes, validation, template filters
├── database/
│   ├── db.py              get_db(), init_db(), seed_db()
│   └── queries.py         Parameterised SQL helpers
├── templates/             Jinja templates; all extend base.html
├── static/                CSS and JavaScript
├── tests/                 One test module per feature
├── .claude/specs/         Numbered feature specs, one per development step
├── Procfile               Start command for Railway
├── requirements.txt
└── LICENSE
```

## Testing

```bash
pytest                                                                 # whole suite
pytest tests/test_delete_expense.py                                    # one file
pytest tests/test_delete_expense.py::test_get_delete_returns_405       # one test
```

Each test run uses a temporary database, so your local `spendly.db` is never touched.

## Deployment

The repo includes a `Procfile` that starts the app with gunicorn:

```
web: gunicorn app:app --bind 0.0.0.0:$PORT
```

### Railway

1. Install the [Railway CLI](https://docs.railway.com/guides/cli) and sign in.
2. From the project root, run `railway up` to create a project and deploy.
3. Set a real secret key:

   ```bash
   railway variable set SECRET_KEY=<a long random string>
   ```

4. SQLite stores data on disk, and a container's disk is wiped on every deploy. To keep your data, add a volume and point the database at it:

   ```bash
   railway volume add --mount-path /data
   railway variable set DB_PATH=/data/spendly.db
   ```

5. Generate a public domain with `railway domain`.

> **Windows and Git Bash:** put `MSYS_NO_PATHCONV=1` in front of the commands in step 4. Without it, Git Bash rewrites `/data` into a Windows path.

Railway is not free forever: after the trial you need a paid plan. See [Railway pricing](https://docs.railway.com/pricing/plans).

## Security notes

What is in place:

- Passwords are hashed with Werkzeug before they are stored.
- All SQL uses parameterised queries.
- Expense edit and delete are scoped to the logged-in owner.
- Delete is POST-only.

What to know before running it publicly:

- Set `SECRET_KEY` to a long random value. The default is for local development only.
- There are no CSRF tokens on forms yet.
- The first run seeds a sample account, so anyone who knows its login can use it on a public deployment. Delete or change it before sharing the app.
- SQLite suits small, single-instance deployments. It is not meant for heavy concurrent writes.

## Roadmap

- [x] Accounts, profile dashboard and date filtering
- [x] Add, edit and delete expenses
- [x] Railway deployment with a persistent database
- [ ] Analytics page with charts (currently a placeholder)
- [ ] CSRF protection on forms

## Development workflow

Each step has a spec in [`.claude/specs/`](.claude/specs). A feature gets its own branch, a test module, and a pull request that is squash-merged into `main`.

## License

Released under the [MIT License](LICENSE).
