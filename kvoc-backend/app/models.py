import datetime as dt

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: dt.datetime.now(dt.timezone.utc))

    # Set once the user saves a card via Stripe (see integrations/payments.py
    # and docs/PAYMENT_INTEGRATION.md). Null until then - nothing about
    # registering or logging in touches Stripe.
    stripe_customer_id = Column(String, nullable=True)

    # Set once the app registers for push notifications (see
    # POST /auth/device-token and integrations/notifications.py). Null until
    # then - the daily tick just skips sending anything for that user.
    # One token per user (last registration wins) - good enough for a single
    # phone per account; a user signed in on two devices only gets pushes on
    # whichever registered most recently.
    fcm_token = Column(String, nullable=True)

    # "forgot password" flow (see POST /auth/forgot-password, integrations/email.py).
    # Both null between requests - a token is single-use and time-boxed.
    reset_token = Column(String, nullable=True)
    reset_token_expires = Column(DateTime, nullable=True)

    # Lets GET/POST /admin/* endpoints belong to a real user account instead
    # of only a shared bearer token - see routers/admin.py. Nobody is an
    # admin by default; the first one has to be granted directly in the
    # database (or via KVOC_ADMIN_TOKEN - see config.py) since there's no
    # "promote to admin" endpoint (an admin granting themselves more access
    # over an API is exactly the kind of thing that shouldn't be self-serve).
    is_admin = Column(Boolean, nullable=False, default=False)

    hens = relationship("Hen", back_populates="owner", cascade="all, delete-orphan")
    # Both cascade on account deletion (DELETE /auth/me), same reasoning as
    # hens above - see models further down for what these are.
    animals = relationship("Animal", back_populates="owner", cascade="all, delete-orphan")
    share_contributions = relationship("ShareContribution", back_populates="user", cascade="all, delete-orphan")


class Farm(Base):
    __tablename__ = "farms"

    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=False, default="")

    # Real town-center coordinates (demo-grade precision) for the "find
    # farms near me" feature - see GET /farms?lat=&lng=&radius_km=. Nullable
    # so a farm added without them just never gets a distance, rather than
    # breaking the listing for everyone else.
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)

    # A farm can only actually gather/deliver so many eggs a week - without
    # some cap, nothing stops an unlimited number of customers picking the
    # same small farm. Null = not tracked / unlimited (fine for a farm that
    # hasn't told us its real capacity yet). See routers/hens.py's
    # adopt_hen() and docs/LOGISTICS.md.
    weekly_capacity = Column(Integer, nullable=True)

    hens = relationship("Hen", back_populates="farm")


class Hen(Base):
    """One customer's adoption - the subscription itself. Belongs to exactly
    one User (see app/auth.py for how that's enforced at the API level).
    """

    __tablename__ = "hens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    hen_name = Column(String, nullable=False, default="Nuška")
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False)
    daily_amount = Column(Integer, nullable=False, default=20)
    address = Column(String, nullable=False, default="")
    paused = Column(Boolean, nullable=False, default=False)
    # None normally. "billing" when a failed wallet top-up paused this hen
    # automatically (see routers/wallet.py) rather than the user choosing
    # to - lets a later successful top-up auto-resume it without also
    # un-pausing a hen the user paused deliberately for their own reasons.
    paused_reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: dt.datetime.now(dt.timezone.utc))

    farm = relationship("Farm", back_populates="hens")
    owner = relationship("User", back_populates="hens")
    feed_log = relationship(
        "FeedLogEntry", back_populates="hen", order_by="FeedLogEntry.date",
        cascade="all, delete-orphan",
    )
    deliveries = relationship(
        "Delivery", back_populates="hen", order_by="Delivery.date",
        cascade="all, delete-orphan",
    )
    paused_days = relationship(
        "PausedDay", back_populates="hen", cascade="all, delete-orphan",
    )


class FeedLogEntry(Base):
    __tablename__ = "feed_log_entries"

    id = Column(Integer, primary_key=True)
    hen_id = Column(Integer, ForeignKey("hens.id"), nullable=False)
    date = Column(Date, nullable=False)
    amount = Column(Integer, nullable=False)
    message = Column(String, nullable=False)
    is_bonus = Column(Boolean, nullable=False, default=False)

    hen = relationship("Hen", back_populates="feed_log")


