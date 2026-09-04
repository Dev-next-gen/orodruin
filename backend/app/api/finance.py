"""Financial intelligence (L4) — US federal awards via USASpending.gov (open, no key)."""

import requests
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api", tags=["finance"])

URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"


@router.get("/finance/awards")
def awards(q: str = Query(..., min_length=2), limit: int = Query(20, le=50)):
    body = {
        "filters": {
            "award_type_codes": ["A", "B", "C", "D"],
            "keywords": [q.strip()],
        },
        "fields": [
            "Award ID",
            "Recipient Name",
            "Award Amount",
            "Awarding Agency",
            "Start Date",
            "Period of Performance Start Date",
        ],
        "limit": limit,
        "sort": "Award Amount",
        "order": "desc",
    }
    try:
        r = requests.post(URL, json=body, timeout=30)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError) as exc:
        return {"query": q, "count": 0, "results": [], "error": str(exc)}

    results = []
    for a in data.get("results", []):
        results.append(
            {
                "award_id": a.get("Award ID"),
                "recipient": a.get("Recipient Name"),
                "amount": a.get("Award Amount"),
                "agency": a.get("Awarding Agency"),
                "start": a.get("Start Date") or a.get("Period of Performance Start Date"),
            }
        )
    return {"query": q, "count": len(results), "results": results}
