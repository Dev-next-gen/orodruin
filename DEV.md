# OSINT Platform — Dev (GDELT vertical slice)

First runnable slice: **GDELT → PostgreSQL → FastAPI → React/MapLibre map**.

## Stack in this slice
- `db` — PostgreSQL 16 (Docker, port 5544 on host)
- `backend/` — FastAPI + SQLAlchemy 2.0 + a GDELT ingester (Python 3.12)
- `frontend/` — React 18 + Vite + MapLibre GL (no API token, CARTO dark basemap)

## 1. Start the database
```bash
docker compose up -d
```

## 2. Backend (venv)
```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# create tables + pull the latest 15-min GDELT slice (~2k events)
python -m app.ingest.run --once

# serve the API
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Keep it fed live in another shell:
```bash
python -m app.ingest.run --loop 900
```

## 3. Frontend
```bash
cd frontend
npm install
npm run dev      # http://<server-ip>:5173
```

## API
- `GET /health`
- `GET /api/events?limit=&quad_class=&country=&actor=&root_code=&bbox=w,s,e,n`
- `GET /api/events/geojson?...` — FeatureCollection for the map
- `GET /api/stats` — totals, by class, top countries
- `GET /api/graph?limit=&country=` — actor co-occurrence graph (for slice 2)

## Next slices
2. Actor co-occurrence graph view (endpoint already live) + ACLED & SIPRI ingesters
3. Local LLM layer (ROCm): entity extraction, threat scoring, summaries
4. Neo4j graph store, ElasticSearch full-text, Kafka real-time
