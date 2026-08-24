"""Smoke tests for the Kvoč API. Run them with `pytest` from the
kvoc-backend directory - they're meant to actually be run, not just read.

Uses its own sqlite file (test_kvoc.db) so it never touches whatever
database `python run.py` is using for real browsing, and forces the mock
payment provider so these tests never need real Stripe credentials.
"""
import datetime as dt
import os

os.environ["KVOC_DATABASE_URL"] = "sqlite:///./test_kvoc.db"
os.environ["KVOC_PAYMENT_PROVIDER"] = "mock"
if os.path.exists("test_kvoc.db"):
    os.remove("test_kvoc.db")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

_counter = {"n": 0}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _new_user_headers(client, email=None):
    """Register a fresh user and return Authorization headers for them.
    Each call uses a unique email so tests don't collide with each other.
    """
    _counter["n"] += 1
    email = email or f"test{_counter['n']}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "correct horse battery staple"})
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, email


def _adopt_hen(client, headers, daily_amount=20, farm_key="lipa"):
    r = client.post("/hens", json={"hen_name": "Testovačka", "farm_key": farm_key, "daily_amount": daily_amount}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_device_token_registers_and_clears(client):
    from app import models
    from app.database import SessionLocal

    headers, email = _new_user_headers(client)

    r = client.post("/auth/device-token", json={"fcm_token": "fake-fcm-token-abc"}, headers=headers)
    assert r.status_code == 204

    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == email).first()
        assert user.fcm_token == "fake-fcm-token-abc"
    finally:
        db.close()

    # empty string clears it - the mobile app does this on logout, so a
    # signed-out device doesn't keep receiving someone else's notifications
    r = client.post("/auth/device-token", json={"fcm_token": ""}, headers=headers)
    assert r.status_code == 204
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == email).first()
        assert user.fcm_token is None
    finally:
        db.close()


def test_device_token_requires_auth(client):
    r = client.post("/auth/device-token", json={"fcm_token": "x"})
    assert r.status_code == 401


def test_farms_are_seeded(client):
    r = client.get("/farms")
    assert r.status_code == 200
    farms = r.json()
    assert {f["key"] for f in farms} == {"lipa", "dvur", "polana"}


# ---------------------------- auth ----------------------------