class Delivery(Base):
    __tablename__ = "deliveries"

    id = Column(Integer, primary_key=True)
    hen_id = Column(Integer, ForeignKey("hens.id"), nullable=False)
    week_start = Column(Date, nullable=False)
    date = Column(Date, nullable=False)  # the Friday the delivery was triggered on
    amount = Column(Integer, nullable=False)
    eggs = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="transit")  # transit | delivered

    hen = relationship("Hen", back_populates="deliveries")


class WalletTopUp(Base):
    """A real (or mock) charge that added money to a hen's wallet balance -
    distinct from FeedLogEntry, which is just the daily internal ledger
    draw-down against that balance. See docs/PAYMENT_INTEGRATION.md.
    """

    __tablename__ = "wallet_topups"

    id = Column(Integer, primary_key=True)
    hen_id = Column(Integer, ForeignKey("hens.id"), nullable=False)
    amount_czk = Column(Integer, nullable=False)
    provider = Column(String, nullable=False)  # "mock" | "stripe"
    provider_reference = Column(String, nullable=False)
    status = Column(String, nullable=False)  # "succeeded" | "failed"
    created_at = Column(DateTime, default=lambda: dt.datetime.now(dt.timezone.utc))

    hen = relationship("Hen")


class PausedDay(Base):
    """Records exactly which calendar days a hen's subscription was paused.

    Needed so a streak can be *frozen* by a pause rather than broken by it -
    a plain boolean `Hen.paused` flag alone can't tell you that later, since
    it only reflects the *current* state, not what happened on past days.
    """

    __tablename__ = "paused_days"

    id = Column(Integer, primary_key=True)
    hen_id = Column(Integer, ForeignKey("hens.id"), nullable=False)
    date = Column(Date, nullable=False)

    hen = relationship("Hen", back_populates="paused_days")


# ============================================================================
# Other livestock (see docs/LIVESTOCK.md) - deliberately separate tables from
# Hen/FeedLogEntry/Delivery/PausedDay above, not a rename or a shared base
# class. Two reasons: (1) the already-shipped, already-tested hen/egg flow
# keeps working completely untouched no matter what happens here, and
# (2) "one animal per customer, weekly delivery" (Animal, below) and "many
# customers pool one animal, one payout when it's ready" (MeatShare, further
# below) are genuinely different lifecycles, not the same shape twice - see
# each class's own docstring.
# ============================================================================


class FarmAnimalOffering(Base):
    """Which (species, product) combinations a farm actually offers, and how
    many of that specific combination it can handle per week. A farm's goat
    milk capacity and its sheep wool capacity are two unrelated numbers, so
    this is its own row per combination rather than one shared number like
    Farm.weekly_capacity (which is hens/eggs only, and stays that way).
    """

    __tablename__ = "farm_animal_offerings"

    id = Column(Integer, primary_key=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False)
    species = Column(String, nullable=False)   # "goat" | "sheep" | "cow" - see config.ANIMAL_PRODUCTS
    product = Column(String, nullable=False)   # "milk" | "wool" - must be valid for that species
    weekly_capacity = Column(Integer, nullable=True)  # None = not tracked/unlimited, same convention as Farm.weekly_capacity

    farm = relationship("Farm")


class Animal(Base):
    """One customer's adoption of a non-hen animal for its ongoing (no
    slaughter involved) product - milk or wool. Same "feed it daily, get
    product weekly" shape as Hen, parameterized by species/product instead
    of hardcoded to hens/eggs - see config.ANIMAL_PRODUCTS for the registry
    of which species make which product, at what rate.
    """

    __tablename__ = "animals"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    species = Column(String, nullable=False)
    product = Column(String, nullable=False)
    name = Column(String, nullable=False, default="")
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False)
    daily_amount = Column(Integer, nullable=False, default=20)
    address = Column(String, nullable=False, default="")
    paused = Column(Boolean, nullable=False, default=False)
    paused_reason = Column(String, nullable=True)  # same "billing" convention as Hen.paused_reason
    created_at = Column(DateTime, default=lambda: dt.datetime.now(dt.timezone.utc))

    farm = relationship("Farm")
    owner = relationship("User", back_populates="animals")
    product_log = relationship(
        "AnimalProductLogEntry", back_populates="animal", order_by="AnimalProductLogEntry.date",
        cascade="all, delete-orphan",
    )
    deliveries = relationship(
        "AnimalDelivery", back_populates="animal", order_by="AnimalDelivery.date",
        cascade="all, delete-orphan",
    )
    paused_days = relationship(
        "AnimalPausedDay", back_populates="animal", cascade="all, delete-orphan",
    )


