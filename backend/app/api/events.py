from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.cameo import quad_label, root_label
from app.db import get_db
from app.models import Actor, Event

router = APIRouter(prefix="/api", tags=["events"])


def _apply_filters(q, quad_class, root_code, country, actor, bbox, since_hours=None):
    if since_hours:
        q = q.where(Event.date_added >= datetime.utcnow() - timedelta(hours=since_hours))
    if quad_class:
        q = q.where(Event.quad_class == quad_class)
    if root_code:
        q = q.where(Event.event_root_code == root_code)
    if country:
        q = q.where(Event.geo_country == country.upper())
    if actor:
        like = f"%{actor.upper()}%"
        q = q.where(
            (Event.actor1.has(Actor.name.ilike(like)))
            | (Event.actor2.has(Actor.name.ilike(like)))
        )
    if bbox:
        try:
            w, s, e, n = (float(x) for x in bbox.split(","))
            q = q.where(Event.lon >= w, Event.lon <= e, Event.lat >= s, Event.lat <= n)
        except ValueError:
            pass
    return q


def _event_dict(e: Event) -> dict:
    return {
        "id": e.id,
        "sqldate": e.sqldate,
        "date_added": e.date_added.isoformat() if e.date_added else None,
        "event_code": e.event_code,
        "event_root_code": e.event_root_code,
        "event_root_label": root_label(e.event_root_code),
        "quad_class": e.quad_class,
        "quad_label": quad_label(e.quad_class),
        "goldstein": e.goldstein,
        "avg_tone": e.avg_tone,
        "num_mentions": e.num_mentions,
        "num_sources": e.num_sources,
        "num_articles": e.num_articles,
        "actor1": e.actor1.name if e.actor1 else None,
        "actor2": e.actor2.name if e.actor2 else None,
        "geo_fullname": e.geo_fullname,
        "geo_country": e.geo_country,
        "lat": e.lat,
        "lon": e.lon,
        "source_url": e.source_url,
    }


@router.get("/events")
def list_events(
    db: Session = Depends(get_db),
    limit: int = Query(500, le=5000),
    quad_class: int | None = None,
    root_code: str | None = None,
    country: str | None = None,
    actor: str | None = None,
    bbox: str | None = None,
    since_hours: int | None = None,
):
    q = select(Event).where(Event.lat.isnot(None))
    q = _apply_filters(q, quad_class, root_code, country, actor, bbox, since_hours)
    q = q.order_by(Event.date_added.desc()).limit(limit)
    events = db.execute(q).unique().scalars().all()
    return [_event_dict(e) for e in events]


@router.get("/events/geojson")
def events_geojson(
    db: Session = Depends(get_db),
    limit: int = Query(2000, le=10000),
    quad_class: int | None = None,
    root_code: str | None = None,
    country: str | None = None,
    actor: str | None = None,
    bbox: str | None = None,
    since_hours: int | None = None,
):
    q = select(Event).where(Event.lat.isnot(None))
    q = _apply_filters(q, quad_class, root_code, country, actor, bbox, since_hours)
    q = q.order_by(Event.date_added.desc()).limit(limit)
    events = db.execute(q).unique().scalars().all()
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [e.lon, e.lat]},
            "properties": _event_dict(e),
        }
        for e in events
    ]
    return {"type": "FeatureCollection", "features": features}


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    total = db.execute(select(func.count(Event.id))).scalar() or 0
    n_actors = db.execute(select(func.count(Actor.id))).scalar() or 0
    by_quad = {
        (quad_label(k) if k else "Unknown"): v
        for k, v in db.execute(
            select(Event.quad_class, func.count(Event.id)).group_by(Event.quad_class)
        ).all()
    }
    top_countries = [
        {"country": c, "count": n}
        for c, n in db.execute(
            select(Event.geo_country, func.count(Event.id))
            .where(Event.geo_country.isnot(None))
            .group_by(Event.geo_country)
            .order_by(func.count(Event.id).desc())
            .limit(15)
        ).all()
    ]
    return {
        "events": total,
        "actors": n_actors,
        "by_quad_class": by_quad,
        "top_countries": top_countries,
    }
