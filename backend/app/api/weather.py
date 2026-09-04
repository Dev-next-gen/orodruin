"""Weather — global precipitation radar (RainViewer, keyless animated tiles) and
point forecasts / wind (Open-Meteo, keyless). Feeds both a map layer and the AI
analyst, which can factor weather and wind into its situational synthesis."""

import time

import requests
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api", tags=["weather"])

_cache: dict = {}
_RADAR_TTL = 300
_PT_TTL = 600

WMO = {
    0: "Ciel clair", 1: "Peu nuageux", 2: "Partiellement nuageux", 3: "Couvert",
    45: "Brouillard", 48: "Brouillard givrant", 51: "Bruine légère", 53: "Bruine",
    55: "Bruine dense", 61: "Pluie légère", 63: "Pluie", 65: "Pluie forte",
    66: "Pluie verglaçante", 67: "Pluie verglaçante forte", 71: "Neige légère",
    73: "Neige", 75: "Neige forte", 77: "Grains de neige", 80: "Averses légères",
    81: "Averses", 82: "Averses violentes", 85: "Averses de neige", 86: "Averses de neige fortes",
    95: "Orage", 96: "Orage avec grêle", 99: "Orage avec forte grêle",
}


@router.get("/weather/radar")
def weather_radar():
    """Latest global precipitation-radar tile template (RainViewer, no key)."""
    now = time.time()
    hit = _cache.get("radar")
    if hit and now - hit[0] < _RADAR_TTL:
        return hit[1]
    try:
        d = requests.get("https://api.rainviewer.com/public/weather-maps.json", timeout=15).json()
        host = d["host"]
        frames = d["radar"]["past"] + d["radar"].get("nowcast", [])
        latest = frames[-1]
        # color 2 = universal, options 1_1 = smoothed + snow
        template = f"{host}{latest['path']}/256/{{z}}/{{x}}/{{y}}/2/1_1.png"
        out = {"tiles": template, "time": latest["time"],
               "frames": [{"time": f["time"], "path": f["path"]} for f in frames], "host": host}
    except (requests.RequestException, ValueError, KeyError, IndexError):
        out = {"tiles": None, "frames": []}
    _cache["radar"] = (now, out)
    return out


@router.get("/weather")
def weather(lat: float = Query(...), lon: float = Query(...)):
    """Current conditions + wind at a point (Open-Meteo, no key)."""
    key = f"{lat:.2f},{lon:.2f}"
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < _PT_TTL:
        return hit[1]
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,"
                           "weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m,pressure_msl,cloud_cover",
                "wind_speed_unit": "kmh",
            },
            timeout=15,
        )
        c = r.json().get("current", {})
    except (requests.RequestException, ValueError):
        return {"found": False}

    out = {
        "found": True, "lat": lat, "lon": lon,
        "temp": c.get("temperature_2m"), "feels_like": c.get("apparent_temperature"),
        "humidity": c.get("relative_humidity_2m"), "precip": c.get("precipitation"),
        "wind_speed": c.get("wind_speed_10m"), "wind_dir": c.get("wind_direction_10m"),
        "wind_gusts": c.get("wind_gusts_10m"), "pressure": c.get("pressure_msl"),
        "clouds": c.get("cloud_cover"), "code": c.get("weather_code"),
        "condition": WMO.get(c.get("weather_code"), "—"),
    }
    _cache[key] = (now, out)
    return out
