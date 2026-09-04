"""OFAC SDN sanctions ingester (US Treasury, open, no key).

CSV: https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.CSV
Columns: ent_num, name, sdn_type, program, title, ..., remarks (last).
"-0-" means empty.
"""

from __future__ import annotations

import csv
import io

import requests
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import SessionLocal
from app.models import Sanction

URL = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.CSV"


def _cl(v):
    v = (v or "").strip()
    return None if v in ("", "-0-") else v


def ingest_ofac() -> dict:
    r = requests.get(URL, timeout=90)  # requests follows redirects
    r.raise_for_status()
    reader = csv.reader(io.StringIO(r.text))

    rows = []
    for row in reader:
        if len(row) < 4:
            continue
        try:
            eid = int(row[0])
        except ValueError:
            continue
        rows.append(
            {
                "id": eid,
                "name": (_cl(row[1]) or "?")[:512],
                "sdn_type": _cl(row[2]),
                "program": (_cl(row[3]) or "")[:255] or None,
                "title": (_cl(row[4]) or "")[:512] or None if len(row) > 4 else None,
                "remarks": (_cl(row[-1]) or "")[:2000] or None,
            }
        )

    if not rows:
        return {"inserted": 0}

    db = SessionLocal()
    try:
        for i in range(0, len(rows), 1000):
            chunk = rows[i : i + 1000]
            stmt = pg_insert(Sanction).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=[Sanction.id],
                set_={
                    "name": stmt.excluded.name,
                    "sdn_type": stmt.excluded.sdn_type,
                    "program": stmt.excluded.program,
                    "title": stmt.excluded.title,
                    "remarks": stmt.excluded.remarks,
                },
            )
            db.execute(stmt)
            db.commit()
        return {"entities": len(rows)}
    finally:
        db.close()
