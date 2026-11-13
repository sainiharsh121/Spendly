import pytest

import database.db as db
from app import app as flask_app
from database import queries


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def login(client, email="demo@spendly.com", password="demo123"):
    return client.post("/login", data={"email": email, "password": password})


def register_and_login(client, name="Asha Rao", email="asha@example.com"):
    client.post(
        "/register",
        data={"name": name, "email": email, "password": "longenough1"},
    )
    login(client, email=email, password="longenough1")


def user_id_for(email):
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()["id"]
    finally:
        conn.close()


def add_expense(user_id, amount=10.0, category="Food", description="Lunch", day="2025-04-10"):
    conn = db.get_db()
    try:
        cur = conn.execute(
            "INSERT INTO expenses (user_id, amount, category, description, date) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, description, day),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def expense_exists(expense_id):
    conn = db.get_db()
    try:
        return (
            conn.execute(
                "SELECT 1 FROM expenses WHERE id = ?", (expense_id,)
            ).fetchone()
            is not None
        )
    finally:
        conn.close()


def count_expenses():
    conn = db.get_db()
    try:
        return conn.execute("SELECT COUNT(*) AS n FROM expenses").fetchone()["n"]
    finally:
        conn.close()


# ------------------------------------------------------------------ #
# Unit: queries.delete_expense                                        #
# ------------------------------------------------------------------ #


def test_delete_expense_removes_own_row(client):
    uid = user_id_for("demo@spendly.com")
    eid = add_expense(uid)
    assert queries.delete_expense(eid, uid) is True
    assert not expense_exists(eid)


def test_delete_expense_wrong_user_leaves_row(client):
    uid = user_id_for("demo@spendly.com")
    eid = add_expense(uid)
    assert queries.delete_expense(eid, uid + 999) is False
    assert expense_exists(eid)


def test_delete_expense_nonexistent_id_changes_nothing(client):
    uid = user_id_for("demo@spendly.com")
    before = count_expenses()
    assert queries.delete_expense(999999, uid) is False
    assert count_expenses() == before


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #


def test_logged_out_post_redirects_to_login_and_keeps_row(client):
    eid = add_expense(user_id_for("demo@spendly.com"))
    resp = client.post(f"/expenses/{eid}/delete")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    assert expense_exists(eid)


def test_delete_own_expense_redirects_to_profile(client):
    login(client)
    eid = add_expense(user_id_for("demo@spendly.com"))
    resp = client.post(f"/expenses/{eid}/delete")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")
    assert not expense_exists(eid)


def test_deleted_expense_no_longer_listed_on_profile(client):
    login(client)
    eid = add_expense(user_id_for("demo@spendly.com"), description="Unique-zebra-lunch")
    assert b"Unique-zebra-lunch" in client.get("/profile").data
    client.post(f"/expenses/{eid}/delete")
    assert b"Unique-zebra-lunch" not in client.get("/profile").data


def test_delete_other_users_expense_returns_404(client):
    other_id = add_expense(user_id_for("demo@spendly.com"))
    client.post(
        "/register",
        data={"name": "Asha Rao", "email": "asha@example.com", "password": "longenough1"},
    )
    login(client, email="asha@example.com", password="longenough1")
    resp = client.post(f"/expenses/{other_id}/delete")
    assert resp.status_code == 404
    assert expense_exists(other_id)


def test_delete_nonexistent_expense_returns_404(client):
    login(client)
    assert client.post("/expenses/999999/delete").status_code == 404


def test_get_delete_returns_405(client):
    login(client)
    eid = add_expense(user_id_for("demo@spendly.com"))
    assert client.get(f"/expenses/{eid}/delete").status_code == 405
    assert expense_exists(eid)


def test_profile_renders_post_delete_form_per_row(client):
    login(client)
    eid = add_expense(user_id_for("demo@spendly.com"))
    html = client.get("/profile").data.decode()
    assert f'action="/expenses/{eid}/delete"' in html
    assert 'method="post"' in html.lower()
    assert "confirm(" in html
