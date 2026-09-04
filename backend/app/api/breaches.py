"""Global data-breach tracker — Have I Been Pwned (HIBP) public breach database.

The legitimate index of known worldwide data breaches: name, date, number of
accounts and the data classes exposed (passwords, cards, etc.). Legal, public
source — unlike criminal leak forums, which this platform does not touch."""

import time

import requests
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api", tags=["breaches"])

URL = "https://haveibeenpwned.com/api/v3/breaches"
_cache: dict = {}
_TTL = 3600
UA = "osint-platform/1.0"


def _load():
    now = time.time()
    hit = _cache.get("all")
    if hit and now - hit[0] < _TTL:
        return hit[1]
    try:
        data = requests.get(URL, headers={"User-Agent": UA}, timeout=25).json()
        data.sort(key=lambda b: b.get("AddedDate", ""), reverse=True)
    except (requests.RequestException, ValueError):
        data = []
    _cache["all"] = (now, data)
    return data


def recent_breach_items(limit=40):
    """Breaches formatted as news-feed items (for the cyber news window)."""
    out = []
    for b in _load()[:limit]:
        classes = ", ".join(b.get("DataClasses", [])[:4])
        cnt = b.get("PwnCount", 0)
        out.append({
            "source": "HIBP",
            "title": f"Fuite : {b.get('Name')} — {cnt:,} comptes ({classes})",
            "link": f"https://haveibeenpwned.com/PwnedWebsites#{b.get('Name')}",
            "published": (b.get("AddedDate") or b.get("BreachDate") or ""),
        })
    return out


@router.get("/breaches")
def breaches(limit: int = Query(60, le=200), q: str = Query("")):
    data = _load()
    if q:
        ql = q.lower()
        data = [b for b in data if ql in (b.get("Name", "") + b.get("Domain", "")).lower()]
    return {
        "count": len(data),
        "breaches": [{
            "name": b.get("Name"), "domain": b.get("Domain"),
            "added": (b.get("AddedDate") or "")[:10], "breach_date": b.get("BreachDate"),
            "accounts": b.get("PwnCount"), "data_classes": b.get("DataClasses", []),
            "verified": b.get("IsVerified"),
        } for b in data[:limit]],
    }