def test_register_login_and_me(client):
    headers, email = _new_user_headers(client)

    r = client.get("/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["email"] == email
    assert r.json()["has_saved_payment_method"] is False

    r = client.post("/auth/login", data={"username": email, "password": "correct horse battery staple"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_login_wrong_password_rejected(client):
    _, email = _new_user_headers(client)
    r = client.post("/auth/login", data={"username": email, "password": "not the right password"})
    assert r.status_code == 401


def test_duplicate_registration_rejected(client):
    _, email = _new_user_headers(client)
    r = client.post("/auth/register", json={"email": email, "password": "another password entirely"})
    assert r.status_code == 409


def test_hens_endpoint_requires_auth(client):
    r = client.post("/hens", json={"hen_name": "Bez tokenu", "farm_key": "lipa"})
    assert r.status_code == 401


def test_hen_ownership_is_isolated_between_users(client):
    headers_a, _ = _new_user_headers(client)
    headers_b, _ = _new_user_headers(client)
    hen_a = _adopt_hen(client, headers_a)

    # user B can't see or modify user A's hen - 404, not 403, so B can't
    # even confirm the id exists
    r = client.get(f"/hens/{hen_a['id']}", headers=headers_b)
    assert r.status_code == 404
    r = client.patch(f"/hens/{hen_a['id']}", json={"paused": True}, headers=headers_b)
    assert r.status_code == 404

    r = client.get(f"/hens/{hen_a['id']}", headers=headers_a)
    assert r.status_code == 200


# ---------------------------- hens / tick logic ----------------------------

def test_unknown_farm_key_rejected(client):
    headers, _ = _new_user_headers(client)
    r = client.post("/hens", json={"hen_name": "X", "farm_key": "does-not-exist"}, headers=headers)
    assert r.status_code == 404


def test_adopt_hen_runs_day_one(client):
    headers, _ = _new_user_headers(client)
    hen = _adopt_hen(client, headers, daily_amount=20)
    assert hen["hen_name"] == "Testovačka"
    assert hen["daily_amount"] == 20

    r = client.get(f"/hens/{hen['id']}/feed-log", headers=headers)
    assert r.status_code == 200
    log = r.json()
    if dt.date.today().weekday() < 5:
        assert len(log) >= 1
        assert "Testovačka" in log[0]["message"]
    else:
        assert log == []  # adopted on a weekend: nothing to log until Monday


def test_full_week_produces_a_delivery(client):
    headers, _ = _new_user_headers(client)
    hen = _adopt_hen(client, headers, daily_amount=20, farm_key="dvur")
    hen_id = hen["id"]

    # offsets 1..6 are guaranteed to reach the very next Friday regardless of
    # which weekday "today" happens to be when this test runs, and never far
    # enough to reach a *second* Friday
    for offset in range(1, 7):
        rr = client.post(f"/admin/run-tick?days_offset={offset}")
        assert rr.status_code == 200

    r = client.get(f"/hens/{hen_id}/deliveries", headers=headers)
    assert r.status_code == 200
    deliveries = r.json()
    assert len(deliveries) == 1

    d = deliveries[0]
    week_start = dt.date.fromisoformat(d["week_start"])
    friday = dt.date.fromisoformat(d["date"])
    # every weekday between that Monday and the triggering Friday must be
    # counted, including the Friday itself - exactly the case a same-session
    # autoflush bug would silently undercount
    expected_weekdays = sum(
        1 for n in range((friday - week_start).days + 1)
        if (week_start + dt.timedelta(days=n)).weekday() < 5
    )
    assert d["amount"] == expected_weekdays * 20
    assert d["eggs"] == max(1, round(d["amount"] / 12.5))
    assert d["status"] in ("transit", "delivered")

    r = client.get(f"/hens/{hen_id}/wallet", headers=headers)
    assert r.status_code == 200
    assert r.json()["daily_amount"] == 20


def test_wallet_reflects_demo_advanced_days_not_just_real_today(client):
    """Regression test: a live click-through in the browser found that
    /wallet computed week_balance/streak from the real wall-clock date even
    after POST /admin/run-tick had advanced this hen's data into the
    future - so the number silently stayed frozen while /feed-log clearly
    showed new entries. See effective_today_for_hen() in app/tick.py.
    """
    headers, _ = _new_user_headers(client)
    hen = _adopt_hen(client, headers, daily_amount=20)
    hen_id = hen['id']

    r = client.get(f"/hens/{hen_id}/wallet", headers=headers)
    before = r.json()

    client.post("/admin/run-tick?days_offset=1")
    r = client.get(f"/hens/{hen_id}/feed-log", headers=headers)
    log_after = r.json()

    r = client.get(f"/hens/{hen_id}/wallet", headers=headers)
    after = r.json()

    # only meaningful if the offset day actually produced a new weekday entry
    # (won't if today+1 lands on a weekend for this test run)
    if len(log_after) > 0 and len([e for e in log_after if not e['is_bonus']]) >= 2:
        assert after['week_balance'] > before['week_balance']
        assert after['streak'] > before['streak']


def test_settings_update(client):
    headers, _ = _new_user_headers(client)
    hen = _adopt_hen(client, headers, farm_key="polana")

    r = client.patch(f"/hens/{hen['id']}", json={"daily_amount": 30, "paused": True}, headers=headers)
    assert r.status_code == 200
    updated = r.json()
    assert updated["daily_amount"] == 30
    assert updated["paused"] is True


def test_pause_freezes_the_streak_instead_of_breaking_it(client):
    headers, _ = _new_user_headers(client)
    hen = _adopt_hen(client, headers)
    hen_id = hen["id"]

    r = client.get(f"/hens/{hen_id}/wallet", headers=headers)
    streak_day0 = r.json()["streak"]

    client.patch(f"/hens/{hen_id}", json={"paused": True}, headers=headers)
    client.post("/admin/run-tick?days_offset=1")
    client.post("/admin/run-tick?days_offset=2")
    client.patch(f"/hens/{hen_id}", json={"paused": False}, headers=headers)
    client.post("/admin/run-tick?days_offset=3")

    r = client.get(f"/hens/{hen_id}/wallet", headers=headers)
    streak_after = r.json()["streak"]

    # a pause must never make the streak worse than where it started
    assert streak_after >= streak_day0


# ---------------------------- wallet (mock payment provider) ----------------------------

def test_wallet_topup_flow_with_mock_provider(client):
    headers, _ = _new_user_headers(client)
    hen = _adopt_hen(client, headers)
    hen_id = hen["id"]

    r = client.post(f"/hens/{hen_id}/wallet/setup-intent", headers=headers)
    assert r.status_code == 200
    assert r.json()["client_secret"]

    r = client.get("/auth/me", headers=headers)
    assert r.json()["has_saved_payment_method"] is True

    r = client.post(f"/hens/{hen_id}/wallet/topup", json={"amount_czk": 100}, headers=headers)
    assert r.status_code == 201
    topup = r.json()
    assert topup["amount_czk"] == 100
    assert topup["status"] == "succeeded"
    assert topup["provider"] == "mock"

    r = client.get(f"/hens/{hen_id}/wallet/topups", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_topup_without_saved_card_is_rejected(client):
    headers, _ = _new_user_headers(client)
    hen = _adopt_hen(client, headers)
    r = client.post(f"/hens/{hen['id']}/wallet/topup", json={"amount_czk": 100}, headers=headers)
    assert r.status_code == 400
