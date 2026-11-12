# Spec: Edit Expense

## Overview
Replace the `/expenses/<id>/edit` placeholder string with a real edit form. From the profile page's "Recent expenses" table, a logged-in user clicks Edit on a row and lands on a form pre-filled with that expense's amount, category, date and description. Submitting valid changes updates the row and returns the user to `/profile`, where the totals, category breakdown and table reflect the change. Invalid input re-renders the form with an error and the user's submitted values. Users can only edit their own expenses: another user's expense (or a non-existent id) is a 404. This is the first step that writes to the `expenses` table through the UI, so it also introduces the shared list of valid categories and the amount/date/category validation that Step 7 (add) can reuse.

## Depends on
- Step 1 — Database setup (`get_db()`, `expenses` table with `amount`, `category`, `date`, `description`).
- Step 3 — Login and logout (`_current_user()`, `session["user_id"]`).
- Step 4 — Profile page (the Edit links in the recent-expenses table, and the page the edit redirects back to).

Step 7 (add expense) is **not** required and is still a placeholder; do not implement it here. Steps 5 and 6 have no spec in `.claude/specs/` yet and are not depended on.

## Routes
- `GET /expenses/<int:id>/edit` — render the edit form pre-filled from the expense; redirect to `/login` if not logged in; 404 if the expense does not exist or belongs to another user — logged-in
- `POST /expenses/<int:id>/edit` — validate and update the expense; on success redirect (302) to `/profile?updated=1`; on validation failure re-render the form with status 200, an error message and the submitted values; same auth and 404 rules as GET — logged-in

The existing `edit_expense` view function keeps its name and `id` parameter (`url_for('edit_expense', id=e.id)` is already used in `profile.html`). `add_expense` and `delete_expense` remain placeholders and are left alone.

## Database changes
No database changes. The update uses the existing `expenses` columns in `database/db.py`:
- Updated: `amount` (REAL), `category` (TEXT), `date` (TEXT, `YYYY-MM-DD`), `description` (TEXT, nullable)
- Never changed: `id`, `user_id`, `created_at`

Every query that reads or writes an expense includes `user_id = ?` alongside `id = ?`, so ownership is enforced in SQL, not just in the view.

## Templates
- **Create:**
  - `templates/edit_expense.html` — extends `base.html`; title `Edit expense — Spendly`; a card with heading "Edit expense" and a `POST` form whose `action` is `{{ url_for('edit_expense', id=expense.id) }}`, containing:
    - Amount — `<input type="number" step="0.01" min="0.01">`
    - Category — `<select>` built from the shared category list, current value selected
    - Date — `<input type="date">`
    - Description — `<input type="text" maxlength="200">`, optional
    - "Save changes" submit button and a "Cancel" link back to `url_for('profile')`
    - An error block (same look as `.auth-error`) shown when `error` is set. Fields re-populate from the submitted values on error.
- **Modify:**
  - `templates/profile.html` — when `updated` is set (`/profile?updated=1`), show a one-line "Expense updated." success notice above the stat row (reuse the `.auth-success` look). No other change; the Edit links already point at `edit_expense`.

## Files to change
- `app.py` — add a `CATEGORIES` constant (Food, Transport, Bills, Health, Entertainment, Shopping, Other); add `_validate_expense(form)` helper returning `(cleaned, error)`; replace the `edit_expense` placeholder with a `GET`/`POST` view; pass `updated=request.args.get("updated")` into the `profile` view's template context.
- `templates/profile.html` — success notice.
- `static/css/style.css` — expense-form styles (card, `<select>` styled to match `.form-input`, two-column row for amount/date on wide screens collapsing to one column on mobile, cancel link), built only from existing CSS variables.

## Files to create
- `templates/edit_expense.html`
- `tests/test_edit_expense.py` — pytest tests using a temporary database (follow the pattern in `tests/test_profile.py` and `tests/test_login_logout.py`).

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — no string formatting or f-strings in SQL
- Passwords hashed with werkzeug (this step does not touch passwords; never select or render `password_hash`)
- Use CSS variables — never hardcode hex values; reuse the existing tokens (`--accent`, `--paper-card`, `--border`, `--ink-*`, `--radius-*`, `--font-display`, `--font-body`)
- All templates extend `base.html`
- Not logged in (including a session whose `user_id` no longer exists) → redirect to `/login`, no `next` parameter
- Load the expense with `WHERE id = ? AND user_id = ?`; if no row, `abort(404)`. Do not distinguish "not yours" from "does not exist"
- Update with `UPDATE expenses SET amount = ?, category = ?, date = ?, description = ? WHERE id = ? AND user_id = ?`, then `commit()`; close the connection in `finally`
- Validation (server-side; HTML attributes are only a convenience):
  - amount: required, parses as a number, finite (reject `nan`/`inf`), greater than 0, and at most 2 decimal places once rounded; store as a float rounded to 2 dp
  - category: must be one of `CATEGORIES`
  - date: required, must parse with `datetime.strptime(value, "%Y-%m-%d")`; store the `YYYY-MM-DD` string
  - description: trimmed, at most 200 characters; empty string is stored as `NULL`
  - On failure return a single specific message (e.g. "Please enter a valid amount greater than 0.") and do not modify the row
- Ignore any `user_id`, `id` or `created_at` fields in the submitted form; they must never be updated
- Rely on Jinja autoescaping for the description and error text; never use `|safe`
- Keep route function names unchanged; leave `add_expense` and `delete_expense` placeholders alone
- Do not implement add, delete, bulk edit, CSRF libraries, flash-message infrastructure or JavaScript in this step (the `?updated=1` query parameter mirrors the existing `?registered=1` pattern)

## Definition of done
- [ ] Visiting `/expenses/<id>/edit` while logged out redirects (302) to `/login`
- [ ] Signing in as `demo@spendly.com` / `demo123` and clicking Edit on a profile row opens a styled form (not the "coming in Step 8" string) pre-filled with that expense's amount, category, date and description
- [ ] Changing the amount and saving redirects to `/profile?updated=1`, shows "Expense updated.", and the profile's total spent, this-month figure, category breakdown and table row all reflect the new amount
- [ ] Changing the category moves the spend between categories in the profile breakdown, and the table row shows the new category badge
- [ ] Clearing the description and saving stores no description and the table shows "—"
- [ ] An amount of `0`, a negative number, `abc`, `nan` or empty is rejected with status 200, an error message, the submitted values kept in the form, and the database row unchanged
- [ ] An invalid or empty date and a category outside the fixed list are each rejected the same way
- [ ] A description longer than 200 characters is rejected
- [ ] Editing an expense that belongs to a different user returns 404 and does not change that row (verified with two users in a test)
- [ ] Requesting `/expenses/99999/edit` (non-existent id) returns 404
- [ ] A session cookie with a non-existent `user_id` redirects to `/login`
- [ ] Posting extra fields such as `user_id` or `created_at` does not change those columns
- [ ] The form is usable at mobile width (~375px): no horizontal page scroll, fields stack
- [ ] No hardcoded hex colours were added to `style.css` or the templates
- [ ] `pytest` passes, including the existing registration, login/logout and profile tests
