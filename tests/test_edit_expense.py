from datetime import date

import pytest

import database.db as db
from app import _profile_data, app as flask_app

VALID = {
    "amount": "20.00",
    "category": "Transport",
    "date": "2025-04-10",
    "description": "Taxi",
}


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


def add_expense(user_id, amount, category, description, day):
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


def get_expense(expense_id):
    conn = db.get_db()
    try:
        return dict(
            conn.execute(
                "SELECT * FROM expenses WHERE id = ?", (expense_id,)
            ).fetchone()
        )
    finally:
        conn.close()


def post_edit(client, expense_id=1, **overrides):
    data = {**VALID, **overrides}
    return client.post(f"/expenses/{expense_id}/edit", data=data)


# ------------------------------------------------------------------ #
# Auth                                                                #
# ------------------------------------------------------------------ #


def test_logged_out_get_redirects_to_login(client):
    resp = client.get("/expenses/1/edit")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_logged_out_post_redirects_and_changes_nothing(client):
    before = get_expense(1)
    resp = post_edit(client)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    assert get_expense(1) == before


def test_session_with_missing_user_redirects_to_login(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 9999
    resp = client.get("/expenses/1/edit")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


# ------------------------------------------------------------------ #
# GET                                                                 #
# ------------------------------------------------------------------ #


def test_get_renders_prefilled_form(client):
    login(client)
    exp = get_expense(1)
    resp = client.get("/expenses/1/edit")
    page = resp.data.decode()
    assert resp.status_code == 200
    assert "coming in Step 8" not in page
    assert "Edit expense" in page
    assert f'value="{exp["amount"]}"' in page
    assert f'value="{exp["date"]}"' in page
    assert f'value="{exp["description"]}"' in page
    assert '<option value="Food" selected>' in page
    assert page.count("<option") == 7
    assert "pbkdf2" not in page and "scrypt" not in page


def test_profile_edit_links_reach_the_form(client):
    login(client)
    assert b'href="/expenses/1/edit"' in client.get("/profile").data
    assert client.get("/expenses/1/edit").status_code == 200


# ------------------------------------------------------------------ #
# POST: success                                                       #
# ------------------------------------------------------------------ #


def test_valid_edit_updates_row_and_redirects(client):
    login(client)
    resp = post_edit(client)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile?updated=1")

    row = get_expense(1)
    assert row["amount"] == 20.0
    assert row["category"] == "Transport"
    assert row["date"] == "2025-04-10"
    assert row["description"] == "Taxi"


def test_profile_shows_notice_and_new_totals_after_edit(client):
    login(client)
    # seeded expense 1 is Food 12.50; total of the seed is 370.64
    post_edit(client, amount="112.50")
    page = client.get("/profile?updated=1").data.decode()
    assert "Expense updated." in page
    assert "₹470.64" in page
    assert "Expense updated." not in client.get("/profile").data.decode()


def test_category_change_moves_spend_between_categories(client):
    login(client)
    with flask_app.app_context():
        before = {c["category"]: c["total"] for c in _profile_data(1)["categories"]}
    post_edit(client, amount="12.50", category="Health")
    with flask_app.app_context():
        after = {c["category"]: c["total"] for c in _profile_data(1)["categories"]}
    assert after["Food"] == pytest.approx(before["Food"] - 12.50)
    assert after["Health"] == pytest.approx(before["Health"] + 12.50)


def test_empty_description_is_stored_as_null(client):
    login(client)
    resp = post_edit(client, description="   ")
    assert resp.status_code == 302
    assert get_expense(1)["description"] is None
    assert "—" in client.get("/profile").data.decode()


def test_integer_and_one_decimal_amounts_are_accepted(client):
    login(client)
    assert post_edit(client, amount="15").status_code == 302
    assert get_expense(1)["amount"] == 15.0
    assert post_edit(client, amount="15.5").status_code == 302
    assert get_expense(1)["amount"] == 15.5


# ------------------------------------------------------------------ #
# POST: validation                                                    #
# ------------------------------------------------------------------ #


@pytest.mark.parametrize(
    "amount", ["0", "0.00", "-5", "abc", "nan", "inf", "1e3", "1.234", ""]
)
def test_invalid_amount_rejected(client, amount):
    login(client)
    before = get_expense(1)
    resp = post_edit(client, amount=amount, description="keep-me-visible")
    page = resp.data.decode()
    assert resp.status_code == 200
    assert "Please enter a valid amount greater than 0." in page
    assert "keep-me-visible" in page  # submitted values are re-populated
    assert get_expense(1) == before


@pytest.mark.parametrize("bad_date", ["", "not-a-date", "2025-13-01", "2025-02-30"])
def test_invalid_date_rejected(client, bad_date):
    login(client)
    before = get_expense(1)
    resp = post_edit(client, date=bad_date)
    assert resp.status_code == 200
    assert "Please enter a valid date." in resp.data.decode()
    assert get_expense(1) == before


@pytest.mark.parametrize("bad_category", ["", "Crypto", "food"])
def test_invalid_category_rejected(client, bad_category):
    login(client)
    before = get_expense(1)
    resp = post_edit(client, category=bad_category)
    assert resp.status_code == 200
    assert "Please choose a category." in resp.data.decode()
    assert get_expense(1) == before


def test_description_length_limit(client):
    login(client)
    before = get_expense(1)
    resp = post_edit(client, description="x" * 201)
    assert resp.status_code == 200
    assert "200 characters" in resp.data.decode()
    assert get_expense(1) == before

    assert post_edit(client, description="x" * 200).status_code == 302
    assert get_expense(1)["description"] == "x" * 200


def test_error_page_escapes_submitted_description(client):
    login(client)
    resp = post_edit(client, amount="bad", description="<script>alert(1)</script>")
    assert b"<script>alert(1)</script>" not in resp.data
    assert b"&lt;script&gt;alert(1)&lt;/script&gt;" in resp.data


# ------------------------------------------------------------------ #
# Ownership                                                           #
# ------------------------------------------------------------------ #


def test_nonexistent_expense_is_404(client):
    login(client)
    assert client.get("/expenses/99999/edit").status_code == 404
    assert post_edit(client, expense_id=99999).status_code == 404


def test_other_users_expense_is_404_and_unchanged(client):
    register_and_login(client)
    # expense 1 belongs to the demo user, not Asha
    before = get_expense(1)
    assert client.get("/expenses/1/edit").status_code == 404
    assert post_edit(client, expense_id=1, amount="999").status_code == 404
    assert get_expense(1) == before


def test_user_can_edit_their_own_but_not_demo_expense(client):
    register_and_login(client)
    uid = user_id_for("asha@example.com")
    own = add_expense(uid, 7.0, "Other", "mine", date.today().isoformat())
    assert post_edit(client, expense_id=own, amount="8").status_code == 302
    assert get_expense(own)["amount"] == 8.0


def test_extra_form_fields_cannot_change_owner_or_created_at(client):
    login(client)
    before = get_expense(1)
    resp = post_edit(client, user_id="2", id="999", created_at="2000-01-01 00:00:00")
    assert resp.status_code == 302
    after = get_expense(1)
    assert after["user_id"] == before["user_id"]
    assert after["id"] == before["id"]
    assert after["created_at"] == before["created_at"]
