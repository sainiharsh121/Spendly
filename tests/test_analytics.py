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


@pytest.fixture
def logged_in(client):
    client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    return client


def test_logged_out_visit_redirects_to_login(client):
    resp = client.get("/analytics")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_logged_in_visit_renders_page(logged_in):
    resp = logged_in.get("/analytics")
    assert resp.status_code == 200
    assert b"Coming Soon" in resp.data
    assert b"Advanced Analytics" in resp.data


def test_stale_session_is_redirected(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 9999
    assert client.get("/analytics").status_code == 302


def test_nav_link_hidden_when_logged_out(client):
    for path in ("/", "/login", "/register"):
        assert b"Analytics" not in client.get(path).data


def test_nav_link_visible_when_logged_in(logged_in):
    for path in ("/profile", "/expenses/add"):
        assert b'href="/analytics"' in logged_in.get(path).data


def test_nav_link_active_only_on_analytics_page(logged_in):
    on_page = logged_in.get("/analytics").data.decode()
    assert 'class="active" aria-current="page">Analytics' in on_page
    elsewhere = logged_in.get("/profile").data.decode()
    assert 'class="">Analytics' in elsewhere
    assert "aria-current" not in elsewhere
