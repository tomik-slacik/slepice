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


class FarmOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    name: str
    description: str


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
