"""Internet backbone infrastructure — submarine cables and their landing points
(TeleGeography). The physical layer of the global network: the cables that link
continents and the stations where they come ashore. Powers a toggleable map layer
and a global network-status window."""

import time

import requests
from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["infra"])

CABLES = "https://www.submarinecablemap.com/api/v3/cable/cable-geo.json"
LANDING = "https://www.submarinecablemap.com/api/v3/landing-point/landing-point-geo.json"
_cache: dict = {}
_TTL = 24 * 3600  # infrastructure changes slowly
UA = "Mozilla/5.0 (X11; Linux x86_64) osint-platform"


def _get(url, key):
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < _TTL:
        return hit[1]
    try:
        data = requests.get(url, headers={"User-Agent": UA}, timeout=30).json()
    except (requests.RequestException, ValueError):
        data = {"type": "FeatureCollection", "features": []}
    _cache[key] = (now, data)
    return data


@router.get("/infra/cables")
def infra_cables():
    """Submarine cable routes (LineStrings), each with name + brand colour."""
    return _get(CABLES, "cables")


@router.get("/infra/landing")
def infra_landing():
    """Submarine cable landing points (where cables come ashore)."""
    return _get(LANDING, "landing")


@router.get("/infra/status")
def infra_status():
    """Global network-status summary for the floating status window."""
    cables = _get(CABLES, "cables")
    landing = _get(LANDING, "landing")
    # count distinct cable systems by name
    names = {f.get("properties", {}).get("name") for f in cables.get("features", [])}
    out = {
        "cable_systems": len([n for n in names if n]),
        "cable_segments": len(cables.get("features", [])),
        "landing_points": len(landing.get("features", [])),
    }
    # fold in space weather (affects HF/satcom) if available
    try:
        from app.api.spaceweather import space_weather
        sw = space_weather()
        out["space_weather"] = {"kp": sw.get("kp"), "scales": sw.get("scales"),
                                "alerts": len(sw.get("alerts", []))}
    except Exception:  # noqa: BLE001
        pass
    return out
