"""Real-time road traffic — TomTom Traffic Flow tile proxy (key stays server-side)."""

import time

import requests
from fastapi import APIRouter, Response

from app.config import settings

router = APIRouter(prefix="/api", tags=["traffic"])

# relative0 = colour by speed relative to free-flow (green→red)
TILE = "https://api.tomtom.com/traffic/map/4/tile/flow/relative0/{z}/{x}/{y}.png"
_cache: dict = {}
_TTL = 120  # traffic changes fast


@router.get("/traffic/{z}/{x}/{y}.png")
def traffic_tile(z: int, x: int, y: int):
    if not settings.tomtom_key:
        return Response(status_code=204)
    key = (z, x, y)
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < _TTL:
        return Response(content=hit[1], media_type="image/png")
    try:
        r = requests.get(TILE.format(z=z, x=x, y=y), params={"key": settings.tomtom_key}, timeout=20)
    except requests.RequestException:
        return Response(status_code=204)
    if r.status_code != 200:
        return Response(status_code=204)
    _cache[key] = (now, r.content)
    if len(_cache) > 4000:
        for k in list(_cache)[:1500]:
            _cache.pop(k, None)
    return Response(content=r.content, media_type="image/png")
