from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Disaster

router = APIRouter(prefix="/api", tags=["disasters"])

TYPE_LABEL = {
    "EQ": "Earthquake", "TC": "Cyclone", "FL": "Flood",
    "VO": "Volcano", "DR": "Drought", "WF": "Wildfire", "TS": "Tsunami",
}


@router.get("/disasters/geojson")
def disasters_geojson(
    db: Session = Depends(get_db),
    alert_level: str | None = None,
    event_type: str | None = None,
    limit: int = Query(500, le=2000),
):
    q = select(Disaster).where(Disaster.lat.isnot(None))
    if alert_level:
        q = q.where(Disaster.alert_level == alert_level)
    if event_type:
        q = q.where(Disaster.event_type == event_type)
    q = q.order_by(Disaster.updated_at.desc()).limit(limit)
    rows = db.execute(q).scalars().all()
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [d.lon, d.lat]},
                "properties": {
                    "id": d.id,
                    "event_type": d.event_type,
                    "type_label": TYPE_LABEL.get(d.event_type, d.event_type),
                    "alert_level": d.alert_level,
                    "name": d.name,
                    "country": d.country,
                    "from_date": d.from_date,
                    "severity": d.severity,
                    "url": d.url,
                },
            }
            for d in rows
        ],
    }


@router.get("/disasters/stats")
def disasters_stats(db: Session = Depends(get_db)):
    total = db.execute(select(func.count(Disaster.id))).scalar() or 0
    by_alert = dict(
        db.execute(
            select(Disaster.alert_level, func.count(Disaster.id)).group_by(Disaster.alert_level)
        ).all()
    )
    return {"disasters": total, "by_alert": by_alert}
