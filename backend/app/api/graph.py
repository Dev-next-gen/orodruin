from collections import Counter

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Actor, Event

router = APIRouter(prefix="/api", tags=["graph"])


@router.get("/graph")
def actor_graph(
    db: Session = Depends(get_db),
    limit: int = Query(250, le=1000),
    country: str | None = None,
):
    """Actor co-occurrence graph: two actors linked when they share events."""
    q = select(Event.actor1_id, Event.actor2_id).where(
        Event.actor1_id.isnot(None), Event.actor2_id.isnot(None)
    )
    if country:
        q = q.where(Event.geo_country == country.upper())
    q = q.limit(limit * 40)
    rows = db.execute(q).all()

    edge_w: Counter = Counter()
    for a, b in rows:
        if a == b:
            continue
        edge_w[tuple(sorted((a, b)))] += 1

    top = edge_w.most_common(limit)
    node_ids = {n for pair, _ in top for n in pair}
    actors = {
        ac.id: ac
        for ac in db.execute(
            select(Actor).where(Actor.id.in_(node_ids))
        ).scalars().all()
    }
    nodes = [
        {"id": i, "name": actors[i].name, "country": actors[i].country_code}
        for i in node_ids
        if i in actors
    ]
    edges = [
        {"source": a, "target": b, "weight": w}
        for (a, b), w in top
        if a in actors and b in actors
    ]
    return {"nodes": nodes, "edges": edges}
