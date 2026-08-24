import datetime as dt

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .database import Base


class Farm(Base):
    __tablename__ = "farms"

    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=False, default="")

    hens = relationship("Hen", back_populates="farm")


class Hen(Base):
    """One customer's adoption - the subscription itself.

    There is intentionally no real user/auth model yet (see README): each
    Hen just carries a free-text owner_name. Add a proper User table with
    hashed passwords or OAuth before this goes anywhere near real customers.
    """

    __tablename__ = "hens"

    id = Column(Integer, primary_key=True)
    owner_name = Column(String, nullable=False)
    hen_name = Column(String, nullable=False, default="Nuška")
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False)
    daily_amount = Column(Integer, nullable=False, default=20)
    address = Column(String, nullable=False, default="")
    paused = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=lambda: dt.datetime.now(dt.timezone.utc))

    farm = relationship("Farm", back_populates="hens")
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
