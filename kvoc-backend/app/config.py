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
# database without touching code - see tests/test_api.py. In production
# (docs/DEPLOYMENT.md) this should be a real Postgres URL, not sqlite - a
# deployed container's filesystem is not guaranteed to survive a restart.
DATABASE_URL = os.environ.get("KVOC_DATABASE_URL", "sqlite:///./kvoc.db")

# ---- CORS ----
# The bundled webapp (app/webapp/) is served from the same origin as the
# API, so it never needs this. It exists for any *other* client (a
# separately-hosted frontend, a mobile app pointed at a real deployment).
# "*" is fine for local dev and low-stakes demos; set to your real
# frontend's origin(s), comma-separated, before deploying anywhere the
# wallet/payment endpoints matter.
CORS_ORIGINS = [o.strip() for o in os.environ.get("KVOC_CORS_ORIGINS", "*").split(",") if o.strip()]

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

# ---- notifications ----
# Which NotificationProvider app/integrations/notifications.py hands back.
# "console" (the safe default) never talks to any external service, just
# prints what would be sent. "fcm" sends a real push via Firebase Cloud
# Messaging and needs KVOC_FIREBASE_CREDENTIALS_JSON - see docs/NOTIFICATIONS.md.
NOTIFICATION_PROVIDER = os.environ.get("KVOC_NOTIFICATION_PROVIDER", "console")
FIREBASE_CREDENTIALS_JSON = os.environ.get("KVOC_FIREBASE_CREDENTIALS_JSON", "")

# ---- payments ----
# Which PaymentProvider app/integrations/payments.py hands back. "mock" (the
# safe default) never touches real money. "stripe" requires KVOC_STRIPE_SECRET_KEY
# to be set - see docs/PAYMENT_INTEGRATION.md.
PAYMENT_PROVIDER = os.environ.get("KVOC_PAYMENT_PROVIDER", "mock")
STRIPE_SECRET_KEY = os.environ.get("KVOC_STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("KVOC_STRIPE_PUBLISHABLE_KEY", "")
TOPUP_WEEKS_COVERED = 4  # how many weeks of daily_amount one top-up should cover

# ---- other livestock (see docs/LIVESTOCK.md) ----
# One place that defines which species make which ongoing (non-slaughter)
# product, at what real-world rate - adding a new species/product combo
# later is adding an entry here (+ a farm offering it, see seed.py), not
# writing new code. kc_per_unit is a rough real-world price used to convert
# a daily_amount into a weekly quantity, same idea as config.KC_PER_EGG -
# validate against real suppliers before this ever charges anyone for real.
ANIMAL_PRODUCTS = {
    "goat": {
        "milk": {"unit": "l", "unit_label": "litrů mléka", "kc_per_unit": 25},
    },
    # sheep intentionally has no ongoing (non-slaughter) product here -
    # "wool" was removed on purpose: a sheep in this app is a meat-share-only
    # species now, see MEAT_SHARE_SPECIES below. GET /animals/available-products
    # simply won't list sheep at all, which is correct - no code elsewhere
    # needs to special-case "sheep with no products".
    "cow": {
        "milk": {"unit": "l", "unit_label": "litrů mléka", "kc_per_unit": 22},
    },
}
MEAT_SHARE_SPECIES = ["cow", "goat", "sheep"]  # who a MeatShare is allowed to be

# ---- email ----
# Which EmailProvider app/integrations/email.py hands back. "console" (the
# safe default) never sends anything real, just prints what would be sent.
# "smtp" sends a real email through any SMTP account (Gmail with an app
# password works fine for low volume / getting started - no dedicated
# transactional-email service account required) - see docs/EMAIL.md.
EMAIL_PROVIDER = os.environ.get("KVOC_EMAIL_PROVIDER", "console")
SMTP_HOST = os.environ.get("KVOC_SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("KVOC_SMTP_PORT", "587"))
SMTP_USERNAME = os.environ.get("KVOC_SMTP_USERNAME", "")
SMTP_PASSWORD = os.environ.get("KVOC_SMTP_PASSWORD", "")
EMAIL_FROM = os.environ.get("KVOC_EMAIL_FROM", "Kvoč <noreply@kvoc.cz>")
PASSWORD_RESET_EXPIRE_MINUTES = 30
# where the reset link in the email points - the bundled webapp by default
PASSWORD_RESET_URL_BASE = os.environ.get("KVOC_PASSWORD_RESET_URL_BASE", "/app/")

# ---- admin ----
# A single shared bearer token for routers/admin.py's data endpoints
# (X-Admin-Token header) - simplest thing that actually works for a
# one-or-two-person operation. Empty by default, which *disables* every
# admin endpoint outright (never silently open) - set it before you need
# the admin dashboard. A User.is_admin flag (see models.py) is the other,
# per-account way in - either is accepted.
ADMIN_TOKEN = os.environ.get("KVOC_ADMIN_TOKEN", "")

# ---- login rate limiting ----
# Per-email, in-memory (see auth.py) - resets on process restart and isn't
# shared across multiple server instances. Fine for this project's actual
# deployment shape (one process, see docs/DEPLOYMENT.md); a multi-instance
# deployment would need this moved to somewhere shared (e.g. Redis) instead.
LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_MINUTES = 15
