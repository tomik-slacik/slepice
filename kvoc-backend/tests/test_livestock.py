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


def test_cancel_contribution_refunds_and_reopens_a_full_share(client):
    r = client.post(
        "/admin/meat-shares",
        json={"farm_key": "dvur", "species": "cow", "label": "Zrusitelna Kravicka", "total_shares": 4,
              "price_per_share_czk": 500},
        headers=ADMIN_HEADERS,
    )
    share_id = r.json()["id"]

    headers_a, _ = _new_user_headers(client)
    _give_saved_card(client, headers_a)
    headers_b, _ = _new_user_headers(client)
    _give_saved_card(client, headers_b)

    client.post(f"/meat-shares/{share_id}/contribute", json={"shares": 1}, headers=headers_a)
    r = client.post(f"/meat-shares/{share_id}/contribute", json={"shares": 3}, headers=headers_b)
    assert r.json()["status"] == "full"

    # A cancels their single share - share must reopen (it's no longer
    # fully taken) and A must show no stake left, without touching B's
    r = client.delete(f"/meat-shares/{share_id}/contribution", headers=headers_a)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "open"
    assert r.json()["shares_taken"] == 3
    assert r.json()["my_shares"] == 0

    r = client.get(f"/meat-shares/{share_id}", headers=headers_b)
    assert r.json()["my_shares"] == 3

    # someone else can now take the share A gave up
    headers_c, _ = _new_user_headers(client)
    _give_saved_card(client, headers_c)
    r = client.post(f"/meat-shares/{share_id}/contribute", json={"shares": 1}, headers=headers_c)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "full"


def test_cancel_contribution_without_any_stake_is_rejected(client):
    headers, _ = _new_user_headers(client)
    shares = client.get("/meat-shares", headers=headers).json()
    share_id = [s for s in shares if s["label"] == "Kráva Bětka"][0]["id"]
    r = client.delete(f"/meat-shares/{share_id}/contribution", headers=headers)
    assert r.status_code == 404


def test_cannot_cancel_a_contribution_once_the_share_is_processing_or_later(client):
    r = client.post(
        "/admin/meat-shares",
        json={"farm_key": "dvur", "species": "goat", "label": "Pozde Na Zruseni Koza", "total_shares": 1,
              "price_per_share_czk": 100},
        headers=ADMIN_HEADERS,
    )
    share_id = r.json()["id"]

    headers, _ = _new_user_headers(client)
    _give_saved_card(client, headers)
    client.post(f"/meat-shares/{share_id}/contribute", json={"shares": 1}, headers=headers)

    client.post(f"/admin/meat-shares/{share_id}/mark-ready", json={"total_yield_kg": 10}, headers=ADMIN_HEADERS)

    r = client.delete(f"/meat-shares/{share_id}/contribution", headers=headers)
    assert r.status_code == 409
    # rejected cleanly - the contribution (and payout) must still be there
    assert client.get(f"/meat-shares/{share_id}", headers=headers).json()["my_shares"] == 1


def test_meat_share_endpoints_require_admin(client):
    r = client.post(
        "/admin/meat-shares",
        json={"farm_key": "dvur", "species": "cow", "label": "Neopravnena Krava", "total_shares": 1, "price_per_share_czk": 1},
    )
    assert r.status_code == 403


# ---------------------------- admin: farm animal offerings ----------------------------
# POST /admin/farms/{key}/animal-offerings had zero test coverage before
# this - it's what actually lets a farm offer a species/product combo (see
# its own docstring), so "nothing ever adopts goat milk at a farm that
# doesn't offer it" (test_adopt_animal_rejects_a_farm_that_doesnt_offer_it
# above) was only ever tested from the *seeded* data's side, never this
# endpoint's.

