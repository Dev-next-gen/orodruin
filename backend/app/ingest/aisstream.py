"""AISStream real-time vessel collector (WebSocket).

Free key: https://aisstream.io/apikeys
Streams AIS PositionReport + ShipStaticData; upserts latest position per MMSI.
Runs forever with auto-reconnect. Batches DB writes.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import websockets
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.db import SessionLocal
from app.models import Vessel

WS_URL = "wss://stream.aisstream.io/v0/stream"
FLUSH_EVERY = 200          # messages
FLUSH_SECONDS = 4.0

# buffer: mmsi -> row dict (latest wins)
_buffer: dict[int, dict] = {}
_names: dict[int, str] = {}
_types: dict[int, int] = {}


def _flush():
    if not _buffer:
        return 0
    rows = list(_buffer.values())
    _buffer.clear()
    db = SessionLocal()
    try:
        stmt = pg_insert(Vessel).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Vessel.mmsi],
            set_={
                "name": stmt.excluded.name,
                "lat": stmt.excluded.lat,
                "lon": stmt.excluded.lon,
                "sog": stmt.excluded.sog,
                "cog": stmt.excluded.cog,
                "heading": stmt.excluded.heading,
                "ship_type": stmt.excluded.ship_type,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        db.execute(stmt)
        db.commit()
        return len(rows)
    finally:
        db.close()


def _handle(msg: dict):
    mtype = msg.get("MessageType")
    meta = msg.get("MetaData") or {}
    mmsi = meta.get("MMSI")
    if not mmsi:
        return

    if mtype == "ShipStaticData":
        static = (msg.get("Message") or {}).get("ShipStaticData") or {}
        if static.get("Type") is not None:
            _types[mmsi] = static.get("Type")
        name = (static.get("Name") or meta.get("ShipName") or "").strip()
        if name:
            _names[mmsi] = name
        return

    if mtype != "PositionReport":
        return

    pr = (msg.get("Message") or {}).get("PositionReport") or {}
    lat = meta.get("latitude")
    lon = meta.get("longitude")
    if lat is None or lon is None:
        return
    name = (meta.get("ShipName") or _names.get(mmsi) or "").strip() or None
    if name:
        _names[mmsi] = name

    _buffer[mmsi] = {
        "mmsi": mmsi,
        "name": _names.get(mmsi),
        "lat": lat,
        "lon": lon,
        "sog": pr.get("Sog"),
        "cog": pr.get("Cog"),
        "heading": pr.get("TrueHeading"),
        "ship_type": _types.get(mmsi),
        "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
    }


async def _run_once():
    sub = {
        "APIKey": settings.aisstream_key,
        "BoundingBoxes": [[[-90, -180], [90, 180]]],
        "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
    }
    async with websockets.connect(WS_URL, ping_interval=20, max_size=2**22) as ws:
        await ws.send(json.dumps(sub))
        print("AISStream connected.", flush=True)
        count = 0
        last_flush = asyncio.get_event_loop().time()
        async for raw in ws:
            try:
                _handle(json.loads(raw))
            except (json.JSONDecodeError, KeyError):
                continue
            count += 1
            now = asyncio.get_event_loop().time()
            if count % FLUSH_EVERY == 0 or (now - last_flush) > FLUSH_SECONDS:
                n = _flush()
                if n:
                    print(f"upserted {n} vessels (buffer flush)", flush=True)
                last_flush = now


async def run_forever():
    if not settings.aisstream_key:
        print("AISSTREAM_KEY not set in backend/.env")
        return
    while True:
        try:
            await _run_once()
        except Exception as exc:  # noqa: BLE001
            print(f"AISStream disconnected: {exc}; reconnecting in 5s", flush=True)
            _flush()
            await asyncio.sleep(5)
