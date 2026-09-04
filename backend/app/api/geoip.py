"""IP geolocation — ip-api.com (free, no key). Plots any IP address on the map
with its city/country and network (ISP / org / ASN)."""

import time

import requests
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api", tags=["geoip"])

_cache: dict = {}
_TTL = 3600


@router.get("/geoip")
def geoip(ip: str = Query(..., description="IPv4/IPv6 address or hostname")):
    ip = ip.strip()
    hit = _cache.get(ip)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]
    try:
        r = requests.get(
            f"http://ip-api.com/json/{ip}",
            params={"fields": "status,message,country,countryCode,regionName,city,lat,lon,isp,org,as,query"},
            timeout=12,
        )
        d = r.json()
    except (requests.RequestException, ValueError):
        return {"found": False}

    if d.get("status") != "success":
        return {"found": False, "error": d.get("message", "lookup failed")}
    out = {
        "found": True, "ip": d.get("query"), "lat": d.get("lat"), "lon": d.get("lon"),
        "city": d.get("city"), "region": d.get("regionName"),
        "country": d.get("country"), "country_code": d.get("countryCode"),
        "isp": d.get("isp"), "org": d.get("org"), "asn": d.get("as"),
    }
    _cache[ip] = (time.time(), out)
    return out
