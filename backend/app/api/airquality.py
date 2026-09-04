"""Atmospheric monitoring — Sentinel-5P (TROPOMI) via Copernicus CDSE. Global NO2,
methane, CO and aerosol columns as transparent overlay tiles. NO2 tracks traffic /
industrial / combustion activity; a strong OSINT signal for economic & military
tempo. Uses the same CDSE OAuth client as the Sentinel-2 layer."""

import time

import requests
from fastapi import APIRouter, Response

from app.api.satellite import PROCESS_URL, _get_token, _tile_bbox_3857

router = APIRouter(prefix="/api", tags=["airquality"])

# product -> (S5P band, max value for the colour ramp, recency days)
PRODUCTS = {
    "no2": ("NO2", 0.00018, 7),
    "co": ("CO", 0.05, 7),
    "ch4": ("CH4", 1900, 10),
    "aer": ("AER_AI_340_380", 3.0, 5),
}

_cache: dict = {}
_TTL = 3 * 3600


def _evalscript(band, vmax):
    # blue -> cyan -> green -> yellow -> red ramp, transparent where no data
    return (
        "//VERSION=3\n"
        f'function setup(){{return{{input:["{band}","dataMask"],output:{{bands:4}}}}}}\n'
        "function evaluatePixel(s){\n"
        f"  var v=s.{band}/{vmax};\n"
        "  v=Math.max(0,Math.min(1,v));\n"
        "  var r,g,b;\n"
        "  if(v<0.25){r=0;g=v*4*0.8;b=0.6+v*1.6;}\n"
        "  else if(v<0.5){r=0;g=0.8;b=0.8-(v-0.25)*3.2;}\n"
        "  else if(v<0.75){r=(v-0.5)*4;g=0.9;b=0;}\n"
        "  else {r=1;g=0.9-(v-0.75)*3.6;b=0;}\n"
        "  return [r,g,b, s.dataMask*0.65];\n"
        "}"
    )


@router.get("/airquality/{z}/{x}/{y}.png")
def tile(z: int, x: int, y: int, product: str = "no2"):
    band_info = PRODUCTS.get(product, PRODUCTS["no2"])
    band, vmax, days = band_info
    key = (product, z, x, y)
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < _TTL:
        return Response(content=hit[1], media_type="image/png")

    token = _get_token()
    if not token:
        return Response(status_code=204)

    frm = time.strftime("%Y-%m-%dT00:00:00Z", time.gmtime(now - days * 86400))
    to = time.strftime("%Y-%m-%dT00:00:00Z", time.gmtime(now))
    body = {
        "input": {
            "bounds": {"bbox": _tile_bbox_3857(z, x, y),
                       "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/3857"}},
            "data": [{
                "type": "sentinel-5p-l2",
                "dataFilter": {"timeRange": {"from": frm, "to": to}, "mosaickingOrder": "mostRecent"},
            }],
        },
        "output": {"width": 256, "height": 256,
                   "responses": [{"identifier": "default", "format": {"type": "image/png"}}]},
        "evalscript": _evalscript(band, vmax),
    }
    try:
        r = requests.post(PROCESS_URL,
                          headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                          json=body, timeout=40)
    except requests.RequestException:
        return Response(status_code=204)
    if r.status_code != 200:
        return Response(status_code=204)

    _cache[key] = (now, r.content)
    if len(_cache) > 3000:
        for k in list(_cache)[:1000]:
            _cache.pop(k, None)
    return Response(content=r.content, media_type="image/png")
