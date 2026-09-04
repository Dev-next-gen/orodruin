"""Satellites layer — real-time positions via SGP4 propagation of CelesTrak TLEs.

Free, no key. Fetches TLEs (station + bright/visual satellites), propagates to
the current instant, returns sub-satellite lat/lon points.
"""

import math
import time
from datetime import datetime, timezone

import requests
from fastapi import APIRouter, Query
from sgp4.api import Satrec, jday

router = APIRouter(prefix="/api", tags=["satellites"])

GROUPS = {
    "stations": "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle",
    "visual": "https://celestrak.org/NORAD/elements/gp.php?GROUP=visual&FORMAT=tle",
    "gps": "https://celestrak.org/NORAD/elements/gp.php?GROUP=gps-ops&FORMAT=tle",
}

_tle_cache: dict = {}
_TLE_TTL = 6 * 3600


def _fetch_tles(group):
    hit = _tle_cache.get(group)
    if hit and time.time() - hit["t"] < _TLE_TTL:
        return hit["data"]
    r = requests.get(GROUPS[group], timeout=30)
    r.raise_for_status()
    lines = [ln.rstrip() for ln in r.text.splitlines() if ln.strip()]
    sats = []
    for i in range(0, len(lines) - 2, 3):
        name, l1, l2 = lines[i], lines[i + 1], lines[i + 2]
        if l1.startswith("1 ") and l2.startswith("2 "):
            sats.append((name.strip(), l1, l2))
    _tle_cache[group] = {"t": time.time(), "data": sats}
    return sats


def _gmst_rad(jd, fr):
    T = ((jd - 2451545.0) + fr) / 36525.0
    sec = 67310.54841 + (876600 * 3600 + 8640184.812866) * T + 0.093104 * T * T - 6.2e-6 * T ** 3
    return (sec % 86400) / 86400.0 * 2 * math.pi


def _teme_to_latlon(r, gmst):
    x, y, z = r
    cg, sg = math.cos(gmst), math.sin(gmst)
    xe = x * cg + y * sg
    ye = -x * sg + y * cg
    lon = math.degrees(math.atan2(ye, xe))
    lat = math.degrees(math.atan2(z, math.sqrt(xe * xe + ye * ye)))
    alt = math.sqrt(xe * xe + ye * ye + z * z) - 6371.0
    return lat, lon, alt


@router.get("/satellites/geojson")
def satellites_geojson(groups: str = Query("stations,visual")):
    now = datetime.now(timezone.utc)
    jd, fr = jday(now.year, now.month, now.day, now.hour, now.minute, now.second + now.microsecond / 1e6)
    gmst = _gmst_rad(jd, fr)

    features = []
    seen = set()
    for g in groups.split(","):
        g = g.strip()
        if g not in GROUPS:
            continue
        try:
            sats = _fetch_tles(g)
        except requests.RequestException:
            continue
        for name, l1, l2 in sats:
            key = l1[2:7]  # NORAD id
            if key in seen:
                continue
            seen.add(key)
            try:
                sat = Satrec.twoline2rv(l1, l2)
                e, r, _ = sat.sgp4(jd, fr)
                if e != 0:
                    continue
                lat, lon, alt = _teme_to_latlon(r, gmst)
            except Exception:  # noqa: BLE001
                continue
            if not (math.isfinite(lat) and math.isfinite(lon)):
                continue
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": {
                        "name": name,
                        "norad": key,
                        "altitude_km": round(alt),
                        "group": g,
                    },
                }
            )
    return {"type": "FeatureCollection", "features": features}
