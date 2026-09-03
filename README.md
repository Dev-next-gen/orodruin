# OSINT Platform

> Open-source alternative to Palantir Gotham — intelligence aggregation, entity graph, real-time threat analysis from 50+ public sources.

**Status: 🚧 Active Development**

## Vision

Palantir Gotham costs $25M+/year. Intelligence capabilities shouldn't require a defense budget. This platform aggregates the same quality of open-source intelligence using public APIs, declassified data, and AI-powered analysis.

Inspired by Palantir's Ontology SDK ([gotham-platform-python](https://github.com/palantir/gotham-platform-python)), Blueprint UI components, and their open architecture principles (Apache Iceberg, Spark, ElasticSearch).

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                             │
│         React + Palantir Blueprint UI + MapBox              │
│    ┌──────────┬──────────┬──────────┬──────────────────┐    │
│    │  Map     │  Graph   │  Timeline│  Alert Feed      │    │
│    │  View    │  View    │  View    │  (real-time)     │    │
│    └──────────┴──────────┴──────────┴──────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│                      API Gateway (FastAPI)                   │
├──────────────┬──────────────┬───────────────────────────────┤
│  Ontology    │  Analysis    │  Ingest Pipeline              │
│  Engine      │  Engine      │  (50+ sources)                │
│  (Neo4j)     │  (LLM-based) │  (Celery + Redis)             │
├──────────────┴──────────────┴───────────────────────────────┤
│              Storage Layer                                   │
│  PostgreSQL (events) │ Neo4j (graph) │ ElasticSearch (search)│
└─────────────────────────────────────────────────────────────┘
```

## Ontology Model (Palantir-inspired)

The core data model mirrors Palantir's Ontology SDK:

```
Object Types:
├── Actor          (state, non-state, individual)
├── Event          (conflict, sanction, strike, movement)
├── Location       (country, region, coordinates, facility)
├── Asset          (weapon system, vessel, aircraft, facility)
├── Organization   (military unit, NGO, company, network)
└── Document       (report, cable, intercept, publication)

Link Types:
├── Actor    ──[CONTROLS]──►   Asset
├── Actor    ──[LOCATED_IN]──► Location
├── Event    ──[OCCURRED_AT]── Location
├── Actor    ──[SANCTIONED_BY]─ Organization
├── Actor    ──[LINKED_TO]────  Actor
└── Asset    ──[USED_IN]──────  Event
```

## Data Sources — 6 Levels

### Level 1 — Official Declassified Sources
| Source | Content | Update |
|--------|---------|--------|
| IAEA (iaea.org) | Nuclear worldwide | Weekly |
| SIPRI (sipri.org) | Arsenals / conflicts | Monthly |
| ISW (understandingwar.org) | Real-time conflict maps | Daily |
| ACLED (acleddata.com) | 185k+ violent events | API |
| GDELT Project | All events since 1979 | 15 min |
| UN OCHA (reliefweb.int) | Humanitarian crises | Daily |
| ICG (crisisgroup.org) | Emerging conflicts | Weekly |
| FAS (fas.org) | Nuclear weapons | Monthly |
| OpenSanctions | Sanctioned entities | Daily |
| OFAC (treasury.gov) | US sanctions | Daily |
| EU Sanctions Map | EU sanctions | Daily |
| CIA World Factbook | Country data | Yearly |
| RAND Corporation | Strategic studies | Monthly |

### Level 2 — Satellite Intelligence
| Source | Resolution | Frequency |
|--------|-----------|-----------|
| Sentinel Hub (ESA) | 10m | 5 days |
| Copernicus (EU) | 10m | Real-time |
| Google Earth Engine | Archive | On-demand |
| NASA FIRMS | Thermal detection | 3h |
| MarineTraffic | Vessel tracking | Real-time |
| ADS-B Exchange | Military flights | Real-time |
| FlightRadar24 | Air traffic | Real-time |

### Level 3 — HUMINT / Social Media
| Source | Content | Method |
|--------|---------|--------|
| Telegram OSINT channels | Raw field reports | Monitoring |
| Twitter/X OSINT community | Geolocated imagery | List monitoring |
| Bellingcat | OSINT investigations | Scraping |
| Strava / fitness apps | Military positions | Periodic analysis |
| Shodan | Connected systems | API |
| Censys | Infrastructure + TLS | API |
| GreyNoise | Anomalous network activity | API |

### Level 4 — Financial & Economic
| Source | Signal | Access |
|--------|--------|--------|
| UN COMTRADE | Arms transfers (disguised) | Free API |
| OpenCorporates | Shell companies | API |
| ICIJ (Pandora/Panama) | Hidden financial networks | Search |
| Kpler | Oil flows | API |
| USASpending.gov | US government contracts | Free |
| EDGAR (SEC) | Listed defense contracts | Free |
| VesselFinder | Tankers / cargo | Free |
| OpenStreetMap/Overpass | Physical infrastructure | Free API |

### Level 5 — Academic & Technical
| Source | Content | Access |
|--------|---------|--------|
| ArXiv | Nuclear / missile publications | Free API |
| Semantic Scholar | Cross-citations | Free API |
| CSIS Missile Threat | Missile database | Free |
| Nuclear Notebook (FAS) | Arsenal by country | Free |
| Arms Control Association | Treaties / violations | Free |
| NTI Nuclear Security Index | Risk score by country | Free |

### Level 6 — Legal Grey Sources
| Source | Content |
|--------|---------|
| FOIA requests (USA) | Declassified documents |
| EU National Archives (+30y) | Diplomatic cables |
| NATO public reports | Threat assessments |
| Congressional Research Service | Geopolitical analysis |
| EU Parliament reports | Geopolitical analysis |

## Tech Stack

```
Backend:
  Python 3.12 + FastAPI + Celery + Redis
  PostgreSQL 16 (events, timeseries)
  Neo4j 5 (entity graph / ontology)
  ElasticSearch 8 (full-text search)
  Apache Kafka (event streaming)

