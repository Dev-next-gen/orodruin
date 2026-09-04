"""Global weather tiles — OpenWeatherMap (wind, temperature, clouds, pressure)
proxied so the key stays server-side. Planet-wide coverage, unlike the RainViewer
precipitation radar. Requires a free OpenWeatherMap key (Settings)."""

import time

import requests
from fastapi import APIRouter, Response

from app.config import settings

router = APIRouter(prefix="/api", tags=["wxtiles"])

LAYERS = {
    "wind": "wind_new", "temp": "temp_new", "clouds": "clouds_new",
    "pressure": "pressure_new", "precip": "precipitation_new",
}
_cache: dict = {}
_TTL = 900


@router.get("/wxtiles/{layer}/{z}/{x}/{y}.png")
def wx_tile(layer: str, z: int, x: int, y: int):
    owm = LAYERS.get(layer)
    if not owm or not settings.openweather_key:
        return Response(status_code=204)
    key = (layer, z, x, y)
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < _TTL:
        return Response(content=hit[1], media_type="image/png")
    try:
        r = requests.get(
            f"https://tile.openweathermap.org/map/{owm}/{z}/{x}/{y}.png",
            params={"appid": settings.openweather_key}, timeout=20,
        )
    except requests.RequestException:
        return Response(status_code=204)
    if r.status_code != 200:
        return Response(status_code=204)
    _cache[key] = (now, r.content)
    if len(_cache) > 4000:
        for k in list(_cache)[:1500]:
            _cache.pop(k, None)
    return Response(content=r.content, media_type="image/png")
