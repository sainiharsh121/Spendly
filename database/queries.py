"""Pure query helpers (no Flask imports). Each opens and closes its own connection."""

from datetime import date, datetime, timedelta

from database.db import get_db


def _date_clause(date_from, date_to):
    """Return (sql_fragment, params) restricting expenses.date to a closed range.

    Only applies when both bounds are given; otherwise the query is unfiltered.
    """
    if date_from and date_to:
        return " AND date BETWEEN ? AND ?", [date_from, date_to]
    return "", []


def get_user_by_id(user_id):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    try:
        member_since = datetime.strptime(
            row["created_at"], "%Y-%m-%d %H:%M:%S"
        ).strftime("%B %Y")
    except (TypeError, ValueError):
        member_since = row["created_at"]
    return {"name": row["name"], "email": row["email"], "member_since": member_since}


def get_summary_stats(user_id, date_from=None, date_to=None):
    clause, params = _date_clause(date_from, date_to)
    conn = get_db()
    try:
        totals = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS n "
            "FROM expenses WHERE user_id = ?" + clause,
            [user_id, *params],
        ).fetchone()
        top = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ?"
            + clause
            + " GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
            [user_id, *params],
        ).fetchone()
    finally:
        conn.close()
    return {
        "total_spent": totals["total"],
        "transaction_count": totals["n"],
        "top_category": top["category"] if top else "—",
    }


def get_month_total(user_id):
    """Total spent in the current calendar month."""
    month_start = date.today().replace(day=1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)
    conn = get_db()
    try:
        return conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses "
            "WHERE user_id = ? AND date >= ? AND date < ?",
            (user_id, month_start.isoformat(), next_month.isoformat()),
        ).fetchone()[0]
    finally:
        conn.close()


def get_recent_transactions(user_id, limit=10, date_from=None, date_to=None):
    clause, params = _date_clause(date_from, date_to)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, date, description, category, amount FROM expenses "
            "WHERE user_id = ?" + clause + " ORDER BY date DESC, id DESC LIMIT ?",
            [user_id, *params, limit],
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def get_category_breakdown(user_id, date_from=None, date_to=None):
    clause, params = _date_clause(date_from, date_to)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            "WHERE user_id = ?" + clause + " GROUP BY category ORDER BY total DESC",
            [user_id, *params],
        ).fetchall()
    finally:
        conn.close()
    grand = sum(row["total"] for row in rows)
    return [
        {
            "category": row["category"],
            "total": row["total"],
            "pct": round(row["total"] / grand * 100, 1) if grand else 0,
        }
        for row in rows
    ]


def insert_expense(user_id, amount, category, date, description):
    """Insert one expense and return its new id."""
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date, description),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def delete_expense(expense_id, user_id):
    """Delete one expense owned by user_id. Return True if a row was removed."""
    conn = get_db()
    try:
        cur = conn.execute(
            "DELETE FROM expenses WHERE id = ? AND user_id = ?",
            (expense_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
