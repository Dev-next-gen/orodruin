from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Vessel

router = APIRouter(prefix="/api", tags=["vessels"])

# AIS ship-type ranges -> label
def _type_label(t):
    if t is None:
        return "Unknown"
    if 60 <= t <= 69:
        return "Passenger"
    if 70 <= t <= 79:
        return "Cargo"
    if 80 <= t <= 89:
        return "Tanker"
    if 30 <= t <= 32:
        return "Fishing"
    if t in (35,):
        return "Military"
    if 40 <= t <= 49:
        return "High-speed"
    if 50 <= t <= 59:
        return "Special"
    return "Other"


@router.get("/vessels/geojson")
def vessels_geojson(
    db: Session = Depends(get_db),
    limit: int = Query(6000, le=20000),
    max_age_min: int = Query(60),
    bbox: str | None = None,
):
    cutoff = datetime.utcnow() - timedelta(minutes=max_age_min)
    q = select(Vessel).where(Vessel.updated_at >= cutoff, Vessel.lat.isnot(None))
    if bbox:
        try:
            w, s, e, n = (float(x) for x in bbox.split(","))
            q = q.where(Vessel.lon >= w, Vessel.lon <= e, Vessel.lat >= s, Vessel.lat <= n)
        except ValueError:
            pass
    q = q.order_by(Vessel.updated_at.desc()).limit(limit)
    rows = db.execute(q).scalars().all()
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [v.lon, v.lat]},
                "properties": {
                    "mmsi": v.mmsi,
                    "name": v.name,
                    "sog": v.sog,
                    "cog": v.cog,
                    "heading": v.heading,
                    "ship_type": v.ship_type,
                    "type_label": _type_label(v.ship_type),
                    "updated_at": v.updated_at.isoformat() if v.updated_at else None,
                },
            }
            for v in rows
        ],
    }


@router.get("/vessels/stats")
def vessels_stats(db: Session = Depends(get_db)):
    total = db.execute(select(func.count(Vessel.mmsi))).scalar() or 0
    cutoff = datetime.utcnow() - timedelta(minutes=15)
    recent = db.execute(
        select(func.count(Vessel.mmsi)).where(Vessel.updated_at >= cutoff)
    ).scalar() or 0
    return {"vessels": total, "recent_15min": recent}
