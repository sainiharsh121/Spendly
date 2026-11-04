# Spec: Profile Page

## Overview
Replace the `/profile` placeholder string with a real, designed page. A logged-in user lands here after signing in (Steps 2 and 3 both redirect to it), so it is the first screen of the app proper. The page shows who the user is (name, email, member-since), a row of summary stats computed from their expenses (total spent, number of expenses, this month's spend, top category), a category breakdown with proportional bars, and a table of their most recent expenses. It is read-only: adding, editing and deleting expenses arrive in Steps 7-9, so the page links to those existing placeholder routes but does not implement them. Visitors who are not logged in are redirected to `/login`.

## Depends on
- Step 1 — Database setup (`get_db()`, `users` and `expenses` tables, seeded demo user with 8 expenses).
- Step 2 — Registration (users exist with `created_at`).
- Step 3 — Login and logout (`session["user_id"]`, `_current_user()`, `current_user_name` context variable, redirects to `/profile`).

## Routes
- `GET /profile` — render the profile page for the logged-in user; redirect to `/login` if there is no valid session — logged-in

The existing `profile` view function keeps its name (`url_for('profile')` is used by the login and register redirects). No other routes change; `/expenses/add`, `/expenses/<id>/edit` and `/expenses/<id>/delete` remain placeholders and are only linked to.

## Database changes
No database changes. All data comes from the existing tables in `database/db.py`:
- `users` — `id`, `name`, `email`, `created_at`
- `expenses` — `user_id`, `amount` (REAL), `category`, `date` (`YYYY-MM-DD`), `description` (nullable)

Every query is filtered by `user_id = ?` so a user only ever sees their own expenses.

## Templates
- **Create:**
  - `templates/profile.html` — extends `base.html`; sections, top to bottom:
    1. **Header card** — avatar circle with the user's initial, name (display font), email, "Member since <Month YYYY>", and an "Add expense" button linking to `url_for('add_expense')`.
    2. **Stat row** — four cards: Total spent, Expenses (count), This month, Top category. Amounts shown as `₹1,234.50`.
    3. **Category breakdown** — one row per category with spend, percentage of total and a horizontal bar whose width is the percentage (inline `style="width: N%"` is the only inline style allowed). Sorted highest spend first.
    4. **Recent expenses** — table of the latest 10 expenses (date, description, category badge, amount), newest first, each row with Edit / Delete links to the existing placeholder routes.
    5. **Empty state** — when the user has no expenses, replace sections 2-4 stats with zeros and show a friendly message with an "Add your first expense" link instead of the breakdown and table.
- **Modify:**
  - `templates/base.html` — make the navbar user name a link to `url_for('profile')` (still shows "Sign out" next to it).

## Files to change
- `app.py` — replace the `/profile` placeholder with the real view; add small helper(s) to query the summary, category breakdown and recent expenses; add a `rupee`/amount formatting Jinja filter (or format in the view).
- `templates/base.html`
- `static/css/style.css` — new profile styles (cards, stat grid, breakdown bars, table, category badges, empty state, responsive layout), built only from existing CSS variables.

## Files to create
- `templates/profile.html`
- `tests/test_profile.py` — pytest tests using a temporary database (follow the pattern in `tests/test_login_logout.py`).

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — no string formatting or f-strings in SQL
- Passwords hashed with werkzeug (never select or render `password_hash` on this page)
- Use CSS variables — never hardcode hex values; reuse the existing tokens (`--accent`, `--accent-light`, `--accent-2`, `--accent-2-light`, `--paper-card`, `--border`, `--ink-*`, `--radius-*`, `--font-display`, `--font-body`). If a new colour is truly needed, add it as a variable in `:root` rather than inline.
- All templates extend `base.html`
- `/profile` must redirect to `/login` when `_current_user()` is `None` (including a session whose `user_id` no longer exists); do not add a `next` parameter
- Compute aggregates in SQL (`SUM`, `COUNT`, `GROUP BY`) rather than loading every row into Python
- "This month" = expenses whose `date` starts with the current `YYYY-MM` (use a parameterised `date BETWEEN ? AND ?` or `LIKE ?` with a bound value)
- Guard against divide-by-zero when total spent is 0
- Rely on Jinja autoescaping for user-controlled text (name, email, description); never use `|safe`
- Category badge colour comes from a CSS class per fixed category (Food, Transport, Bills, Health, Entertainment, Shopping, Other), with a fallback style for any unknown value
- Layout must be responsive: stat grid collapses from 4 → 2 → 1 columns and the table scrolls horizontally or stacks on narrow screens
- Do not implement add/edit/delete, filtering, pagination, avatar upload or password change in this step
- Keep existing route function names; leave other placeholder routes alone

## Definition of done
- [ ] Visiting `/profile` while logged out redirects (302) to `/login`
- [ ] Signing in as `demo@spendly.com` / `demo123` lands on a styled profile page (not the "coming in Step 4" string)
- [ ] The header shows the user's name, email, initial avatar and "Member since" month/year
- [ ] The demo user's stat cards show the correct total (sum of the 8 seeded expenses), count of 8, this month's total, and top category
- [ ] The category breakdown lists each category the user has spent in, highest first, with percentages that add up to about 100% and bar widths matching them
- [ ] The recent expenses table shows at most 10 rows, newest first, with date, description, category badge and amount
- [ ] A newly registered user with no expenses sees zeros in the stats and the empty-state message with an "Add your first expense" link, with no errors or division-by-zero
- [ ] One user never sees another user's expenses (verified with two users in a test)
- [ ] A session cookie with a non-existent `user_id` redirects to `/login`
- [ ] The navbar user name links to `/profile`; "Add expense", Edit and Delete links point at the existing placeholder routes
- [ ] The page is usable at mobile width (~375px): no horizontal page scroll, stats stack
- [ ] No hardcoded hex colours were added to `style.css` or the template
- [ ] `pytest` passes, including the existing registration and login/logout tests
