"""NASA EONET — natural events (storms, volcanoes, floods, wildfires...).

Open, no API key. https://eonet.gsfc.nasa.gov/api/v3/events
Live proxy with a short cache; returns the most recent point per event.
"""

import time

import requests
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api", tags=["eonet"])

URL = "https://eonet.gsfc.nasa.gov/api/v3/events"
_cache: dict = {}
_TTL = 600  # 10 min


def _last_point(geoms):
    if not geoms:
        return None
    g = geoms[-1]
    t, c = g.get("type"), g.get("coordinates")
    date = g.get("date")
    if t == "Point" and isinstance(c, list) and len(c) >= 2:
        return c[0], c[1], date
    if t == "Polygon" and c:
        ring = c[0]
        xs = [p[0] for p in ring if len(p) >= 2]
        ys = [p[1] for p in ring if len(p) >= 2]
        if xs and ys:
            return sum(xs) / len(xs), sum(ys) / len(ys), date
    return None


@router.get("/eonet/geojson")
def eonet_geojson(status: str = Query("open"), limit: int = Query(500, le=1000)):
    key = f"{status}:{limit}"
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit["t"] < _TTL:
        return hit["data"]

    r = requests.get(URL, params={"status": status, "limit": limit}, timeout=30)
    r.raise_for_status()
    events = r.json().get("events", [])

    features = []
    for e in events:
        pt = _last_point(e.get("geometry", []))
        if not pt:
            continue
        lon, lat, date = pt
        cats = e.get("categories", []) or [{}]
        sources = e.get("sources", []) or []
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "id": e.get("id"),
                    "title": e.get("title"),
                    "category": cats[0].get("title"),
                    "category_id": cats[0].get("id"),
                    "date": date,
                    "link": (sources[0].get("url") if sources else None) or e.get("link"),
                },
            }
        )
    fc = {"type": "FeatureCollection", "features": features}
    _cache[key] = {"t": now, "data": fc}
    return fc
