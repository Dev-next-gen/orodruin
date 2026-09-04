"""Live TV aggregator — public IPTV streams from the open iptv-org catalog.

Thousands of publicly-available channels worldwide as direct HLS (.m3u8) URLs,
joined with channel metadata and grouped by country. Far more reliable than
YouTube live_stream embeds (no consent wall, no offline-channel failures)."""

import time

import requests
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api", tags=["tv"])

BASE = "https://iptv-org.github.io/api"
_cache = {"ts": 0, "data": None}
_TTL = 6 * 3600  # catalog is near-static


def _load_catalog():
    now = time.time()
    if _cache["data"] and now - _cache["ts"] < _TTL:
        return _cache["data"]

    ch = requests.get(f"{BASE}/channels.json", timeout=40).json()
    st = requests.get(f"{BASE}/streams.json", timeout=40).json()
    try:
        countries = {c["code"]: c["name"] for c in requests.get(f"{BASE}/countries.json", timeout=20).json()}
    except Exception:  # noqa: BLE001
        countries = {}

    # channel_id -> list of clean stream urls (prefer no special headers)
    streams = {}
    for s in st:
        cid = s.get("channel")
        url = s.get("url")
        if not cid or not url:
            continue
        # streams needing a custom UA/referrer rarely play in a browser <video>
        penalty = 1 if (s.get("user_agent") or s.get("referrer")) else 0
        streams.setdefault(cid, []).append((penalty, 0 if url.startswith("https") else 1, url))

    for cid in streams:
        streams[cid] = [u for _, _, u in sorted(streams[cid])]

    _cache["data"] = {"channels": ch, "streams": streams, "countries": countries}
    _cache["ts"] = now
    return _cache["data"]


@router.get("/tv/channels")
def tv_channels(
    category: str = Query("news", description="iptv-org category, or 'all'"),
    limit: int = Query(1600, le=6000),
):
    cat = _load_catalog()
    channels, streams, countries = cat["channels"], cat["streams"], cat["countries"]

    grouped: dict[str, dict] = {}
    total = 0
    for c in channels:
        if c.get("closed") or c.get("is_nsfw"):
            continue
        cats = c.get("categories") or []
        if category != "all" and category not in cats:
            continue
        urls = streams.get(c["id"])
        if not urls:
            continue
        code = c.get("country") or "ZZ"
        g = grouped.setdefault(code, {"code": code, "name": countries.get(code, code), "channels": []})
        g["channels"].append({
            "id": c["id"],
            "name": c["name"],
            "network": c.get("network"),
            "urls": urls[:3],  # up to 3 sources for reliability fallback
        })
        total += 1
        if total >= limit:
            break

    for g in grouped.values():
        g["channels"].sort(key=lambda x: x["name"].lower())
    out = sorted(grouped.values(), key=lambda g: (g["name"] == g["code"], g["name"]))
    return {"count": total, "countries": out}
