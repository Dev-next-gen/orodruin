"""USGS earthquakes — live proxy (free, no key, global, updated every minute)."""

import time

import requests
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api", tags=["quakes"])

FEEDS = {
    "2.5_day": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson",
    "4.5_day": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson",
    "significant_week": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_week.geojson",
    "2.5_week": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_week.geojson",
}

_cache: dict = {}
_TTL = 300  # 5 min


@router.get("/quakes/geojson")
def quakes_geojson(feed: str = Query("2.5_day")):
    url = FEEDS.get(feed, FEEDS["2.5_day"])
    now = time.time()
    hit = _cache.get(feed)
    if hit and now - hit["t"] < _TTL:
        return hit["data"]

    r = requests.get(url, timeout=30)
    r.raise_for_status()
    raw = r.json()

    features = []
    for f in raw.get("features", []):
        g = f.get("geometry") or {}
        coords = g.get("coordinates") or []
        if len(coords) < 2:
            continue
        p = f.get("properties") or {}
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [coords[0], coords[1]]},
                "properties": {
                    "id": f.get("id"),
                    "mag": p.get("mag"),
                    "place": p.get("place"),
                    "time": p.get("time"),  # epoch ms
                    "depth_km": coords[2] if len(coords) > 2 else None,
                    "tsunami": p.get("tsunami"),
                    "url": p.get("url"),
                },
            }
        )
    fc = {"type": "FeatureCollection", "features": features}
    _cache[feed] = {"t": now, "data": fc}
    return fc
