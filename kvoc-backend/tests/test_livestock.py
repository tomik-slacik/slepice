"""Tests for the other-livestock system (docs/LIVESTOCK.md): goat/sheep/cow
Animal subscriptions, and the pooled MeatShare/ShareContribution flow.

Uses the same running app/database/fixtures as tests/test_api.py (same
test_kvoc.db, same client fixture) - run with `pytest` from this directory,
same as always.
"""
import datetime as dt
import os

os.environ.setdefault("KVOC_DATABASE_URL", "sqlite:///./test_kvoc.db")
os.environ.setdefault("KVOC_ADMIN_TOKEN", "test-admin-token")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

ADMIN_HEADERS = {"X-Admin-Token": "test-admin-token"}
_counter = {"n": 0}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _new_user_headers(client, email=None):
    _counter["n"] += 1
    email = email or f"livestock{_counter['n']}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "correct horse battery staple"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, email


def _give_saved_card(client, headers):
    """A saved-card prerequisite is shared across hens/animals/meat-shares
    (same Stripe customer per user, not per subscription) - any hen_id
    works to reach it, see routers/wallet.py."""
    r = client.post("/hens", json={"hen_name": "KartaSetup", "farm_key": "lipa"}, headers=headers)
    hen_id = r.json()["id"]
    r = client.post(f"/hens/{hen_id}/wallet/setup-intent", headers=headers)
    assert r.status_code == 200, r.text


# ---------------------------- Animal (goat/sheep/cow) ----------------------------

def test_available_products_lists_the_registry(client):
    r = client.get("/animals/available-products")
    assert r.status_code == 200
    combos = {(p["species"], p["product"]) for p in r.json()}
    # sheep deliberately has no ongoing product - meat-share only, see
    # config.ANIMAL_PRODUCTS's comment and the meat-share tests below
    assert combos == {("goat", "milk"), ("cow", "milk")}


def test_adopt_animal_rejects_a_farm_that_doesnt_offer_it(client):
    headers, _ = _new_user_headers(client)
    # "lipa" only offers cow/milk in the seed data, not goat/milk
    r = client.post("/animals", json={"species": "goat", "product": "milk", "farm_key": "lipa"}, headers=headers)
    assert r.status_code == 404


def test_adopt_animal_rejects_an_invalid_species_product_combo(client):
    headers, _ = _new_user_headers(client)
    r = client.post("/animals", json={"species": "goat", "product": "meat", "farm_key": "dvur"}, headers=headers)
    assert r.status_code == 400


