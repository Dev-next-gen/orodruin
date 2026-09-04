"""Cyber threat intelligence — live ransomware victim disclosures (ransomware.live).

Thousands of ransomware group leak-site posts, geolocated by victim country so
they plot on the map and feed the globe intel stream. A distinct OSINT pillar
(who is being hit, by which group, in which sector) alongside Shodan exposure."""

import hashlib
import time

import requests
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api", tags=["cyber"])

SRC = "https://data.ransomware.live/posts.json"
_cache: dict = {}
_TTL = 1800

# ISO2 country centroids (approx) for plotting victims by country
CENTROID = {
    "US": (39.8, -98.6), "CA": (56.1, -106.3), "MX": (23.6, -102.5), "BR": (-14.2, -51.9),
    "AR": (-38.4, -63.6), "CL": (-35.7, -71.5), "CO": (4.6, -74.3), "PE": (-9.2, -75.0),
    "GB": (54.0, -2.0), "IE": (53.4, -8.2), "FR": (46.6, 2.2), "DE": (51.2, 10.4),
    "ES": (40.0, -3.7), "PT": (39.6, -8.0), "IT": (41.9, 12.6), "NL": (52.1, 5.3),
    "BE": (50.6, 4.7), "CH": (46.8, 8.2), "AT": (47.6, 14.1), "SE": (60.1, 18.6),
    "NO": (60.5, 8.5), "FI": (61.9, 25.7), "DK": (56.3, 9.5), "PL": (51.9, 19.1),
    "CZ": (49.8, 15.5), "SK": (48.7, 19.7), "HU": (47.2, 19.5), "RO": (45.9, 24.9),
    "BG": (42.7, 25.5), "GR": (39.1, 21.8), "TR": (39.0, 35.2), "UA": (48.4, 31.2),
    "RU": (61.5, 105.3), "IL": (31.0, 34.9), "AE": (23.4, 53.8), "SA": (23.9, 45.1),
    "QA": (25.3, 51.2), "EG": (26.8, 30.8), "ZA": (-30.6, 22.9), "NG": (9.1, 8.7),
    "KE": (-0.0, 37.9), "MA": (31.8, -7.1), "IN": (20.6, 79.0), "PK": (30.4, 69.3),
    "BD": (23.7, 90.4), "CN": (35.9, 104.2), "JP": (36.2, 138.3), "KR": (35.9, 127.8),
    "TW": (23.7, 121.0), "HK": (22.3, 114.2), "SG": (1.35, 103.8), "MY": (4.2, 101.98),
    "TH": (15.9, 100.99), "VN": (14.1, 108.3), "ID": (-0.8, 113.9), "PH": (12.9, 121.8),
    "AU": (-25.3, 133.8), "NZ": (-40.9, 174.9), "CR": (9.7, -83.8), "PA": (8.5, -80.8),
    "EC": (-1.8, -78.2), "UY": (-32.5, -55.8), "VE": (6.4, -66.6), "DO": (18.7, -70.2),
    "GT": (15.8, -90.2), "LU": (49.8, 6.1), "IS": (64.9, -19.0), "HR": (45.1, 15.2),
    "RS": (44.0, 21.0), "SI": (46.2, 15.0), "LT": (55.2, 23.9), "LV": (56.9, 24.6),
    "EE": (58.6, 25.0), "CY": (35.1, 33.4), "MT": (35.9, 14.4),
}


def _centroid(cc, seed):
    base = CENTROID.get((cc or "").upper())
    if not base:
        return None
    # deterministic jitter (±~1.2°) so multiple victims per country don't overlap
    h = int(hashlib.md5(seed.encode()).hexdigest(), 16)
    dlat = ((h % 1000) / 1000 - 0.5) * 2.4
    dlon = (((h >> 10) % 1000) / 1000 - 0.5) * 2.4
    return (base[0] + dlat, base[1] + dlon)


def _load(limit):
    now = time.time()
    hit = _cache.get("posts")
    if hit and now - hit[0] < _TTL:
        return hit[1]
    try:
        posts = requests.get(SRC, timeout=30).json()
    except (requests.RequestException, ValueError):
        return []
    posts.sort(key=lambda p: p.get("discovered") or "", reverse=True)
    _cache["posts"] = (now, posts)
    return posts


@router.get("/ransomware")
def ransomware(limit: int = Query(120, le=400), geo: bool = Query(True)):
    posts = _load(limit)[: limit * 3]  # oversample; many lack a mappable country
    if not geo:
        out = [{
            "victim": p.get("post_title"), "group": p.get("group_name"),
            "country": p.get("country"), "sector": p.get("activity"),
            "discovered": (p.get("discovered") or "")[:10],
        } for p in posts[:limit]]
        return {"count": len(out), "victims": out}

    feats = []
    for p in posts:
        pt = _centroid(p.get("country"), p.get("post_title") or p.get("post_url") or "")
        if not pt:
            continue
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [pt[1], pt[0]]},
            "properties": {
                "victim": p.get("post_title"), "group": p.get("group_name"),
                "country": p.get("country"), "sector": p.get("activity"),
                "discovered": (p.get("discovered") or "")[:10],
            },
        })
        if len(feats) >= limit:
            break
    return {"type": "FeatureCollection", "features": feats}
