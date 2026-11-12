import calendar
import re
from datetime import date, timedelta

import pytest

import database.db as db
from app import _months_ago, app as flask_app

TODAY = date.today()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()
    flask_app.config["TESTING"] = True
    c = flask_app.test_client()
    c.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    return c


def add(user_id, amount, category, description, day):
    conn = db.get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, description, date) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, description, day.isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def page(client, query=""):
    resp = client.get("/profile" + query)
    assert resp.status_code == 200
    return resp.data.decode()


def test_no_params_is_unfiltered(client):
    add(1, 11.11, "Food", "ancient-meal", date(2020, 1, 5))
    html = page(client)
    assert "ancient-meal" in html
    assert "₹381.75" in html  # 370.64 + 11.11
    assert 'class="filter-chip active">All Time' in html


def test_this_month_excludes_older_expenses(client):
    add(1, 11.11, "Food", "old-meal", TODAY.replace(day=1) - timedelta(days=1))
    last = TODAY.replace(day=calendar.monthrange(TODAY.year, TODAY.month)[1])
    html = page(client, f"?date_from={TODAY.replace(day=1)}&date_to={last}")
    assert "old-meal" not in html
    assert "Monthly bus pass" in html
    assert 'class="filter-chip active">This Month' in html


def test_rendered_preset_links_activate_themselves(client):
    html = page(client)
    for label in ("This Month", "Last 3 Months", "Last 6 Months"):
        link = re.search(rf'href="(/profile\?[^"]+)"[^>]*>{label}<', html).group(1)
        followed = page(client, link[len("/profile") :].replace("&amp;", "&"))
        assert f'class="filter-chip active">{label}' in followed


def test_last_3_months_boundaries_are_inclusive(client):
    edge = _months_ago(TODAY, 3)
    add(1, 1.00, "Other", "on-edge", edge)
    add(1, 2.00, "Other", "before-edge", edge - timedelta(days=1))
    html = page(client, f"?date_from={edge}&date_to={TODAY}")
    assert "on-edge" in html
    assert "before-edge" not in html
    assert 'class="filter-chip active">Last 3 Months' in html


def test_last_6_months_preset_active(client):
    start = _months_ago(TODAY, 6)
    html = page(client, f"?date_from={start}&date_to={TODAY}")
    assert 'class="filter-chip active">Last 6 Months' in html


def test_custom_range_filters_all_sections_inclusively(client):
    add(1, 10, "Food", "in-a", date(2023, 5, 1))
    add(1, 20, "Bills", "in-b", date(2023, 5, 31))
    add(1, 99, "Shopping", "out-before", date(2023, 4, 30))
    add(1, 99, "Shopping", "out-after", date(2023, 6, 1))
    html = page(client, "?date_from=2023-05-01&date_to=2023-05-31")
    assert "in-a" in html and "in-b" in html
    assert "out-before" not in html and "out-after" not in html
    assert "₹30.00" in html  # total spent
    assert "Bills" in html  # top category
    assert "filter-form active" in html
    assert 'value="2023-05-01"' in html and 'value="2023-05-31"' in html
    assert not any(
        f'class="filter-chip active">{label}' in html
        for label in ("This Month", "Last 3 Months", "Last 6 Months", "All Time")
    )


def test_reversed_range_flashes_error_and_is_unfiltered(client):
    html = page(client, "?date_from=2024-02-01&date_to=2024-01-01")
    assert "Start date must be before end date." in html
    assert "Monthly bus pass" in html
    assert 'class="filter-chip active">All Time' in html


@pytest.mark.parametrize(
    "query",
    [
        "?date_from=not-a-date",
        "?date_from=not-a-date&date_to=also-bad",
        "?date_to=2024-01-01",
        "?date_from=2024-01-01",
        "?date_from=&date_to=",
        "?date_from=2024-13-45&date_to=2024-14-01",
    ],
)
def test_malformed_or_partial_dates_fall_back_silently(client, query):
    html = page(client, query)
    assert "Start date must be before end date." not in html
    assert "Monthly bus pass" in html
    assert "₹370.64" in html


def test_empty_range_shows_zeroes_and_no_breakdown(client):
    html = page(client, "?date_from=1999-01-01&date_to=1999-01-31")
    assert "₹0.00" in html
    assert "No expenses in this range." in html
    assert "Spending by category" not in html
    assert "No expenses yet" not in html
    assert 'class="filter-bar"' in html  # filter stays usable


def test_other_users_expenses_never_leak_into_range(client):
    conn = db.get_db()
    try:
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES ('O', 'o@x.com', 'x')"
        )
        conn.commit()
    finally:
        conn.close()
    add(2, 777.77, "Food", "someone-elses", date(2023, 5, 10))
    html = page(client, "?date_from=2023-05-01&date_to=2023-05-31")
    assert "someone-elses" not in html
    assert "777.77" not in html


def test_rupee_symbol_survives_filtering(client):
    html = page(client, "?date_from=2023-05-01&date_to=2023-05-31")
    assert "₹" in html
    assert "£" not in html and "$" not in html
