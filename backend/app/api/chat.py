"""Conversational OSINT analyst — LLM agent with tool access to all backend data.

The local LLM can call backend tools (events, hotspots, alerts, sanctions, cyber,
finance, research, disasters, stats) to answer questions grounded in live data.
"""

import json
import re
import time

import requests
from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.alerts import alerts as _alerts
from app.api.cameras import nearest_camera as _nearest_camera
from app.api.cameras import nearest_cameras as _nearest_cameras
from app.api.cyber import host as _cyber
from app.api.breaches import breaches as _breaches
from app.api.cyberthreat import ransomware as _ransomware
from app.api.fires import fires_geojson as _fires
from app.api.flights import flights_geojson as _flights
from app.api.geoip import geoip as _geoip
from app.api.infra import infra_status as _infra_status
from app.api.powerplants import powerplants_geojson as _powerplants
from app.api.quakes import quakes_geojson as _quakes
from app.api.roads import incidents as _road_incidents
from app.api.vessels import vessels_geojson as _vessels
from app.api.geocode import geocode as _geocode
from app.api.spaceweather import space_weather as _spaceweather
from app.api.weather import weather as _weather
from app.api.events import list_events as _events
from app.api.finance import awards as _finance
from app.api.hotspots import hotspots as _hotspots
from app.api.markets import markets as _markets
from app.api.prediction import prediction_markets as _prediction
from app.api.research import search as _research
from app.api.sanctions import search as _sanctions
from app.config import settings
from app.db import SessionLocal
from app.llm import available
from app.llm import headers as _llm_headers
from app.models import Disaster, Event, Fire, Sanction, Vessel

router = APIRouter(prefix="/api", tags=["chat"])

