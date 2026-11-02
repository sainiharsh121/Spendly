# Spec: Login and Logout

## Overview
Make sign-in real. `POST /login` checks the submitted email and password against the `users` table, stores the user's id in Flask's signed session cookie, and redirects to the app. `/logout` clears the session and returns the visitor to the landing page. The navbar switches between "Sign in / Get started" and the user's name / "Sign out" depending on session state. Step 2 deliberately stopped short of sessions, so this is the step that introduces `secret_key` and the notion of a logged-in user, which every later step (profile, expenses) relies on.

## Depends on
- Step 1 — Database setup (`get_db()`, `users` table, seeded `demo@spendly.com` / `demo123`).
- Step 2 — Registration (users with werkzeug-hashed passwords; `/login?registered=1` notice).

## Routes
- `GET /login` — render the sign-in form (exists); if already logged in, redirect to `/profile` — public
- `POST /login` — validate credentials; on success set `session["user_id"]` and redirect to `/profile`; on failure re-render the form with a generic error — public
- `GET /register` — (exists) if already logged in, redirect to `/profile` — public
- `GET /logout` — clear the session and redirect to `/` — public (harmless when not logged in)

`/profile` is still the Step 4 placeholder string; redirecting there is intentional. The existing `login`, `register` and `logout` function names stay unchanged. No `next` parameter is supported, so there is no open-redirect surface.

## Database changes
No database changes. Authentication uses `users.email` and `users.password_hash` as defined in `database/db.py`.

## Templates
- **Create:** none
- **Modify:**
  - `templates/login.html` — form `action` becomes `{{ url_for('login') }}`; re-populate the `email` input from the submitted value on error (never the password); keep the existing `error` and `registered` blocks.
  - `templates/base.html` — navbar: when `session.user_id` is set, show the user's name (passed as `current_user_name`) and a "Sign out" link to `url_for('logout')`; otherwise keep "Sign in" and "Get started".

## Files to change
- `app.py` — set `app.secret_key`; implement `POST /login`, `/logout`; add redirect-if-logged-in to `login` and `register`; add a `context_processor` exposing the current user's name to templates.
- `templates/login.html`
- `templates/base.html`
- `static/css/style.css` — small additions for the navbar user name / sign-out link, variables only.
- `.gitignore` — only if needed to keep any `.env` file out of git.

## Files to create
- `tests/test_login_logout.py` — pytest tests using a temporary database.

## New dependencies
No new dependencies. Flask's built-in `session` is used.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — no string formatting in SQL
- Passwords hashed with werkzeug: verify with `check_password_hash`, never compare plain text, never log passwords
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- `app.secret_key` is read from the `SECRET_KEY` environment variable, with a clearly named development-only fallback so `python app.py` still works; never commit a real production secret
- Store only `user_id` in the session; load the user's name from the database per request (via the context processor), and treat a `user_id` that no longer exists as logged out
- Email is trimmed and lower-cased before lookup (matches registration)
- Failure message is the same for unknown email and wrong password: "Invalid email or password." — do not reveal which was wrong
- Call `session.clear()` on logout and before setting `user_id` on login
- Keep route function names unchanged; leave the other placeholder routes alone
- Do not add `next`-style redirects, "remember me", password reset or CSRF libraries in this step

## Definition of done
- [ ] Signing in as `demo@spendly.com` / `demo123` redirects (302) to `/profile`
- [ ] Signing in with a freshly registered user works (email case does not matter)
- [ ] A wrong password and an unknown email both re-render `/login` with status 200 and exactly "Invalid email or password."
- [ ] After a failed attempt the email field keeps its value and the password field is empty
- [ ] Empty email or password is rejected with a clear error and does not touch the session
- [ ] After login the navbar shows the user's name and "Sign out" instead of "Sign in" / "Get started"
- [ ] `GET /logout` redirects to `/`, the session is empty afterwards, and the navbar shows "Sign in" again
- [ ] While logged in, visiting `/login` or `/register` redirects to `/profile`
- [ ] A session cookie with a non-existent `user_id` is treated as logged out
- [ ] `python app.py` starts without a missing-secret-key error and no hardcoded hex colours were added to `style.css`
- [ ] `pytest` passes, including the existing registration tests
