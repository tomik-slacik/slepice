"""Other livestock (goat/sheep/cow -> milk/wool) - see docs/LIVESTOCK.md.
Deliberately a near-mirror of routers/hens.py, generalized by species/
product instead of hardcoded to hens/eggs - see that file's own comments for
anything not re-explained here.

Known, honest gap: unlike Hen, Animal has no wallet top-up flow of its own
yet (no POST .../wallet/topup equivalent) - adopting one records the
subscription and the daily tick runs, but nothing charges a real card for
it yet. Wiring that in is straightforward (same payment provider, same
pattern as routers/wallet.py) but wasn't done in this pass - see
docs/LIVESTOCK.md.
"""
import datetime as dt
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import config, models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..tick import compute_animal_streak, compute_animal_week_balance, effective_today_for_animal, run_tick_for_animal

router = APIRouter(prefix="/animals", tags=["animals"])


def _get_owned_animal(animal_id: int, current_user: models.User, db: Session) -> models.Animal:
    animal = db.get(models.Animal, animal_id)
    if animal is None:
        raise HTTPException(404, "animal not found")
    if animal.user_id != current_user.id:
        raise HTTPException(404, "animal not found")  # see hens.py - same "don't confirm it exists" reasoning
    return animal


@router.get("/available-products", response_model=List[schemas.AvailableProductOut])
def available_products():
    """The full config.ANIMAL_PRODUCTS registry, flattened - lets a client
    build a species/product picker without hardcoding the list itself."""
    out = []
    for species, products in config.ANIMAL_PRODUCTS.items():
        for product, info in products.items():
            out.append(schemas.AvailableProductOut(
                species=species, product=product,
                unit=info["unit"], unit_label=info["unit_label"], kc_per_unit=info["kc_per_unit"],
            ))
    return out


@router.post("", response_model=schemas.AnimalOut, status_code=201)
def adopt_animal(
    payload: schemas.AnimalCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    valid_products = config.ANIMAL_PRODUCTS.get(payload.species)
    if valid_products is None or payload.product not in valid_products:
        raise HTTPException(400, f"'{payload.species}' doesn't make '{payload.product}' - see GET /animals/available-products")

    farm = db.query(models.Farm).filter(models.Farm.key == payload.farm_key).first()
    if farm is None:
        raise HTTPException(404, f"unknown farm_key '{payload.farm_key}'")

    offering = (
        db.query(models.FarmAnimalOffering)
        .filter(
            models.FarmAnimalOffering.farm_id == farm.id,
            models.FarmAnimalOffering.species == payload.species,
            models.FarmAnimalOffering.product == payload.product,
        )
        .first()
    )
    if offering is None:
        raise HTTPException(404, f"'{farm.name}' doesn't offer {payload.species}/{payload.product}")
    if offering.weekly_capacity is not None:
        current_count = (
            db.query(models.Animal)
            .filter(
                models.Animal.farm_id == farm.id,
                models.Animal.species == payload.species,
                models.Animal.product == payload.product,
            )
            .count()
        )
        if current_count >= offering.weekly_capacity:
            raise HTTPException(409, f"'{farm.name}' has no free capacity for {payload.species}/{payload.product} this week")

    animal = models.Animal(
        user_id=current_user.id,
        species=payload.species,
        product=payload.product,
        name=payload.name,
        farm_id=farm.id,
        daily_amount=payload.daily_amount,
        address=payload.address,
    )
    db.add(animal)
    db.commit()
    db.refresh(animal)

    run_tick_for_animal(db, animal, dt.date.today())
    db.refresh(animal)
    return animal


@router.get("", response_model=List[schemas.AnimalOut])
def list_my_animals(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.Animal).filter(models.Animal.user_id == current_user.id).all()


@router.get("/{animal_id}", response_model=schemas.AnimalOut)
def get_animal(animal_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_owned_animal(animal_id, current_user, db)


@router.patch("/{animal_id}", response_model=schemas.AnimalOut)
def update_animal(
    animal_id: int,
    payload: schemas.AnimalUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    animal = _get_owned_animal(animal_id, current_user, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(animal, field, value)
    db.commit()
    db.refresh(animal)
    return animal


@router.delete("/{animal_id}", status_code=204)
def cancel_animal(animal_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    animal = _get_owned_animal(animal_id, current_user, db)
    db.delete(animal)
    db.commit()


@router.get("/{animal_id}/wallet", response_model=schemas.AnimalWalletOut)
def get_animal_wallet(animal_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    animal = _get_owned_animal(animal_id, current_user, db)
    today = effective_today_for_animal(db, animal)
    return schemas.AnimalWalletOut(
        daily_amount=animal.daily_amount,
        week_balance=compute_animal_week_balance(db, animal, today),
        streak=compute_animal_streak(db, animal, today),
    )


@router.get("/{animal_id}/product-log", response_model=List[schemas.AnimalProductLogEntryOut])
def get_product_log(animal_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    animal = _get_owned_animal(animal_id, current_user, db)
    return list(reversed(animal.product_log))


@router.get("/{animal_id}/deliveries", response_model=List[schemas.AnimalDeliveryOut])
def get_animal_deliveries(animal_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    animal = _get_owned_animal(animal_id, current_user, db)
    return list(reversed(animal.deliveries))