TOOLS = [
    {"type": "function", "function": {
        "name": "get_stats",
        "description": "Global counts across the platform (events, actors, fires, vessels, sanctions).",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "query_events",
        "description": "Recent geopolitical events (GDELT). Filter by country FIPS code, quad_class (1=verbal coop,2=material coop,3=verbal conflict,4=material conflict), actor name, or recency in hours.",
        "parameters": {"type": "object", "properties": {
            "country": {"type": "string", "description": "FIPS country code, e.g. UP=Ukraine, RS=Russia, IR=Iran"},
            "quad_class": {"type": "integer"},
            "actor": {"type": "string"},
            "since_hours": {"type": "integer"},
            "limit": {"type": "integer", "default": 20},
        }},
    }},
    {"type": "function", "function": {
        "name": "get_hotspots",
        "description": "Ranked tension hotspots (weighted aggregation of recent conflict events + fires).",
        "parameters": {"type": "object", "properties": {"window_hours": {"type": "integer", "default": 48}}},
    }},
    {"type": "function", "function": {
        "name": "get_alerts",
        "description": "Live high-severity alerts: material conflicts, red/orange disasters, intense fires, emergency aircraft.",
        "parameters": {"type": "object", "properties": {"hours": {"type": "integer", "default": 24}}},
    }},
    {"type": "function", "function": {
        "name": "search_sanctions",
        "description": "Screen a person/entity name against OFAC + OpenSanctions (global sanctions/watchlists).",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "cyber_lookup",
        "description": "Exposed ports, services and known-exploited CVEs for an IP address (Shodan InternetDB + CISA KEV).",
        "parameters": {"type": "object", "properties": {"ip": {"type": "string"}}, "required": ["ip"]},
    }},
    {"type": "function", "function": {
        "name": "finance_awards",
        "description": "US federal contracts (USASpending) by keyword — defense/aerospace recipients and amounts.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "research_papers",
        "description": "Recent academic publications (ArXiv) on a strategic topic (nuclear, missile, hypersonic, AI).",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "get_markets",
        "description": "Live financial markets: stock indices (S&P 500, Nasdaq, CAC 40, DAX, Nikkei…), forex, commodities (gold, oil), and crypto (BTC, ETH) with prices and % change.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "get_disasters",
        "description": "Active GDACS disaster alerts (earthquakes, cyclones, floods, volcanoes) with severity.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "get_fires",
        "description": "Active wildfire detections (NASA FIRMS). Total count and the most intense fires by radiative power (MW).",
        "parameters": {"type": "object", "properties": {"min_mw": {"type": "number", "default": 50}}},
    }},
    {"type": "function", "function": {
        "name": "get_quakes",
        "description": "Recent earthquakes (USGS): magnitude, place, depth. Use for seismic activity questions.",
        "parameters": {"type": "object", "properties": {"feed": {"type": "string", "description": "2.5_day, 4.5_day, significant_week", "default": "2.5_day"}}},
    }},
    {"type": "function", "function": {
        "name": "get_infra",
        "description": "Global internet backbone status: number of submarine cable systems, segments, landing points, plus space weather affecting comms.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "get_powerplants",
        "description": "Energy infrastructure near a place: power plants with capacity (MW) and fuel type (gas, oil, nuclear, coal, hydro, solar…). Give a place name.",
        "parameters": {"type": "object", "properties": {"place": {"type": "string"}, "min_mw": {"type": "number", "default": 50}}, "required": ["place"]},
    }},
    {"type": "function", "function": {
        "name": "get_road_hazards",
        "description": "Live road incidents near a place: accidents, closures, jams, hazards (TomTom). Give a place name.",
        "parameters": {"type": "object", "properties": {"place": {"type": "string"}}, "required": ["place"]},
    }},
    {"type": "function", "function": {
        "name": "geolocate_ip",
        "description": "Geolocate an IP address (city, country, ISP/org/ASN) and pin it on the map.",
        "parameters": {"type": "object", "properties": {"ip": {"type": "string"}}, "required": ["ip"]},
    }},
    {"type": "function", "function": {
        "name": "get_ransomware",
        "description": "Recent ransomware victim disclosures from leak sites (ransomware.live): victim org, ransomware group, country and sector. Use for cyber threat questions ('recent ransomware attacks', 'who is Qilin hitting', 'attacks in France/healthcare').",
        "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "default": 25}}},
    }},
    {"type": "function", "function": {
        "name": "get_breaches",
        "description": "Global data-breach database (Have I Been Pwned): recent worldwide breaches with name, date, accounts affected and data types leaked. Optionally filter by company/domain keyword.",
        "parameters": {"type": "object", "properties": {"q": {"type": "string"}, "limit": {"type": "integer", "default": 15}}},
    }},
    {"type": "function", "function": {
        "name": "get_weather",
        "description": "Current weather and wind at a place (temperature, wind speed/direction/gusts, precipitation, clouds, pressure) via Open-Meteo. Give a place name (city/region).",
        "parameters": {"type": "object", "properties": {"place": {"type": "string"}}, "required": ["place"]},
    }},
    {"type": "function", "function": {
        "name": "get_space_weather",
        "description": "Current space weather (NOAA SWPC): planetary Kp index, R/S/G storm scales and active alerts. Relevant to HF comms, GPS accuracy and satellite operations.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "get_vessels",
        "description": "Live ship traffic (AIS): total tracked vessels and a sample with name, type, speed and position.",
        "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "default": 12}}},
    }},
    {"type": "function", "function": {
        "name": "get_flights",
        "description": "Live aircraft (ADS-B): total tracked flights and any emergency-squawk aircraft with callsign and country.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "open_camera",
        "description": "Open a live public camera on the map UI for a place (city/landmark/road), e.g. 'London', 'Tower Bridge', 'California I-80'. Finds the nearest public camera and opens its player on the frontend. Use when the user wants to SEE a place live.",
        "parameters": {"type": "object", "properties": {"place": {"type": "string"}}, "required": ["place"]},
    }},
    {"type": "function", "function": {
        "name": "open_cameras_near",
        "description": "Open SEVERAL live cameras around a place at once (e.g. 'show me the cameras around Trafalgar Square'). Finds the nearest public cameras and opens their players.",
        "parameters": {"type": "object", "properties": {
            "place": {"type": "string"}, "count": {"type": "integer", "default": 3}}, "required": ["place"]},
    }},
    {"type": "function", "function": {
        "name": "area_intel",
        "description": "Full intelligence picture for a place: recent geopolitical events, live alerts, weather and nearby public cameras around it. Use for 'what's happening in/around X' or 'brief me on X'. Also recenters the map there.",
        "parameters": {"type": "object", "properties": {"place": {"type": "string"}}, "required": ["place"]},
    }},
    {"type": "function", "function": {
        "name": "apply_filters",
        "description": "Set the event map filters (GDELT): quad_class (1=verbal coop,2=material coop,3=verbal conflict,4=material conflict), country (FIPS code), actor name, hours (time window). Applies them to the map.",
        "parameters": {"type": "object", "properties": {
            "quad_class": {"type": "integer"}, "country": {"type": "string"},
            "actor": {"type": "string"}, "hours": {"type": "integer"}}},
    }},
    {"type": "function", "function": {
        "name": "focus_map",
        "description": "Fly/zoom the map to a point. IMPORTANT: when you already have the EXACT coordinates of the thing you are pointing at (from an event, quake, fire, hotspot, alert, camera or any tool result that returned lat/lon), pass those exact `lat` and `lon` for pinpoint accuracy — do NOT re-geocode a place name in that case. Only pass `place` when you have no coordinates. Use a higher zoom (11-14) for a precise point, lower (5-7) for a region. WARNING: GeoJSON coordinates are in [longitude, latitude] order — so for a feature with coordinates [X, Y], pass lon=X and lat=Y (do not swap them).",
        "parameters": {"type": "object", "properties": {
            "lat": {"type": "number", "description": "exact latitude of the target point"},
            "lon": {"type": "number", "description": "exact longitude of the target point"},
            "place": {"type": "string", "description": "place name, only if you have no coordinates"},
            "zoom": {"type": "integer", "default": 11}}},
    }},
    {"type": "function", "function": {
        "name": "toggle_layer",
        "description": "Turn a map data layer on or off. Layers: fires, quakes, eonet, vessels, flights, disasters, satellites, cameras, traffic, roads, weather, cyber.",
        "parameters": {"type": "object", "properties": {
            "layer": {"type": "string"}, "on": {"type": "boolean", "default": True}}, "required": ["layer"]},
    }},
    {"type": "function", "function": {
        "name": "get_prediction_markets",
        "description": "Polymarket prediction markets — real-money crowd-priced probabilities on geopolitical/economic/tech events, with money volume. Among the best-calibrated forecasting signals; use to ground probability estimates. Optionally filter by keyword (e.g. 'election', 'Fed', 'Ukraine', 'Iran').",
        "parameters": {"type": "object", "properties": {
            "q": {"type": "string", "description": "keyword to filter markets"},
            "limit": {"type": "integer", "default": 15},
        }},
    }},
]


