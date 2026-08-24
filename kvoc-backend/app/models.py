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

    hens = relationship("Hen", back_populates="owner", cascade="all, delete-orphan")


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
