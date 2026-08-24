from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import create_access_token, get_current_user, hash_password, verify_password
from ..database import get_db

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
    return schemas.TokenOut(access_token=create_access_token(user.id))


@router.post("/login", response_model=schemas.TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Uses the standard OAuth2 password-flow form (username + password)
    so the auto-generated /docs page's "Authorize" button works out of the
    box - `username` here is the user's email.
    """
    user = db.query(models.User).filter(models.User.email == form.username.lower()).first()
    if user is None or not verify_password(form.password, user.password_hash):
        raise HTTPException(401, "incorrect email or password")
    return schemas.TokenOut(access_token=create_access_token(user.id))


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    out = schemas.UserOut.model_validate(current_user)
    out.has_saved_payment_method = bool(current_user.stripe_customer_id)
    return out


@router.post("/change-password", status_code=204)
def change_password(
    payload: schemas.ChangePasswordIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Requires the current password, same as any real account settings
    page - there's no separate "forgot password" flow (that needs an email
    provider to actually deliver a reset link, which is a bigger, separate
    integration - see docs/DEPLOYMENT.md's env var table for what's already
    configurable vs. not set up yet).
    """
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(401, "current password is incorrect")
    current_user.password_hash = hash_password(payload.new_password)
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