def run_tool(name, args, db):
    if name == "get_stats":
        return {
            "events": db.execute(select(func.count(Event.id))).scalar(),
            "fires": db.execute(select(func.count(Fire.id))).scalar(),
            "vessels": db.execute(select(func.count(Vessel.mmsi))).scalar(),
            "sanctions": db.execute(select(func.count(Sanction.id))).scalar(),
            "disasters": db.execute(select(func.count(Disaster.id))).scalar(),
        }
    if name == "query_events":
        return _events(
            db=db, limit=min(int(args.get("limit", 20)), 40),
            quad_class=args.get("quad_class"), root_code=None,
            country=args.get("country"), actor=args.get("actor"),
            bbox=None, since_hours=args.get("since_hours"),
        )
    if name == "get_hotspots":
        return _hotspots(db=db, window_hours=int(args.get("window_hours", 48)), limit=12, cell=2.0, include_fires=True)
    if name == "get_alerts":
        return _alerts(db=db, hours=int(args.get("hours", 24)), limit=25)
    if name == "search_sanctions":
        return _sanctions(db=db, q=args["query"], limit=15)
    if name == "cyber_lookup":
        return _cyber(ip=args["ip"])
    if name == "finance_awards":
        return _finance(q=args["query"], limit=10)
    if name == "research_papers":
        return _research(q=args["query"], limit=8)
    if name == "get_markets":
        return _markets()
    if name == "get_prediction_markets":
        return _prediction(limit=min(int(args.get("limit", 15)), 30), q=args.get("q", ""))
    if name == "get_ransomware":
        return _ransomware(limit=min(int(args.get("limit", 25)), 60), geo=False)
    if name == "get_space_weather":
        return _spaceweather()
    if name == "get_breaches":
        return _breaches(limit=min(int(args.get("limit", 15)), 40), q=args.get("q", ""))
    if name == "get_fires":
        fc = _fires(db=db, limit=8000, bbox=None, min_frp=float(args.get("min_mw", 50)))
        feats = fc.get("features", [])
        feats_sorted = sorted(feats, key=lambda f: -(f["properties"].get("frp") or 0))[:12]
        top = [{"frp": f["properties"].get("frp"), "sat": f["properties"].get("satellite"),
                "lat": f["geometry"]["coordinates"][1], "lon": f["geometry"]["coordinates"][0]} for f in feats_sorted]
        return {"count": len(feats), "top_by_power": top}
    if name == "get_quakes":
        fc = _quakes(feed=args.get("feed", "2.5_day"))
        out = [{"mag": ft["properties"].get("mag"), "place": ft["properties"].get("place"),
                "depth_km": ft["properties"].get("depth_km")} for ft in fc.get("features", [])[:15]]
        return {"count": len(fc.get("features", [])), "quakes": out}
    if name == "get_infra":
        return _infra_status()
    if name == "get_powerplants":
        g = _geocode(q=args["place"], limit=1)
        hit = (g.get("results") or [None])[0]
        if not hit:
            return {"error": f"place not found: {args['place']}"}
        lat, lon = hit["lat"], hit["lon"]
        bbox = f"{lon-1.2},{lat-1.2},{lon+1.2},{lat+1.2}"
        fc = _powerplants(bbox=bbox, min_mw=float(args.get("min_mw", 50)), limit=40)
        plants = [{"name": f["properties"]["name"], "mw": f["properties"]["mw"],
                   "fuel": f["properties"]["fuel"]} for f in fc.get("features", [])]
        return {"_action": {"type": "focus_map", "lat": lat, "lon": lon, "zoom": 8},
                "place": hit["name"], "count": len(plants), "plants": plants[:25]}
    if name == "get_road_hazards":
        g = _geocode(q=args["place"], limit=1)
        hit = (g.get("results") or [None])[0]
        if not hit:
            return {"error": f"place not found: {args['place']}"}
        lat, lon = hit["lat"], hit["lon"]
        fc = _road_incidents(bbox=f"{lon-0.15},{lat-0.15},{lon+0.15},{lat+0.15}")
        haz = [{"label": f["properties"]["label"], "desc": f["properties"]["desc"]}
               for f in fc.get("features", [])[:15]]
        return {"_action": {"type": "focus_map", "lat": lat, "lon": lon, "zoom": 11},
                "place": hit["name"], "count": len(fc.get("features", [])), "hazards": haz}
    if name == "geolocate_ip":
        r = _geoip(ip=args["ip"])
        if r.get("found") and r.get("lat") is not None:
            r["_action"] = {"type": "focus_map", "lat": r["lat"], "lon": r["lon"], "zoom": 10}
        return r
    if name == "get_weather":
        g = _geocode(q=args["place"], limit=1)
        hit = (g.get("results") or [None])[0]
        if not hit:
            return {"error": f"place not found: {args['place']}"}
        return _weather(lat=hit["lat"], lon=hit["lon"])
    if name == "get_vessels":
        fc = _vessels(db=db, limit=6000, max_age_min=60, bbox=None)
        feats = fc.get("features", [])
        n = int(args.get("limit", 12))
        sample = [{"name": f["properties"].get("name"), "type": f["properties"].get("type_label"),
                   "sog": f["properties"].get("sog"), "lat": f["geometry"]["coordinates"][1],
                   "lon": f["geometry"]["coordinates"][0]} for f in feats[:n]]
        return {"tracked": len(feats), "sample": sample}
    if name == "get_flights":
        fc = _flights(bbox=None, limit=8000)
        feats = fc.get("features", [])
        emg = [{"callsign": f["properties"].get("callsign"), "country": f["properties"].get("country"),
                "emergency": f["properties"].get("emergency")} for f in feats
               if f["properties"].get("emergency")]
        return {"tracked": len(feats), "emergencies": emg[:15]}
    if name == "open_camera":
        g = _geocode(q=args["place"], limit=1)
        hit = (g.get("results") or [None])[0]
        if not hit:
            return {"error": f"place not found: {args['place']}"}
        cam = _nearest_camera(hit["lat"], hit["lon"])
        if not cam:
            return {"error": "no camera found near " + args["place"]}
        p = cam["properties"]
        cc = cam["geometry"]["coordinates"]
        return {
            "_action": {"type": "open_camera", "camera": {
                "id": p.get("id"), "title": p.get("title"), "source": p.get("source"),
                "city": p.get("city"), "country": p.get("country"),
                "lat": cc[1], "lon": cc[0],
                "image": p.get("image"), "stream": p.get("stream"),
                "mp4": p.get("mp4"), "embed": p.get("embed"),
            }},
            "opened": {"title": p.get("title"), "source": p.get("source"), "country": p.get("country")},
        }
    if name == "open_cameras_near":
        g = _geocode(q=args["place"], limit=1)
        hit = (g.get("results") or [None])[0]
        if not hit:
            return {"error": f"place not found: {args['place']}"}
        cams = _nearest_cameras(hit["lat"], hit["lon"], min(int(args.get("count", 3)), 6))
        acts, opened = [], []
        for cam in cams:
            p = cam["properties"]
            cc = cam["geometry"]["coordinates"]
            acts.append({"type": "open_camera", "camera": {
                "id": p.get("id"), "title": p.get("title"), "source": p.get("source"),
                "city": p.get("city"), "country": p.get("country"), "lat": cc[1], "lon": cc[0],
                "image": p.get("image"), "stream": p.get("stream"), "mp4": p.get("mp4"), "embed": p.get("embed"),
            }})
            opened.append({"title": p.get("title"), "source": p.get("source")})
        acts.append({"type": "focus_map", "lat": hit["lat"], "lon": hit["lon"], "zoom": 11})
        return {"_actions": acts, "opened": opened}
    if name == "area_intel":
        g = _geocode(q=args["place"], limit=1)
        hit = (g.get("results") or [None])[0]
        if not hit:
            return {"error": f"place not found: {args['place']}"}
        lat, lon = hit["lat"], hit["lon"]
        bbox = f"{lon-1.5},{lat-1.5},{lon+1.5},{lat+1.5}"
        events = _events(db=db, limit=12, quad_class=None, root_code=None, country=None,
                         actor=None, bbox=bbox, since_hours=72)
        ev_list = events.get("features", events) if isinstance(events, dict) else events
        all_alerts = _alerts(db=db, hours=48, limit=60).get("alerts", [])
        near_alerts = [a for a in all_alerts if a.get("lat") is not None
                       and abs(a["lat"] - lat) < 3 and abs(a["lon"] - lon) < 3][:10]
        cams = _nearest_cameras(lat, lon, 30)
        cams_near = sum(1 for c in cams
                        if abs(c["geometry"]["coordinates"][1] - lat) < 1.5
                        and abs(c["geometry"]["coordinates"][0] - lon) < 1.5)
        wx = _weather(lat=lat, lon=lon)
        return {
            "_action": {"type": "focus_map", "lat": lat, "lon": lon, "zoom": 8},
            "place": hit["name"],
            "events_nearby": ev_list if isinstance(ev_list, list) else ev_list.get("features", []),
            "alerts_nearby": near_alerts,
            "cameras_nearby": cams_near,
            "weather": {"condition": wx.get("condition"), "temp": wx.get("temp"),
                        "wind_speed": wx.get("wind_speed"), "wind_gusts": wx.get("wind_gusts")},
        }
    if name == "apply_filters":
        f = {}
        if args.get("quad_class") is not None:
            f["quad_class"] = str(args["quad_class"])
        if args.get("country"):
            f["country"] = str(args["country"]).upper()
        if args.get("actor"):
            f["actor"] = str(args["actor"])
        if args.get("hours") is not None:
            f["hours"] = int(args["hours"])
        return {"_action": {"type": "apply_filters", "filters": f}, "applied": f}
    if name == "focus_map":
        zoom = int(args.get("zoom", 11))
        # exact coordinates take priority — no geocoding drift
        if args.get("lat") is not None and args.get("lon") is not None:
            return {"_action": {"type": "focus_map", "lat": float(args["lat"]),
                                "lon": float(args["lon"]), "zoom": zoom},
                    "focused": f"{float(args['lat']):.4f},{float(args['lon']):.4f}"}
        if not args.get("place"):
            return {"error": "focus_map needs either lat+lon or a place name"}
        g = _geocode(q=args["place"], limit=1)
        hit = (g.get("results") or [None])[0]
        if not hit:
            return {"error": f"place not found: {args['place']}"}
        return {"_action": {"type": "focus_map", "lat": hit["lat"], "lon": hit["lon"],
                            "zoom": zoom}, "focused": hit["name"]}
    if name == "toggle_layer":
        layer_map = {
            "fires": "showFires", "quakes": "showQuakes", "earthquakes": "showQuakes",
            "eonet": "showEonet", "vessels": "showVessels", "ships": "showVessels",
            "flights": "showFlights", "aircraft": "showFlights", "disasters": "showDisasters",
            "satellites": "showSats", "sat": "showSats", "cameras": "showCams", "cams": "showCams",
            "traffic": "showTraffic", "roads": "showRoads", "weather": "showWeather",
            "cyber": "showCyber", "ransomware": "showCyber", "infra": "showInfra",
            "cables": "showInfra", "power": "showPower", "powerplants": "showPower",
            "air": "showAir", "no2": "showAir", "pollution": "showAir",
        }
        key = layer_map.get(str(args.get("layer", "")).lower())
        if not key:
            return {"error": f"unknown layer: {args.get('layer')}"}
        on = bool(args.get("on", True))
        return {"_action": {"type": "toggle_layer", "layer": key, "on": on}, "toggled": {key: on}}
    if name == "get_disasters":
        rows = db.execute(
            select(Disaster).where(Disaster.alert_level.in_(["Orange", "Red"])).limit(20)
        ).scalars().all()
        return [{"type": d.event_type, "level": d.alert_level, "name": d.name, "country": d.country} for d in rows]
    return {"error": f"unknown tool {name}"}


