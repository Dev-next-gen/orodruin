"""Public camera aggregator — thousands of geolocated live public traffic cameras
worldwide, from open government/agency feeds (no key) plus Windy webcams.

Each camera is normalized to a common shape and carries a directly-loadable media
URL, so the map can plot it at its exact position and the player can show it:
  image  -> refreshing JPEG snapshot
  stream -> HLS (.m3u8) live video
  mp4    -> short rolling MP4 clip (TfL)
  embed  -> iframe player (Windy)

Sources (all verified): TfL JamCams (London), Caltrans CCTV (California, 12
districts), DriveBC (British Columbia), LTA/data.gov.sg (Singapore), NZTA (New
Zealand), Windy Webcams (global gap-filler)."""

import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

import requests
from fastapi import APIRouter, Query

from app.config import settings

router = APIRouter(prefix="/api", tags=["cameras"])

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
_cache: dict = {}
_TTL = 900  # camera lists are near-static; the images refresh client-side


def _feat(cid, title, lat, lon, source, kind="traffic", image=None, stream=None, mp4=None, embed=None, city=None, country=None):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {"id": cid, "title": title, "source": source, "kind": kind,
                       "image": image, "stream": stream, "mp4": mp4, "embed": embed,
                       "city": city, "country": country},
    }


def _tfl():
    out = []
    r = requests.get("https://api.tfl.gov.uk/Place/Type/JamCam", headers={"User-Agent": UA}, timeout=25)
    for p in r.json():
        lat, lon = p.get("lat"), p.get("lon")
        if lat is None or lon is None:
            continue
        ap = {x.get("key"): x.get("value") for x in (p.get("additionalProperties") or [])}
        out.append(_feat(p.get("id"), p.get("commonName"), lat, lon, "TfL London",
                         image=ap.get("imageUrl"), mp4=ap.get("videoUrl"), city="London", country="GB"))
    return out


def _caltrans_district(n):
    out = []
    url = f"https://cwwp2.dot.ca.gov/data/d{n}/cctv/cctvStatusD{n:02d}.json"
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
        rows = r.json().get("data", [])
    except (requests.RequestException, ValueError):
        return out
    for row in rows:
        c = row.get("cctv") or {}
        loc = c.get("location") or {}
        try:
            lat, lon = float(loc.get("latitude")), float(loc.get("longitude"))
        except (TypeError, ValueError):
            continue
        if not lat and not lon:
            continue
        img = ((c.get("imageData") or {}).get("static") or {}).get("currentImageURL")
        strm = ((c.get("imageData") or {}).get("streamingVideo") or {}).get("streamingVideoURL")
        out.append(_feat(f"ct-{c.get('index') or loc.get('locationName')}", loc.get("locationName"),
                         lat, lon, "Caltrans", image=img or None, stream=strm or None,
                         city=loc.get("county"), country="US"))
    return out


def _caltrans():
    out = []
    with ThreadPoolExecutor(max_workers=12) as ex:
        for res in ex.map(_caltrans_district, range(1, 13)):
            out.extend(res)
    return out


def _drivebc():
    out = []
    r = requests.get("https://www.drivebc.ca/api/webcams/", headers={"User-Agent": UA}, timeout=25)
    for w in r.json():
        loc = w.get("location") or {}
        coords = loc.get("coordinates") or []
        if len(coords) < 2:
            continue
        img = (w.get("links") or {}).get("imageDisplay")
        if img and img.startswith("/"):
            img = "https://www.drivebc.ca" + img
        out.append(_feat(f"bc-{w.get('id')}", w.get("name"), coords[1], coords[0], "DriveBC",
                         image=img, city="British Columbia", country="CA"))
    return out


def _singapore():
    out = []
    r = requests.get("https://api.data.gov.sg/v1/transport/traffic-images", timeout=20)
    items = r.json().get("items") or []
    cams = items[0].get("cameras", []) if items else []
    for c in cams:
        loc = c.get("location") or {}
        lat, lon = loc.get("latitude"), loc.get("longitude")
        if lat is None or lon is None:
            continue
        out.append(_feat(f"sg-{c.get('camera_id')}", f"SG cam {c.get('camera_id')}", lat, lon,
                         "LTA Singapore", image=c.get("image"), city="Singapore", country="SG"))
    return out


def _nzta():
    out = []
    r = requests.get("https://trafficnz.info/service/traffic/rest/4/cameras/all",
                     headers={"User-Agent": UA}, timeout=25)
    root = ET.fromstring(r.content)
    for cam in root.iter("camera"):
        def g(tag, el=cam):
            e = el.find(tag)
            return e.text if e is not None else None
        j = cam.find("journey")
        try:
            lat = float(g("startLatitude", j)); lon = float(g("startLongitude", j))
        except (TypeError, ValueError, AttributeError):
            continue
        img = g("imageUrl")
        if img and img.startswith("/"):
            img = "https://trafficnz.info" + img
        out.append(_feat(f"nz-{g('id')}", g("description"), lat, lon, "NZTA",
                         image=img, country="NZ"))
    return out


