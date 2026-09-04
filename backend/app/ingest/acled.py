"""ACLED armed-conflict ingester (OAuth, myACLED Research tier+).

Registration: https://acleddata.com/user/register
NOTE: the "Open" access tier does NOT include API access — the read endpoint
returns {"message":"Access denied"} until the account is Research/Partner/Enterprise.
This module is ready and will populate as soon as the tier is upgraded.
"""

from __future__ import annotations

import time

import requests
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import Conflict

_token_cache = {"access": None, "exp": 0}


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(v):
    f = _f(v)
    return int(f) if f is not None else None


def get_token() -> str:
    if _token_cache["access"] and time.time() < _token_cache["exp"] - 60:
        return _token_cache["access"]
    r = requests.post(
        settings.acled_token_url,
        data={
            "username": settings.acled_email,
            "password": settings.acled_password,
            "grant_type": "password",
            "client_id": "acled",
            "scope": "authenticated",
        },
        timeout=30,
    )
    r.raise_for_status()
    d = r.json()
    _token_cache["access"] = d["access_token"]
    _token_cache["exp"] = time.time() + int(d.get("expires_in", 86400))
    return _token_cache["access"]


def _read_page(token: str, page: int, limit: int) -> dict:
    r = requests.get(
        settings.acled_read_url,
        params={"limit": limit, "page": page, "_format": "json"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    if r.status_code in (401, 403):
        return {"message": "Access denied", "http": r.status_code}
    r.raise_for_status()
    try:
        return r.json()
    except ValueError:
        return {"message": "Access denied", "raw": r.text[:160]}


def ingest_acled(pages: int = 2, limit: int = 500) -> dict:
    if not (settings.acled_email and settings.acled_password):
        return {"error": "ACLED_EMAIL/ACLED_PASSWORD not set in backend/.env"}

    token = get_token()
    db = SessionLocal()
    seen = inserted = 0
    try:
        existing = set(db.execute(select(Conflict.id)).scalars().all())
        for page in range(1, pages + 1):
            payload = _read_page(token, page, limit)
            if isinstance(payload, dict) and payload.get("message") == "Access denied":
                return {
                    "error": "Access denied — myACLED account needs Research tier or "
                    "higher for API access (Open tier has none).",
                    "inserted": inserted,
                }
            rows = payload.get("data") or []
            if not rows:
                break
            for row in rows:
                seen += 1
                did = str(row.get("event_id_cnty") or row.get("data_id") or "").strip()
                if not did or did in existing:
                    continue
                db.add(
                    Conflict(
                        id=did,
                        event_date=row.get("event_date"),
                        event_type=row.get("event_type"),
                        sub_event_type=row.get("sub_event_type"),
                        actor1=row.get("actor1"),
                        actor2=row.get("actor2"),
                        country=row.get("country"),
                        admin1=row.get("admin1"),
                        location=row.get("location"),
                        lat=_f(row.get("latitude")),
                        lon=_f(row.get("longitude")),
                        fatalities=_i(row.get("fatalities")),
                        notes=(row.get("notes") or "")[:2000] or None,
                        src=(row.get("source") or "")[:255] or None,
                    )
                )
                existing.add(did)
                inserted += 1
            db.commit()
        return {"seen": seen, "inserted": inserted, "pages": pages}
    finally:
        db.close()
