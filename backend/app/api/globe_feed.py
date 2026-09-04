"""Consolidated globe feed — a diverse mix of geolocated live items for the 3D globe
notifications: general GDELT events, earthquakes, natural events, disasters, fires."""

import random

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.eonet import eonet_geojson
from app.api.quakes import quakes_geojson
from app.cameo import root_label
from app.db import get_db
from app.models import Disaster, Event, Fire

router = APIRouter(prefix="/api", tags=["globe"])


@router.get("/globe-feed")
def globe_feed(db: Session = Depends(get_db), limit: int = Query(120, le=250)):
    items = []

    # 1) general GDELT events (all classes → diversity), random-ish recent sample
    evs = db.execute(
        select(Event)
        .where(Event.lat.isnot(None))
        .order_by(func.random())
        .limit(70)
    ).unique().scalars().all()
    for e in evs:
        a1 = e.actor1.name if e.actor1 else None
        a2 = e.actor2.name if e.actor2 else None
        who = " → ".join([x for x in (a1, a2) if x]) or (e.geo_fullname or e.geo_country or "")
        sev = 5 if e.quad_class == 4 else 4 if e.quad_class == 3 else 3
        items.append({
            "title": f"{root_label(e.event_root_code)}: {who}"[:90],
            "lat": e.lat, "lon": e.lon, "sev": sev, "type": "event", "url": e.source_url,
        })

    # 2) GDACS disasters
    for d in db.execute(
        select(Disaster).where(Disaster.lat.isnot(None)).order_by(func.random()).limit(20)
    ).scalars().all():
        sev = 5 if d.alert_level == "Red" else 4 if d.alert_level == "Orange" else 3
        items.append({
            "title": f"{d.name or d.event_type} ({d.alert_level})"[:90],
            "lat": d.lat, "lon": d.lon, "sev": sev, "type": "disaster", "url": d.url,
        })

    # 3) intense fires
    for f in db.execute(
        select(Fire).where(Fire.frp.isnot(None), Fire.frp >= 80).order_by(func.random()).limit(12)
    ).scalars().all():
        items.append({
            "title": f"Feu {f.frp:.0f} MW ({f.satellite or 'VIIRS'})",
            "lat": f.lat, "lon": f.lon, "sev": 4, "type": "fire",
        })

    # 4) earthquakes (live proxy)
    try:
        for ft in quakes_geojson(feed="2.5_day").get("features", [])[:25]:
            p = ft["properties"]
            lon, lat = ft["geometry"]["coordinates"]
            mag = p.get("mag") or 0
            sev = 5 if mag >= 5.5 else 4 if mag >= 4 else 3
            items.append({
                "title": f"M{mag:.1f} — {p.get('place', '')}"[:90],
                "lat": lat, "lon": lon, "sev": sev, "type": "quake", "url": p.get("url"),
            })
    except Exception:  # noqa: BLE001
        pass

    # 5) live ransomware attacks (cyber pillar), geolocated by victim country
    try:
        from app.api.cyberthreat import ransomware as _rw
        for ft in _rw(limit=25, geo=True).get("features", [])[:18]:
            p = ft["properties"]
            lon, lat = ft["geometry"]["coordinates"]
            items.append({
                "title": f"Ransomware {p.get('group', '')}: {p.get('victim', '')}"[:90],
                "lat": lat, "lon": lon, "sev": 4, "type": "cyber",
            })
    except Exception:  # noqa: BLE001
        pass

    # 6) natural events (EONET)
    try:
        for ft in eonet_geojson(status="open", limit=60).get("features", [])[:20]:
            p = ft["properties"]
            lon, lat = ft["geometry"]["coordinates"]
            items.append({
                "title": f"{p.get('title', '')}"[:90],
                "lat": lat, "lon": lon, "sev": 3, "type": "nature", "url": p.get("link"),
            })
    except Exception:  # noqa: BLE001
        pass

    random.shuffle(items)
    return {"count": len(items), "items": items[:limit]}
