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
