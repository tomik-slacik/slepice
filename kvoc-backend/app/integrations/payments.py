"""Payment provider abstraction.

Kvoč deliberately never charges a card once a day - transaction fees on a
20 Kč payment would eat a large slice of it. Instead the wallet is topped up
in bulk (weekly or monthly) by one *real* charge, and the daily "feeding" is
just an internal ledger entry against that balance. See
docs/PAYMENT_INTEGRATION.md for the full reasoning and a legal note on how
the wallet should be classified.

MockPaymentProvider below is a safe stand-in: it never touches real money,
it just logs what *would* happen. Swap it for a real implementation (GoPay,
Comgate, Stripe, ...) behind this same interface before this goes near real
customers - see the TODO markers.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TopUpResult:
    success: bool
    provider_reference: str
    message: str = ""


class PaymentProvider(ABC):
    @abstractmethod
    def charge_topup(self, hen_id: int, amount_czk: int) -> TopUpResult:
        """Charge the customer's saved payment method for a wallet top-up.

        Called on a recurring schedule (weekly or monthly) - never per day.
        """
        raise NotImplementedError


class MockPaymentProvider(PaymentProvider):
    """Default sandbox stand-in. Always "succeeds" and just logs to stdout -
    no real money ever moves.

    TODO before a real launch: implement a provider against a real Czech
    payment gateway, for example:
      - GoPay:   https://help.gopay.com/en/knowledge-base/technicka-dokumentace-api
      - Comgate: https://apidoc.comgate.cz/
      - Stripe (Payment Intents + saved card / SEPA): https://stripe.com/docs/payments/save-and-reuse
    Keep API keys in environment variables (e.g. KVOC_PAYMENT_API_KEY),
    never in source control.
    """

    def charge_topup(self, hen_id: int, amount_czk: int) -> TopUpResult:
        print(
            f"[MockPaymentProvider] would charge hen #{hen_id} {amount_czk} Kč "
            "for a wallet top-up (no real payment gateway configured)"
        )
        return TopUpResult(success=True, provider_reference=f"mock-{hen_id}", message="mocked")


def get_payment_provider() -> PaymentProvider:
    """Swap this to return a real provider once one is configured - e.g. by
    reading a KVOC_PAYMENT_PROVIDER environment variable.
    """
    return MockPaymentProvider()
