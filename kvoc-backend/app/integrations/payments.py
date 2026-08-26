"""Payment provider abstraction.

Mazlík deliberately never charges a card once a day - transaction fees on a
20 Kč payment would eat a large slice of it. Instead the wallet is topped up
in bulk (weekly or monthly) by one *real* charge, and the daily "feeding" is
just an internal ledger entry against that balance. See
docs/PAYMENT_INTEGRATION.md for the full reasoning and a legal note on how
the wallet should be classified.

MockPaymentProvider is the default and safe: it never touches real money,
just logs what *would* happen. StripePaymentProvider below is a real,
verified-against-Stripe's-docs implementation of the save-a-card /
charge-it-later flow (SetupIntent -> PaymentMethod -> off-session
PaymentIntent) - but it has never been run against an actual Stripe
account from here, because creating that account is something only you can
do (see docs/PAYMENT_INTEGRATION.md). Its request/response shape is tested
against a mocked `stripe` module in tests/test_payments.py, which checks
this code calls the Stripe SDK correctly - that is a different thing from
having charged a real card.

Switch providers with the KVOC_PAYMENT_PROVIDER environment variable
("mock" | "stripe"); "stripe" also needs KVOC_STRIPE_SECRET_KEY.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .. import config


@dataclass
class TopUpResult:
    success: bool
    provider_reference: str
    message: str = ""


@dataclass
class SetupIntentResult:
    client_secret: str
    publishable_key: str


class PaymentProvider(ABC):
    @abstractmethod
    def ensure_customer(self, user_id: int, email: str, existing_customer_id: str | None) -> str:
        """Return a provider-side customer id for this user, creating one on
        first call. `existing_customer_id` is whatever was stored last time
        (None the first time) - implementations should reuse it rather than
        creating a duplicate customer on every call.
        """
        raise NotImplementedError

    @abstractmethod
    def create_setup_intent(self, provider_customer_id: str) -> SetupIntentResult:
        """Start the "save a card" flow. The client uses the returned
        client_secret with Stripe.js (or equivalent) to actually collect
        card details - card numbers must never reach this server, for PCI
        compliance reasons; that is not a limitation to work around.
        """
        raise NotImplementedError

    @abstractmethod
    def charge_saved_method(self, provider_customer_id: str, amount_czk: int) -> TopUpResult:
        """Charge the customer's most recently saved payment method
        off-session (i.e. with nobody actively present to authenticate).
        Called on a recurring top-up schedule - never once a day.
        """
        raise NotImplementedError


class MockPaymentProvider(PaymentProvider):
    """Sandbox stand-in used by default. Nothing here touches real money or
    a real network - every call just logs and returns a fabricated
    reference, so the rest of the app (and the test suite) works fully
    without any payment account at all.
    """

    def ensure_customer(self, user_id: int, email: str, existing_customer_id: str | None) -> str:
        if existing_customer_id:
            return existing_customer_id
        ref = f"mock-cus-{user_id}"
        print(f"[MockPaymentProvider] created fake customer {ref} for {email}")
        return ref

    def create_setup_intent(self, provider_customer_id: str) -> SetupIntentResult:
        print(f"[MockPaymentProvider] would start a card-setup flow for {provider_customer_id}")
        return SetupIntentResult(client_secret="mock-secret", publishable_key="mock-publishable-key")

    def charge_saved_method(self, provider_customer_id: str, amount_czk: int) -> TopUpResult:
        print(f"[MockPaymentProvider] would charge {provider_customer_id} {amount_czk} Kč for a wallet top-up")
        return TopUpResult(success=True, provider_reference=f"mock-charge-{provider_customer_id}", message="mocked")


class StripePaymentProvider(PaymentProvider):
    """Real Stripe integration: Customer -> SetupIntent (card saved
    client-side via Stripe.js/Payment Element) -> off-session PaymentIntent
    to charge the saved card later. Flow verified against
    https://docs.stripe.com/payments/save-and-reuse (Setup Intents API,
    Customers v1) - see docs/PAYMENT_INTEGRATION.md for the full picture,
    including the minimal card-collection page in app/static/card-setup.html
    that this pairs with.

    Needs KVOC_STRIPE_SECRET_KEY set. Never run against a real account from
    this environment - see the module docstring.
    """

    def __init__(self) -> None:
        import stripe  # imported lazily so importing this module never requires the package

        if not config.STRIPE_SECRET_KEY:
            raise RuntimeError(
                "KVOC_PAYMENT_PROVIDER=stripe but KVOC_STRIPE_SECRET_KEY is not set. "
                "See docs/PAYMENT_INTEGRATION.md."
            )
        stripe.api_key = config.STRIPE_SECRET_KEY
        self._stripe = stripe

    def ensure_customer(self, user_id: int, email: str, existing_customer_id: str | None) -> str:
        if existing_customer_id:
            return existing_customer_id
        customer = self._stripe.Customer.create(email=email, metadata={"kvoc_user_id": str(user_id)})
        return customer.id

    def create_setup_intent(self, provider_customer_id: str) -> SetupIntentResult:
        intent = self._stripe.SetupIntent.create(
            customer=provider_customer_id,
            automatic_payment_methods={"enabled": True},
        )
        return SetupIntentResult(
            client_secret=intent.client_secret,
            publishable_key=config.STRIPE_PUBLISHABLE_KEY,
        )

    def charge_saved_method(self, provider_customer_id: str, amount_czk: int) -> TopUpResult:
        methods = self._stripe.PaymentMethod.list(customer=provider_customer_id, type="card")
        if not methods.data:
            return TopUpResult(success=False, provider_reference="", message="no saved payment method")
        payment_method_id = methods.data[0].id

        try:
            intent = self._stripe.PaymentIntent.create(
                amount=amount_czk * 100,  # Stripe amounts are in the smallest currency unit (haléře)
                currency="czk",
                customer=provider_customer_id,
                payment_method=payment_method_id,
                off_session=True,
                confirm=True,
            )
            return TopUpResult(success=intent.status == "succeeded", provider_reference=intent.id, message=intent.status)
        except self._stripe.error.CardError as e:
            # off-session charge was declined or needs the customer to
            # re-authenticate - the caller is responsible for notifying them
            return TopUpResult(success=False, provider_reference=e.json_body.get("error", {}).get("payment_intent", {}).get("id", ""), message=str(e))


def get_payment_provider() -> PaymentProvider:
    if config.PAYMENT_PROVIDER == "stripe":
        return StripePaymentProvider()
    return MockPaymentProvider()
