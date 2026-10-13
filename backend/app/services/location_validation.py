"""Shared location validation for registration and billing."""
from fastapi import HTTPException
from sqlalchemy import select
from ..models import Country, Region, City


def validate_locations(db, country_id, region_id, city_id):
    if country_id is None:
        if region_id is not None or city_id is not None:
            raise HTTPException(422, "Choose a country before region or city")
        return
    country = db.scalar(select(Country).where(Country.id == country_id, Country.enabled.is_(True)))
    if not country: raise HTTPException(422, "Invalid country")
    region = None
    if region_id is not None:
        region = db.scalar(select(Region).where(Region.id == region_id, Region.country_id == country_id, Region.enabled.is_(True)))
        if not region: raise HTTPException(422, "Invalid region")
    if city_id is not None:
        if region is None or not db.scalar(select(City).where(City.id == city_id, City.region_id == region.id, City.enabled.is_(True))):
            raise HTTPException(422, "Invalid city")
