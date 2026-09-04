"""Routing — driving itinerary between two points with GPS-style info (distance,
travel time, live-traffic delay, ETA, estimated fuel cost). TomTom Routing API."""

import requests
from fastapi import APIRouter, Query

from app.config import settings

router = APIRouter(prefix="/api", tags=["route"])

BASE = "https://api.tomtom.com/routing/1/calculateRoute"


def _pt(s):
    lat, lon = (float(x) for x in s.split(","))
    return lat, lon


@router.get("/route")
def route(
    src: str = Query(..., alias="from", description="lat,lon"),
    dst: str = Query(..., alias="to", description="lat,lon"),
    travel_mode: str = Query("car"),
    consumption: float = Query(6.5, description="L/100km for fuel estimate"),
    fuel_price: float = Query(1.85, description="price per litre"),
):
    if not settings.tomtom_key:
        return {"error": "TOMTOM_KEY not set"}
    try:
        (la1, lo1), (la2, lo2) = _pt(src), _pt(dst)
    except ValueError:
        return {"error": "from/to must be lat,lon"}

    try:
        r = requests.get(
            f"{BASE}/{la1},{lo1}:{la2},{lo2}/json",
            params={"key": settings.tomtom_key, "traffic": "true",
                    "routeType": "fastest", "travelMode": travel_mode},
            timeout=25,
        )
        r.raise_for_status()
        data = r.json()
        route0 = data["routes"][0]
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return {"error": "route not found"}

    s = route0["summary"]
    coords = []
    for leg in route0.get("legs", []):
        for p in leg.get("points", []):
            coords.append([p["longitude"], p["latitude"]])

    dist_km = s["lengthInMeters"] / 1000
    liters = dist_km * consumption / 100 if travel_mode == "car" else None
    return {
        "distance_km": round(dist_km, 1),
        "time_min": round(s["travelTimeInSeconds"] / 60),
        "traffic_delay_min": round(s.get("trafficDelayInSeconds", 0) / 60),
        "departure": s.get("departureTime"),
        "arrival": s.get("arrivalTime"),
        "fuel_liters": round(liters, 1) if liters is not None else None,
        "fuel_cost": round(liters * fuel_price, 2) if liters is not None else None,
        "geometry": {"type": "Feature", "geometry": {"type": "LineString", "coordinates": coords}},
    }
