import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { nightPolygon, terminatorLine } from "./terminator.js";

function angDist(lng1, lat1, lng2, lat2) {
  const r = (x) => (x * Math.PI) / 180;
  const dlat = r(lat2 - lat1), dlng = r(lng2 - lng1);
  const a = Math.sin(dlat / 2) ** 2 + Math.cos(r(lat1)) * Math.cos(r(lat2)) * Math.sin(dlng / 2) ** 2;
  return (2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a)) * 180) / Math.PI;
}
const NOTE_CARD_W = 250;

// id of the first road/label layer of the current style → insert base overlays BELOW it
function beforeLabels(map) {
  try {
    for (const l of map.getStyle().layers) {
      if (l.type === "symbol" || /place|label|poi|road|transport|boundar|water_name|country/i.test(l.id)) {
        return l.id;
      }
    }
  } catch { /* style not ready */ }
  return undefined;
}

const QUAD_COLORS = { 1: "#3fb950", 2: "#58a6ff", 3: "#d29922", 4: "#f85149" };

// Free basemaps, no API key. Satellite = Esri World Imagery (Google-Earth-like).
const DARK_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";
// Hybrid satellite: Esri imagery + free Esri reference overlays (roads + place names)
const SATELLITE_STYLE = {
  version: 8,
  glyphs: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/{fontstack}/{range}.pbf",
  sources: {
    esri: {
      type: "raster",
      tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
      tileSize: 256,
      attribution: "Esri, Maxar, Earthstar Geographics",
    },
    esriTransport: {
      type: "raster",
      tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}"],
      tileSize: 256,
    },
    esriPlaces: {
      type: "raster",
      tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"],
      tileSize: 256,
    },
  },
  layers: [
    { id: "esri", type: "raster", source: "esri" },
    { id: "esriTransport", type: "raster", source: "esriTransport" },
    { id: "esriPlaces", type: "raster", source: "esriPlaces" },
  ],
};

const STREETS_STYLE = "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json";

const BASEMAPS = {
  dark: { style: DARK_STYLE, projection: "mercator" },
  streets: { style: STREETS_STYLE, projection: "mercator" },
  satellite: { style: SATELLITE_STYLE, projection: "mercator" },
  // globe = hybrid satellite: Earth imagery loads immediately, roads/labels on zoom
  globe: { style: SATELLITE_STYLE, projection: "globe" },
};

const L = {
  fr: {
    dark: "2D Sombre", satellite: "2D Satellite", globe: "3D Globe",
    actors: "Acteurs", place: "Lieu", published: "Publié (réseau)",
    eventDate: "Date de l'événement", class: "Classe", tone: "Tonalité",
    mentions: "Mentions", source: "source", fire: "Feu actif", detected: "Détecté",
    power: "Puissance (FRP)", confidence: "Confiance", satLabel: "Satellite",
    quake: "Séisme", magnitude: "Magnitude", depth: "Profondeur", when: "Date/heure",
    natEvent: "Événement naturel", category: "Catégorie",
    vessel: "Navire", speed: "Vitesse", course: "Cap", type: "Type", updated: "MàJ",
    flight: "Vol", altitude: "Altitude", ground: "au sol", country: "Pays",
    disaster: "Catastrophe", alertLevel: "Niveau d'alerte", severity: "Sévérité",
  },
  en: {
    dark: "2D Dark", satellite: "2D Satellite", globe: "3D Globe",
    actors: "Actors", place: "Place", published: "Published (network)",
    eventDate: "Event date", class: "Class", tone: "Tone",
    mentions: "Mentions", source: "source", fire: "Active fire", detected: "Detected",
    power: "Power (FRP)", confidence: "Confidence", satLabel: "Satellite",
    quake: "Earthquake", magnitude: "Magnitude", depth: "Depth", when: "Date/time",
    natEvent: "Natural event", category: "Category",
    vessel: "Vessel", speed: "Speed", course: "Course", type: "Type", updated: "Updated",
    flight: "Flight", altitude: "Altitude", ground: "on ground", country: "Country",
    disaster: "Disaster", alertLevel: "Alert level", severity: "Severity",
  },
};

const DISASTER_COLORS = [
  "match", ["get", "alert_level"],
  "Red", "#ff2d2d",
  "Orange", "#ff8c1a",
  "Green", "#3fb950",
  "#8b949e",
];

const VESSEL_COLORS = [
  "match", ["get", "type_label"],
  "Cargo", "#f0a020",
  "Tanker", "#e0574a",
  "Passenger", "#4dd2ff",
  "Fishing", "#7ee787",
  "Military", "#ff4d4d",
  "High-speed", "#d24dff",
  "Special", "#c9b458",
  "#8b949e",
];

// EONET category colors
const EONET_COLORS = [
  "match", ["get", "category_id"],
  "severeStorms", "#4dabff",
  "volcanoes", "#ff4d4d",
  "wildfires", "#ff9f1a",
  "floods", "#22d3ee",
  "seaLakeIce", "#dfe7ff",
  "drought", "#d2a679",
  "dustHaze", "#c9b458",
  "landslides", "#b3844d",
  "#a371f7",
];

const SAT_COLORS = [
  "match", ["get", "group"],
  "stations", "#ffffff",
  "gps", "#ff9f1a",
  "#31e6ff",
];

