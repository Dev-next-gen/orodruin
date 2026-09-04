"""GDELT 2.0 Events ingester.

Downloads GDELT 15-minute export slices, parses the 61-column TSV, and
upserts Actors + Events into PostgreSQL. Free, no API key.

Column reference (GDELT 2.0 Event schema, 0-indexed):
  0  GLOBALEVENTID     1  SQLDATE
  5  Actor1Code        6  Actor1Name      7  Actor1CountryCode   12 Actor1Type1Code
  15 Actor2Code        16 Actor2Name      17 Actor2CountryCode   22 Actor2Type1Code
  26 EventCode         28 EventRootCode   29 QuadClass           30 GoldsteinScale
  31 NumMentions       32 NumSources      33 NumArticles         34 AvgTone
  40 Actor1Geo_Lat     41 Actor1Geo_Long
  52 ActionGeo_FullName 53 ActionGeo_CountryCode
  56 ActionGeo_Lat     57 ActionGeo_Long
  59 DATEADDED (YYYYMMDDHHMMSS)           60 SOURCEURL
"""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime, timedelta, timezone

import requests
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import Actor, Event

GDELT_MIN_COLS = 61
COMMIT_EVERY = 1000


def latest_export_url() -> str:
    r = requests.get(settings.gdelt_lastupdate_url, timeout=30)
    r.raise_for_status()
    for line in r.text.strip().splitlines():
        parts = line.split()
        if parts and parts[-1].endswith("export.CSV.zip"):
            return parts[-1]
    raise RuntimeError("No export file found in GDELT lastupdate.txt")


def _recent_slice_urls(n: int) -> list[str]:
    latest = latest_export_url()
    fname = latest.split("/")[-1]
    base = latest.rsplit("/", 1)[0]
    dt = datetime.strptime(fname.split(".")[0], "%Y%m%d%H%M%S")
    return [
        f"{base}/{(dt - timedelta(minutes=15 * i)).strftime('%Y%m%d%H%M%S')}.export.CSV.zip"
        for i in range(n)
    ]


def _f(v):
    v = (v or "").strip()
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _i(v):
    f = _f(v)
    return int(f) if f is not None else None


def _s(v):
    v = (v or "").strip()
    return v or None


def _rows(url: str):
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    name = zf.namelist()[0]
    with zf.open(name) as fh:
        text = io.TextIOWrapper(fh, encoding="utf-8", errors="replace")
        for row in csv.reader(text, delimiter="\t"):
            if len(row) >= GDELT_MIN_COLS:
                yield row


def _get_or_create_actor(db, cache, code, name, country, type_code):
    code = _s(code)
    name = _s(name)
    if not code and not name:
        return None
    key = code or name
    if key in cache:
        return cache[key]
    actor = db.execute(select(Actor).where(Actor.code == key)).scalar_one_or_none()
    if actor is None:
        actor = Actor(
            code=key,
            name=name or code,
            country_code=_s(country),
            type_code=_s(type_code),
        )
        db.add(actor)
        db.flush()
    cache[key] = actor
    return actor


def _add_row(db, row, cache, seen_ids) -> bool:
    try:
        gid = int(row[0])
    except ValueError:
        return False
    if gid in seen_ids:
        return False

    a1 = _get_or_create_actor(db, cache, row[5], row[6], row[7], row[12])
    a2 = _get_or_create_actor(db, cache, row[15], row[16], row[17], row[22])

    lat, lon = _f(row[56]), _f(row[57])
    if lat is None or lon is None:
        lat, lon = _f(row[40]), _f(row[41])

    try:
        da = datetime.strptime(row[59].strip(), "%Y%m%d%H%M%S")
    except (ValueError, IndexError):
        da = datetime.now(timezone.utc).replace(tzinfo=None)

    db.add(
        Event(
            id=gid,
            sqldate=_i(row[1]) or 0,
            date_added=da,
            event_code=_s(row[26]),
            event_root_code=_s(row[28]),
            quad_class=_i(row[29]),
            goldstein=_f(row[30]),
            avg_tone=_f(row[34]),
            num_mentions=_i(row[31]),
            num_sources=_i(row[32]),
            num_articles=_i(row[33]),
            actor1_id=a1.id if a1 else None,
            actor2_id=a2.id if a2 else None,
            geo_fullname=_s(row[52]),
            geo_country=_s(row[53]),
            lat=lat,
            lon=lon,
            source_url=_s(row[60]),
        )
    )
    seen_ids.add(gid)
    return True


def _ingest_url(url, db, cache, seen_ids) -> tuple[int, int]:
    seen = inserted = 0
    for row in _rows(url):
        seen += 1
        if _add_row(db, row, cache, seen_ids):
            inserted += 1
            if inserted % COMMIT_EVERY == 0:
                db.commit()
    db.commit()
    return seen, inserted


def _load_seen_ids(db) -> set:
    return set(db.execute(select(Event.id)).scalars().all())


def ingest_once() -> dict:
    url = latest_export_url()
    db = SessionLocal()
    try:
        seen, inserted = _ingest_url(url, db, {}, _load_seen_ids(db))
    finally:
        db.close()
    return {"url": url.split("/")[-1], "seen": seen, "inserted": inserted}


def ingest_backfill(hours: int) -> dict:
    urls = _recent_slice_urls(hours * 4)
    db = SessionLocal()
    cache: dict = {}
    total_seen = total_ins = ok = 0
    try:
        seen_ids = _load_seen_ids(db)
        for u in urls:
            try:
                s, i = _ingest_url(u, db, cache, seen_ids)
                total_seen += s
                total_ins += i
                ok += 1
                print(f"  {u.split('/')[-1]}: +{i}", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"  skip {u.split('/')[-1]}: {exc}", flush=True)
    finally:
        db.close()
    return {"slices_ok": ok, "seen": total_seen, "inserted": total_ins}
