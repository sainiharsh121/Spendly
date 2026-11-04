import os
import sqlite3
from datetime import date, datetime, timedelta

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import get_db, init_db, seed_db

app = Flask(__name__)
# Development-only fallback; set SECRET_KEY in the environment for real use.
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-insecure-secret-key")

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

def _current_user():
    """Return the logged-in user's row, or None. Clears a stale session."""
    user_id = session.get("user_id")
    if user_id is None:
        return None
    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()
    if user is None:
        session.clear()
    return user


@app.context_processor
def inject_current_user():
    user = _current_user()
    return {"current_user_name": user["name"] if user else None}


@app.route("/")
def landing():
    return render_template("landing.html")


DUPLICATE_EMAIL_ERROR = "An account with this email already exists."


def _validate_registration(name, email, password):
    """Return an error message for invalid registration input, else None."""
    if not name:
        return "Please enter your name."
    local, sep, domain = email.partition("@")
    if not (local and sep and domain):
        return "Please enter a valid email address."
    if len(password) < 8:
        return "Password must be at least 8 characters."
    return None


@app.route("/register", methods=["GET", "POST"])
def register():
    if _current_user():
        return redirect(url_for("profile"))
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    def fail(message):
        return render_template("register.html", error=message, name=name, email=email)

    error = _validate_registration(name, email, password)
    if error:
        return fail(error)

    conn = get_db()
    try:
        if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            return fail(DUPLICATE_EMAIL_ERROR)
        try:
            conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password)),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            return fail(DUPLICATE_EMAIL_ERROR)
    finally:
        conn.close()

    return redirect(url_for("login", registered=1))


LOGIN_ERROR = "Invalid email or password."


@app.route("/login", methods=["GET", "POST"])
def login():
    if _current_user():
        return redirect(url_for("profile"))
    if request.method == "GET":
        return render_template("login.html", registered=request.args.get("registered"))

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    def fail(message):
        return render_template("login.html", error=message, email=email)

    if not email or not password:
        return fail("Please enter your email and password.")

    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id, password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()
    finally:
        conn.close()

    if user is None or not check_password_hash(user["password_hash"], password):
        return fail(LOGIN_ERROR)

    session.clear()
    session["user_id"] = user["id"]
    return redirect(url_for("profile"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.template_filter("rupee")
def rupee(value):
    return f"₹{value or 0:,.2f}"


@app.template_filter("month_year")
def month_year(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").strftime("%B %Y")
    except (TypeError, ValueError):
        return value


def _profile_data(user_id):
    """Summary stats, category breakdown and recent expenses for one user."""
    today = date.today()
    month_start = today.replace(day=1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)

    conn = get_db()
    try:
        totals = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS n "
            "FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        month_total = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses "
            "WHERE user_id = ? AND date >= ? AND date < ?",
            (user_id, month_start.isoformat(), next_month.isoformat()),
        ).fetchone()[0]
        category_rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            "WHERE user_id = ? GROUP BY category ORDER BY total DESC",
            (user_id,),
        ).fetchall()
        recent = conn.execute(
            "SELECT id, date, description, category, amount FROM expenses "
            "WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT 10",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()

    grand = totals["total"]
    categories = [
        {
            "category": row["category"],
            "total": row["total"],
            "pct": round(row["total"] / grand * 100, 1) if grand else 0,
        }
        for row in category_rows
    ]
    return {
        "total": grand,
        "count": totals["n"],
        "month_total": month_total,
        "top_category": categories[0]["category"] if categories else None,
        "categories": categories,
        "recent": recent,
    }


@app.route("/profile")
def profile():
    user = _current_user()
    if user is None:
        return redirect(url_for("login"))
    return render_template("profile.html", user=user, **_profile_data(user["id"]))


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
