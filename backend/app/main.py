from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api import (
    wxtiles,
    route,
    settings_api,
    airquality,
    breaches,
    alerts,
    analysis,
    cameras,
    chat,
    config_api,
    conflicts,
    cyber,
    disasters,
    eonet,
    events,
    finance,
    fires,
    geocode,
    cyberthreat,
    geoip,
    globe_feed,
    powerplants,
    prediction,
    spaceweather,
    roads,
    tv,
    flights,
    graph,
    gtile,
    hotspots,
    infra,
    markets,
    news,
    quakes,
    research,
    sanctions,
    satellites,
    traffic,
    satellite,
    vessels,
    weather,
)
from app.db import Base, engine

Base.metadata.create_all(engine)

app = FastAPI(
    title="OSINT Platform API",
    version="0.1.0",
    description="Open-source intelligence aggregation — GDELT vertical slice.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
# compress large JSON/GeoJSON responses (cameras ~2.4MB, cables, power plants…)
app.add_middleware(GZipMiddleware, minimum_size=1024)

app.include_router(events.router)
app.include_router(graph.router)
app.include_router(analysis.router)
app.include_router(config_api.router)
app.include_router(settings_api.router)
app.include_router(fires.router)
app.include_router(conflicts.router)
app.include_router(quakes.router)
app.include_router(eonet.router)
app.include_router(vessels.router)
app.include_router(flights.router)
app.include_router(hotspots.router)
app.include_router(disasters.router)
app.include_router(news.router)
app.include_router(sanctions.router)
app.include_router(satellite.router)
app.include_router(airquality.router)
app.include_router(cyber.router)
app.include_router(alerts.router)
app.include_router(finance.router)
app.include_router(research.router)
app.include_router(cameras.router)
app.include_router(chat.router)
app.include_router(satellites.router)
app.include_router(geocode.router)
app.include_router(traffic.router)
app.include_router(gtile.router)
app.include_router(markets.router)
app.include_router(globe_feed.router)
app.include_router(infra.router)
app.include_router(powerplants.router)
app.include_router(cyberthreat.router)
app.include_router(breaches.router)
app.include_router(geoip.router)
app.include_router(spaceweather.router)
app.include_router(weather.router)
app.include_router(wxtiles.router)
app.include_router(prediction.router)
app.include_router(roads.router)
app.include_router(route.router)
app.include_router(tv.router)


@app.get("/health")
def health():
    return {"status": "ok"}
