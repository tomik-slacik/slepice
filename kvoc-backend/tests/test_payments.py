"""Tests that app/integrations/payments.py calls the Stripe SDK correctly.

This does NOT touch a real Stripe account - there isn't one configured
anywhere in this project (see docs/PAYMENT_INTEGRATION.md for why that's
deliberate). It mocks the `stripe` package itself and checks that the right
methods get called with the right parameters - verifying the integration is
*wired correctly*, which is a different claim from "has charged a real
card". MockPaymentProvider (tested via tests/test_api.py) is what actually
exercises the real, working code path end to end.
"""
import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("KVOC_DATABASE_URL", "sqlite:///./test_kvoc.db")

import pytest  # noqa: E402

from app import config  # noqa: E402
from app.integrations.payments import (  # noqa: E402
    MockPaymentProvider,
    StripePaymentProvider,
    get_payment_provider,
)


@pytest.fixture
def stripe_key(monkeypatch):
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "sk_test_fake")
    monkeypatch.setattr(config, "STRIPE_PUBLISHABLE_KEY", "pk_test_fake")


def test_stripe_provider_refuses_to_start_without_a_key(monkeypatch):
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "")
    with pytest.raises(RuntimeError):
        StripePaymentProvider()


def test_ensure_customer_creates_once(stripe_key):
    provider = StripePaymentProvider()
    with patch("stripe.Customer.create") as create:
        create.return_value = MagicMock(id="cus_123")
        cid = provider.ensure_customer(user_id=1, email="a@b.com", existing_customer_id=None)

    assert cid == "cus_123"
    create.assert_called_once()
    _, kwargs = create.call_args
    assert kwargs["email"] == "a@b.com"


def test_ensure_customer_reuses_existing_without_calling_stripe(stripe_key):
    provider = StripePaymentProvider()
    with patch("stripe.Customer.create") as create:
        cid = provider.ensure_customer(user_id=1, email="a@b.com", existing_customer_id="cus_already")

    assert cid == "cus_already"
    create.assert_not_called()


def test_create_setup_intent_requests_automatic_payment_methods(stripe_key):
    provider = StripePaymentProvider()
    with patch("stripe.SetupIntent.create") as create:
        create.return_value = MagicMock(client_secret="seti_secret_123")
        result = provider.create_setup_intent("cus_123")

    assert result.client_secret == "seti_secret_123"
    assert result.publishable_key == "pk_test_fake"
    _, kwargs = create.call_args
    assert kwargs["customer"] == "cus_123"
    assert kwargs["automatic_payment_methods"] == {"enabled": True}


def test_charge_saved_method_uses_off_session_and_confirm(stripe_key):
    provider = StripePaymentProvider()
    fake_methods = MagicMock(data=[MagicMock(id="pm_123")])
    with patch("stripe.PaymentMethod.list", return_value=fake_methods) as list_pm, \
         patch("stripe.PaymentIntent.create") as create_pi:
        create_pi.return_value = MagicMock(id="pi_123", status="succeeded")
        result = provider.charge_saved_method("cus_123", 100)

    list_pm.assert_called_once_with(customer="cus_123", type="card")
    _, kwargs = create_pi.call_args
    # amounts are in the smallest currency unit (halere) - a very easy
    # off-by-100x bug to ship unnoticed with a mock provider alone
    assert kwargs["amount"] == 10000
    assert kwargs["currency"] == "czk"
    assert kwargs["customer"] == "cus_123"
    assert kwargs["payment_method"] == "pm_123"
    assert kwargs["off_session"] is True
    assert kwargs["confirm"] is True
    assert result.success is True
    assert result.provider_reference == "pi_123"


def test_charge_saved_method_with_no_saved_card_fails_cleanly(stripe_key):
    provider = StripePaymentProvider()
    with patch("stripe.PaymentMethod.list", return_value=MagicMock(data=[])):
        result = provider.charge_saved_method("cus_123", 100)

    assert result.success is False


def test_provider_selection_defaults_to_mock():
    # KVOC_PAYMENT_PROVIDER is "mock" (or unset) throughout this test suite -
    # see tests/test_api.py, which sets it before app.config is first imported.
    assert isinstance(get_payment_provider(), MockPaymentProvider)
