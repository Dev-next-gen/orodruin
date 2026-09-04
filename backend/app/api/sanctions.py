from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import GlobalSanction, Sanction

router = APIRouter(prefix="/api", tags=["sanctions"])


@router.get("/sanctions/search")
def search(
    db: Session = Depends(get_db),
    q: str = Query("", min_length=0),
    limit: int = Query(30, le=100),
):
    if not q or len(q.strip()) < 2:
        return {"query": q, "count": 0, "results": []}
    like = f"%{q.strip()}%"
    half = max(5, limit // 2)

    results = []
    for s in db.execute(
        select(Sanction).where(Sanction.name.ilike(like)).limit(half)
    ).scalars().all():
        results.append({
            "source": "OFAC",
            "id": str(s.id),
            "name": s.name,
            "type": s.sdn_type,
            "program": s.program,
            "countries": None,
            "link": f"https://sanctionssearch.ofac.treas.gov/Details.aspx?id={s.id}",
        })

    for g in db.execute(
        select(GlobalSanction).where(GlobalSanction.name.ilike(like)).limit(limit)
    ).scalars().all():
        results.append({
            "source": "OpenSanctions",
            "id": g.id,
            "name": g.name,
            "type": g.schema,
            "program": g.programs,
            "countries": g.countries,
            "link": f"https://www.opensanctions.org/entities/{g.id}/",
        })

    # dedupe by (name.lower, source), keep order, cap
    seen, uniq = set(), []
    for r in results:
        k = (r["name"].lower(), r["source"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)

    return {"query": q, "count": len(uniq), "results": uniq[:limit]}


@router.get("/sanctions/stats")
def stats(db: Session = Depends(get_db)):
    ofac = db.execute(select(func.count(Sanction.id))).scalar() or 0
    glob = db.execute(select(func.count(GlobalSanction.id))).scalar() or 0
    return {"ofac": ofac, "opensanctions": glob, "total": ofac + glob}
