"""Prediction markets — Polymarket (Gamma API). Real-money betting odds are among
the best-calibrated probabilistic signals for geopolitical/economic forecasting,
so the AI analyst can weigh crowd-priced probabilities and money volume."""

import json
import time

import requests
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api", tags=["prediction"])

GAMMA = "https://gamma-api.polymarket.com/markets"
_cache: dict[str, tuple[float, list]] = {}
_TTL = 300


def _fetch(limit: int):
    now = time.time()
    hit = _cache.get("top")
    if hit and now - hit[0] < _TTL:
        return hit[1]
    try:
        r = requests.get(
            GAMMA,
            params={"closed": "false", "active": "true", "limit": max(limit, 120),
                    "order": "volumeNum", "ascending": "false"},
            timeout=20,
        )
        r.raise_for_status()
        raw = r.json()
    except requests.RequestException:
        return []

    out = []
    for m in raw:
        try:
            outcomes = json.loads(m.get("outcomes") or "[]")
            prices = [float(x) for x in json.loads(m.get("outcomePrices") or "[]")]
        except (ValueError, TypeError):
            continue
        if not outcomes or len(prices) != len(outcomes):
            continue
        pairs = sorted(zip(outcomes, prices), key=lambda x: -x[1])
        lead_name, lead_p = pairs[0]
        out.append({
            "question": m.get("question"),
            "slug": m.get("slug"),
            "volume": round(float(m.get("volumeNum") or m.get("volume") or 0)),
            "liquidity": round(float(m.get("liquidity") or 0)),
            "end_date": (m.get("endDate") or "")[:10],
            "leader": lead_name,
            "probability": round(lead_p * 100, 1),
            "outcomes": [{"name": n, "prob": round(p * 100, 1)} for n, p in pairs[:4]],
        })
    _cache["top"] = (now, out)
    return out


@router.get("/prediction-markets")
def prediction_markets(
    limit: int = Query(20, le=60),
    q: str = Query("", description="optional keyword filter on the question"),
):
    markets = _fetch(limit)
    if q:
        ql = q.lower()
        markets = [m for m in markets if ql in (m["question"] or "").lower()]
    markets = markets[:limit]
    return {"count": len(markets), "markets": markets}
