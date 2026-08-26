import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .. import config, models, schemas
from ..auth import (
    check_login_not_locked_out,
    clear_failed_logins,
    create_access_token,
    generate_reset_token,
    get_current_user,
    hash_password,
    record_failed_login,
    verify_password,
)
from ..database import get_db
from ..integrations.email import get_email_provider

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=schemas.TokenOut, status_code=201)
def register(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == payload.email.lower()).first()
    if existing is not None:
        raise HTTPException(409, "an account with this email already exists")

    user = models.User(email=payload.email.lower(), password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    get_email_provider().send(
        user.email, "Vítej v Mazlíkovi",
        "Ahoj!\n\nTvůj účet je založený. Teď stačí adoptovat slepičku (nebo kozu, ovci, "
        "krávu) a v pátek dorazí první dodávka.\n\nMazlík",
    )
    return schemas.TokenOut(access_token=create_access_token(user.id))


@router.post("/login", response_model=schemas.TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Uses the standard OAuth2 password-flow form (username + password)
    so the auto-generated /docs page's "Authorize" button works out of the
    box - `username` here is the user's email.
    """
    email = form.username.lower()
    check_login_not_locked_out(email)  # raises 429 if too many recent failures

    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None or not verify_password(form.password, user.password_hash):
        record_failed_login(email)
        raise HTTPException(401, "incorrect email or password")

    clear_failed_logins(email)
    return schemas.TokenOut(access_token=create_access_token(user.id))


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    out = schemas.UserOut.model_validate(current_user)
    out.has_saved_payment_method = bool(current_user.stripe_customer_id)
    return out


@router.delete("/me", status_code=204)
def delete_account(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Deletes the account and everything under it (hens, feed log,
    deliveries - see the cascade="all, delete-orphan" relationships in
    models.py). Doesn't cancel a real Stripe subscription/saved card by
    itself - Mazlík never holds a recurring Stripe subscription object (see
    docs/PAYMENT_INTEGRATION.md, the wallet-topup model), so there is
    nothing on Stripe's side left running once this returns; a saved card
    (PaymentMethod) is simply orphaned on Stripe, not charged again.
    """
    db.delete(current_user)
    db.commit()


@router.post("/change-password", status_code=204)
def change_password(
    payload: schemas.ChangePasswordIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """For someone already logged in and who remembers their current
    password. Forgotten password -> POST /auth/forgot-password instead.
    """
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(401, "current password is incorrect")
    current_user.password_hash = hash_password(payload.new_password)
    db.commit()


@router.post("/forgot-password", status_code=204)
def forgot_password(payload: schemas.ForgotPasswordIn, db: Session = Depends(get_db)):
    """Always returns 204 whether or not that email has an account -
    otherwise this endpoint would let anyone check which emails are
    registered. If it does exist, emails a one-time link valid for
    config.PASSWORD_RESET_EXPIRE_MINUTES.
    """
    user = db.query(models.User).filter(models.User.email == payload.email.lower()).first()
    if user is not None:
        token = generate_reset_token()
        user.reset_token = token
        user.reset_token_expires = dt.datetime.now(dt.timezone.utc) + dt.timedelta(
            minutes=config.PASSWORD_RESET_EXPIRE_MINUTES
        )
        db.commit()
        reset_link = f"{config.PASSWORD_RESET_URL_BASE}?reset_token={token}"
        get_email_provider().send(
            user.email, "Obnovení hesla v Mazlíkovi",
            "Ahoj,\n\nněkdo (doufejme ty) požádal o obnovení hesla. Odkaz platí "
            f"{config.PASSWORD_RESET_EXPIRE_MINUTES} minut:\n\n{reset_link}\n\n"
            "Pokud jsi o obnovení nežádal/a, nic se neděje - stačí tenhle e-mail ignorovat.\n\nMazlík",
        )


@router.post("/reset-password", status_code=204)
def reset_password(payload: schemas.ResetPasswordIn, db: Session = Depends(get_db)):
    user = (
        db.query(models.User)
        .filter(models.User.reset_token == payload.reset_token)
        .first()
    )
    now = dt.datetime.now(dt.timezone.utc)
    valid = (
        user is not None
        and user.reset_token_expires is not None
        and user.reset_token_expires.replace(tzinfo=dt.timezone.utc) > now
    )
    if not valid:
        raise HTTPException(400, "reset link is invalid or expired - request a new one")

    user.password_hash = hash_password(payload.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()


@router.post("/device-token", status_code=204)
def register_device_token(
    payload: schemas.DeviceTokenIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Called by the mobile app right after it gets an FCM registration
    token (see mobile-app's push-notifications.js), so the next daily tick
    can actually push to this device instead of just logging to the
    server console. An empty string clears it (e.g. on logout) so a stale
    token on a device the user signed out of doesn't keep receiving
    someone else's notifications.
    """
    current_user.fcm_token = payload.fcm_token or None
    db.commit()
