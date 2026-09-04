"""Global energy infrastructure — ~35,000 power plants worldwide (WRI Global Power
Plant Database): location, capacity, fuel type. A strategic OSINT layer (energy is
critical infrastructure), with strong coverage of Gulf/MENA oil & gas generation."""

import csv
import io
import time

import requests
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api", tags=["power"])

CSV_URL = ("https://raw.githubusercontent.com/wri/global-power-plant-database/"
           "master/output_database/global_power_plant_database.csv")
_cache: dict = {}
_TTL = 7 * 24 * 3600

FUEL_COLOR = {
    "Coal": "#6b7280", "Gas": "#d8973b", "Oil": "#8a5a2b", "Petcoke": "#8a5a2b",
    "Nuclear": "#e5484d", "Hydro": "#3fa7c8", "Solar": "#f0d020", "Wind": "#3fa870",
    "Geothermal": "#b048d8", "Biomass": "#7d9a3b", "Waste": "#9a7d3b",
    "Wave and Tidal": "#3fa7c8", "Storage": "#8b949e", "Cogeneration": "#d8973b",
}


def _load():
    now = time.time()
    hit = _cache.get("feats")
    if hit and now - hit[0] < _TTL:
        return hit[1]
    feats = []
    try:
        r = requests.get(CSV_URL, timeout=45)
        r.raise_for_status()
        reader = csv.DictReader(io.StringIO(r.text))
        for row in reader:
            try:
                lat = float(row["latitude"]); lon = float(row["longitude"])
                mw = float(row["capacity_mw"]) if row.get("capacity_mw") else 0.0
            except (ValueError, KeyError, TypeError):
                continue
            feats.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "name": row.get("name"), "mw": round(mw), "fuel": row.get("primary_fuel"),
                    "country": row.get("country_long"), "year": row.get("commissioning_year"),
                },
            })
    except (requests.RequestException, csv.Error):
        pass
    _cache["feats"] = (now, feats)
    return feats


@router.get("/powerplants/geojson")
def powerplants_geojson(
    bbox: str = Query("", description="minLon,minLat,maxLon,maxLat"),
    min_mw: float = Query(0),
    limit: int = Query(40000, le=40000),
):
    feats = _load()
    if min_mw:
        feats = [f for f in feats if (f["properties"]["mw"] or 0) >= min_mw]
    if bbox:
        try:
            x1, y1, x2, y2 = [float(v) for v in bbox.split(",")]
            feats = [f for f in feats
                     if x1 <= f["geometry"]["coordinates"][0] <= x2
                     and y1 <= f["geometry"]["coordinates"][1] <= y2]
        except ValueError:
            pass
    return {"type": "FeatureCollection", "count": len(feats), "features": feats[:limit]}


@router.get("/powerplants/fuel-colors")
def fuel_colors():
    return FUEL_COLOR