# A hard, unambiguous no-emoji rule that survives models that like to decorate.
_NO_EMOJI_FR = ("RÈGLE ABSOLUE : n'utilise JAMAIS d'emoji, d'émoticône, de pictogramme ni de symbole "
                "décoratif (aucun 📊 📈 🔥 ✅ 🌍 etc.), ni dans le texte ni dans les titres. Ton strictement "
                "professionnel et sobre d'analyste de renseignement. Tu peux structurer en titres et listes "
                "markdown, mais sans aucune décoration graphique. ")
_NO_EMOJI_EN = ("ABSOLUTE RULE: NEVER use emoji, emoticons, pictographs or decorative symbols (no 📊 📈 🔥 ✅ etc.), "
                "neither in text nor headings. Keep a strictly professional, sober intelligence-analyst tone. "
                "You may use markdown headings and lists, but no graphical decoration. ")

SYS = {
    "fr": (_NO_EMOJI_FR +
           "Tu es l'analyste OSINT de cette plateforme de renseignement. Tu t'appuies sur les DONNÉES RÉELLES "
           "du backend via les outils fournis, et tu PILOTES l'interface : tu peux ouvrir une caméra publique en "
           "direct (open_camera), recentrer/zoomer la carte (focus_map) et activer/désactiver des couches "
           "(toggle_layer). Enchaîne plusieurs outils si besoin. Après avoir agi et récupéré les données, "
           "synthétise en français, factuellement, en citant des chiffres et acteurs concrets, et tire des "
           "DÉDUCTIONS utiles (corrélations, risques, recommandations). Croise les sources."),
    "en": (_NO_EMOJI_EN +
           "You are this intelligence platform's OSINT analyst. You ground answers in the backend's REAL DATA via "
           "the tools, and you DRIVE the interface: open a live public camera (open_camera), recenter/zoom the map "
           "(focus_map) and toggle layers (toggle_layer). Chain tools as needed. After acting and gathering data, "
           "synthesize factually in English with concrete numbers, and draw useful DEDUCTIONS (correlations, risks, "
           "recommendations), cross-referencing sources."),
    "ar": ("قاعدة صارمة: لا تستخدم أبداً أي رموز تعبيرية أو إيموجي أو رموز زخرفية إطلاقاً. حافظ على نبرة مهنية "
           "رصينة كمحلل استخبارات. أنت محلل OSINT في هذه المنصة، تعتمد على البيانات الحقيقية عبر الأدوات، ويمكنك "
           "التحكم بالواجهة: فتح كاميرا (open_camera)، تحريك الخريطة (focus_map)، تفعيل الطبقات (toggle_layer). "
           "بعد جمع البيانات، قدّم تحليلاً واقعياً بالعربية مع أرقام ملموسة واستنتاجات مفيدة."),
    "ru": ("СТРОГОЕ ПРАВИЛО: НИКОГДА не используйте эмодзи, эмотиконы или декоративные символы. Держите строго "
           "профессиональный, сдержанный тон аналитика разведки. Вы — OSINT-аналитик этой платформы, опираетесь "
           "на РЕАЛЬНЫЕ данные через инструменты и УПРАВЛЯЕТЕ интерфейсом: open_camera, focus_map, toggle_layer. "
           "После сбора данных дайте фактическую сводку на русском с конкретными цифрами и полезными ВЫВОДАМИ."),
}


