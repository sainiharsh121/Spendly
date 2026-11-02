import pytest
from werkzeug.security import check_password_hash

import database.db as db
from app import app as flask_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def user_count():
    conn = db.get_db()
    try:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    finally:
        conn.close()


def post(client, **overrides):
    data = {"name": "Asha Rao", "email": "asha@example.com", "password": "longenough1"}
    data.update(overrides)
    return client.post("/register", data=data)


def test_get_register_renders_form(client):
    resp = client.get("/register")
    assert resp.status_code == 200
    assert b'name="password"' in resp.data


def test_valid_registration_creates_hashed_user_and_redirects(client):
    before = user_count()
    resp = post(client)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login?registered=1")
    assert user_count() == before + 1

    conn = db.get_db()
    try:
        row = conn.execute(
            "SELECT name, password_hash FROM users WHERE email = ?", ("asha@example.com",)
        ).fetchone()
    finally:
        conn.close()
    assert row["name"] == "Asha Rao"
    assert row["password_hash"] != "longenough1"
    assert check_password_hash(row["password_hash"], "longenough1")


@pytest.mark.parametrize("email", ["demo@spendly.com", "DEMO@spendly.com"])
def test_duplicate_email_rejected(client, email):
    before = user_count()
    resp = post(client, email=email)
    assert resp.status_code == 200
    assert b"already exists" in resp.data
    assert user_count() == before


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"name": "   "}, b"enter your name"),
        ({"email": "foo@"}, b"valid email"),
        ({"email": "nope"}, b"valid email"),
        ({"password": "short12"}, b"at least 8 characters"),
    ],
)
def test_invalid_input_rejected(client, overrides, message):
    before = user_count()
    resp = post(client, **overrides)
    assert resp.status_code == 200
    assert message in resp.data
    assert user_count() == before


def test_error_repopulates_name_and_email_but_not_password(client):
    resp = post(client, password="zq7x")
    assert b'value="Asha Rao"' in resp.data
    assert b'value="asha@example.com"' in resp.data
    assert b"zq7x" not in resp.data


def test_login_shows_success_notice_only_when_registered(client):
    assert b"Account created" in client.get("/login?registered=1").data
    assert b"Account created" not in client.get("/login").data
