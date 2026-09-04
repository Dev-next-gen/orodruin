"""Threat hotspot detection — weighted spatial aggregation of recent events."""

from collections import Counter
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Event, Fire

# QuadClass weights: material conflict dominates the threat score.
WEIGHT = {4: 5.0, 3: 2.0, 2: 1.0, 1: 0.6}

router = APIRouter(prefix="/api", tags=["hotspots"])


@router.get("/hotspots")
def hotspots(
    db: Session = Depends(get_db),
    window_hours: int = Query(48, le=720),
    limit: int = Query(12, le=50),
    cell: float = Query(2.0),
    include_fires: bool = Query(True),
):
    cutoff = datetime.utcnow() - timedelta(hours=window_hours)
    rows = db.execute(
        select(
            Event.lat, Event.lon, Event.quad_class,
            Event.geo_country, Event.geo_fullname, Event.num_mentions,
        )
        .where(Event.lat.isnot(None), Event.date_added >= cutoff)
        .order_by(Event.date_added.desc())
        .limit(25000)
    ).all()

    cells: dict = {}

    def _cell(lat, lon):
        return (round(lat / cell) * cell, round(lon / cell) * cell)

    for lat, lon, qc, country, place, mentions in rows:
        key = _cell(lat, lon)
        c = cells.setdefault(
            key, {"score": 0.0, "events": 0, "fires": 0, "countries": Counter(), "places": Counter()}
        )
        boost = 1.0 + min(mentions or 0, 30) / 30.0
        c["score"] += WEIGHT.get(qc, 1.0) * boost
        c["events"] += 1
        if country:
            c["countries"][country] += 1
        if place:
            c["places"][place] += 1

    if include_fires:
        fire_cut = datetime.utcnow() - timedelta(hours=min(window_hours, 72))
        for lat, lon, frp in db.execute(
            select(Fire.lat, Fire.lon, Fire.frp).where(
                Fire.lat.isnot(None), Fire.acq_datetime >= fire_cut
            )
        ).all():
            key = _cell(lat, lon)
            c = cells.get(key)
            if c is not None:  # only reinforce cells that already have events
                c["fires"] += 1
                c["score"] += 0.3 + min(frp or 0, 100) / 100.0

    out = []
    for (gy, gx), c in cells.items():
        out.append(
            {
                "lat": round(gy, 3),
                "lon": round(gx, 3),
                "score": round(c["score"], 1),
                "events": c["events"],
                "fires": c["fires"],
                "country": c["countries"].most_common(1)[0][0] if c["countries"] else None,
                "place": c["places"].most_common(1)[0][0] if c["places"] else None,
            }
        )
    out.sort(key=lambda x: -x["score"])
    return {"window_hours": window_hours, "hotspots": out[:limit]}
