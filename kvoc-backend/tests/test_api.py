"""Smoke tests for the Kvoč API. Run them with `pytest` from the
kvoc-backend directory - they're meant to actually be run, not just read.

Uses its own sqlite file (test_kvoc.db) so it never touches whatever
database `python run.py` is using for real browsing.
"""
import datetime as dt
import os

os.environ["KVOC_DATABASE_URL"] = "sqlite:///./test_kvoc.db"
if os.path.exists("test_kvoc.db"):
    os.remove("test_kvoc.db")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_farms_are_seeded(client):
    r = client.get("/farms")
    assert r.status_code == 200
    farms = r.json()
    assert {f["key"] for f in farms} == {"lipa", "dvur", "polana"}


def test_unknown_farm_key_rejected(client):
    r = client.post("/hens", json={"owner_name": "X", "farm_key": "does-not-exist"})
    assert r.status_code == 404


def test_adopt_hen_runs_day_one(client):
    r = client.post("/hens", json={
        "owner_name": "Test User",
        "hen_name": "Testovačka",
        "farm_key": "lipa",
        "daily_amount": 20,
        "address": "Testovací 1, Praha",
    })
    assert r.status_code == 201
    hen = r.json()
    assert hen["hen_name"] == "Testovačka"
    assert hen["daily_amount"] == 20

    r = client.get(f"/hens/{hen['id']}/feed-log")
    assert r.status_code == 200
    log = r.json()
    if dt.date.today().weekday() < 5:
        assert len(log) >= 1
        assert "Testovačka" in log[0]["message"]
    else:
        assert log == []  # adopted on a weekend: nothing to log until Monday


def test_full_week_produces_a_delivery(client):
    r = client.post("/hens", json={"owner_name": "Weekly", "farm_key": "dvur", "daily_amount": 20})
    hen_id = r.json()["id"]

    # offsets 1..6 are guaranteed to reach the very next Friday regardless of
    # which weekday "today" happens to be when this test runs, and never far
    # enough to reach a *second* Friday
    for offset in range(1, 7):
        rr = client.post(f"/admin/run-tick?days_offset={offset}")
        assert rr.status_code == 200

    r = client.get(f"/hens/{hen_id}/deliveries")
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

    r = client.get(f"/hens/{hen_id}/wallet")
    assert r.status_code == 200
    assert r.json()["daily_amount"] == 20


def test_settings_update(client):
    r = client.post("/hens", json={"owner_name": "Settings", "farm_key": "polana"})
    hen_id = r.json()["id"]

    r = client.patch(f"/hens/{hen_id}", json={"daily_amount": 30, "paused": True})
    assert r.status_code == 200
    updated = r.json()
    assert updated["daily_amount"] == 30
    assert updated["paused"] is True


def test_pause_freezes_the_streak_instead_of_breaking_it(client):
    r = client.post("/hens", json={"owner_name": "Pauser", "farm_key": "lipa"})
    hen_id = r.json()["id"]

    r = client.get(f"/hens/{hen_id}/wallet")
    streak_day0 = r.json()["streak"]

    client.patch(f"/hens/{hen_id}", json={"paused": True})
    client.post("/admin/run-tick?days_offset=1")
    client.post("/admin/run-tick?days_offset=2")
    client.patch(f"/hens/{hen_id}", json={"paused": False})
    client.post("/admin/run-tick?days_offset=3")

    r = client.get(f"/hens/{hen_id}/wallet")
    streak_after = r.json()["streak"]

    # a pause must never make the streak worse than where it started
    assert streak_after >= streak_day0
