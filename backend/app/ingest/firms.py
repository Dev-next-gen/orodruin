"""NASA FIRMS active-fire ingester (global, all countries).

Free MAP_KEY: https://firms.modaps.eosdis.nasa.gov/api/map_key/
Area API CSV: /api/area/csv/{MAP_KEY}/{SOURCE}/world/{DAYS}

VIIRS CSV columns:
  latitude, longitude, bright_ti4, scan, track, acq_date, acq_time,
  satellite, instrument, confidence, version, bright_ti5, frp, daynight
"""

from __future__ import annotations

import csv
import io
from datetime import datetime

import requests
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import Fire

BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
COMMIT_EVERY = 1000


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fires_url(days: int = 1) -> str:
    return f"{BASE}/{settings.firms_map_key}/{settings.firms_source}/world/{days}"


def ingest_fires(days: int = 1) -> dict:
    if not settings.firms_map_key:
        return {"error": "FIRMS_MAP_KEY not set — add it to backend/.env"}

    r = requests.get(fires_url(days), timeout=180)
    r.raise_for_status()
    if r.text.lstrip().lower().startswith(("invalid", "<!doctype", "<html")):
        return {"error": "FIRMS rejected the key or request", "body": r.text[:160]}

    reader = csv.DictReader(io.StringIO(r.text))
    db = SessionLocal()
    seen = inserted = 0
    try:
        existing = set(db.execute(select(Fire.ext_key)).scalars().all())
        for row in reader:
            seen += 1
            lat = _f(row.get("latitude"))
            lon = _f(row.get("longitude"))
            if lat is None or lon is None:
                continue
            acq_date = (row.get("acq_date") or "").strip()
            acq_time = (row.get("acq_time") or "").strip().zfill(4)
            sat = (row.get("satellite") or "").strip()
            ext_key = f"{lat:.4f}|{lon:.4f}|{acq_date}|{acq_time}|{sat}"
            if ext_key in existing:
                continue
            try:
                dt = datetime.strptime(f"{acq_date} {acq_time}", "%Y-%m-%d %H%M")
            except ValueError:
                dt = None
            db.add(
                Fire(
                    ext_key=ext_key,
                    lat=lat,
                    lon=lon,
                    brightness=_f(row.get("bright_ti4")),
                    frp=_f(row.get("frp")),
                    confidence=(row.get("confidence") or "").strip() or None,
                    acq_datetime=dt,
                    satellite=sat or None,
                    daynight=(row.get("daynight") or "").strip() or None,
                    source=settings.firms_source,
                )
            )
            existing.add(ext_key)
            inserted += 1
            if inserted % COMMIT_EVERY == 0:
                db.commit()
        db.commit()
    finally:
        db.close()
    return {"source": settings.firms_source, "seen": seen, "inserted": inserted}
