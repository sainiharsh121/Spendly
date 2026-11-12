import os
import re
import sqlite3
from datetime import date, datetime, timedelta

from flask import Flask, abort, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database import queries
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


def _profile_data(user_id, date_from=None, date_to=None):
    """Summary stats, category breakdown and recent expenses for one user."""
    stats = queries.get_summary_stats(user_id, date_from, date_to)
    categories = queries.get_category_breakdown(user_id, date_from, date_to)
    return {
        "total": stats["total_spent"],
        "count": stats["transaction_count"],
        "month_total": queries.get_month_total(user_id),
        "top_category": categories[0]["category"] if categories else None,
        "categories": categories,
        "recent": queries.get_recent_transactions(
            user_id, date_from=date_from, date_to=date_to
        ),
    }


@app.route("/profile")
def profile():
    user = _current_user()
    if user is None:
        return redirect(url_for("login"))
    return render_template(
        "profile.html",
        user=user,
        updated=request.args.get("updated"),
        **_profile_data(user["id"]),
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]

AMOUNT_PATTERN = re.compile(r"\d+(\.\d{1,2})?")


def _validate_expense(form):
    """Validate expense form input. Returns (cleaned, error); one is always None."""
    amount_raw = form.get("amount", "").strip()
    if not AMOUNT_PATTERN.fullmatch(amount_raw) or float(amount_raw) <= 0:
        return None, "Please enter a valid amount greater than 0."
    amount = round(float(amount_raw), 2)

    category = form.get("category", "")
    if category not in CATEGORIES:
        return None, "Please choose a category."

    date_raw = form.get("date", "").strip()
    try:
        datetime.strptime(date_raw, "%Y-%m-%d")
    except ValueError:
        return None, "Please enter a valid date."

    description = form.get("description", "").strip()
    if len(description) > 200:
        return None, "Description must be 200 characters or fewer."

    return {
        "amount": amount,
        "category": category,
        "date": date_raw,
        "description": description or None,
    }, None


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    user = _current_user()
    if user is None:
        return redirect(url_for("login"))

    conn = get_db()
    try:
        expense = conn.execute(
            "SELECT id, amount, category, date, description FROM expenses "
            "WHERE id = ? AND user_id = ?",
            (id, user["id"]),
        ).fetchone()
        if expense is None:
            abort(404)

        if request.method == "GET":
            return render_template(
                "edit_expense.html",
                expense=expense,
                form=expense,
                categories=CATEGORIES,
            )

        cleaned, error = _validate_expense(request.form)
        if error:
            return render_template(
                "edit_expense.html",
                expense=expense,
                form=request.form,
                error=error,
                categories=CATEGORIES,
            )

        conn.execute(
            "UPDATE expenses SET amount = ?, category = ?, date = ?, description = ? "
            "WHERE id = ? AND user_id = ?",
            (
                cleaned["amount"],
                cleaned["category"],
                cleaned["date"],
                cleaned["description"],
                id,
                user["id"],
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return redirect(url_for("profile", updated=1))


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
