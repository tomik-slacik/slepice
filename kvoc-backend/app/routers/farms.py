from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import config, models, schemas
from ..database import get_db
from ..geo import haversine_km

router = APIRouter(prefix="/farms", tags=["farms"])


@router.get("", response_model=List[schemas.FarmOut])
def list_farms(
    lat: Optional[float] = Query(default=None, ge=-90, le=90),
    lng: Optional[float] = Query(default=None, ge=-180, le=180),
    radius_km: Optional[float] = Query(default=None, gt=0),
    db: Session = Depends(get_db),
):
    """Every farm always gets spots_left (see docs/LOGISTICS.md - a farm
    can only actually handle so many customers a week). lat/lng additionally
    adds a real, computed distance_km to each farm and sorts by it;
    radius_km (only meaningful together with lat/lng) drops farms further
    than that away instead of just sorting them to the bottom.
    """
    farms = db.query(models.Farm).all()
    offerings = db.query(models.FarmAnimalOffering).all()
    animals = db.query(models.Animal).all()

    out = []
    for f in farms:
        row = schemas.FarmOut.model_validate(f)
        row.spots_left = f.weekly_capacity - len(f.hens) if f.weekly_capacity is not None else None
        if lat is not None and lng is not None and f.lat is not None and f.lng is not None:
            row.distance_km = haversine_km(lat, lng, f.lat, f.lng)

        for o in offerings:
            if o.farm_id != f.id:
                continue
            unit_label = config.ANIMAL_PRODUCTS.get(o.species, {}).get(o.product, {}).get("unit_label", "")
            spots = None
            if o.weekly_capacity is not None:
                taken = sum(1 for a in animals if a.farm_id == f.id and a.species == o.species and a.product == o.product)
                spots = o.weekly_capacity - taken
            row.animal_offerings.append(schemas.FarmOfferingOut(
                species=o.species, product=o.product, unit_label=unit_label, spots_left=spots,
            ))
        out.append(row)

    if lat is None or lng is None:
        return out

    if radius_km is not None:
        out = [r for r in out if r.distance_km is not None and r.distance_km <= radius_km]
    out.sort(key=lambda r: (r.distance_km is None, r.distance_km))
    return out
