"""Cyber exposure lookup — Shodan InternetDB (free, no key, no credits).

Returns exposed ports, hostnames, CVEs and tags for an IP.
https://internetdb.shodan.io/{ip}
"""

import time

import requests
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api", tags=["cyber"])

URL = "https://internetdb.shodan.io/{ip}"
KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"

_kev = {"set": set(), "t": 0}
_KEV_TTL = 12 * 3600


def _kev_set():
    if _kev["set"] and time.time() - _kev["t"] < _KEV_TTL:
        return _kev["set"]
    try:
        r = requests.get(KEV_URL, timeout=25)
        r.raise_for_status()
        _kev["set"] = {v["cveID"] for v in r.json().get("vulnerabilities", [])}
        _kev["t"] = time.time()
    except (requests.RequestException, ValueError, KeyError):
        pass
    return _kev["set"]


@router.get("/cyber/host")
def host(ip: str = Query(..., min_length=3)):
    ip = ip.strip()
    try:
        r = requests.get(URL.format(ip=ip), timeout=20)
    except requests.RequestException as exc:
        return {"ip": ip, "found": False, "message": str(exc)}

    if r.status_code == 404:
        return {"ip": ip, "found": False, "message": "No exposure data for this IP."}
    if r.status_code != 200:
        return {"ip": ip, "found": False, "message": f"InternetDB error {r.status_code}"}

    d = r.json()
    kev = _kev_set()
    vulns = [{"id": v, "kev": v in kev} for v in d.get("vulns", [])[:40]]
    vulns.sort(key=lambda x: (not x["kev"], x["id"]))  # KEV first
    return {
        "ip": d.get("ip", ip),
        "found": True,
        "ports": sorted(d.get("ports", [])),
        "hostnames": d.get("hostnames", []),
        "cpes": d.get("cpes", [])[:20],
        "vulns": vulns,
        "kev_count": sum(1 for v in vulns if v["kev"]),
        "tags": d.get("tags", []),
    }
