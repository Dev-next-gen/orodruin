"""Address geocoding — OpenStreetMap Nominatim (open, no key). Navigate to an address."""

import time

import requests
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api", tags=["geocode"])

URL = "https://nominatim.openstreetmap.org/search"
_last = {"t": 0.0}


@router.get("/geocode")
def geocode(q: str = Query(..., min_length=2), limit: int = Query(5, le=10)):
    # Nominatim asks for <=1 req/s and a descriptive User-Agent
    dt = time.time() - _last["t"]
    if dt < 1.0:
        time.sleep(1.0 - dt)
    _last["t"] = time.time()
    try:
        r = requests.get(
            URL,
            params={"q": q.strip(), "format": "jsonv2", "limit": limit, "addressdetails": 0},
            headers={"User-Agent": "osint-platform/1.0 (nextgen-labs.net)"},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError) as exc:
        return {"query": q, "results": [], "error": str(exc)}

    return {
        "query": q,
        "results": [
            {
                "name": d.get("display_name"),
                "lat": float(d["lat"]),
                "lon": float(d["lon"]),
                "type": d.get("type"),
                "importance": d.get("importance"),
            }
            for d in data
            if d.get("lat") and d.get("lon")
        ],
    }