def test_adopt_animal_succeeds_and_runs_day_one(client):
    headers, _ = _new_user_headers(client)
    r = client.post(
        "/animals",
        json={"species": "goat", "product": "milk", "name": "Koza Rozárka", "farm_key": "dvur", "daily_amount": 20},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    animal = r.json()
    assert animal["species"] == "goat"
    assert animal["name"] == "Koza Rozárka"

    r = client.get(f"/animals/{animal['id']}/product-log", headers=headers)
    assert r.status_code == 200
    if dt.date.today().weekday() < 5:
        assert len(r.json()) >= 1  # day-one tick already ran, same as adopt_hen


def test_animal_capacity_is_enforced_and_freed_by_cancellation(client):
    from app import models
    from app.database import SessionLocal

    # a dedicated, test-only offering on "polana" (which has no animal
    # offering of its own since sheep/wool was removed - see config.py) -
    # deliberately NOT touching dvur's or lipa's real seeded capacity,
    # which test_animal_ownership_is_isolated_between_users and
    # test_admin_run_tick_advances_animals_too also adopt against
    db = SessionLocal()
    try:
        polana = db.query(models.Farm).filter(models.Farm.key == "polana").first()
        db.add(models.FarmAnimalOffering(farm_id=polana.id, species="goat", product="milk", weekly_capacity=1))
        db.commit()
    finally:
        db.close()

    headers_a, _ = _new_user_headers(client)
    r = client.post("/animals", json={"species": "goat", "product": "milk", "farm_key": "polana"}, headers=headers_a)
    assert r.status_code == 201

    headers_b, _ = _new_user_headers(client)
    r = client.post("/animals", json={"species": "goat", "product": "milk", "farm_key": "polana"}, headers=headers_b)
    assert r.status_code == 409

    first_id = client.get("/animals", headers=headers_a).json()[0]["id"]
    r = client.delete(f"/animals/{first_id}", headers=headers_a)
    assert r.status_code == 204

    r = client.post("/animals", json={"species": "goat", "product": "milk", "farm_key": "polana"}, headers=headers_b)
    assert r.status_code == 201


def test_animal_ownership_is_isolated_between_users(client):
    headers_a, _ = _new_user_headers(client)
    headers_b, _ = _new_user_headers(client)
    r = client.post("/animals", json={"species": "cow", "product": "milk", "farm_key": "lipa"}, headers=headers_a)
    animal_id = r.json()["id"]

    r = client.get(f"/animals/{animal_id}", headers=headers_b)
    assert r.status_code == 404
    r = client.delete(f"/animals/{animal_id}", headers=headers_b)
    assert r.status_code == 404
    r = client.get(f"/animals/{animal_id}", headers=headers_a)
    assert r.status_code == 200


def test_farms_endpoint_shows_which_animal_products_each_farm_offers(client):
    r = client.get("/farms")
    farms = {f["key"]: f for f in r.json()}
    dvur_products = {(o["species"], o["product"]) for o in farms["dvur"]["animal_offerings"]}
    assert ("goat", "milk") in dvur_products
    assert farms["ricany"]["animal_offerings"] == []  # hens/eggs-only farm


def test_admin_run_tick_advances_animals_too(client):
    headers, _ = _new_user_headers(client)
    r = client.post("/animals", json={"species": "cow", "product": "milk", "name": "X", "farm_key": "lipa"}, headers=headers)
    animal_id = r.json()["id"]

    r = client.post("/admin/run-tick?days_offset=1", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    assert r.json()["ran_for_animals"] >= 1

    r = client.get(f"/animals/{animal_id}/wallet", headers=headers)
    assert r.status_code == 200
    assert r.json()["daily_amount"] == config_default_amount()


def config_default_amount():
    from app import config
    return config.DEFAULT_DAILY_AMOUNT


# ---------------------------- MeatShare ----------------------------

def test_meat_shares_list_includes_the_seeded_demo_share(client):
    headers, _ = _new_user_headers(client)
    r = client.get("/meat-shares", headers=headers)
    assert r.status_code == 200
    labels = {s["label"] for s in r.json()}
    assert "Kráva Bětka" in labels


def test_contribute_without_saved_card_is_rejected(client):
    headers, _ = _new_user_headers(client)
    shares = client.get("/meat-shares", headers=headers).json()
    share_id = [s for s in shares if s["label"] == "Kráva Bětka"][0]["id"]
    r = client.post(f"/meat-shares/{share_id}/contribute", json={"shares": 1}, headers=headers)
    assert r.status_code == 400


def test_meat_share_full_contribute_and_proportional_payout(client):
    # a fresh share for this test, so it's never contaminated by whatever
    # the seeded "Kráva Bětka" already has from other tests in this module
    r = client.post(
        "/admin/meat-shares",
        json={"farm_key": "dvur", "species": "cow", "label": "Testovací Kráva", "total_shares": 4,
              "price_per_share_czk": 500, "includes_hide": True},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 201, r.text
    share_id = r.json()["id"]
    assert r.json()["shares_taken"] == 0

    headers_a, _ = _new_user_headers(client)
    _give_saved_card(client, headers_a)
    headers_b, _ = _new_user_headers(client)
    _give_saved_card(client, headers_b)

    r = client.post(f"/meat-shares/{share_id}/contribute", json={"shares": 1}, headers=headers_a)
    assert r.status_code == 200, r.text
    assert r.json()["shares_taken"] == 1
    assert r.json()["my_shares"] == 1
    assert r.json()["status"] == "open"

    # buying more than what's left must fail cleanly, and not partially apply
    r = client.post(f"/meat-shares/{share_id}/contribute", json={"shares": 10}, headers=headers_b)
    assert r.status_code == 409
    assert client.get(f"/meat-shares/{share_id}", headers=headers_b).json()["shares_taken"] == 1

    # B takes the remaining 3 of 4 -> share flips to "full"
    r = client.post(f"/meat-shares/{share_id}/contribute", json={"shares": 3}, headers=headers_b)
    assert r.status_code == 200, r.text
    assert r.json()["shares_taken"] == 4
    assert r.json()["status"] == "full"

    # now genuinely full - even 1 more share from anyone must be refused
    headers_c, _ = _new_user_headers(client)
    _give_saved_card(client, headers_c)
    r = client.post(f"/meat-shares/{share_id}/contribute", json={"shares": 1}, headers=headers_c)
    assert r.status_code == 409

    # admin records the real yield - 100 kg total, split 1:3 between A and B
    r = client.post(f"/admin/meat-shares/{share_id}/mark-ready", json={"total_yield_kg": 100}, headers=ADMIN_HEADERS)
    assert r.status_code == 200
    assert r.json()["status"] == "ready"

    r = client.get(f"/meat-shares/{share_id}", headers=headers_a)
    assert r.json()["my_payout_kg"] == 25.0  # 1/4 of 100kg
    r = client.get(f"/meat-shares/{share_id}", headers=headers_b)
    assert r.json()["my_payout_kg"] == 75.0  # 3/4 of 100kg
    # C never contributed - must see no payout, not an error and not someone else's
    r = client.get(f"/meat-shares/{share_id}", headers=headers_c)
    assert r.json()["my_shares"] == 0
    assert r.json()["my_payout_kg"] is None


def test_cannot_contribute_to_a_non_open_share(client):
    r = client.post(
        "/admin/meat-shares",
        json={"farm_key": "dvur", "species": "goat", "label": "Uzavrena Koza", "total_shares": 1,
              "price_per_share_czk": 100},
        headers=ADMIN_HEADERS,
    )
    share_id = r.json()["id"]
    client.post(f"/admin/meat-shares/{share_id}/mark-ready", json={"total_yield_kg": 10}, headers=ADMIN_HEADERS)

    headers, _ = _new_user_headers(client)
    _give_saved_card(client, headers)
    r = client.post(f"/meat-shares/{share_id}/contribute", json={"shares": 1}, headers=headers)
    assert r.status_code == 409


def test_meat_share_endpoints_require_admin(client):
    r = client.post(
        "/admin/meat-shares",
        json={"farm_key": "dvur", "species": "cow", "label": "Neopravnena Krava", "total_shares": 1, "price_per_share_czk": 1},
    )
    assert r.status_code == 403
