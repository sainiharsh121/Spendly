import pytest

import database.db as db
from app import CATEGORIES, app as flask_app

VALID = {
    "amount": "50.0",
    "category": "Food",
    "date": "2026-03-20",
    "description": "Lunch",
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


@pytest.fixture
def logged_in(client):
    client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    return client


def expense_count(user_id=1):
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
    finally:
        conn.close()


def newest_expense():
    conn = db.get_db()
    try:
        return dict(conn.execute("SELECT * FROM expenses ORDER BY id DESC").fetchone())
    finally:
        conn.close()


def test_get_requires_login(client):
    resp = client.get("/expenses/add")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_post_requires_login_and_inserts_nothing(client):
    resp = client.post("/expenses/add", data=VALID)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    assert expense_count() == 8


def test_get_shows_form_with_all_categories(logged_in):
    resp = logged_in.get("/expenses/add")
    html = resp.data.decode()
    assert resp.status_code == 200
    assert "<form" in html and 'method="POST"' in html
    assert 'action="/expenses/add"' in html
    for category in CATEGORIES:
        assert f'<option value="{category}"' in html
    assert html.count("<option") == 7
    assert 'name="amount"' in html and 'name="date"' in html
    assert 'name="description"' in html and 'maxlength="200"' in html


def test_get_defaults_date_to_today(logged_in):
    from datetime import date

    assert (
        f'value="{date.today().isoformat()}"'
        in logged_in.get("/expenses/add").data.decode()
    )


def test_valid_post_inserts_and_redirects_to_profile(logged_in):
    resp = logged_in.post("/expenses/add", data=VALID)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")
    assert expense_count() == 9
    row = newest_expense()
    assert (row["user_id"], row["amount"], row["category"]) == (1, 50.0, "Food")
    assert (row["date"], row["description"]) == ("2026-03-20", "Lunch")


def test_new_expense_appears_on_profile(logged_in):
    logged_in.post("/expenses/add", data={**VALID, "description": "zq-new-expense"})
    assert b"zq-new-expense" in logged_in.get("/profile").data


def test_blank_description_stored_as_null(logged_in):
    resp = logged_in.post("/expenses/add", data={**VALID, "description": "   "})
    assert resp.status_code == 302
    assert newest_expense()["description"] is None


def test_missing_description_field_is_allowed(logged_in):
    data = {k: v for k, v in VALID.items() if k != "description"}
    assert logged_in.post("/expenses/add", data=data).status_code == 302
    assert newest_expense()["description"] is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"amount": ""},
        {"amount": "0"},
        {"amount": "-5"},
        {"amount": "abc"},
        {"category": "Gambling"},
        {"category": ""},
        {"date": "not-a-date"},
        {"date": ""},
        {"description": "x" * 201},
    ],
)
def test_invalid_input_rerenders_with_error_and_inserts_nothing(logged_in, overrides):
    resp = logged_in.post("/expenses/add", data={**VALID, **overrides})
    assert resp.status_code == 200
    assert b"auth-error" in resp.data
    assert expense_count() == 8


def test_error_rerender_keeps_submitted_values(logged_in):
    resp = logged_in.post(
        "/expenses/add",
        data={**VALID, "amount": "0", "category": "Health", "description": "keep-me"},
    )
    html = resp.data.decode()
    assert 'value="2026-03-20"' in html
    assert 'value="keep-me"' in html
    assert '<option value="Health" selected>' in html


def test_navbar_link_only_when_logged_in(client):
    assert b"Add Expense" not in client.get("/").data
    client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    assert b'href="/expenses/add">Add Expense' in client.get("/profile").data


def test_profile_has_add_expense_button(logged_in):
    assert (
        b'href="/expenses/add" class="btn-primary">Add expense'
        in logged_in.get("/profile").data
    )