def test_add_animal_offering_lets_a_farm_start_offering_a_combo(client):
    r = client.post(
        "/admin/farms/ricany/animal-offerings",
        json={"species": "goat", "product": "milk", "weekly_capacity": 5},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 201, r.text
    assert r.json() == {"farm_key": "ricany", "species": "goat", "product": "milk", "weekly_capacity": 5}

    # and it's real - a fresh adoption there now succeeds instead of 404ing
    headers, _ = _new_user_headers(client)
    r = client.post("/animals", json={"species": "goat", "product": "milk", "farm_key": "ricany"}, headers=headers)
    assert r.status_code == 201, r.text


def test_add_animal_offering_rejects_unknown_farm(client):
    r = client.post(
        "/admin/farms/no-such-farm/animal-offerings",
        json={"species": "goat", "product": "milk"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 404


def test_add_animal_offering_rejects_a_combo_the_species_doesnt_make(client):
    r = client.post(
        "/admin/farms/ricany/animal-offerings",
        json={"species": "goat", "product": "wool"},  # goats don't make wool
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 400


def test_add_animal_offering_rejects_a_duplicate(client):
    client.post(
        "/admin/farms/kladno/animal-offerings",
        json={"species": "cow", "product": "milk"},
        headers=ADMIN_HEADERS,
    )
    r = client.post(
        "/admin/farms/kladno/animal-offerings",
        json={"species": "cow", "product": "milk"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 409


def test_add_animal_offering_requires_admin(client):
    r = client.post(
        "/admin/farms/ricany/animal-offerings",
        json={"species": "goat", "product": "milk"},
    )
    assert r.status_code == 403


# ---------------------------- admin: delivery route ----------------------------
# GET /admin/farms/{key}/delivery-route (docs/LOGISTICS.md) - the hen-only
# case is covered in test_api.py; this proves a hen and an animal on the
# same farm both show up as stops on the same route, correctly ordered
# against each other by real distance, not just within their own kind.

def test_delivery_route_mixes_hens_and_animals_on_one_farm(client):
    headers_hen, _ = _new_user_headers(client)
    headers_goat, _ = _new_user_headers(client)

    # "dvur" is seeded at lat 49.7847, lng 14.6873 (app/seed.py) - the goat
    # is placed closer than the hen on purpose, so a correct mixed route
    # must visit the goat first regardless of which kind it is
    r = client.post(
        "/hens",
        json={"hen_name": "Vzdálená Slepička", "farm_key": "dvur", "lat": 49.83, "lng": 14.73},
        headers=headers_hen,
    )
    assert r.status_code == 201, r.text
    hen = r.json()

    r = client.post(
        "/animals",
        json={"species": "goat", "product": "milk", "farm_key": "dvur", "lat": 49.786, "lng": 14.690},
        headers=headers_goat,
    )
    assert r.status_code == 201, r.text
    goat = r.json()  # no `name` given - the route should fall back to a species label

    r = client.get("/admin/farms/dvur/delivery-route", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    stops = r.json()["route"]
    kinds_and_ids = [(s["kind"], s["id"]) for s in stops]
    assert ("hen", hen["id"]) in kinds_and_ids
    assert ("animal", goat["id"]) in kinds_and_ids
    assert kinds_and_ids.index(("animal", goat["id"])) < kinds_and_ids.index(("hen", hen["id"]))

    goat_stop = [s for s in stops if s["kind"] == "animal" and s["id"] == goat["id"]][0]
    assert goat_stop["name"] == "Koza"  # no custom name given above - species label fallback


# ---------------------------- admin: edit an animal on a user's behalf ----------------------------
# PATCH /admin/animals/{id} (docs/ADMIN.md) - the animal-side twin of
# test_api.py's test_admin_can_view_and_edit_a_users_hen, which only ever
# covered the hen version even though admin.html's Detail panel and
# adminToggleAnimalPause() call this exact endpoint for animals too.

def test_admin_can_edit_a_users_animal(client):
    headers, _ = _new_user_headers(client)
    r = client.post(
        "/animals",
        json={"species": "goat", "product": "milk", "name": "Koza Rozárka", "farm_key": "dvur"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    animal = r.json()

    r = client.patch(f"/admin/animals/{animal['id']}", json={"paused": True}, headers=ADMIN_HEADERS)
    assert r.status_code == 200, r.text
    assert r.json()["paused"] is True

    # the owner sees the change too - same row, not a shadow copy
    r = client.get(f"/animals/{animal['id']}", headers=headers)
    assert r.json()["paused"] is True

    r = client.patch("/admin/animals/99999999", json={"paused": True}, headers=ADMIN_HEADERS)
    assert r.status_code == 404


def test_admin_update_animal_requires_admin(client):
    headers, _ = _new_user_headers(client)
    r = client.post(
        "/animals",
        json={"species": "cow", "product": "milk", "farm_key": "lipa"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    animal = r.json()
    r = client.patch(f"/admin/animals/{animal['id']}", json={"paused": True})
    assert r.status_code == 403


# ---------------------------- animal wallet top-ups ----------------------------
# POST /animals/{id}/wallet/topup (and setup-intent, topups) - the animal
# side of routers/wallet.py, closing the one honestly-documented gap in
# docs/LIVESTOCK.md ("Animal nema vlastni platebni tok"). Mirrors
# test_api.py's hen-wallet tests closely on purpose - same behavior, same
# guarantees, just for an Animal instead of a Hen.

def _adopt_animal(client, headers, species="cow", product="milk", farm_key="lipa", daily_amount=20):
    r = client.post(
        "/animals",
        json={"species": species, "product": product, "farm_key": farm_key, "daily_amount": daily_amount},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_animal_setup_intent_works_for_an_account_with_only_an_animal_no_hen_at_all(client):
    # the whole reason this endpoint exists separately from
    # /hens/{hen_id}/wallet/setup-intent rather than reusing it - an
    # account with no hen has no hen_id to call that version on
    headers, _ = _new_user_headers(client)
    animal = _adopt_animal(client, headers)

    r = client.post(f"/animals/{animal['id']}/wallet/setup-intent", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["client_secret"]

    r = client.get("/auth/me", headers=headers)
    assert r.json()["has_saved_payment_method"] is True


def test_animal_wallet_topup_flow_with_mock_provider(client):
    headers, _ = _new_user_headers(client)
    animal = _adopt_animal(client, headers)
    animal_id = animal["id"]

    client.post(f"/animals/{animal_id}/wallet/setup-intent", headers=headers)

    r = client.post(f"/animals/{animal_id}/wallet/topup", json={"amount_czk": 100}, headers=headers)
    assert r.status_code == 201, r.text
    topup = r.json()
    assert topup["amount_czk"] == 100
    assert topup["status"] == "succeeded"
    assert topup["provider"] == "mock"

    r = client.get(f"/animals/{animal_id}/wallet/topups", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_animal_topup_without_saved_card_is_rejected(client):
    headers, _ = _new_user_headers(client)
    animal = _adopt_animal(client, headers)
    r = client.post(f"/animals/{animal['id']}/wallet/topup", json={"amount_czk": 100}, headers=headers)
    assert r.status_code == 400


def test_failed_animal_topup_auto_pauses_and_successful_one_resumes_it(client):
    from unittest.mock import patch

    from app.integrations.payments import TopUpResult

    headers, _ = _new_user_headers(client)
    animal = _adopt_animal(client, headers)
    animal_id = animal["id"]
    client.post(f"/animals/{animal_id}/wallet/setup-intent", headers=headers)

    with patch(
        "app.integrations.payments.MockPaymentProvider.charge_saved_method",
        return_value=TopUpResult(success=False, provider_reference="mock-fail", message="card declined"),
    ):
        r = client.post(f"/animals/{animal_id}/wallet/topup", json={"amount_czk": 100}, headers=headers)
    assert r.status_code == 402

    r = client.get(f"/animals/{animal_id}", headers=headers)
    assert r.json()["paused"] is True

    # a real (unpatched, mock-succeeding) top-up should resume it again
    r = client.post(f"/animals/{animal_id}/wallet/topup", json={"amount_czk": 100}, headers=headers)
    assert r.status_code == 201
    r = client.get(f"/animals/{animal_id}", headers=headers)
    assert r.json()["paused"] is False


def test_successful_animal_topup_never_resumes_a_manually_paused_animal(client):
    headers, _ = _new_user_headers(client)
    animal = _adopt_animal(client, headers)
    animal_id = animal["id"]
    client.post(f"/animals/{animal_id}/wallet/setup-intent", headers=headers)

    client.patch(f"/animals/{animal_id}", json={"paused": True}, headers=headers)
    r = client.post(f"/animals/{animal_id}/wallet/topup", json={"amount_czk": 100}, headers=headers)
    assert r.status_code == 201

    r = client.get(f"/animals/{animal_id}", headers=headers)
    assert r.json()["paused"] is True  # a top-up succeeding doesn't override a deliberate pause


def test_animal_wallet_endpoints_are_isolated_between_users(client):
    headers_a, _ = _new_user_headers(client)
    headers_b, _ = _new_user_headers(client)
    animal = _adopt_animal(client, headers_a)

    r = client.post(f"/animals/{animal['id']}/wallet/setup-intent", headers=headers_b)
    assert r.status_code == 404
    r = client.post(f"/animals/{animal['id']}/wallet/topup", json={"amount_czk": 100}, headers=headers_b)
    assert r.status_code == 404
    r = client.get(f"/animals/{animal['id']}/wallet/topups", headers=headers_b)
    assert r.status_code == 404
