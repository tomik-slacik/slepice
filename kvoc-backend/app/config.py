"""Central place for tunable business constants.

Nothing here is a secret. Real credentials (payment provider keys, push
service keys) belong in environment variables, never in this file and never
committed to source control. See docs/PAYMENT_INTEGRATION.md.
"""
import os

# ---- wallet / pricing ----
MIN_DAILY_AMOUNT = 10
MAX_DAILY_AMOUNT = 40
DAILY_AMOUNT_STEP = 5
DEFAULT_DAILY_AMOUNT = 20
KC_PER_EGG = 12.5     # rough egg price used to convert Kč -> eggs; validate against real suppliers
BONUS_CHANCE = 0.18   # chance of an extra "bonus egg" flavour notification on a fed day

# ---- schedule ----
DELIVERY_WEEKDAY = 4   # Python's date.weekday(): Monday=0 ... Sunday=6  ->  4 = Friday
DAILY_TICK_HOUR = 8    # local hour the real daily charge/notification job fires at
DAILY_TICK_MINUTE = 0
SCHEDULER_TIMEZONE = "Europe/Prague"

# ---- database ----
# Overridable so tests (and any future deployment) can point at a different
# database without touching code - see tests/test_api.py.
DATABASE_URL = os.environ.get("KVOC_DATABASE_URL", "sqlite:///./kvoc.db")

# ---- auth ----
# TODO: set KVOC_JWT_SECRET to a real, stable secret before deploying
# anywhere - without it every process restart invalidates all tokens
# (fine for local dev, useless in production).
import secrets as _secrets  # noqa: E402

JWT_SECRET = os.environ.get("KVOC_JWT_SECRET") or _secrets.token_urlsafe(32)
if not os.environ.get("KVOC_JWT_SECRET"):
    print(
        "[config] KVOC_JWT_SECRET not set - using a random secret for this process only. "
        "Existing tokens will stop working on restart. Fine for local dev; "
        "set a real KVOC_JWT_SECRET environment variable before deploying anywhere."
    )
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 7

# ---- payments ----
# Which PaymentProvider app/integrations/payments.py hands back. "mock" (the
# safe default) never touches real money. "stripe" requires KVOC_STRIPE_SECRET_KEY
# to be set - see docs/PAYMENT_INTEGRATION.md.
PAYMENT_PROVIDER = os.environ.get("KVOC_PAYMENT_PROVIDER", "mock")
STRIPE_SECRET_KEY = os.environ.get("KVOC_STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("KVOC_STRIPE_PUBLISHABLE_KEY", "")
TOPUP_WEEKS_COVERED = 4  # how many weeks of daily_amount one top-up should cover