_DIREST_RE = re.compile(
    r'nom:"(?P<nom>.*?)",x\s*:\s*(?P<x>[-0-9.]+),y:\s*(?P<y>[-0-9.]+),'
    r'add:"chargerFenetreModale\((?P<id>\d+)\)"'
)


def _direst():
    """DIR Est traffic cameras (Grand Est, France). The camera list (name + coords
    + id) is embedded in the portal HTML; images are direct at /lastimg/{id}."""
    out = []
    r = requests.get("https://webcam.dir-est.fr/", headers={"User-Agent": UA}, timeout=20)
    html = r.text
    seg = html[html.find("var liens"):]
    for m in _DIREST_RE.finditer(seg):
        try:
            lat, lon = float(m.group("y")), float(m.group("x"))
        except ValueError:
            continue
        cid = m.group("id")
        out.append(_feat(f"direst-{cid}", m.group("nom"), lat, lon, "DIR Est",
                         image=f"https://webcam.dir-est.fr/lastimg/{cid}", country="FR"))
    return out


def _finland():
    out = []
    r = requests.get("https://tie.digitraffic.fi/api/weathercam/v1/stations",
                     headers={"Accept-Encoding": "gzip", "User-Agent": UA}, timeout=30)
    for feat in r.json().get("features", []):
        coords = (feat.get("geometry") or {}).get("coordinates") or []
        if len(coords) < 2:
            continue
        props = feat.get("properties") or {}
        preset = next((p for p in (props.get("presets") or []) if p.get("inCollection")), None)
        if not preset:
            continue
        pid = preset.get("id")
        out.append(_feat(f"fi-{pid}", props.get("name"), coords[1], coords[0], "Digitraffic FI",
                         image=f"https://weathercam.digitraffic.fi/{pid}.jpg", country="FI"))
    return out


def _windy(limit=1000):
    """Tourist / city / monument webcams (Windy) — LIVE cams only (player.live),
    so no timelapse-only entries. Embedded via Windy's live iframe player."""
    if not settings.windy_key:
        return []
    out = []
    headers = {"x-windy-api-key": settings.windy_key}
    for offset in range(0, limit, 50):
        try:
            r = requests.get("https://api.windy.com/webcams/api/v3/webcams", headers=headers,
                             params={"limit": 50, "offset": offset, "include": "location,player,images"}, timeout=25)
            if r.status_code != 200:
                break
            webcams = r.json().get("webcams", [])
        except requests.RequestException:
            break
        for w in webcams:
            player = w.get("player") or {}
            live = player.get("live")
            if not live:  # keep only genuinely live webcams
                continue
            loc = w.get("location") or {}
            lat, lon = loc.get("latitude"), loc.get("longitude")
            if lat is None or lon is None:
                continue
            preview = ((w.get("images") or {}).get("current") or {}).get("preview")
            out.append(_feat(f"windy-{w.get('webcamId')}", w.get("title"), lat, lon, "Windy Live",
                             kind="webcam", image=preview, embed=live,
                             city=loc.get("city"), country=loc.get("country")))
        if len(webcams) < 50:
            break
    return out


# Traffic DOT feeds (live JPEG/HLS/MP4) + Finland weathercams + Windy LIVE-only
# tourist/city/monument webcams. Timelapse-only Windy cams are filtered out.
PROVIDERS = {
    "tfl": _tfl, "caltrans": _caltrans, "drivebc": _drivebc,
    "singapore": _singapore, "nzta": _nzta, "finland": _finland,
    "direst": _direst, "windy": _windy,
}


@router.get("/cameras/geojson")
def cameras_geojson(
    limit: int = Query(9000, le=15000),
    bbox: str = Query("", description="optional minLon,minLat,maxLon,maxLat"),
    sources: str = Query("", description="comma list; default all"),
):
    want = [s for s in sources.split(",") if s] or list(PROVIDERS)
    key = ",".join(sorted(want))
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < _TTL:
        feats = hit[1]
    else:
        feats = []
        with ThreadPoolExecutor(max_workers=len(want)) as ex:
            futs = {ex.submit(PROVIDERS[s]): s for s in want if s in PROVIDERS}
            for fut in futs:
                try:
                    feats.extend(fut.result())
                except Exception:  # noqa: BLE001
                    pass
        _cache[key] = (now, feats)

    if bbox:
        try:
            x1, y1, x2, y2 = [float(v) for v in bbox.split(",")]
            feats = [f for f in feats
                     if x1 <= f["geometry"]["coordinates"][0] <= x2
                     and y1 <= f["geometry"]["coordinates"][1] <= y2]
        except ValueError:
            pass

    return {"type": "FeatureCollection", "count": len(feats), "features": feats[:limit]}


def nearest_cameras(lat: float, lon: float, n: int = 1):
    """Return the n camera features closest to a point (for the AI analyst)."""
    fc = cameras_geojson(limit=15000, bbox="", sources="")
    scored = []
    for f in fc["features"]:
        c = f["geometry"]["coordinates"]
        scored.append(((c[0] - lon) ** 2 + (c[1] - lat) ** 2, f))
    scored.sort(key=lambda x: x[0])
    return [f for _, f in scored[:n]]


def nearest_camera(lat: float, lon: float):
    r = nearest_cameras(lat, lon, 1)
    return r[0] if r else None
