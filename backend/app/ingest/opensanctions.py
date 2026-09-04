"""OpenSanctions consolidated ingester (open, no key).

CSV (~68 MB, ~80k entities): all sanctions/watchlists (OFAC, EU, UN, UK, ...).
https://data.opensanctions.org/datasets/latest/sanctions/targets.simple.csv
"""

from __future__ import annotations

import csv
import io

import requests
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import SessionLocal
from app.models import GlobalSanction

URL = "https://data.opensanctions.org/datasets/latest/sanctions/targets.simple.csv"


def _s(v, n):
    v = (v or "").strip()
    return v[:n] if v else None


def ingest_opensanctions() -> dict:
    r = requests.get(URL, timeout=180)
    r.raise_for_status()
    reader = csv.DictReader(io.StringIO(r.text))

    db = SessionLocal()
    total = 0
    batch = []
    try:
        def flush(rows):
            if not rows:
                return
            stmt = pg_insert(GlobalSanction).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=[GlobalSanction.id],
                set_={
                    "name": stmt.excluded.name,
                    "schema": stmt.excluded.schema,
                    "aliases": stmt.excluded.aliases,
                    "countries": stmt.excluded.countries,
                    "programs": stmt.excluded.programs,
                    "datasets": stmt.excluded.datasets,
                },
            )
            db.execute(stmt)
            db.commit()

        for row in reader:
            eid = _s(row.get("id"), 96)
            name = _s(row.get("name"), 512)
            if not eid or not name:
                continue
            batch.append(
                {
                    "id": eid,
                    "name": name,
                    "schema": _s(row.get("schema"), 48),
                    "aliases": _s(row.get("aliases"), 1500),
                    "countries": _s(row.get("countries"), 255),
                    "programs": _s(row.get("program_ids") or row.get("sanctions"), 1024),
                    "datasets": _s(row.get("dataset"), 512),
                }
            )
            if len(batch) >= 2000:
                flush(batch)
                total += len(batch)
                batch = []
        flush(batch)
        total += len(batch)
        return {"entities": total}
    finally:
        db.close()
