from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import City, Country, Region
router = APIRouter(prefix="/api/locations", tags=["locations"])

def item(row, code=None): return {"id": row.id, "name": row.name, "code": code}
@router.get("/countries")
def countries(db: Session = Depends(get_db)): return [item(x, x.code) for x in db.scalars(select(Country).where(Country.enabled.is_(True)).order_by(Country.name))]
@router.get("/countries/{country_id}/regions")
def regions(country_id: int, db: Session = Depends(get_db)): return [item(x) for x in db.scalars(select(Region).where(Region.country_id == country_id, Region.enabled.is_(True)).order_by(Region.name))]
@router.get("/regions/{region_id}/cities")
def cities(region_id: int, db: Session = Depends(get_db)): return [item(x) for x in db.scalars(select(City).where(City.region_id == region_id, City.enabled.is_(True)).order_by(City.name))]