Frontend:
  React 19 + TypeScript
  Palantir Blueprint UI (open-source)
  MapBox GL (geospatial visualization)
  D3.js + Plottable (charts)
  Framer Motion (animations)

AI Layer:
  Local LLM (Qwen2.5 14B/72B via llama.cpp)
  Entity extraction, event classification
  Threat scoring, pattern recognition
  Summary generation

Infrastructure:
  Docker + Kubernetes
  AMD ROCm for AI inference
  Prometheus + Grafana monitoring
```

## Comparison to Palantir Gotham

| Feature | Palantir Gotham | OSINT Platform |
|---------|----------------|----------------|
| Entity graph | ✅ | ✅ Neo4j |
| Real-time feeds | ✅ | ✅ Kafka |
| Map visualization | ✅ | ✅ MapBox |
| AI analysis | ✅ | ✅ Local LLM |
| Satellite imagery | ✅ Premium | ✅ ESA/Copernicus (free) |
| Cost | $25M+/year | Self-hosted |
| Source code | Proprietary | Open-source (MIT) |

## Quick Start

```bash
git clone https://github.com/Dev-next-gen/osint-platform
cd osint-platform

# Start all services
docker-compose up -d

# Initialize database + ontology
./scripts/init-db.sh

# Start ingestion pipeline
python ingest/start.py --sources level1,level2

# Open dashboard
open http://localhost:3000
```

## Roadmap

- [x] Architecture design
- [x] Ontology model (Palantir-inspired)
- [x] Source catalog (50+ sources)
- [ ] Core ingestion pipeline (GDELT, ACLED, SIPRI)
- [ ] Entity extraction (LLM-based)
- [ ] Neo4j graph model
- [ ] React dashboard + MapBox integration
- [ ] Satellite imagery layer (Sentinel Hub)
- [ ] Financial signals integration
- [ ] API v1 public release

## Contributing

This is an open-source intelligence tool for research, journalism, and academic use. All data sources used are publicly available and legally accessible.

## License

MIT — Léo Camus / [NextGen Labs](https://nextgen-labs.net)

---

*Inspired by Palantir's open-source ecosystem: [gotham-platform-python](https://github.com/palantir/gotham-platform-python), [Blueprint](https://github.com/palantir/blueprint), [osdk-ts](https://github.com/palantir/osdk-ts)*

