"""Real-time alert feed — pushes the highest-severity items across all sources."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.flights import EMERGENCY_SQUAWKS, _cache as flights_cache
from app.cameo import root_label
from app.db import get_db
from app.models import Disaster, Event, Fire

router = APIRouter(prefix="/api", tags=["alerts"])


def _emergency_aircraft():
    hit = flights_cache.get("all")
    if not hit:
        return []
    out = []
    for s in (hit["data"].get("states") or []):
        squawk = s[14] if len(s) > 14 else None
        label = EMERGENCY_SQUAWKS.get(squawk)
        if label and s[5] is not None and s[6] is not None:
            out.append(
                {
                    "type": "aircraft",
                    "severity": 5,
                    "title": f"{(s[1] or s[0] or '').strip()} — {label} ({squawk})",
                    "place": s[2],
                    "lat": s[6],
                    "lon": s[5],
                    "time": None,
                    "source": "OpenSky",
                }
            )
    return out


@router.get("/alerts")
def alerts(
    db: Session = Depends(get_db),
    hours: int = Query(24, le=168),
    limit: int = Query(40, le=100),
):
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    out = []

    # 1) Material-conflict events (quad_class 4)
    evs = (
        db.execute(
            select(Event)
            .where(Event.quad_class == 4, Event.lat.isnot(None), Event.date_added >= cutoff)
            .order_by(Event.num_mentions.desc().nullslast(), Event.date_added.desc())
            .limit(limit)
        )
        .unique()
        .scalars()
        .all()
    )
    for e in evs:
        m = e.num_mentions or 0
        sev = 3 if m < 10 else 4 if m < 40 else 5
        a1 = e.actor1.name if e.actor1 else "?"
        a2 = e.actor2.name if e.actor2 else "?"
        out.append(
            {
                "type": "conflict",
                "severity": sev,
                "title": f"{root_label(e.event_root_code)}: {a1} → {a2}",
                "place": e.geo_fullname or e.geo_country,
                "lat": e.lat,
                "lon": e.lon,
                "time": e.date_added.isoformat() if e.date_added else None,
                "source": "GDELT",
                "link": e.source_url,
            }
        )

    # 2) GDACS Orange/Red disasters
    for d in db.execute(
        select(Disaster).where(
            Disaster.alert_level.in_(["Orange", "Red"]), Disaster.lat.isnot(None)
        ).limit(30)
    ).scalars().all():
        out.append(
            {
                "type": "disaster",
                "severity": 5 if d.alert_level == "Red" else 4,
                "title": f"{d.name or d.event_type} ({d.alert_level})",
                "place": d.country,
                "lat": d.lat,
                "lon": d.lon,
                "time": d.from_date,
                "source": "GDACS",
                "link": d.url,
            }
        )

    # 3) High-intensity fires (FRP)
    for f in db.execute(
        select(Fire)
        .where(Fire.frp.isnot(None), Fire.frp >= 100, Fire.acq_datetime >= cutoff)
        .order_by(Fire.frp.desc())
        .limit(15)
    ).scalars().all():
        out.append(
            {
                "type": "fire",
                "severity": 3,
                "title": f"Feu intense — {f.frp:.0f} MW",
                "place": f.satellite,
                "lat": f.lat,
                "lon": f.lon,
                "time": f.acq_datetime.isoformat() if f.acq_datetime else None,
                "source": "FIRMS",
            }
        )

    # 4) Emergency aircraft (live)
    out.extend(_emergency_aircraft())

    out.sort(key=lambda x: (-x["severity"], x.get("time") or ""), reverse=False)
    out.sort(key=lambda x: -x["severity"])
    return {"count": len(out), "alerts": out[:limit]}
