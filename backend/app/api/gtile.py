"""Google HD imagery — Map Tiles API 2D satellite proxy (needs Map Tiles API enabled).

Manages the Google session token server-side; serves XYZ tiles the map can overlay
for maximum detail at high zoom. Blank (204) until Map Tiles API + billing are enabled.
"""

import time

import requests
from fastapi import APIRouter, Response

from app.config import settings

router = APIRouter(prefix="/api", tags=["gtile"])

SESSION_URL = "https://tile.googleapis.com/v1/createSession"
TILE_URL = "https://tile.googleapis.com/v1/2dtiles/{z}/{x}/{y}"

_session = {"token": None, "exp": 0, "maxZoom": 20, "minZoom": 0}
_cache: dict = {}
_TTL = 6 * 3600


def _get_session():
    if _session["token"] and time.time() < _session["exp"] - 300:
        return _session["token"]
    if not settings.google_maps_key:
        return None
    try:
        r = requests.post(
            SESSION_URL,
            params={"key": settings.google_maps_key},
            json={"mapType": "satellite", "language": "en-US", "region": "US"},
            timeout=20,
        )
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    d = r.json()
    _session["token"] = d.get("session")
    _session["exp"] = time.time() + 3000
    # Google tells us the real available zoom range for this map type
    if d.get("maxZoom") is not None:
        _session["maxZoom"] = int(d["maxZoom"])
    if d.get("minZoom") is not None:
        _session["minZoom"] = int(d["minZoom"])
    return _session["token"]


@router.get("/gtile/meta")
def gtile_meta():
    """Zoom range of the current Google session (so the frontend can cap the layer)."""
    _get_session()
    return {"minZoom": _session["minZoom"], "maxZoom": _session["maxZoom"],
            "available": bool(_session["token"])}


@router.get("/gtile/{z}/{x}/{y}.png")
def gtile(z: int, x: int, y: int):
    key = (z, x, y)
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < _TTL:
        return Response(content=hit[1], media_type="image/jpeg")
    sess = _get_session()
    if not sess:
        return Response(status_code=204)
    # beyond Google's available zoom → 204 so MapLibre over-zooms the last sharp
    # tile instead of showing Google's "map data not yet available" placeholder
    if z > _session["maxZoom"]:
        return Response(status_code=204)
    try:
        r = requests.get(
            TILE_URL.format(z=z, x=x, y=y),
            params={"session": sess, "key": settings.google_maps_key},
            timeout=20,
        )
    except requests.RequestException:
        return Response(status_code=204)
    if r.status_code != 200:
        return Response(status_code=204)
    _cache[key] = (now, r.content)
    if len(_cache) > 3000:
        for k in list(_cache)[:1000]:
            _cache.pop(k, None)
    return Response(content=r.content, media_type=r.headers.get("content-type", "image/jpeg"))