export default function MapView({ query, version, tick = 0, onCount, onCamera, lang = "fr", showFires = false, showQuakes = false, showEonet = false, showVessels = false, showFlights = false, showDisasters = false, showSat = false, showSats = false, showCams = false, showTraffic = false, showRoads = false, showWeather = false, showCyber = false, showInfra = false, showPower = false, showAir = false, airProduct = "no2", wxMode = "precip", showGoogleHD = false, basemap = "dark", focus = null, route = null, markers = [], onMapClick = null }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const dataRef = useRef(null);
  const firesRef = useRef(null);
  const firesLoadedRef = useRef(false);
  const quakesRef = useRef(null);
  const quakesLoadedRef = useRef(false);
  const eonetRef = useRef(null);
  const eonetLoadedRef = useRef(false);
  const vesselsRef = useRef(null);
  const vesselsLoadedRef = useRef(false);
  const flightsRef = useRef(null);
  const flightsLoadedRef = useRef(false);
  const disastersRef = useRef(null);
  const disastersLoadedRef = useRef(false);
  const satsRef = useRef(null);
  const satsLoadedRef = useRef(false);
  const camsRef = useRef(null);
  const camsLoadedRef = useRef(false);
  const roadsRef = useRef(null);
  const roadsLoadedRef = useRef(false);
  const cyberRef = useRef(null);
  const cyberLoadedRef = useRef(false);
  const infraCablesRef = useRef(null);
  const infraLandingRef = useRef(null);
  const infraLoadedRef = useRef(false);
  const powerRef = useRef(null);
  const powerLoadedRef = useRef(false);
  const wxTemplateRef = useRef(null);
  const markerObjsRef = useRef({});
  const onMapClickRef = useRef(onMapClick);
  onMapClickRef.current = onMapClick;
  const basemapRef = useRef(basemap);
  const spinRef = useRef(false);
  const globeAlertsRef = useRef([]);
  const activeNotesRef = useRef([]);
  const noteTsRef = useRef(0);
  const [globeNotes, setGlobeNotes] = useState([]);
  const [satOverlay, setSatOverlay] = useState([]);
  const satTsRef = useRef(0);
  const [colOffset, setColOffset] = useState({ left: 0, right: 0 });

  // On the globe: lift satellites a few pixels off the surface (fixed screen offset,
  // so it survives zoom) along the outward radial from the view centre → "orbit" feel.
  function updateSatOverlay() {
    const map = mapRef.current, cont = containerRef.current;
    if (!map || !cont || basemapRef.current !== "globe" || !showSatsRef.current || !satsRef.current) {
      if (satOverlay.length) setSatOverlay([]);
      return;
    }
    const c = map.getCenter();
    const W = cont.clientWidth, H = cont.clientHeight;
    const cx = W / 2, cy = H / 2;
    const out = [];
    for (const f of satsRef.current.features) {
      const [lon, lat] = f.geometry.coordinates;
      if (angDist(c.lng, c.lat, lon, lat) > 89) continue; // visible hemisphere only
      const p = map.project([lon, lat]);
      if (p.x < -20 || p.y < -20 || p.x > W + 20 || p.y > H + 20) continue;
      let dx = p.x - cx, dy = p.y - cy;
      const d = Math.hypot(dx, dy) || 1;
      const lift = 6 + Math.min(26, (f.properties.altitude_km / 6371) * 34); // small, fixed px
      out.push({
        id: f.properties.norad,
        x: p.x + (dx / d) * lift,
        y: p.y + (dy / d) * lift,
        sx: p.x, sy: p.y,
        group: f.properties.group,
      });
    }
    setSatOverlay(out);
  }

  function startColDrag(side, e, note) {
    e.preventDefault();
    const startX = e.clientX;
    const start = colOffset[side];
    let moved = 0;
    const move = (ev) => { moved += Math.abs(ev.movementX); setColOffset((o) => ({ ...o, [side]: start + (ev.clientX - startX) })); };
    const up = () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
      // a click (no real drag) on a note flies the map to its exact point
      if (moved < 5 && note && note.lat != null) {
        spinRef.current = false;
        mapRef.current.flyTo({ center: [note.lon, note.lat], zoom: 5, duration: 1400 });
      }
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  }
  const langRef = useRef(lang);
  langRef.current = lang;
  const onCameraRef = useRef(onCamera);
  onCameraRef.current = onCamera;

  // pick a random set of visible-hemisphere items → they appear/change as the globe turns
  function pickGlobeNotes() {
    const map = mapRef.current;
    if (!map || basemapRef.current !== "globe") return;
    const c = map.getCenter();
    const visible = globeAlertsRef.current.filter((a) => angDist(c.lng, c.lat, a.lon, a.lat) <= 72);
    for (let i = visible.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [visible[i], visible[j]] = [visible[j], visible[i]];
    }
    activeNotesRef.current = visible.slice(0, 6);
    updateGlobeNotes();
  }

  function updateGlobeNotes() {
    const map = mapRef.current, cont = containerRef.current;
    if (!map || !cont || basemapRef.current !== "globe") {
      if (globeNotes.length) setGlobeNotes([]);
      return;
    }
    const center = map.getCenter();
    const out = [];
    for (const a of activeNotesRef.current) {
      if (angDist(center.lng, center.lat, a.lon, a.lat) > 76) continue; // rotated out of view
      const p = map.project([a.lon, a.lat]);
      out.push({ ...a, x: p.x, y: p.y });
    }
    setGlobeNotes(out); // random order, no priority
  }

  function spinStep() {
    const map = mapRef.current;
    if (!map || !spinRef.current) return;
    if (map.getZoom() >= 3.2) { spinRef.current = false; return; } // zoomed in → fixed
    const c = map.getCenter();
    c.lng -= 4; // ~90 s per revolution
    map.easeTo({ center: c, duration: 1000, easing: (n) => n });
  }

  // keep current toggle states in refs so re-created layers (after setStyle) get the right visibility
  const showSatRef = useRef(showSat); showSatRef.current = showSat;
  const showFiresRef = useRef(showFires); showFiresRef.current = showFires;
  const showQuakesRef = useRef(showQuakes); showQuakesRef.current = showQuakes;
  const showEonetRef = useRef(showEonet); showEonetRef.current = showEonet;
  const showVesselsRef = useRef(showVessels); showVesselsRef.current = showVessels;
  const showFlightsRef = useRef(showFlights); showFlightsRef.current = showFlights;
  const showDisastersRef = useRef(showDisasters); showDisastersRef.current = showDisasters;
  const showSatsRef = useRef(showSats); showSatsRef.current = showSats;
  const showCamsRef = useRef(showCams); showCamsRef.current = showCams;
  const showTrafficRef = useRef(showTraffic); showTrafficRef.current = showTraffic;
  const showRoadsRef = useRef(showRoads); showRoadsRef.current = showRoads;
  const showWeatherRef = useRef(showWeather); showWeatherRef.current = showWeather;
  const wxModeRef = useRef(wxMode); wxModeRef.current = wxMode;
  const showCyberRef = useRef(showCyber); showCyberRef.current = showCyber;
  const showInfraRef = useRef(showInfra); showInfraRef.current = showInfra;
  const showPowerRef = useRef(showPower); showPowerRef.current = showPower;
  const showAirRef = useRef(showAir); showAirRef.current = showAir;
  const airProductRef = useRef(airProduct); airProductRef.current = airProduct;
  const showGHDRef = useRef(showGoogleHD); showGHDRef.current = showGoogleHD;

  function applyVisibility(map) {
    const m = {
      "sat-raster": showSatRef.current,
      "ghd-raster": showGHDRef.current,
      "traffic-raster": showTrafficRef.current,
      "fire-circles": showFiresRef.current,
      "quake-circles": showQuakesRef.current,
      "eonet-circles": showEonetRef.current,
      "vessel-circles": showVesselsRef.current,
      "flight-circles": showFlightsRef.current,
      "disaster-circles": showDisastersRef.current,
      // globe → satellites shown as slightly-lifted overlay; 2D → flat layer
      "sat-circles": showSatsRef.current && basemapRef.current !== "globe",
      "cam-circles": showCamsRef.current,
      "road-circles": showRoadsRef.current,
      "weather-raster": showWeatherRef.current,
      "cyber-circles": showCyberRef.current,
      "infra-cables-line": showInfraRef.current,
      "infra-landing-circles": showInfraRef.current,
      "power-circles": showPowerRef.current,
      "air-raster": showAirRef.current,
    };
    for (const [id, on] of Object.entries(m)) {
      if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
    }
  }

  function addSatLayer(map) {
    if (!map.getSource("sat")) {
      map.addSource("sat", {
        type: "raster",
        tiles: [`${window.location.origin}/api/satellite/{z}/{x}/{y}.jpg`],
        tileSize: 256,
        maxzoom: 16,
        attribution: "Sentinel-2 / Copernicus",
      });
    }
    if (!map.getLayer("sat-raster")) {
      map.addLayer({
        id: "sat-raster",
        type: "raster",
        source: "sat",
        layout: { visibility: showSatRef.current ? "visible" : "none" },
        paint: { "raster-opacity": 1 },
      }, beforeLabels(map));
    }
  }

  function addGoogleHDLayer(map) {
    if (!map.getSource("ghd")) {
      map.addSource("ghd", {
        type: "raster",
        tiles: [`${window.location.origin}/api/gtile/{z}/{x}/{y}.png`],
        tileSize: 256,
        minzoom: 6,
        maxzoom: 20, // Google 2D satellite tops out ~20; beyond, MapLibre over-zooms
        attribution: "© Google",
      });
    }
    if (!map.getLayer("ghd-raster")) {
      map.addLayer({
        id: "ghd-raster",
        type: "raster",
        source: "ghd",
        layout: { visibility: showGHDRef.current ? "visible" : "none" },
        paint: { "raster-opacity": 1 },
      }, beforeLabels(map));
    }
  }

  function addTrafficLayer(map) {
    if (!map.getSource("traffic")) {
      map.addSource("traffic", {
        type: "raster",
        tiles: [`${window.location.origin}/api/traffic/{z}/{x}/{y}.png`],
        tileSize: 256,
        attribution: "Traffic © TomTom",
      });
    }
    if (!map.getLayer("traffic-raster")) {
      map.addLayer({
        id: "traffic-raster",
        type: "raster",
        source: "traffic",
        layout: { visibility: showTrafficRef.current ? "visible" : "none" },
        paint: { "raster-opacity": 0.9 },
      }, beforeLabels(map));
    }
  }

  function addNightLayer(map) {
    if (!map.getSource("nightside")) {
      map.addSource("nightside", { type: "geojson", data: nightPolygon(new Date()) });
    }
    if (!map.getLayer("nightside-fill")) {
      map.addLayer({
        id: "nightside-fill",
        type: "fill",
        source: "nightside",
        paint: { "fill-color": "#02060f", "fill-opacity": 0.35 },
      }, beforeLabels(map));
    }
    if (!map.getSource("nightline")) {
      map.addSource("nightline", { type: "geojson", data: terminatorLine(new Date()) });
    }
    if (!map.getLayer("nightline-line")) {
      map.addLayer({
        id: "nightline-line",
        type: "line",
        source: "nightline",
        paint: { "line-color": "#ffc55e", "line-width": 1.6, "line-opacity": 0.75, "line-blur": 1 },
      });
    }
  }

  function updateNight() {
    const map = mapRef.current;
    if (!map) return;
    const d = new Date();
    if (map.getSource("nightside")) map.getSource("nightside").setData(nightPolygon(d));
    if (map.getSource("nightline")) map.getSource("nightline").setData(terminatorLine(d));
  }

  function addEventsLayer(map) {
    if (!map.getSource("events")) {
      map.addSource("events", { type: "geojson", data: dataRef.current || emptyFC() });
    }
    if (!map.getLayer("events-circles")) {
      map.addLayer({
        id: "events-circles",
        type: "circle",
        source: "events",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 1, 3, 6, 7],
          "circle-color": [
            "match", ["get", "quad_class"],
            1, QUAD_COLORS[1], 2, QUAD_COLORS[2],
            3, QUAD_COLORS[3], 4, QUAD_COLORS[4], "#8b949e",
          ],
          "circle-opacity": 0.85,
          "circle-stroke-width": 0.5,
          "circle-stroke-color": "#0d1117",
        },
      });
    }
  }

  function addFiresLayer(map) {
    if (!map.getSource("fires")) {
      map.addSource("fires", { type: "geojson", data: firesRef.current || emptyFC() });
    }
    if (!map.getLayer("fire-circles")) {
      map.addLayer({
        id: "fire-circles",
        type: "circle",
        source: "fires",
        layout: { visibility: showFiresRef.current ? "visible" : "none" },
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 1, 2, 6, 5],
          "circle-color": [
            "interpolate", ["linear"], ["coalesce", ["get", "frp"], 0],
            0, "#ffe066", 15, "#ff9f1a", 60, "#f8552b", 200, "#e01e1e",
          ],
          "circle-opacity": 0.9,
          "circle-blur": 0.3,
        },
      });
    }
  }

  function addQuakesLayer(map) {
    if (!map.getSource("quakes")) {
      map.addSource("quakes", { type: "geojson", data: quakesRef.current || emptyFC() });
    }
    if (!map.getLayer("quake-circles")) {
      map.addLayer({
        id: "quake-circles",
        type: "circle",
        source: "quakes",
        layout: { visibility: showQuakesRef.current ? "visible" : "none" },
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["coalesce", ["get", "mag"], 0], 2.5, 3, 6, 12, 8, 22],
          "circle-color": [
            "interpolate", ["linear"], ["coalesce", ["get", "mag"], 0],
            2.5, "#8ab4ff", 4.5, "#a371f7", 6, "#d24dff", 7.5, "#ff4dd2",
          ],
          "circle-opacity": 0.7,
          "circle-stroke-width": 1,
          "circle-stroke-color": "#c9d1ff",
        },
      });
    }
  }

  function addEonetLayer(map) {
    if (!map.getSource("eonet")) {
      map.addSource("eonet", { type: "geojson", data: eonetRef.current || emptyFC() });
    }
    if (!map.getLayer("eonet-circles")) {
      map.addLayer({
        id: "eonet-circles",
        type: "circle",
        source: "eonet",
        layout: { visibility: showEonetRef.current ? "visible" : "none" },
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 1, 5, 6, 10],
          "circle-color": EONET_COLORS,
          "circle-opacity": 0.55,
          "circle-stroke-width": 1.5,
          "circle-stroke-color": "#ffffff",
        },
      });
    }
  }

  function addVesselsLayer(map) {
    if (!map.getSource("vessels")) {
      map.addSource("vessels", { type: "geojson", data: vesselsRef.current || emptyFC() });
    }
    if (!map.getLayer("vessel-circles")) {
      map.addLayer({
        id: "vessel-circles",
        type: "circle",
        source: "vessels",
        layout: { visibility: showVesselsRef.current ? "visible" : "none" },
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 2, 2, 8, 5],
          "circle-color": VESSEL_COLORS,
          "circle-opacity": 0.85,
          "circle-stroke-width": 0.4,
          "circle-stroke-color": "#0d1117",
        },
      });
    }
  }

  function addFlightsLayer(map) {
    if (!map.getSource("flights")) {
      map.addSource("flights", { type: "geojson", data: flightsRef.current || emptyFC() });
    }
    if (!map.getLayer("flight-circles")) {
      map.addLayer({
        id: "flight-circles",
        type: "circle",
        source: "flights",
        layout: { visibility: showFlightsRef.current ? "visible" : "none" },
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 2, 2.5, 8, 5],
          "circle-color": ["case",
            ["to-boolean", ["get", "emergency"]], "#ff2d2d",
            ["==", ["get", "on_ground"], true], "#8b949e", "#00e5ff"],
          "circle-opacity": 0.85,
          "circle-stroke-width": ["case", ["to-boolean", ["get", "emergency"]], 2, 0.3],
          "circle-stroke-color": ["case", ["to-boolean", ["get", "emergency"]], "#ffea00", "#0d1117"],
        },
      });
    }
  }

  function addCamsLayer(map) {
    if (!map.getSource("cams")) {
      map.addSource("cams", { type: "geojson", data: camsRef.current || emptyFC() });
    }
    if (!map.getLayer("cam-circles")) {
      map.addLayer({
        id: "cam-circles",
        type: "circle",
        source: "cams",
        layout: { visibility: showCamsRef.current ? "visible" : "none" },
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 1, 3, 6, 6],
          "circle-color": "#c17aff",
          "circle-opacity": 0.9,
          "circle-stroke-width": 1,
          "circle-stroke-color": "#ffffff",
        },
      });
    }
  }

  function addSatsLayer(map) {
    if (!map.getSource("sats")) {
      map.addSource("sats", { type: "geojson", data: satsRef.current || emptyFC() });
    }
    if (!map.getLayer("sat-circles")) {
      map.addLayer({
        id: "sat-circles",
        type: "circle",
        source: "sats",
        layout: { visibility: showSatsRef.current ? "visible" : "none" },
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 1, 2.5, 6, 4],
          "circle-color": SAT_COLORS,
          "circle-opacity": 0.95,
          "circle-stroke-width": 0.6,
          "circle-stroke-color": "#0d1117",
        },
      });
    }
  }

  function addDisastersLayer(map) {
    if (!map.getSource("disasters")) {
      map.addSource("disasters", { type: "geojson", data: disastersRef.current || emptyFC() });
    }
    if (!map.getLayer("disaster-circles")) {
      map.addLayer({
        id: "disaster-circles",
        type: "circle",
        source: "disasters",
        layout: { visibility: showDisastersRef.current ? "visible" : "none" },
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 1, 6, 6, 13],
          "circle-color": DISASTER_COLORS,
          "circle-opacity": 0.35,
          "circle-stroke-width": 2,
          "circle-stroke-color": DISASTER_COLORS,
        },
      });
    }
  }

  function addRoadsLayer(map) {
    if (!map.getSource("roads")) {
      map.addSource("roads", { type: "geojson", data: roadsRef.current || emptyFC() });
    }
    if (!map.getLayer("road-circles")) {
      map.addLayer({
        id: "road-circles",
        type: "circle",
        source: "roads",
        layout: { visibility: showRoadsRef.current ? "visible" : "none" },
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 6, 3.5, 12, 6.5],
          "circle-color": ["case",
            ["==", ["get", "kind"], "radar"], "#3fa7c8",
            ["==", ["get", "sev"], 5], "#e5484d",
            ["==", ["get", "sev"], 4], "#d8973b",
            "#d29922"],
          "circle-opacity": 0.9,
          "circle-stroke-width": ["case", ["==", ["get", "kind"], "radar"], 1.4, 0.8],
          "circle-stroke-color": ["case", ["==", ["get", "kind"], "radar"], "#e9eff6", "#0b0f15"],
        },
      });
    }
  }

  function addCyberLayer(map) {
    if (!map.getSource("cyber")) {
      map.addSource("cyber", { type: "geojson", data: cyberRef.current || emptyFC() });
    }
    if (!map.getLayer("cyber-circles")) {
      map.addLayer({
        id: "cyber-circles",
        type: "circle",
        source: "cyber",
        layout: { visibility: showCyberRef.current ? "visible" : "none" },
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 1, 4, 6, 8],
          "circle-color": "#e5484d",
          "circle-opacity": 0.28,
          "circle-stroke-width": 1.4,
          "circle-stroke-color": "#e5484d",
        },
      });
    }
  }

  function addAirLayer(map) {
    if (!map.getSource("air")) {
      map.addSource("air", {
        type: "raster",
        tiles: [`${window.location.origin}/api/airquality/{z}/{x}/{y}.png?product=${airProductRef.current}`],
        tileSize: 256,
        maxzoom: 7,
        attribution: "Sentinel-5P / Copernicus",
      });
    }
    if (!map.getLayer("air-raster")) {
      map.addLayer({
        id: "air-raster",
        type: "raster",
        source: "air",
        layout: { visibility: showAirRef.current ? "visible" : "none" },
        paint: { "raster-opacity": 0.85 },
      }, beforeLabels(map));
    }
  }

  function addPowerLayer(map) {
    if (!map.getSource("power")) {
      map.addSource("power", { type: "geojson", data: powerRef.current || emptyFC() });
    }
    if (!map.getLayer("power-circles")) {
      map.addLayer({
        id: "power-circles",
        type: "circle",
        source: "power",
        layout: { visibility: showPowerRef.current ? "visible" : "none" },
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 1, 1.6, 6, 4],
          "circle-color": ["match", ["get", "fuel"],
            "Coal", "#6b7280", "Gas", "#d8973b", "Oil", "#8a5a2b", "Nuclear", "#e5484d",
            "Hydro", "#3fa7c8", "Solar", "#f0d020", "Wind", "#3fa870", "Geothermal", "#b048d8",
            "Biomass", "#7d9a3b", "#8b949e"],
          "circle-opacity": 0.8,
          "circle-stroke-width": 0.4,
          "circle-stroke-color": "#0b0f15",
        },
      });
    }
  }

  async function loadPower() {
    const map = mapRef.current;
    if (!map) return;
    try {
      if (!powerRef.current) {
        powerRef.current = await fetch("/api/powerplants/geojson?min_mw=1").then((r) => r.json());
        powerLoadedRef.current = true;
      }
      addPowerLayer(map);
      if (map.getSource("power")) map.getSource("power").setData(powerRef.current);
    } catch {
      /* ignore */
    }
  }

  function addRouteLayer(map) {
    if (!map.getSource("route")) {
      map.addSource("route", { type: "geojson", data: route || emptyFC() });
    }
    if (!map.getLayer("route-line")) {
      map.addLayer({
        id: "route-line",
        type: "line",
        source: "route",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": "#57c7e8",
          "line-width": ["interpolate", ["linear"], ["zoom"], 4, 3, 12, 6],
          "line-opacity": 0.9,
        },
      });
    }
  }

  function addInfraLayer(map) {
    if (!map.getSource("infra-cables")) {
      map.addSource("infra-cables", { type: "geojson", data: infraCablesRef.current || emptyFC() });
    }
    if (!map.getSource("infra-landing")) {
      map.addSource("infra-landing", { type: "geojson", data: infraLandingRef.current || emptyFC() });
    }
    if (!map.getLayer("infra-cables-line")) {
      map.addLayer({
        id: "infra-cables-line",
        type: "line",
        source: "infra-cables",
        layout: { visibility: showInfraRef.current ? "visible" : "none", "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": ["case", ["has", "color"], ["get", "color"], "#3fa7c8"],
          "line-width": ["interpolate", ["linear"], ["zoom"], 1, 0.7, 6, 1.6],
          "line-opacity": 0.75,
        },
      }, beforeLabels(map));
    }
    if (!map.getLayer("infra-landing-circles")) {
      map.addLayer({
        id: "infra-landing-circles",
        type: "circle",
        source: "infra-landing",
        layout: { visibility: showInfraRef.current ? "visible" : "none" },
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 1, 2, 6, 4.5],
          "circle-color": "#57c7e8",
          "circle-opacity": 0.85,
          "circle-stroke-width": 0.6,
          "circle-stroke-color": "#0b0f15",
        },
      });
    }
  }

  async function loadInfra() {
    const map = mapRef.current;
    if (!map) return;
    try {
      if (!infraCablesRef.current) {
        const [cables, landing] = await Promise.all([
          fetch("/api/infra/cables").then((r) => r.json()).catch(() => emptyFC()),
          fetch("/api/infra/landing").then((r) => r.json()).catch(() => emptyFC()),
        ]);
        infraCablesRef.current = cables;
        infraLandingRef.current = landing;
        infraLoadedRef.current = true;
      }
      addInfraLayer(map);
      if (map.getSource("infra-cables")) map.getSource("infra-cables").setData(infraCablesRef.current);
      if (map.getSource("infra-landing")) map.getSource("infra-landing").setData(infraLandingRef.current);
    } catch {
      /* ignore */
    }
  }

  async function weatherTemplate() {
    const mode = wxModeRef.current;
    if (mode === "precip") {
      if (!wxTemplateRef.current) {
        const d = await fetch("/api/weather/radar").then((r) => r.json());
        if (d.tiles) wxTemplateRef.current = d.tiles;
      }
      return wxTemplateRef.current;
    }
    return `${window.location.origin}/api/wxtiles/${mode}/{z}/{x}/{y}.png`;
  }

  function addWeatherLayer(map, tmpl) {
    if (!tmpl) return;
    if (!map.getSource("wxradar")) {
      map.addSource("wxradar", { type: "raster", tiles: [tmpl], tileSize: 256 });
    }
    if (!map.getLayer("weather-raster")) {
      map.addLayer({
        id: "weather-raster",
        type: "raster",
        source: "wxradar",
        layout: { visibility: showWeatherRef.current ? "visible" : "none" },
        paint: { "raster-opacity": 0.65 },
      }, beforeLabels(map));
    }
  }

  useEffect(() => {
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: BASEMAPS[basemapRef.current].style,
      center: [20, 30],
      zoom: 1.7,
      preserveDrawingBuffer: true, // required so the map can be captured to an image
    });
    map.addControl(new maplibregl.NavigationControl(), "top-right");
    mapRef.current = map;

    // layer-scoped handlers registered once; survive style swaps (same layer id)
    map.on("click", "events-circles", (e) => {
      const p = e.features[0].properties;
      new maplibregl.Popup({ maxWidth: "300px", closeOnClick: false })
        .setLngLat(e.lngLat)
        .setHTML(popupHtml(p, langRef.current))
        .addTo(map);
    });
    map.on("mouseenter", "events-circles", () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", "events-circles", () => (map.getCanvas().style.cursor = ""));

    map.on("click", "fire-circles", (e) => {
      const p = e.features[0].properties;
      new maplibregl.Popup({ maxWidth: "260px", closeOnClick: false })
        .setLngLat(e.lngLat)
        .setHTML(firePopupHtml(p, langRef.current))
        .addTo(map);
    });
    map.on("mouseenter", "fire-circles", () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", "fire-circles", () => (map.getCanvas().style.cursor = ""));

    map.on("click", "quake-circles", (e) => {
      const p = e.features[0].properties;
      new maplibregl.Popup({ maxWidth: "260px", closeOnClick: false })
        .setLngLat(e.lngLat)
        .setHTML(quakePopupHtml(p, langRef.current))
        .addTo(map);
    });
    map.on("mouseenter", "quake-circles", () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", "quake-circles", () => (map.getCanvas().style.cursor = ""));

    map.on("click", "eonet-circles", (e) => {
      const p = e.features[0].properties;
      new maplibregl.Popup({ maxWidth: "280px", closeOnClick: false })
        .setLngLat(e.lngLat)
        .setHTML(eonetPopupHtml(p, langRef.current))
        .addTo(map);
    });
    map.on("mouseenter", "eonet-circles", () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", "eonet-circles", () => (map.getCanvas().style.cursor = ""));

    map.on("click", "vessel-circles", (e) => {
      const p = e.features[0].properties;
      new maplibregl.Popup({ maxWidth: "260px", closeOnClick: false })
        .setLngLat(e.lngLat)
        .setHTML(vesselPopupHtml(p, langRef.current))
        .addTo(map);
    });
    map.on("mouseenter", "vessel-circles", () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", "vessel-circles", () => (map.getCanvas().style.cursor = ""));

    map.on("click", "flight-circles", (e) => {
      const p = e.features[0].properties;
      new maplibregl.Popup({ maxWidth: "260px", closeOnClick: false })
        .setLngLat(e.lngLat)
        .setHTML(flightPopupHtml(p, langRef.current))
        .addTo(map);
    });
    map.on("mouseenter", "flight-circles", () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", "flight-circles", () => (map.getCanvas().style.cursor = ""));

    map.on("click", "disaster-circles", (e) => {
      const p = e.features[0].properties;
      new maplibregl.Popup({ maxWidth: "280px", closeOnClick: false })
        .setLngLat(e.lngLat)
        .setHTML(disasterPopupHtml(p, langRef.current))
        .addTo(map);
    });
    map.on("mouseenter", "disaster-circles", () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", "disaster-circles", () => (map.getCanvas().style.cursor = ""));

    map.on("click", "sat-circles", (e) => {
      const p = e.features[0].properties;
      new maplibregl.Popup({ maxWidth: "240px", closeOnClick: false })
        .setLngLat(e.lngLat)
        .setHTML(`<h4>${p.name}</h4><div class="popup-meta">NORAD ${p.norad} · alt ${p.altitude_km} km</div>`)
        .addTo(map);
    });
    map.on("mouseenter", "sat-circles", () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", "sat-circles", () => (map.getCanvas().style.cursor = ""));

    map.on("click", "cam-circles", (e) => {
      const p = e.features[0].properties;
      if (onCameraRef.current) {
        onCameraRef.current({
          id: p.id,
          title: p.title || "Camera",
          place: `${p.source || ""}${p.city ? " · " + p.city : ""}${p.country ? ", " + p.country : ""}`,
          image: p.image || null,
          stream: p.stream || null,
          mp4: p.mp4 || null,
          embed: p.embed || null,
        });
      }
    });
    map.on("mouseenter", "cam-circles", () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", "cam-circles", () => (map.getCanvas().style.cursor = ""));

    map.on("click", "road-circles", (e) => {
      const p = e.features[0].properties;
      new maplibregl.Popup({ maxWidth: "240px", closeOnClick: false })
        .setLngLat(e.lngLat)
        .setHTML(roadPopupHtml(p, langRef.current))
        .addTo(map);
    });
    map.on("mouseenter", "road-circles", () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", "road-circles", () => (map.getCanvas().style.cursor = ""));

    map.on("click", "cyber-circles", (e) => {
      const p = e.features[0].properties;
      new maplibregl.Popup({ maxWidth: "260px", closeOnClick: false })
        .setLngLat(e.lngLat)
        .setHTML(cyberPopupHtml(p, langRef.current))
        .addTo(map);
    });
    map.on("mouseenter", "cyber-circles", () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", "cyber-circles", () => (map.getCanvas().style.cursor = ""));

    map.on("click", "infra-cables-line", (e) => {
      const p = e.features[0].properties;
      new maplibregl.Popup({ maxWidth: "240px", closeOnClick: false })
        .setLngLat(e.lngLat)
        .setHTML(`<h4>${p.name || "Câble sous-marin"}</h4><div class="popup-meta">${langRef.current === "fr" ? "Câble sous-marin (TeleGeography)" : "Submarine cable (TeleGeography)"}</div>`)
        .addTo(map);
    });
    map.on("click", "infra-landing-circles", (e) => {
      const p = e.features[0].properties;
      new maplibregl.Popup({ maxWidth: "240px", closeOnClick: false })
        .setLngLat(e.lngLat)
        .setHTML(`<h4>${p.name || "Landing point"}</h4><div class="popup-meta">${langRef.current === "fr" ? "Point d'atterrissage de câble" : "Cable landing point"}</div>`)
        .addTo(map);
    });
    map.on("mouseenter", "infra-cables-line", () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", "infra-cables-line", () => (map.getCanvas().style.cursor = ""));

    map.on("click", "power-circles", (e) => {
      const p = e.features[0].properties;
      new maplibregl.Popup({ maxWidth: "240px", closeOnClick: false })
        .setLngLat(e.lngLat)
        .setHTML(`<h4>${p.name || "Centrale"}</h4><div class="popup-meta"><b>${p.fuel || "?"}</b> · ${p.mw || "?"} MW</div><div class="popup-meta">${p.country || ""}${p.year ? " · " + p.year : ""}</div>`)
        .addTo(map);
    });
    map.on("mouseenter", "power-circles", () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", "power-circles", () => (map.getCanvas().style.cursor = ""));

    // auto-rotate the 3D globe; stop when the user clicks, drags or zooms
    map.on("moveend", () => { if (spinRef.current) spinStep(); });
    // road hazards are viewport-scoped: refetch after each pan/zoom while enabled
    // (debounced so rapid panning doesn't spam the API)
    let roadsDebounce;
    map.on("moveend", () => {
      if (!showRoadsRef.current) return;
      clearTimeout(roadsDebounce);
      roadsDebounce = setTimeout(loadRoads, 450);
    });
    // generic map click → used by marker mode (App decides whether to add a pin)
    map.on("click", (e) => {
      if (onMapClickRef.current) onMapClickRef.current({ lat: e.lngLat.lat, lon: e.lngLat.lng });
    });
    map.on("mousedown", () => { spinRef.current = false; });
    map.on("dragstart", () => { spinRef.current = false; });
    map.on("wheel", () => { spinRef.current = false; });
    map.on("touchstart", () => { spinRef.current = false; });
    // right-click on the globe restarts the rotation
    map.on("contextmenu", (e) => {
      if (basemapRef.current === "globe") {
        if (e.originalEvent) e.originalEvent.preventDefault();
        spinRef.current = true;
        spinStep();
      }
    });

    // update floating globe notifications + orbiting satellites as the globe rotates
    map.on("render", () => {
      if (basemapRef.current !== "globe") return;
      const now = performance.now();
      if (now - noteTsRef.current >= 140) { noteTsRef.current = now; updateGlobeNotes(); }
      if (showSatsRef.current && now - satTsRef.current >= 110) { satTsRef.current = now; updateSatOverlay(); }
    });

    // fires on first load and after every setStyle()
    map.on("style.load", () => {
      addSatLayer(map);
      addGoogleHDLayer(map);
      addTrafficLayer(map);
      addNightLayer(map);
      addEventsLayer(map);
      addFiresLayer(map);
      addQuakesLayer(map);
      try {
        map.setProjection({ type: BASEMAPS[basemapRef.current].projection });
      } catch (e) {
        /* older maplibre without globe: ignore */
      }
      if (basemapRef.current === "globe") {
        if (map.getZoom() >= 3.2) {
          map.easeTo({ center: [map.getCenter().lng, 20], zoom: 1.7, duration: 900 });
        }
        spinRef.current = true;
        setTimeout(spinStep, 1000);
      } else {
        spinRef.current = false;
      }
      if (dataRef.current && map.getSource("events")) {
        map.getSource("events").setData(dataRef.current);
      }
      if (firesRef.current && map.getSource("fires")) {
        map.getSource("fires").setData(firesRef.current);
      }
      if (quakesRef.current && map.getSource("quakes")) {
        map.getSource("quakes").setData(quakesRef.current);
      }
      addEonetLayer(map);
      if (eonetRef.current && map.getSource("eonet")) {
        map.getSource("eonet").setData(eonetRef.current);
      }
      addVesselsLayer(map);
      if (vesselsRef.current && map.getSource("vessels")) {
        map.getSource("vessels").setData(vesselsRef.current);
      }
      addFlightsLayer(map);
      if (flightsRef.current && map.getSource("flights")) {
        map.getSource("flights").setData(flightsRef.current);
      }
      addDisastersLayer(map);
      if (disastersRef.current && map.getSource("disasters")) {
        map.getSource("disasters").setData(disastersRef.current);
      }
      addSatsLayer(map);
      if (satsRef.current && map.getSource("sats")) {
        map.getSource("sats").setData(satsRef.current);
      }
      addCamsLayer(map);
      if (camsRef.current && map.getSource("cams")) {
        map.getSource("cams").setData(camsRef.current);
      }
      addRoadsLayer(map);
      if (roadsRef.current && map.getSource("roads")) {
        map.getSource("roads").setData(roadsRef.current);
      }
      addCyberLayer(map);
      if (cyberRef.current && map.getSource("cyber")) {
        map.getSource("cyber").setData(cyberRef.current);
      }
      if (showWeatherRef.current) loadWeather();
      addAirLayer(map);
      addPowerLayer(map);
      if (powerRef.current && map.getSource("power")) {
        map.getSource("power").setData(powerRef.current);
      }
      addInfraLayer(map);
      if (infraCablesRef.current && map.getSource("infra-cables")) {
        map.getSource("infra-cables").setData(infraCablesRef.current);
        map.getSource("infra-landing").setData(infraLandingRef.current || emptyFC());
      }
      addRouteLayer(map);
      if (route && map.getSource("route")) map.getSource("route").setData(route);
      applyVisibility(map);
    });

    map.on("load", load);
    const nightTimer = setInterval(updateNight, 120000); // day/night follows real UTC
    return () => { clearInterval(nightTimer); map.remove(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    load();
    if (firesLoadedRef.current) loadFires();
    if (quakesLoadedRef.current) loadQuakes();
    if (eonetLoadedRef.current) loadEonet();
    if (vesselsLoadedRef.current) loadVessels();
    if (flightsLoadedRef.current) loadFlights();
    if (disastersLoadedRef.current) loadDisasters();
    if (satsLoadedRef.current) loadSats();
    if (camsLoadedRef.current) loadCams();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [version, tick]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (showCams && !camsLoadedRef.current) loadCams();
    if (map.getLayer("cam-circles")) {
      map.setLayoutProperty("cam-circles", "visibility", showCams ? "visible" : "none");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showCams]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (showRoads) loadRoads();
    if (map.getLayer("road-circles")) {
      map.setLayoutProperty("road-circles", "visibility", showRoads ? "visible" : "none");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showRoads]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (showCyber && !cyberLoadedRef.current) loadCyber();
    if (map.getLayer("cyber-circles")) {
      map.setLayoutProperty("cyber-circles", "visibility", showCyber ? "visible" : "none");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showCyber]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (showInfra) loadInfra();
    for (const id of ["infra-cables-line", "infra-landing-circles"]) {
      if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", showInfra ? "visible" : "none");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showInfra]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (showPower && !powerLoadedRef.current) loadPower();
    if (map.getLayer("power-circles")) {
      map.setLayoutProperty("power-circles", "visibility", showPower ? "visible" : "none");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showPower]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (map.getLayer("air-raster")) {
      map.setLayoutProperty("air-raster", "visibility", showAir ? "visible" : "none");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showAir]);

  // switch Sentinel-5P product (NO2 / CH4 / CO / aerosol) without recreating the layer
  useEffect(() => {
    const map = mapRef.current;
    const src = map && map.getSource("air");
    if (src && src.setTiles) {
      src.setTiles([`${window.location.origin}/api/airquality/{z}/{x}/{y}.png?product=${airProduct}`]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [airProduct]);

  // switch weather mode (precip radar / wind / temperature / clouds)
  useEffect(() => {
    if (showWeatherRef.current) loadWeather();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wxMode]);

  // itinerary line
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.getSource("route")) return;
    map.getSource("route").setData(route || emptyFC());
    if (route && route.geometry && route.geometry.coordinates.length > 1) {
      const cs = route.geometry.coordinates;
      let minX = 180, minY = 90, maxX = -180, maxY = -90;
      for (const [x, y] of cs) { minX = Math.min(minX, x); minY = Math.min(minY, y); maxX = Math.max(maxX, x); maxY = Math.max(maxY, y); }
      try { map.fitBounds([[minX, minY], [maxX, maxY]], { padding: 80, duration: 900 }); } catch { /* ignore */ }
    }
  }, [route]);

  // manual markers (draggable pins the user drops)
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const objs = markerObjsRef.current;
    const ids = new Set(markers.map((m) => m.id));
    for (const id of Object.keys(objs)) {
      if (!ids.has(id)) { objs[id].remove(); delete objs[id]; }
    }
    for (const m of markers) {
      if (!objs[m.id]) {
        const el = document.createElement("div");
        el.className = "map-pin";
        el.title = m.label || "";
        const mk = new maplibregl.Marker({ element: el, anchor: "bottom" }).setLngLat([m.lon, m.lat]);
        if (m.label) mk.setPopup(new maplibregl.Popup({ offset: 18 }).setHTML(`<div>${m.label}</div>`));
        mk.addTo(map);
        objs[m.id] = mk;
      } else {
        objs[m.id].setLngLat([m.lon, m.lat]);
      }
    }
  }, [markers]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (showWeather) {
      loadWeather().then(() => {
        if (map.getLayer("weather-raster")) map.setLayoutProperty("weather-raster", "visibility", "visible");
      });
    } else if (map.getLayer("weather-raster")) {
      map.setLayoutProperty("weather-raster", "visibility", "none");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showWeather]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    let timer;
    if (showSats) {
      if (!satsLoadedRef.current) loadSats();
      timer = setInterval(loadSats, 15000); // satellites move fast
    } else {
      setSatOverlay([]);
    }
    if (map.getLayer("sat-circles")) {
      map.setLayoutProperty("sat-circles", "visibility", showSats && basemap !== "globe" ? "visible" : "none");
    }
    if (showSats && basemap === "globe") updateSatOverlay();
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showSats, basemap]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (showFires && !firesLoadedRef.current) loadFires();
    if (map.getLayer("fire-circles")) {
      map.setLayoutProperty("fire-circles", "visibility", showFires ? "visible" : "none");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showFires]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (showQuakes && !quakesLoadedRef.current) loadQuakes();
    if (map.getLayer("quake-circles")) {
      map.setLayoutProperty("quake-circles", "visibility", showQuakes ? "visible" : "none");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showQuakes]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (showEonet && !eonetLoadedRef.current) loadEonet();
    if (map.getLayer("eonet-circles")) {
      map.setLayoutProperty("eonet-circles", "visibility", showEonet ? "visible" : "none");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showEonet]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (showVessels && !vesselsLoadedRef.current) loadVessels();
    if (map.getLayer("vessel-circles")) {
      map.setLayoutProperty("vessel-circles", "visibility", showVessels ? "visible" : "none");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showVessels]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (showFlights && !flightsLoadedRef.current) loadFlights();
    if (map.getLayer("flight-circles")) {
      map.setLayoutProperty("flight-circles", "visibility", showFlights ? "visible" : "none");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showFlights]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (showDisasters && !disastersLoadedRef.current) loadDisasters();
    if (map.getLayer("disaster-circles")) {
      map.setLayoutProperty("disaster-circles", "visibility", showDisasters ? "visible" : "none");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showDisasters]);

  async function loadFires() {
    const map = mapRef.current;
    const geo = await fetch("/api/fires/geojson?limit=12000").then((r) => r.json());
    firesRef.current = geo;
    firesLoadedRef.current = true;
    if (map && map.getSource("fires")) map.getSource("fires").setData(geo);
  }

  async function loadQuakes() {
    const map = mapRef.current;
    const geo = await fetch("/api/quakes/geojson?feed=2.5_week").then((r) => r.json());
    quakesRef.current = geo;
    quakesLoadedRef.current = true;
    if (map && map.getSource("quakes")) map.getSource("quakes").setData(geo);
  }

  async function loadEonet() {
    const map = mapRef.current;
    const geo = await fetch("/api/eonet/geojson?status=open&limit=500").then((r) => r.json());
    eonetRef.current = geo;
    eonetLoadedRef.current = true;
    if (map && map.getSource("eonet")) map.getSource("eonet").setData(geo);
  }

  async function loadVessels() {
    const map = mapRef.current;
    const geo = await fetch("/api/vessels/geojson?limit=8000&max_age_min=60").then((r) => r.json());
    vesselsRef.current = geo;
    vesselsLoadedRef.current = true;
    if (map && map.getSource("vessels")) map.getSource("vessels").setData(geo);
  }

  async function loadFlights() {
    const map = mapRef.current;
    const geo = await fetch("/api/flights/geojson?limit=8000").then((r) => r.json());
    flightsRef.current = geo;
    flightsLoadedRef.current = true;
    if (map && map.getSource("flights")) map.getSource("flights").setData(geo);
  }

  async function loadDisasters() {
    const map = mapRef.current;
    const geo = await fetch("/api/disasters/geojson?limit=500").then((r) => r.json());
    disastersRef.current = geo;
    disastersLoadedRef.current = true;
    if (map && map.getSource("disasters")) map.getSource("disasters").setData(geo);
  }

  async function loadSats() {
    const map = mapRef.current;
    const geo = await fetch("/api/satellites/geojson?groups=stations,visual").then((r) => r.json());
    satsRef.current = geo;
    satsLoadedRef.current = true;
    if (map && map.getSource("sats")) map.getSource("sats").setData(geo);
  }

  async function loadCams(retries = 3) {
    const map = mapRef.current;
    try {
      const geo = await fetch("/api/cameras/geojson?limit=9000").then((r) => r.json());
      if (!geo || !geo.features) throw new Error("bad cameras payload");
      camsRef.current = geo;
      camsLoadedRef.current = true;
      if (map && map.getSource("cams")) map.getSource("cams").setData(geo);
    } catch {
      // survive transient API downtime (e.g. a backend restart)
      if (retries > 0) setTimeout(() => loadCams(retries - 1), 4000);
    }
  }

  // road hazards (accidents/closures/hazards + fixed speed cameras) for the current
  // viewport — these sources are bbox-scoped, so refetch on pan/zoom while enabled.
  async function loadRoads() {
    const map = mapRef.current;
    if (!map) return;
    if (map.getZoom() < 6) {
      roadsRef.current = emptyFC();
      if (map.getSource("roads")) map.getSource("roads").setData(roadsRef.current);
      return;
    }
    const b = map.getBounds();
    const bbox = `${b.getWest().toFixed(4)},${b.getSouth().toFixed(4)},${b.getEast().toFixed(4)},${b.getNorth().toFixed(4)}`;
    try {
      const [inc, cam] = await Promise.all([
        fetch(`/api/roads/incidents?bbox=${bbox}`).then((r) => r.json()).catch(() => ({ features: [] })),
        fetch(`/api/roads/speedcams?bbox=${bbox}`).then((r) => r.json()).catch(() => ({ features: [] })),
      ]);
      const fc = { type: "FeatureCollection", features: [...(inc.features || []), ...(cam.features || [])] };
      roadsRef.current = fc;
      roadsLoadedRef.current = true;
      if (map.getSource("roads")) map.getSource("roads").setData(fc);
    } catch {
      /* ignore */
    }
  }

  async function loadCyber() {
    const map = mapRef.current;
    try {
      const fc = await fetch("/api/ransomware?limit=250&geo=true").then((r) => r.json());
      cyberRef.current = fc;
      cyberLoadedRef.current = true;
      if (map && map.getSource("cyber")) map.getSource("cyber").setData(fc);
    } catch {
      /* ignore */
    }
  }

  async function loadWeather() {
    const map = mapRef.current;
    if (!map) return;
    try {
      const tmpl = await weatherTemplate();
      if (!tmpl) return;
      addWeatherLayer(map, tmpl);
      const src = map.getSource("wxradar");
      if (src && src.setTiles) src.setTiles([tmpl]);
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (map.getLayer("sat-raster")) {
      map.setLayoutProperty("sat-raster", "visibility", showSat ? "visible" : "none");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showSat]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (map.getLayer("traffic-raster")) {
      map.setLayoutProperty("traffic-raster", "visibility", showTraffic ? "visible" : "none");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showTraffic]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (map.getLayer("ghd-raster")) {
      map.setLayoutProperty("ghd-raster", "visibility", showGoogleHD ? "visible" : "none");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showGoogleHD]);

  // load high-severity alerts to annotate the globe (refresh each minute in globe mode)
  useEffect(() => {
    let loadTimer, pickTimer;
    async function load() {
      try {
        const d = await fetch("/api/globe-feed?limit=140").then((r) => r.json());
        globeAlertsRef.current = (d.items || [])
          .filter((a) => a.lat != null && a.lon != null)
          .map((a, i) => ({ id: `${a.type}-${i}`, title: a.title, sev: a.sev, lat: a.lat, lon: a.lon, url: a.url }));
        pickGlobeNotes();
      } catch {
        /* ignore */
      }
    }
    if (basemap === "globe") {
      load();
      loadTimer = setInterval(load, 60000);
      pickTimer = setInterval(pickGlobeNotes, 3500); // new random news appear as it rotates
    } else {
      globeAlertsRef.current = [];
      activeNotesRef.current = [];
      setGlobeNotes([]);
    }
    return () => { clearInterval(loadTimer); clearInterval(pickTimer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [basemap]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !focus) return;
    map.flyTo({ center: [focus.lon, focus.lat], zoom: focus.zoom || 5, duration: 1500 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus]);

  // basemap is controlled by the parent (App)
  useEffect(() => {
    const map = mapRef.current;
    if (!map || basemap === basemapRef.current || !BASEMAPS[basemap]) return;
    basemapRef.current = basemap;
    map.setStyle(BASEMAPS[basemap].style); // triggers style.load -> re-adds layers + projection
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [basemap]);

  async function load() {
    const map = mapRef.current;
    if (!map || !map.getSource("events")) return;
    const geo = await fetch(`/api/events/geojson?${query}`).then((r) => r.json());
    dataRef.current = geo;
    map.getSource("events").setData(geo);
    onCount?.(geo.features.length);
  }

  const positioned = layoutNotes(globeNotes, containerRef.current, colOffset);
  function screenshot() {
    const map = mapRef.current;
    if (!map) return;
    map.once("render", () => {
      try {
        const url = map.getCanvas().toDataURL("image/png");
        const a = document.createElement("a");
        a.href = url;
        a.download = `osint-map-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.png`;
        document.body.appendChild(a); a.click(); a.remove();
      } catch { /* ignore */ }
    });
    map.triggerRepaint();
  }

  return (
    <>
      <div id="map" ref={containerRef} />
      <button className="map-shot-btn" onClick={screenshot} title={lang === "fr" ? "Capturer la carte (PNG)" : "Capture map (PNG)"}>⤓</button>
      {basemap === "globe" && showSats && satOverlay.length > 0 && (
        <svg className="sat-overlay">
          {satOverlay.map((s) => (
            <g key={s.id}>
              <line x1={s.sx} y1={s.sy} x2={s.x} y2={s.y} className="sat-tether" />
              <circle cx={s.x} cy={s.y} r={s.group === "gps" ? 2.6 : 2} className={`satdot ${s.group}`} />
            </g>
          ))}
        </svg>
      )}
      {basemap === "globe" && positioned.length > 0 && (
        <div className="globe-notes">
          <svg className="globe-lines">
            {positioned.map((n) => (
              <g key={n.id}>
                <line x1={n.connectX} y1={n.cardY + 16} x2={n.x} y2={n.y} className={`gline s${n.sev}`} />
                <circle
                  cx={n.x} cy={n.y} r={n.url ? 6 : 4} className={`gdot s${n.sev}`}
                  style={{ pointerEvents: n.url ? "auto" : "none", cursor: n.url ? "pointer" : "default" }}
                  onClick={() => n.url && window.open(n.url, "_blank", "noopener")}
                >
                  {n.url && <title>Ouvrir la source</title>}
                </circle>
              </g>
            ))}
          </svg>
          {positioned.map((n) => (
            <div
              key={n.id}
              className={`globe-note s${n.sev}`}
              style={{ left: n.cardX, top: n.cardY, width: NOTE_CARD_W, cursor: "pointer" }}
              onMouseDown={(e) => startColDrag(n.side, e, n)}
              title="Cliquer : aller au point · glisser : déplacer la colonne"
            >
              <span className="gsev" />
              <span className="gtitle">{n.title}</span>
              {n.url && (
                <a
                  className="gsrc" href={n.url} target="_blank" rel="noopener noreferrer"
                  onMouseDown={(e) => e.stopPropagation()} onClick={(e) => e.stopPropagation()}
                  title="Ouvrir la source"
                >↗</a>
              )}
            </div>
          ))}
        </div>
      )}
    </>
  );
}

// place notification cards just outside the globe's left/right edge, close to their point
function layoutNotes(notes, cont, colOffset = { left: 0, right: 0 }) {
  if (!cont) return [];
  const W = cont.clientWidth, H = cont.clientHeight;
  const cx = W / 2;
  const globeHalf = Math.min(W, H) * 0.33; // approx on-screen globe radius
  const gap = 14;
  const sides = { left: [], right: [] };
  for (const n of notes) (n.x < cx ? sides.left : sides.right).push(n);
  const out = [];
  for (const side of ["left", "right"]) {
    const list = sides[side].sort((a, b) => a.y - b.y);
    let lastY = -999;
    for (const n of list) {
      const cardY = Math.max(lastY + 46, Math.min(n.y - 14, H - 54));
      lastY = cardY;
      const base = side === "left"
        ? cx - globeHalf - NOTE_CARD_W - gap
        : cx + globeHalf + gap;
      const cardX = Math.max(4, Math.min(W - NOTE_CARD_W - 4, base + colOffset[side]));
      const connectX = side === "left" ? cardX + NOTE_CARD_W : cardX;
      out.push({ ...n, side, cardX, cardY, connectX });
    }
  }
  return out;
}

function emptyFC() {
  return { type: "FeatureCollection", features: [] };
}

function fmtDateTime(iso) {
  if (!iso) return "—";
  const [d, t] = iso.split("T");
  return `${d} ${t ? t.slice(0, 5) : ""} UTC`;
}

function cyberPopupHtml(p, lang) {
  return `
    <h4>${lang === "fr" ? "Attaque ransomware" : "Ransomware attack"}</h4>
    <div class="popup-meta"><b>${p.victim || "?"}</b></div>
    <div class="popup-meta">${lang === "fr" ? "Groupe" : "Group"}: ${p.group || "?"} · ${p.sector || "?"}</div>
    <div class="popup-time">${p.country || ""} · ${p.discovered || ""}</div>
    <div class="popup-meta">ransomware.live</div>
  `;
}

function roadPopupHtml(p, lang) {
  const l = L[lang] || L.fr;
  if (p.kind === "radar") {
    const ms = p.maxspeed ? ` — ${p.maxspeed} km/h` : "";
    return `<h4>${lang === "fr" ? "Radar" : "Speed camera"}${ms}</h4><div class="popup-meta">OpenStreetMap</div>`;
  }
  return `
    <h4>${p.label || (lang === "fr" ? "Incident routier" : "Road incident")}</h4>
    <div class="popup-meta">${p.desc || ""}</div>
    <div class="popup-meta">${l.source}: TomTom Traffic</div>
  `;
}

function fmtDate(sqldate) {
  const s = String(sqldate || "");
  if (s.length !== 8) return "—";
  return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`;
}

function disasterPopupHtml(p, lang) {
  const l = L[lang] || L.fr;
  return `
    <h4>${p.type_label || l.disaster} — ${p.alert_level || ""}</h4>
    <div class="popup-meta">${p.name || ""}</div>
    <div class="popup-meta"><b>${l.country}:</b> ${p.country || "—"}</div>
    ${p.severity ? `<div class="popup-meta"><b>${l.severity}:</b> ${p.severity}</div>` : ""}
    ${p.url ? `<div style="margin-top:5px"><a href="${p.url}" target="_blank" rel="noopener">GDACS ↗</a></div>` : ""}
  `;
}

function flightPopupHtml(p, lang) {
  const l = L[lang] || L.fr;
  const alt = p.altitude_m != null ? `${Number(p.altitude_m).toFixed(0)} m` : "—";
  const spd = p.velocity_ms != null ? `${(Number(p.velocity_ms) * 3.6).toFixed(0)} km/h` : "—";
  return `
    <h4>${p.callsign || p.icao24}${p.emergency ? " — URGENCE" : ""}</h4>
    ${p.emergency ? `<div class="popup-time" style="color:#ff2d2d"><b>URGENCE:</b> ${p.emergency} (${p.squawk})</div>` : ""}
    <div class="popup-meta"><b>${l.country}:</b> ${p.country || "—"}</div>
    <div class="popup-meta"><b>${l.altitude}:</b> ${p.on_ground ? l.ground : alt} · <b>${l.speed}:</b> ${spd}</div>
  `;
}

function vesselPopupHtml(p, lang) {
  const l = L[lang] || L.fr;
  const sog = p.sog != null ? `${Number(p.sog).toFixed(1)} kn` : "—";
  const cog = p.cog != null ? `${Number(p.cog).toFixed(0)}°` : "—";
  const upd = p.updated_at ? p.updated_at.replace("T", " ").slice(0, 16) + " UTC" : "—";
  return `
    <h4>${p.name || "MMSI " + p.mmsi}</h4>
    <div class="popup-meta"><b>${l.type}:</b> ${p.type_label || "—"} · MMSI ${p.mmsi}</div>
    <div class="popup-meta"><b>${l.speed}:</b> ${sog} · <b>${l.course}:</b> ${cog}</div>
    <div class="popup-time"><b>${l.updated}:</b> ${upd}</div>
  `;
}

function eonetPopupHtml(p, lang) {
  const l = L[lang] || L.fr;
  const when = p.date ? p.date.replace("T", " ").slice(0, 16) + " UTC" : "—";
  return `
    <h4>${p.title || l.natEvent}</h4>
    <div class="popup-meta"><b>${l.category}:</b> ${p.category || "—"}</div>
    <div class="popup-time"><b>${l.when}:</b> ${when}</div>
    ${p.link ? `<div style="margin-top:5px"><a href="${p.link}" target="_blank" rel="noopener">${l.source} ↗</a></div>` : ""}
  `;
}

function quakePopupHtml(p, lang) {
  const l = L[lang] || L.fr;
  const mag = p.mag != null ? Number(p.mag).toFixed(1) : "—";
  const depth = p.depth_km != null ? `${Number(p.depth_km).toFixed(0)} km` : "—";
  const when = p.time ? new Date(Number(p.time)).toISOString().replace("T", " ").slice(0, 16) + " UTC" : "—";
  return `
    <h4>${l.quake} M${mag}</h4>
    <div class="popup-meta">${p.place || ""}</div>
    <div class="popup-time"><b>${l.when}:</b> ${when}</div>
    <div class="popup-meta"><b>${l.depth}:</b> ${depth}${p.tsunami ? " · tsunami" : ""}</div>
    ${p.url ? `<div style="margin-top:5px"><a href="${p.url}" target="_blank" rel="noopener">USGS ↗</a></div>` : ""}
  `;
}

function firePopupHtml(p, lang) {
  const l = L[lang] || L.fr;
  const frp = p.frp != null ? `${Number(p.frp).toFixed(1)} MW` : "—";
  return `
    <h4>${l.fire}</h4>
    <div class="popup-time"><b>${l.detected}:</b> ${fmtDateTime(p.acq_datetime)}</div>
    <div class="popup-meta"><b>${l.power}:</b> ${frp} · <b>${l.confidence}:</b> ${p.confidence ?? "—"}</div>
    <div class="popup-meta"><b>${l.satLabel}:</b> ${p.satellite ?? "—"} · ${p.source ?? ""}</div>
  `;
}

function popupHtml(p, lang) {
  const l = L[lang] || L.fr;
  const tone = p.avg_tone != null ? Number(p.avg_tone).toFixed(1) : "—";
  return `
    <h4>${p.event_root_label || "Event"}</h4>
    <div><b>${l.actors}:</b> ${p.actor1 || "?"} → ${p.actor2 || "?"}</div>
    <div class="popup-meta"><b>${l.place}:</b> ${p.geo_fullname || ""} (${p.geo_country || "?"})</div>
    <div class="popup-time"><b>${l.published}:</b> ${fmtDateTime(p.date_added)}</div>
    <div class="popup-meta"><b>${l.eventDate}:</b> ${fmtDate(p.sqldate)}</div>
    <div class="popup-meta">${l.class}: ${p.quad_label} · ${l.tone}: ${tone} · ${l.mentions}: ${p.num_mentions ?? "—"}</div>
    ${p.source_url ? `<div style="margin-top:5px"><a href="${p.source_url}" target="_blank" rel="noopener">${l.source} ↗</a></div>` : ""}
  `;
}