class AnimalProductLogEntry(Base):
    __tablename__ = "animal_product_log_entries"

    id = Column(Integer, primary_key=True)
    animal_id = Column(Integer, ForeignKey("animals.id"), nullable=False)
    date = Column(Date, nullable=False)
    amount = Column(Integer, nullable=False)
    message = Column(String, nullable=False)
    is_bonus = Column(Boolean, nullable=False, default=False)

    animal = relationship("Animal", back_populates="product_log")


class AnimalDelivery(Base):
    __tablename__ = "animal_deliveries"

    id = Column(Integer, primary_key=True)
    animal_id = Column(Integer, ForeignKey("animals.id"), nullable=False)
    week_start = Column(Date, nullable=False)
    date = Column(Date, nullable=False)
    amount = Column(Integer, nullable=False)
    units = Column(Float, nullable=False)  # e.g. liters of milk, kg of wool - see config.ANIMAL_PRODUCTS[..]["unit"]
    status = Column(String, nullable=False, default="transit")

    animal = relationship("Animal", back_populates="deliveries")


class AnimalPausedDay(Base):
    __tablename__ = "animal_paused_days"

    id = Column(Integer, primary_key=True)
    animal_id = Column(Integer, ForeignKey("animals.id"), nullable=False)
    date = Column(Date, nullable=False)

    animal = relationship("Animal", back_populates="paused_days")


class MeatShare(Base):
    """A single real animal being raised for meat (optionally + hide),
    funded by several customers pooling contributions instead of one
    customer "owning" an entire cow - the real-world cow-share/goat-share
    model, because one animal's meat is far more than one household eats.

    Lifecycle: open (taking contributions) -> full (all shares taken) ->
    processing (farm has sent it for slaughter - a real-world event this
    software doesn't trigger or witness) -> ready (admin recorded the real
    yield - see routers/meat_shares.py) -> fulfilled (delivered; tracked for
    completeness, not automated - see docs/LIVESTOCK.md).
    """

    __tablename__ = "meat_shares"

    id = Column(Integer, primary_key=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False)
    species = Column(String, nullable=False)  # "cow" | "goat" | "sheep"
    label = Column(String, nullable=False)  # e.g. "Kráva Bětka" - same "you know whose it is" idea as a hen's name
    total_shares = Column(Integer, nullable=False)
    price_per_share_czk = Column(Integer, nullable=False)
    includes_hide = Column(Boolean, nullable=False, default=False)
    expected_ready_date = Column(Date, nullable=True)
    status = Column(String, nullable=False, default="open")  # open | full | processing | ready | fulfilled
    # Set only once, at "mark ready" time (routers/meat_shares.py) - the real
    # slaughter yield, which nobody can know until it actually happens.
    total_yield_kg = Column(Float, nullable=True)
    created_at = Column(DateTime, default=lambda: dt.datetime.now(dt.timezone.utc))

    farm = relationship("Farm")
    contributions = relationship(
        "ShareContribution", back_populates="meat_share", cascade="all, delete-orphan",
    )


class ShareContribution(Base):
    """One user's stake in a MeatShare - shares held, not currency, is the
    unit of entitlement (see MeatShare.total_shares); amount_czk is recorded
    at contribution time so a later price change on the share never
    retroactively rewrites what someone already paid.
    """

    __tablename__ = "share_contributions"

    id = Column(Integer, primary_key=True)
    meat_share_id = Column(Integer, ForeignKey("meat_shares.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    shares = Column(Integer, nullable=False)
    amount_czk = Column(Integer, nullable=False)
    provider_reference = Column(String, nullable=False, default="")
    created_at = Column(DateTime, default=lambda: dt.datetime.now(dt.timezone.utc))

    meat_share = relationship("MeatShare", back_populates="contributions")
    user = relationship("User", back_populates="share_contributions")
