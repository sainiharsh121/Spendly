import pytest

import database.db as db
from database import queries


@pytest.fixture
def seeded(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()


def make_user(email="new@example.com"):
    conn = db.get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("New User", email, "x"),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def add(user_id, amount, category, day, description=None):
    conn = db.get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, day, description),
        )
        conn.commit()
    finally:
        conn.close()


def test_get_user_by_id_returns_profile_fields(seeded):
    user = queries.get_user_by_id(1)
    assert user["name"] == "Demo User"
    assert user["email"] == "demo@spendly.com"
    assert len(user["member_since"].split()) == 2  # "Month YYYY"


def test_get_user_by_id_missing_returns_none(seeded):
    assert queries.get_user_by_id(9999) is None


def test_summary_stats_for_seed_user(seeded):
    stats = queries.get_summary_stats(1)
    assert stats["total_spent"] == pytest.approx(370.64)
    assert stats["transaction_count"] == 8
    assert stats["top_category"] == "Bills"


def test_summary_stats_without_expenses(seeded):
    uid = make_user()
    assert queries.get_summary_stats(uid) == {
        "total_spent": 0,
        "transaction_count": 0,
        "top_category": "—",
    }


def test_recent_transactions_newest_first(seeded):
    rows = queries.get_recent_transactions(1)
    assert len(rows) == 8
    assert [r["date"] for r in rows] == sorted((r["date"] for r in rows), reverse=True)
    assert set(rows[0]) >= {"id", "date", "description", "category", "amount"}


def test_recent_transactions_respects_limit(seeded):
    assert len(queries.get_recent_transactions(1, limit=3)) == 3


def test_recent_transactions_without_expenses(seeded):
    assert queries.get_recent_transactions(make_user()) == []


def test_category_breakdown_sorted_and_sums_to_100(seeded):
    cats = queries.get_category_breakdown(1)
    assert len(cats) == 7
    totals = [c["total"] for c in cats]
    assert totals == sorted(totals, reverse=True)
    assert sum(c["pct"] for c in cats) == pytest.approx(100, abs=0.5)


def test_category_breakdown_without_expenses(seeded):
    assert queries.get_category_breakdown(make_user()) == []


def test_date_range_is_inclusive_and_scoped_to_user(seeded):
    uid = make_user()
    other = make_user("other@example.com")
    add(uid, 10, "Food", "2024-01-01")
    add(uid, 20, "Bills", "2024-01-15")
    add(uid, 40, "Food", "2024-02-01")
    add(other, 999, "Other", "2024-01-10")

    stats = queries.get_summary_stats(uid, "2024-01-01", "2024-01-15")
    assert stats["total_spent"] == 30
    assert stats["transaction_count"] == 2
    assert stats["top_category"] == "Bills"
    recent = queries.get_recent_transactions(
        uid, date_from="2024-01-01", date_to="2024-01-15"
    )
    assert len(recent) == 2
    breakdown = queries.get_category_breakdown(uid, "2024-01-01", "2024-01-15")
    assert [c["category"] for c in breakdown] == ["Bills", "Food"]


def test_single_bound_is_ignored(seeded):
    assert (
        queries.get_summary_stats(1, date_from="2099-01-01")["transaction_count"] == 8
    )


def test_insert_expense_returns_id_and_stores_row(seeded):
    new_id = queries.insert_expense(1, 50.0, "Food", "2026-03-20", "Lunch")
    conn = db.get_db()
    try:
        row = conn.execute("SELECT * FROM expenses WHERE id = ?", (new_id,)).fetchone()
    finally:
        conn.close()
    assert (row["user_id"], row["amount"], row["category"]) == (1, 50.0, "Food")
    assert (row["date"], row["description"]) == ("2026-03-20", "Lunch")


def test_insert_expense_stores_null_description(seeded):
    new_id = queries.insert_expense(1, 5.0, "Other", "2026-03-20", None)
    conn = db.get_db()
    try:
        row = conn.execute(
            "SELECT description FROM expenses WHERE id = ?", (new_id,)
        ).fetchone()
    finally:
        conn.close()
    assert row["description"] is None
