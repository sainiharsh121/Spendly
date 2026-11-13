import re
from datetime import date

import pytest

import database.db as db
from app import _profile_data, app as flask_app


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


def add_expense(user_id, amount, category, description, day):
    conn = db.get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, description, date) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, description, day),
        )
        conn.commit()
    finally:
        conn.close()


def user_id_for(email):
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()["id"]
    finally:
        conn.close()


def test_logged_out_redirects_to_login(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_session_with_missing_user_redirects_to_login(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 9999
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_demo_profile_header_and_no_stub(client):
    login(client)
    resp = client.get("/profile")
    assert resp.status_code == 200
    assert b"Demo User" in resp.data
    assert b"demo@spendly.com" in resp.data
    assert b"Member since" in resp.data
    assert b"coming in Step 4" not in resp.data
    assert b"pbkdf2" not in resp.data and b"scrypt" not in resp.data


def test_demo_stats(client):
    login(client)
    page = client.get("/profile").data.decode()
    assert "₹370.64" in page  # total of the 8 seeded expenses
    assert re.search(r"Expenses</div>\s*<div class=\"stat-value\">8<", page)
    assert re.search(r"Top category</div>\s*<div class=\"stat-value\">Bills<", page)


def test_category_breakdown_sorted_and_sums_to_100(client):
    with flask_app.app_context():
        data = _profile_data(1)
    cats = data["categories"]
    assert cats[0]["category"] == "Bills"
    assert cats[0]["pct"] == 32.4
    assert [c["total"] for c in cats] == sorted(
        (c["total"] for c in cats), reverse=True
    )
    assert sum(c["pct"] for c in cats) == pytest.approx(100, abs=0.5)


def test_month_total_only_counts_current_month(client):
    today = date.today()
    add_expense(1, 1000.00, "Other", "Old one", f"{today.year - 1}-01-15")
    with flask_app.app_context():
        data = _profile_data(1)
    assert data["month_total"] == pytest.approx(370.64)
    assert data["total"] == pytest.approx(1370.64)


def test_recent_expenses_limited_to_10_newest_first(client):
    register_and_login(client)
    uid = user_id_for("asha@example.com")
    for i in range(1, 13):
        add_expense(uid, float(i), "Food", f"item-{i:02d}", f"2025-01-{i:02d}")
    page = client.get("/profile").data.decode()
    assert page.count('class="date-cell"') == 10
    assert "item-12" in page and "item-03" in page
    assert "item-02" not in page and "item-01" not in page
    assert page.index("item-12") < page.index("item-03")


def test_new_user_sees_empty_state(client):
    register_and_login(client)
    resp = client.get("/profile")
    assert resp.status_code == 200
    page = resp.data.decode()
    assert "₹0.00" in page
    assert "Add your first expense" in page
    assert 'class="expense-table"' not in page


def test_users_only_see_their_own_expenses(client):
    register_and_login(client)
    uid = user_id_for("asha@example.com")
    add_expense(uid, 7.77, "Other", "zq-secret-xyz", "2025-02-02")

    assert b"zq-secret-xyz" in client.get("/profile").data
    client.get("/logout")

    login(client)
    assert b"zq-secret-xyz" not in client.get("/profile").data


def test_description_is_escaped(client):
    login(client)
    add_expense(1, 5.0, "Other", "<script>alert(1)</script>", "2025-03-03")
    page = client.get("/profile").data
    assert b"<script>alert(1)</script>" not in page
    assert b"&lt;script&gt;alert(1)&lt;/script&gt;" in page


def test_navbar_name_links_to_profile(client):
    login(client)
    page = client.get("/profile").data
    assert b'href="/profile" class="nav-user"' in page


def test_expense_links_point_at_placeholder_routes(client):
    login(client)
    page = client.get("/profile").data
    assert b'href="/expenses/add"' in page
    assert re.search(rb'href="/expenses/\d+/edit"', page)
    assert re.search(rb'<form method="post" action="/expenses/\d+/delete"', page)
