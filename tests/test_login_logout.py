import pytest

import database.db as db
from app import app as flask_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def login(client, email="demo@spendly.com", password="demo123"):
    return client.post("/login", data={"email": email, "password": password})


def test_demo_login_redirects_to_profile_and_sets_session(client):
    resp = login(client)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")
    with client.session_transaction() as sess:
        assert sess["user_id"] == 1


def test_registered_user_can_log_in_with_any_email_case(client):
    client.post(
        "/register",
        data={
            "name": "Asha Rao",
            "email": "asha@example.com",
            "password": "longenough1",
        },
    )
    resp = login(client, email="  ASHA@Example.com ", password="longenough1")
    assert resp.status_code == 302
    with client.session_transaction() as sess:
        assert "user_id" in sess


@pytest.mark.parametrize(
    "email, password",
    [("demo@spendly.com", "wrong-password"), ("nobody@example.com", "demo123")],
)
def test_bad_credentials_give_identical_generic_error(client, email, password):
    resp = login(client, email=email, password=password)
    assert resp.status_code == 200
    assert b"Invalid email or password." in resp.data
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_failed_login_keeps_email_but_not_password(client):
    resp = login(client, password="zq7x-wrong")
    assert b'value="demo@spendly.com"' in resp.data
    assert b"zq7x-wrong" not in resp.data


@pytest.mark.parametrize("email, password", [("", "demo123"), ("demo@spendly.com", "")])
def test_empty_fields_rejected(client, email, password):
    resp = login(client, email=email, password=password)
    assert resp.status_code == 200
    assert b"Please enter your email and password." in resp.data
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_navbar_reflects_login_state(client):
    assert b"Get started" in client.get("/").data
    login(client)
    page = client.get("/").data
    assert b"Demo User" in page
    assert b"Sign out" in page
    assert b"Get started" not in page


def test_logout_clears_session_and_redirects_home(client):
    login(client)
    resp = client.get("/logout")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")
    with client.session_transaction() as sess:
        assert "user_id" not in sess
    assert b"Get started" in client.get("/").data


def test_logout_when_logged_out_is_harmless(client):
    assert client.get("/logout").status_code == 302


@pytest.mark.parametrize("path", ["/login", "/register"])
def test_logged_in_user_is_redirected_away_from_auth_pages(client, path):
    login(client)
    resp = client.get(path)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")


def test_session_with_missing_user_is_treated_as_logged_out(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 9999
    page = client.get("/login")
    assert page.status_code == 200
    assert b"Get started" in page.data
    with client.session_transaction() as sess:
        assert "user_id" not in sess