_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U00002B00-\U00002BFF"
    "\U0001F1E6-\U0001F1FF\U00002190-\U000021FF\U0000FE00-\U0000FE0F\U00002700-\U000027BF]"
)


def _strip_emoji(text: str) -> str:
    """Guarantee an emoji-free analyst reply regardless of the model's habits."""
    if not text:
        return text
    return re.sub(r"[ \t]{2,}", " ", _EMOJI_RE.sub("", text)).strip()


class ChatReq(BaseModel):
    messages: list
    lang: str = "fr"


def _post(convo, with_tools=True):
    body = {
        "model": settings.llm_model,
        "messages": convo,
        "temperature": 0.3,
        "max_tokens": 1400,
        "stream": False,
    }
    if with_tools:
        body["tools"] = TOOLS
        body["tool_choice"] = "auto"
    r = requests.post(f"{settings.llm_base_url}/chat/completions", headers=_llm_headers(), json=body, timeout=180)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]


_rl: dict = {}  # ip -> [timestamps] for public-mode rate limiting


def _rate_limited(request: Request) -> bool:
    if not settings.public_mode:
        return False
    ip = request.client.host if request.client else "?"
    now = time.time()
    hits = [t for t in _rl.get(ip, []) if now - t < 60]
    if len(hits) >= settings.chat_rate_per_min:
        _rl[ip] = hits
        return True
    hits.append(now)
    _rl[ip] = hits
    return False


