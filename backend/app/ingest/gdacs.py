"""GDACS disaster-alert ingester (open, no key).

https://www.gdacs.org/gdacsapi/api/events/geteventlist/EVENTS4APP
Global disaster alerts (earthquake, cyclone, flood, volcano, drought, wildfire)
scored green / orange / red.
"""

from __future__ import annotations

from datetime import datetime, timezone

import requests
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import SessionLocal
from app.models import Disaster

URL = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/EVENTS4APP"


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def ingest_gdacs() -> dict:
    r = requests.get(URL, timeout=30)
    r.raise_for_status()
    feats = r.json().get("features", [])

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = []
    for f in feats:
        p = f.get("properties", {}) or {}
        g = f.get("geometry", {}) or {}
        coords = g.get("coordinates") or [None, None]
        eid = f"{p.get('eventtype')}{p.get('eventid')}"
        url = p.get("url") or {}
        sev = p.get("severitydata") or {}
        rows.append(
            {
                "id": eid,
                "event_type": p.get("eventtype"),
                "alert_level": p.get("alertlevel"),
                "name": (p.get("name") or "")[:255] or None,
                "country": (p.get("country") or "")[:128] or None,
                "lon": _f(coords[0]),
                "lat": _f(coords[1]),
                "from_date": p.get("fromdate"),
                "severity": (sev.get("severitytext") or "")[:255] or None,
                "url": (url.get("report") or "")[:512] or None,
                "updated_at": now,
            }
        )

    if not rows:
        return {"inserted": 0}

    db = SessionLocal()
    try:
        stmt = pg_insert(Disaster).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Disaster.id],
            set_={
                "alert_level": stmt.excluded.alert_level,
                "name": stmt.excluded.name,
                "lat": stmt.excluded.lat,
                "lon": stmt.excluded.lon,
                "severity": stmt.excluded.severity,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        db.execute(stmt)
        db.commit()
        return {"events": len(rows)}
    finally:
        db.close()
