"""Road hazards layer (Waze-equivalent) — worldwide accidents, closures, jams and
hazards via TomTom Traffic Incidents, plus fixed speed cameras via OpenStreetMap.

Waze's own live-map georss blocks datacenter IPs (403), so we source the same
categories of data — accidents, controls/hazards, closures, radars — from APIs
that respond reliably server-side."""

import time

import requests
from fastapi import APIRouter, Query

from app.config import settings

router = APIRouter(prefix="/api", tags=["roads"])

# TomTom incident iconCategory -> (label, severity 3..5)
ICON = {
    0: ("Incident", 3), 1: ("Accident", 5), 2: ("Brouillard", 3), 3: ("Conditions dangereuses", 4),
    4: ("Pluie", 3), 5: ("Verglas", 4), 6: ("Embouteillage", 3), 7: ("Voie fermée", 4),
    8: ("Route fermée", 4), 9: ("Travaux", 3), 10: ("Vent", 3), 11: ("Inondation", 4),
    14: ("Véhicule en panne", 3),
}

# Overpass main is often overloaded; try mirrors in order with a short timeout.
OVERPASS_MIRRORS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

_inc_cache: dict[str, tuple[float, dict]] = {}
_cam_cache: dict[str, tuple[float, dict]] = {}
_INC_TTL = 120
_CAM_TTL = 1800


def _bbox(bbox: str):
    p = [float(x) for x in bbox.split(",")]
    if len(p) != 4:
        raise ValueError("bbox must be minLon,minLat,maxLon,maxLat")
    return p


@router.get("/roads/incidents")
def incidents(bbox: str = Query(..., description="minLon,minLat,maxLon,maxLat")):
    """Live accidents, closures, jams and hazards (TomTom) as GeoJSON points."""
    if not settings.tomtom_key:
        return {"type": "FeatureCollection", "features": []}
    key = bbox
    now = time.time()
    hit = _inc_cache.get(key)
    if hit and now - hit[0] < _INC_TTL:
        return hit[1]

    lon1, lat1, lon2, lat2 = _bbox(bbox)
    fields = "{incidents{type,geometry{type,coordinates},properties{iconCategory,magnitudeOfDelay,events{description,code}}}}"
    try:
        r = requests.get(
            "https://api.tomtom.com/traffic/services/5/incidentDetails",
            params={
                "key": settings.tomtom_key,
                "bbox": f"{lon1},{lat1},{lon2},{lat2}",
                "fields": fields,
                "language": "fr-FR",
                "categoryFilter": "0,1,2,3,4,5,6,7,8,9,10,11,14",
                "timeValidityFilter": "present",
            },
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
    except requests.RequestException:
        return {"type": "FeatureCollection", "features": []}

    feats = []
    for it in data.get("incidents", []):
        geom = it.get("geometry") or {}
        coords = geom.get("coordinates") or []
        if not coords:
            continue
        # reduce a LineString to its mid vertex so it plots as one marker
        if geom.get("type") == "LineString":
            pt = coords[len(coords) // 2]
        else:
            pt = coords
        if not (isinstance(pt, list) and len(pt) >= 2):
            continue
        pr = it.get("properties") or {}
        icon = pr.get("iconCategory", 0)
        label, sev = ICON.get(icon, ("Incident", 3))
        evs = pr.get("events") or []
        desc = evs[0].get("description") if evs else label
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [pt[0], pt[1]]},
            "properties": {"kind": "incident", "icon": icon, "label": label,
                           "desc": desc, "sev": sev, "delay": pr.get("magnitudeOfDelay")},
        })
    out = {"type": "FeatureCollection", "features": feats}
    _inc_cache[key] = (now, out)
    return out


@router.get("/roads/speedcams")
def speedcams(bbox: str = Query(..., description="minLon,minLat,maxLon,maxLat")):
    """Fixed speed cameras (radars) worldwide via OpenStreetMap Overpass."""
    lon1, lat1, lon2, lat2 = _bbox(bbox)
    # Overpass is expensive on huge areas; cap the span.
    if (lon2 - lon1) > 4 or (lat2 - lat1) > 4:
        return {"type": "FeatureCollection", "features": [], "note": "zoom in for radars"}
    key = f"{lon1:.2f},{lat1:.2f},{lon2:.2f},{lat2:.2f}"
    now = time.time()
    hit = _cam_cache.get(key)
    if hit and now - hit[0] < _CAM_TTL:
        return hit[1]

    q = (f"[out:json][timeout:12];node[highway=speed_camera]"
         f"({lat1},{lon1},{lat2},{lon2});out body 400;")
    els = None
    for mirror in OVERPASS_MIRRORS:
        try:
            r = requests.post(
                mirror, data={"data": q},
                headers={"User-Agent": "osint-platform/1.0 (research)", "Accept": "application/json"},
                timeout=14,
            )
            if r.status_code == 200:
                els = r.json().get("elements", [])
                break
        except (requests.RequestException, ValueError):
            continue
    if els is None:
        # don't cache upstream failures; let the next call retry
        return {"type": "FeatureCollection", "features": []}

    feats = []
    for e in els:
        if e.get("lat") is None or e.get("lon") is None:
            continue
        tags = e.get("tags") or {}
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [e["lon"], e["lat"]]},
            "properties": {"kind": "radar", "maxspeed": tags.get("maxspeed"),
                           "role": tags.get("speed_camera") or tags.get("enforcement")},
        })
    out = {"type": "FeatureCollection", "features": feats}
    _cam_cache[key] = (now, out)
    return out
