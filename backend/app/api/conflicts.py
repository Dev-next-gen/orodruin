from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Conflict

router = APIRouter(prefix="/api", tags=["conflicts"])


def _props(c: Conflict) -> dict:
    return {
        "id": c.id,
        "event_date": c.event_date,
        "event_type": c.event_type,
        "sub_event_type": c.sub_event_type,
        "actor1": c.actor1,
        "actor2": c.actor2,
        "country": c.country,
        "admin1": c.admin1,
        "location": c.location,
        "fatalities": c.fatalities,
        "notes": c.notes,
        "src": c.src,
    }


@router.get("/conflicts/geojson")
def conflicts_geojson(
    db: Session = Depends(get_db),
    limit: int = Query(8000, le=30000),
    event_type: str | None = None,
    country: str | None = None,
    min_fatalities: int | None = None,
):
    q = select(Conflict).where(Conflict.lat.isnot(None))
    if event_type:
        q = q.where(Conflict.event_type == event_type)
    if country:
        q = q.where(Conflict.country == country)
    if min_fatalities is not None:
        q = q.where(Conflict.fatalities >= min_fatalities)
    q = q.order_by(Conflict.event_date.desc().nullslast()).limit(limit)
    rows = db.execute(q).scalars().all()
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [c.lon, c.lat]},
                "properties": _props(c),
            }
            for c in rows
        ],
    }


@router.get("/conflicts/stats")
def conflicts_stats(db: Session = Depends(get_db)):
    total = db.execute(select(func.count(Conflict.id))).scalar() or 0
    by_type = dict(
        db.execute(
            select(Conflict.event_type, func.count(Conflict.id))
            .group_by(Conflict.event_type)
            .order_by(func.count(Conflict.id).desc())
        ).all()
    )
    return {"conflicts": total, "by_type": by_type}
