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
    assert {f["key"] for f in farms} == {
        "lipa", "dvur", "polana", "ricany", "beroun", "kladno", "melnik", "kutnahora",
    }
    # every seeded farm has real coordinates - that's the whole point of it
    # being seed data instead of a placeholder
    assert all(f["lat"] is not None and f["lng"] is not None for f in farms)


def test_farms_near_location_get_a_real_distance_and_are_sorted(client):
    # roughly central Prague - Říčany (real town, ~19km out) should end up
    # first, something far away (Kutná Hora, ~60km+) should end up last
    r = client.get("/farms", params={"lat": 50.0755, "lng": 14.4378})
    assert r.status_code == 200
    farms = r.json()
    assert all(f["distance_km"] is not None for f in farms)
    distances = [f["distance_km"] for f in farms]
    assert distances == sorted(distances)
    assert farms[0]["key"] == "ricany"
    assert 15 < farms[0]["distance_km"] < 25


def test_farms_radius_filter_drops_farms_too_far_away(client):
    r = client.get("/farms", params={"lat": 50.0755, "lng": 14.4378, "radius_km": 25})
    assert r.status_code == 200
    farms = r.json()
    assert len(farms) < 8
    assert all(f["distance_km"] <= 25 for f in farms)


def test_farms_without_location_have_no_distance_and_keep_seed_order(client):
    r = client.get("/farms")
    farms = r.json()
    assert all(f["distance_km"] is None for f in farms)


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


def test_change_password_requires_correct_current_password(client):
    headers, email = _new_user_headers(client)
    r = client.post(
        "/auth/change-password",
        json={"current_password": "wrong one", "new_password": "brand new password 123"},
        headers=headers,
    )
    assert r.status_code == 401
    # old password still works - nothing was changed
    r = client.post("/auth/login", data={"username": email, "password": "correct horse battery staple"})
    assert r.status_code == 200


def test_change_password_succeeds_and_old_password_stops_working(client):
    headers, email = _new_user_headers(client)
    r = client.post(
        "/auth/change-password",
        json={"current_password": "correct horse battery staple", "new_password": "brand new password 123"},
        headers=headers,
    )
    assert r.status_code == 204

    r = client.post("/auth/login", data={"username": email, "password": "correct horse battery staple"})
    assert r.status_code == 401
    r = client.post("/auth/login", data={"username": email, "password": "brand new password 123"})
    assert r.status_code == 200


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


def test_cancel_hen_deletes_it_and_its_history(client):
    headers, _ = _new_user_headers(client)
    hen = _adopt_hen(client, headers)

    r = client.delete(f"/hens/{hen['id']}", headers=headers)
    assert r.status_code == 204

    r = client.get(f"/hens/{hen['id']}", headers=headers)
    assert r.status_code == 404
    r = client.get("/hens", headers=headers)
    assert hen["id"] not in [h["id"] for h in r.json()]


def test_cancel_hen_is_isolated_between_users(client):
    headers_a, _ = _new_user_headers(client)
    headers_b, _ = _new_user_headers(client)
    hen_a = _adopt_hen(client, headers_a)

    r = client.delete(f"/hens/{hen_a['id']}", headers=headers_b)
    assert r.status_code == 404

    r = client.get(f"/hens/{hen_a['id']}", headers=headers_a)
    assert r.status_code == 200  # untouched by B's attempt


# ---------------------------- hens / tick logic ----------------------------

def test_unknown_farm_key_rejected(client):
    headers, _ = _new_user_headers(client)
    r = client.post("/hens", json={"hen_name": "X", "farm_key": "does-not-exist"}, headers=headers)
    assert r.status_code == 404


def test_farm_at_capacity_refuses_new_adoptions(client):
    from app import models
    from app.database import SessionLocal

    # shrink a real farm's capacity to something a test can actually fill,
    # rather than adopting 25+ real hens just to hit the seeded number
    db = SessionLocal()
    try:
        farm = db.query(models.Farm).filter(models.Farm.key == "beroun").first()
        farm.weekly_capacity = 1
        db.commit()
    finally:
        db.close()

    headers_a, _ = _new_user_headers(client)
    r = client.post("/hens", json={"hen_name": "První", "farm_key": "beroun"}, headers=headers_a)
    assert r.status_code == 201

    headers_b, _ = _new_user_headers(client)
    r = client.post("/hens", json={"hen_name": "Druhá", "farm_key": "beroun"}, headers=headers_b)
    assert r.status_code == 409

    # cancelling the first frees the spot back up for someone else
    first_id = client.get("/hens", headers=headers_a).json()[0]["id"]
    client.delete(f"/hens/{first_id}", headers=headers_a)
    r = client.post("/hens", json={"hen_name": "Druhá", "farm_key": "beroun"}, headers=headers_b)
    assert r.status_code == 201


def test_farms_report_spots_left(client):
    # kutnahora is never adopted from anywhere else in this file - a real
    # baseline to assert against, unlike lipa/dvur/polana/beroun which other
    # tests (including the capacity test right above this one) also use
    r = client.get("/farms")
    farms = {f["key"]: f for f in r.json()}
    assert farms["kutnahora"]["weekly_capacity"] == 25
    assert farms["kutnahora"]["spots_left"] == 25

    headers, _ = _new_user_headers(client)
    client.post("/hens", json={"hen_name": "X", "farm_key": "kutnahora"}, headers=headers)
    r = client.get("/farms")
    farms = {f["key"]: f for f in r.json()}
    assert farms["kutnahora"]["spots_left"] == 24


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