@router.post("/chat")
def chat_endpoint(req: ChatReq, request: Request):
    if _rate_limited(request):
        return {"reply": "Trop de requêtes — réessaie dans une minute. / Rate limit, try again shortly.",
                "tools_used": [], "actions": []}
    if not available():
        return {"reply": "LLM local indisponible (:8080)."}

    convo = [{"role": "system", "content": SYS.get(req.lang, SYS["fr"])}]
    convo += [{"role": m["role"], "content": m.get("content", "")} for m in req.messages][-12:]

    used = []
    actions = []
    for _ in range(5):
        try:
            msg = _post(convo, with_tools=True)
        except requests.RequestException as exc:
            return {"reply": f"Erreur LLM: {exc}", "tools_used": used, "actions": actions}

        tool_calls = msg.get("tool_calls")
        convo.append({k: v for k, v in msg.items() if k in ("role", "content", "tool_calls")})

        if not tool_calls:
            return {"reply": _strip_emoji(msg.get("content", "")) or "(réponse vide)", "tools_used": used, "actions": actions}

        db = SessionLocal()
        try:
            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                try:
                    a = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    a = {}
                used.append(name)
                try:
                    result = run_tool(name, a, db)
                except Exception as exc:  # noqa: BLE001
                    result = {"error": str(exc)}
                if isinstance(result, dict):
                    if result.get("_action"):
                        actions.append(result["_action"])
                    if isinstance(result.get("_actions"), list):
                        actions.extend(result["_actions"])
                convo.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", name),
                    "name": name,
                    "content": json.dumps(result, default=str)[:5000],
                })
        finally:
            db.close()

    # final answer without tools
    try:
        msg = _post(convo, with_tools=False)
        return {"reply": _strip_emoji(msg.get("content", "")) or "(réponse vide)", "tools_used": used, "actions": actions}
    except requests.RequestException as exc:
        return {"reply": f"Erreur LLM: {exc}", "tools_used": used, "actions": actions}
