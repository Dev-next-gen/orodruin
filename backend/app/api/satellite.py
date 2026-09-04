"""Sentinel-2 satellite imagery — authenticated XYZ tile proxy (Sentinel Hub / CDSE).

Backend holds the OAuth token; serves true-color 256px JPEG tiles the map can use
as a raster source at /api/satellite/{z}/{x}/{y}.jpg.
"""

import math
import time
from datetime import datetime, timedelta, timezone

import requests
from fastapi import APIRouter, Response

from app.config import settings

router = APIRouter(prefix="/api", tags=["satellite"])

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"
R = 6378137.0

EVALSCRIPT = (
    "//VERSION=3\n"
    'function setup(){return{input:["B02","B03","B04"],output:{bands:3}}}\n'
    "function evaluatePixel(s){return [2.5*s.B04,2.5*s.B03,2.5*s.B02]}"
)

_token = {"v": None, "exp": 0}
_cache: dict = {}
_TTL = 6 * 3600


def _get_token():
    if _token["v"] and time.time() < _token["exp"] - 60:
        return _token["v"]
    if not (settings.sentinelhub_client_id and settings.sentinelhub_client_secret):
        return None
    r = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": settings.sentinelhub_client_id,
            "client_secret": settings.sentinelhub_client_secret,
        },
        timeout=30,
    )
    r.raise_for_status()
    d = r.json()
    _token["v"] = d["access_token"]
    _token["exp"] = time.time() + int(d.get("expires_in", 1800))
    return _token["v"]


def _tile_bbox_3857(z, x, y):
    n = 2 ** z
    span = 2 * math.pi * R
    west = x / n * span - math.pi * R
    east = (x + 1) / n * span - math.pi * R
    north = math.pi * R - y / n * span
    south = math.pi * R - (y + 1) / n * span
    return [west, south, east, north]


@router.get("/satellite/{z}/{x}/{y}.jpg")
def tile(z: int, x: int, y: int):
    key = (z, x, y)
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < _TTL:
        return Response(content=hit[1], media_type="image/jpeg")

    token = _get_token()
    if not token:
        return Response(status_code=204)

    to = datetime.now(timezone.utc)
    frm = to - timedelta(days=120)
    body = {
        "input": {
            "bounds": {
                "bbox": _tile_bbox_3857(z, x, y),
                "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/3857"},
            },
            "data": [
                {
                    "type": "sentinel-2-l2a",
                    "dataFilter": {
                        "timeRange": {
                            "from": frm.strftime("%Y-%m-%dT00:00:00Z"),
                            "to": to.strftime("%Y-%m-%dT00:00:00Z"),
                        },
                        "mosaickingOrder": "leastCC",
                    },
                }
            ],
        },
        "output": {
            "width": 256,
            "height": 256,
            "responses": [{"identifier": "default", "format": {"type": "image/jpeg"}}],
        },
        "evalscript": EVALSCRIPT,
    }
    try:
        r = requests.post(
            PROCESS_URL,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=body,
            timeout=40,
        )
    except requests.RequestException:
        return Response(status_code=204)
    if r.status_code != 200:
        return Response(status_code=204)

    _cache[key] = (now, r.content)
    if len(_cache) > 3000:
        for k in list(_cache)[:1000]:
            _cache.pop(k, None)
    return Response(content=r.content, media_type="image/jpeg")
