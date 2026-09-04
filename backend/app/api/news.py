"""News aggregator — merges several news-channel RSS feeds into one ticker."""

import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from email.utils import parsedate_to_datetime

import requests
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api", tags=["news"])

FEEDS = {
    "fr": [
        ("France 24", "https://www.france24.com/fr/rss"),
        ("Le Monde", "https://www.lemonde.fr/rss/une.xml"),
        ("Euronews", "https://fr.euronews.com/rss"),
        ("RFI", "https://www.rfi.fr/fr/rss"),
        ("RFI Moyen-Orient", "https://www.rfi.fr/fr/moyen-orient/rss"),
        ("RFI Afrique", "https://www.rfi.fr/fr/afrique/rss"),
        ("France 24 (AR)", "https://www.france24.com/ar/rss"),
    ],
    "en": [
        # global
        ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
        ("BBC", "https://feeds.bbci.co.uk/news/world/rss.xml"),
        ("France 24", "https://www.france24.com/en/rss"),
        ("DW", "https://rss.dw.com/rdf/rss-en-all"),
        ("Guardian", "https://www.theguardian.com/world/rss"),
        ("NYT World", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"),
        # Middle East / Arab world
        ("BBC Middle East", "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml"),
        ("Guardian Middle East", "https://www.theguardian.com/world/middleeast/rss"),
        ("Middle East Eye", "https://www.middleeasteye.net/rss"),
        ("Al-Monitor", "https://www.al-monitor.com/rss"),
        ("Arab News", "https://backup.arabnews.com/rss.xml"),
        ("Anadolu Agency", "https://www.aa.com.tr/en/rss/default?cat=live"),
        ("Times of Israel", "https://www.timesofisrael.com/feed/"),
        ("Jerusalem Post", "https://www.jpost.com/rss/rssfeedsheadlines.aspx"),
    ],
    "ar": [
        ("الجزيرة", "https://www.aljazeera.net/aljazeerarss/a7c186be-1baa-4bd4-9d80-a84db769f779/73d0e1b4-532f-45ef-b135-bfdff8b8cab9"),
        ("سكاي نيوز عربية", "https://www.skynewsarabia.com/rss"),
        ("فرانس 24", "https://www.france24.com/ar/rss"),
    ],
    # cyber threat intelligence — breaches, ransomware, data leaks, CVEs
    "cyber": [
        ("The Hacker News", "https://feeds.feedburner.com/TheHackersNews"),
        ("BleepingComputer", "https://www.bleepingcomputer.com/feed/"),
        ("Krebs on Security", "https://krebsonsecurity.com/feed/"),
        ("Dark Reading", "https://www.darkreading.com/rss.xml"),
        ("SecurityWeek", "https://www.securityweek.com/feed/"),
        ("Infosecurity Mag", "https://www.infosecurity-magazine.com/rss/news/"),
        ("The Record", "https://therecord.media/feed/"),
        ("GBHackers", "https://gbhackers.com/feed/"),
    ],
}

_cache: dict = {}
_TTL = 300


def _ts(pub):
    if not pub:
        return 0
    try:
        return parsedate_to_datetime(pub).timestamp()
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(pub.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0


def _parse(source, url):
    r = requests.get(url, timeout=15, headers={"User-Agent": "osint-platform/1.0"})
    r.raise_for_status()
    root = ET.fromstring(r.content)
    items = []
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        title = link = pub = None
        for c in el:
            ct = c.tag.split("}")[-1]
            if ct == "title":
                title = (c.text or "").strip()
            elif ct == "link":
                link = (c.text.strip() if c.text else None) or c.get("href")
            elif ct in ("pubDate", "published", "updated", "date"):
                pub = c.text
        if title:
            items.append({"source": source, "title": title, "link": link, "published": pub})
    return items


@router.get("/news")
def news(lang: str = Query("fr"), limit: int = Query(50, le=120)):
    now = time.time()
    hit = _cache.get(lang)
    if hit and now - hit["t"] < _TTL:
        return hit["data"]

    feeds = FEEDS.get(lang, FEEDS["fr"])
    merged = []

    def _safe(feed):
        try:
            return _parse(*feed)
        except Exception:  # noqa: BLE001
            return []

    with ThreadPoolExecutor(max_workers=min(len(feeds), 12)) as ex:
        for res in ex.map(_safe, feeds):
            merged.extend(res)

    # cyber feed also carries the global data-breach tracker (HIBP)
    if lang == "cyber":
        try:
            from app.api.breaches import recent_breach_items
            merged.extend(recent_breach_items(40))
        except Exception:  # noqa: BLE001
            pass

    seen, uniq = set(), []
    for it in merged:
        k = it["title"][:80]
        if k in seen:
            continue
        seen.add(k)
        it["_ts"] = _ts(it.get("published"))
        uniq.append(it)
    uniq.sort(key=lambda x: -x["_ts"])

    # keep HIBP breaches visible: interleave one every ~3 RSS items
    if lang == "cyber":
        br = [i for i in uniq if i["source"] == "HIBP"]
        rest = [i for i in uniq if i["source"] != "HIBP"]
        inter, bi = [], 0
        for idx, it in enumerate(rest):
            inter.append(it)
            if idx % 3 == 2 and bi < len(br):
                inter.append(br[bi]); bi += 1
        inter.extend(br[bi:])
        uniq = inter

    data = {
        "count": len(uniq),
        "items": [{k: v for k, v in it.items() if k != "_ts"} for it in uniq[:limit]],
    }
    _cache[lang] = {"t": now, "data": data}
    return data
