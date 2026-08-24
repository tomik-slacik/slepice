import datetime as dt
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from . import config


class UserCreate(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)
    password: str = Field(..., min_length=8, max_length=200)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    has_saved_payment_method: bool = False


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChangePasswordIn(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=200)
    new_password: str = Field(..., min_length=8, max_length=200)


class ForgotPasswordIn(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)


class ResetPasswordIn(BaseModel):
    reset_token: str = Field(..., min_length=1, max_length=200)
    new_password: str = Field(..., min_length=8, max_length=200)


class DeviceTokenIn(BaseModel):
    # The FCM registration token the mobile app gets back from
    # PushNotifications.register() (see mobile-app's push-notifications.js).
    # Send an empty string to unregister (e.g. on logout).
    fcm_token: str = Field(..., max_length=4096)


class FarmCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=40)
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="", max_length=200)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)
    weekly_capacity: Optional[int] = Field(default=None, gt=0)


class FarmUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=200)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)
    weekly_capacity: Optional[int] = Field(default=None, gt=0)


class FarmOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    name: str
    description: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    # only populated when GET /farms was called with lat/lng - see
    # routers/farms.py. None just means "we don't know", not "far away".
    distance_km: Optional[float] = None
    weekly_capacity: Optional[int] = None
    # None when weekly_capacity itself is None (unlimited/not tracked) -
    # otherwise weekly_capacity minus how many hens are already there. Can't
    # go negative from here (adopt_hen() in routers/hens.py refuses once
    # it hits 0), but a farm that later *lowers* its capacity below its
    # current headcount would show a negative number on purpose - that's a
    # real "this farm is over capacity" signal, not a bug to hide.
    spots_left: Optional[int] = None


class HenCreate(BaseModel):
    hen_name: str = Field(default="Nuška", min_length=1, max_length=40)
    farm_key: str
    daily_amount: int = Field(
        default=config.DEFAULT_DAILY_AMOUNT, ge=config.MIN_DAILY_AMOUNT, le=config.MAX_DAILY_AMOUNT
    )
    address: str = Field(default="", max_length=200)


class HenUpdate(BaseModel):
    hen_name: Optional[str] = Field(default=None, min_length=1, max_length=40)
    daily_amount: Optional[int] = Field(
        default=None, ge=config.MIN_DAILY_AMOUNT, le=config.MAX_DAILY_AMOUNT
    )
    address: Optional[str] = Field(default=None, max_length=200)
    paused: Optional[bool] = None


class HenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    hen_name: str
    farm_id: int
    daily_amount: int
    address: str
    paused: bool


class FeedLogEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: dt.date
    amount: int
    message: str
    is_bonus: bool


class DeliveryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    week_start: dt.date
    date: dt.date
    amount: int
    eggs: int
    status: str


class WalletOut(BaseModel):
    daily_amount: int
    week_balance: int
    streak: int


class SetupIntentOut(BaseModel):
    client_secret: str
    publishable_key: str


class TopUpCreate(BaseModel):
    amount_czk: int = Field(..., gt=0, le=5000)


class TopUpOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount_czk: int
    provider: str
    status: str
    created_at: dt.datetime
