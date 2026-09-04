"""OpenSky Network — live aircraft (ADS-B). Free, anonymous (rate-limited).

https://opensky-network.org/api/states/all
State vector indices: 0 icao24, 1 callsign, 2 origin_country, 5 longitude,
6 latitude, 7 baro_altitude, 8 on_ground, 9 velocity (m/s), 10 true_track, 13 geo_altitude, 14 squawk.
"""

EMERGENCY_SQUAWKS = {"7500": "hijack", "7600": "radio failure", "7700": "emergency"}

import time

import requests
from fastapi import APIRouter, Query

from app.config import settings

router = APIRouter(prefix="/api", tags=["flights"])

URL = "https://opensky-network.org/api/states/all"
TOKEN_URL = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
_cache: dict = {}
_token: dict = {"v": None, "exp": 0}
_TTL = 30  # authenticated allows more frequent polling


def _auth_headers():
    if not (settings.opensky_client_id and settings.opensky_client_secret):
        return {}
    if _token["v"] and time.time() < _token["exp"] - 60:
        return {"Authorization": f"Bearer {_token['v']}"}
    try:
        r = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": settings.opensky_client_id,
                "client_secret": settings.opensky_client_secret,
            },
            timeout=20,
        )
        if r.status_code == 200:
            d = r.json()
            _token["v"] = d["access_token"]
            _token["exp"] = time.time() + int(d.get("expires_in", 1800))
            return {"Authorization": f"Bearer {_token['v']}"}
    except requests.RequestException:
        pass
    return {}


@router.get("/flights/geojson")
def flights_geojson(bbox: str | None = Query(None), limit: int = Query(8000, le=20000)):
    now = time.time()
    hit = _cache.get("all")
    if hit and now - hit["t"] < _TTL:
        raw = hit["data"]
    else:
        try:
            r = requests.get(URL, headers=_auth_headers(), timeout=25)
            if r.status_code == 200:
                raw = r.json()
                _cache["all"] = {"t": now, "data": raw}
            else:
                raw = hit["data"] if hit else {"states": []}
        except (requests.RequestException, ValueError):
            raw = hit["data"] if hit else {"states": []}

    box = None
    if bbox:
        try:
            box = [float(x) for x in bbox.split(",")]  # w,s,e,n
        except ValueError:
            box = None

    features = []
    for s in raw.get("states") or []:
        lon, lat = s[5], s[6]
        if lon is None or lat is None:
            continue
        if box and not (box[0] <= lon <= box[2] and box[1] <= lat <= box[3]):
            continue
        squawk = s[14] if len(s) > 14 else None
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "icao24": s[0],
                    "callsign": (s[1] or "").strip() or None,
                    "country": s[2],
                    "altitude_m": s[7] if s[7] is not None else s[13],
                    "on_ground": s[8],
                    "velocity_ms": s[9],
                    "track": s[10],
                    "squawk": squawk,
                    "emergency": EMERGENCY_SQUAWKS.get(squawk),
                },
            }
        )
        if len(features) >= limit:
            break
    return {"type": "FeatureCollection", "features": features}
