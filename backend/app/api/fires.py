from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Fire

router = APIRouter(prefix="/api", tags=["fires"])


def _fire_props(f: Fire) -> dict:
    return {
        "id": f.id,
        "brightness": f.brightness,
        "frp": f.frp,
        "confidence": f.confidence,
        "acq_datetime": f.acq_datetime.isoformat() if f.acq_datetime else None,
        "satellite": f.satellite,
        "daynight": f.daynight,
        "source": f.source,
    }


@router.get("/fires/geojson")
def fires_geojson(
    db: Session = Depends(get_db),
    limit: int = Query(8000, le=30000),
    bbox: str | None = None,
    min_frp: float | None = None,
):
    q = select(Fire)
    if min_frp is not None:
        q = q.where(Fire.frp >= min_frp)
    if bbox:
        try:
            w, s, e, n = (float(x) for x in bbox.split(","))
            q = q.where(Fire.lon >= w, Fire.lon <= e, Fire.lat >= s, Fire.lat <= n)
        except ValueError:
            pass
    q = q.order_by(Fire.acq_datetime.desc().nullslast()).limit(limit)
    fires = db.execute(q).scalars().all()
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [f.lon, f.lat]},
            "properties": _fire_props(f),
        }
        for f in fires
    ]
    return {"type": "FeatureCollection", "features": features}


@router.get("/fires/stats")
def fires_stats(db: Session = Depends(get_db)):
    total = db.execute(select(func.count(Fire.id))).scalar() or 0
    return {"fires": total}
