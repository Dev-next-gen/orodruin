"""Financial markets — indices, forex, commodities (Yahoo Finance) + crypto (CoinGecko).

Open, no key. Consolidated live market data.
"""

import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

import requests
from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["markets"])

YF = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
UA = {"User-Agent": "Mozilla/5.0 (osint-platform)"}

INDICES = [("^GSPC", "S&P 500"), ("^IXIC", "Nasdaq"), ("^DJI", "Dow Jones"),
           ("^FCHI", "CAC 40"), ("^FTSE", "FTSE 100"), ("^GDAXI", "DAX"),
           ("^N225", "Nikkei 225"), ("^HSI", "Hang Seng"), ("^STOXX50E", "Euro Stoxx 50")]
FOREX = [("EURUSD=X", "EUR/USD"), ("GBPUSD=X", "GBP/USD"), ("USDJPY=X", "USD/JPY"),
         ("USDCNY=X", "USD/CNY"), ("EURRUB=X", "EUR/RUB")]
COMMOD = [("GC=F", "Gold"), ("SI=F", "Silver"), ("CL=F", "WTI Oil"),
          ("BZ=F", "Brent"), ("NG=F", "Nat Gas")]
CRYPTO_IDS = ["bitcoin", "ethereum", "solana", "binancecoin", "ripple"]
CRYPTO_NAMES = {"bitcoin": "Bitcoin", "ethereum": "Ethereum", "solana": "Solana",
                "binancecoin": "BNB", "ripple": "XRP"}

_cache = {"t": 0, "data": None}
_TTL = 60


def _quote(sym_name):
    sym, name = sym_name
    try:
        r = requests.get(YF.format(sym=quote(sym)), headers=UA, timeout=12)
        m = r.json()["chart"]["result"][0]["meta"]
        price = m.get("regularMarketPrice")
        prev = m.get("chartPreviousClose") or m.get("previousClose")
        chg = ((price - prev) / prev * 100) if price and prev else None
        return {"name": name, "symbol": sym, "price": price, "change_pct": round(chg, 2) if chg is not None else None}
    except Exception:  # noqa: BLE001
        return {"name": name, "symbol": sym, "price": None, "change_pct": None}


def _crypto():
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": ",".join(CRYPTO_IDS), "vs_currencies": "usd", "include_24hr_change": "true"},
            timeout=12,
        )
        d = r.json()
        return [
            {"name": CRYPTO_NAMES[c], "symbol": c, "price": d[c]["usd"],
             "change_pct": round(d[c].get("usd_24h_change", 0), 2)}
            for c in CRYPTO_IDS if c in d
        ]
    except Exception:  # noqa: BLE001
        return []


@router.get("/markets")
def markets():
    now = time.time()
    if _cache["data"] and now - _cache["t"] < _TTL:
        return _cache["data"]

    with ThreadPoolExecutor(max_workers=12) as ex:
        indices = list(ex.map(_quote, INDICES))
        forex = list(ex.map(_quote, FOREX))
        commod = list(ex.map(_quote, COMMOD))
    data = {"indices": indices, "forex": forex, "commodities": commod, "crypto": _crypto()}
    _cache["data"] = data
    _cache["t"] = now
    return data
