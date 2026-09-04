"""Space weather — NOAA SWPC (solar flares, geomagnetic storms, radio blackouts).

Space weather degrades HF comms, GPS accuracy and satellite operations, so it is
real context for an intelligence picture that already tracks flights, vessels and
orbital assets."""

import time

import requests
from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["space"])

KP = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
SCALES = "https://services.swpc.noaa.gov/products/noaa-scales.json"
ALERTS = "https://services.swpc.noaa.gov/products/alerts.json"
_cache: dict = {}
_TTL = 600


@router.get("/space-weather")
def space_weather():
    now = time.time()
    hit = _cache.get("sw")
    if hit and now - hit[0] < _TTL:
        return hit[1]

    out = {"kp": None, "kp_series": [], "scales": {}, "alerts": []}
    try:
        rows = requests.get(KP, timeout=15).json()  # [{"time_tag","Kp",...}, ...]
        series = []
        for r in rows:
            if isinstance(r, dict) and r.get("Kp") not in (None, ""):
                series.append({"t": r.get("time_tag"), "kp": float(r["Kp"])})
            elif isinstance(r, list) and len(r) > 1 and r[1] not in (None, "", "Kp"):
                series.append({"t": r[0], "kp": float(r[1])})
        out["kp_series"] = series[-24:]
        if series:
            out["kp"] = series[-1]["kp"]
    except (requests.RequestException, ValueError, TypeError, IndexError):
        pass

    try:
        sc = requests.get(SCALES, timeout=15).json()
        cur = sc.get("0") or {}
        out["scales"] = {
            "R": (cur.get("R") or {}).get("Scale"),
            "S": (cur.get("S") or {}).get("Scale"),
            "G": (cur.get("G") or {}).get("Scale"),
            "date": cur.get("DateStamp"),
        }
    except (requests.RequestException, ValueError):
        pass

    try:
        al = requests.get(ALERTS, timeout=15).json()
        for a in al[:6]:
            msg = (a.get("message") or "").replace("\r", "")
            head = next((ln for ln in msg.split("\n")
                         if ln.startswith(("ALERT:", "WARNING:", "WATCH:", "SUMMARY:"))), None)
            out["alerts"].append({"issued": a.get("issue_datetime"), "text": head or msg[:120]})
    except (requests.RequestException, ValueError):
        pass

    _cache["sw"] = (now, out)
    return out
