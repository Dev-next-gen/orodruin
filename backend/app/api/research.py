"""Academic monitoring (L5) — ArXiv research feed (open, no key).

Track publications on strategic topics (nuclear, missiles, hypersonics, AI, defense).
"""

import xml.etree.ElementTree as ET

import requests
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api", tags=["research"])

URL = "https://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


@router.get("/research/search")
def search(q: str = Query(..., min_length=2), limit: int = Query(15, le=40)):
    try:
        r = requests.get(
            URL,
            params={
                "search_query": f"all:{q.strip()}",
                "start": 0,
                "max_results": limit,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            },
            timeout=30,
        )
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except (requests.RequestException, ET.ParseError) as exc:
        return {"query": q, "count": 0, "results": [], "error": str(exc)}

    results = []
    for e in root.findall("a:entry", NS):
        title = (e.findtext("a:title", "", NS) or "").strip().replace("\n", " ")
        summary = (e.findtext("a:summary", "", NS) or "").strip().replace("\n", " ")
        published = (e.findtext("a:published", "", NS) or "")[:10]
        authors = [a.findtext("a:name", "", NS) for a in e.findall("a:author", NS)]
        link = e.findtext("a:id", "", NS)
        cat = e.find("arxiv:primary_category", NS)
        results.append(
            {
                "title": title,
                "authors": authors[:4],
                "published": published,
                "summary": summary[:280],
                "link": link,
                "category": cat.get("term") if cat is not None else None,
            }
        )
    return {"query": q, "count": len(results), "results": results}
