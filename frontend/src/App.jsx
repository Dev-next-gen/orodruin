import { useEffect, useState, useRef, lazy, Suspense } from "react";
import MapView from "./MapView.jsx";
import GraphView from "./GraphView.jsx";
// Cesium is heavy (~MBs): only load the Google 3D globe when it's actually selected
const GoogleGlobe = lazy(() => import("./GoogleGlobe.jsx"));
import NewsTicker from "./NewsTicker.jsx";
import LiveTV from "./LiveTV.jsx";
import Collapsible from "./Collapsible.jsx";
import ChatBox from "./ChatBox.jsx";
import Clock from "./Clock.jsx";
import CamPlayers from "./CamPlayers.jsx";
import NetworkStatus from "./NetworkStatus.jsx";
import WeatherLegend from "./WeatherLegend.jsx";
import NewsFeed from "./NewsFeed.jsx";
import AirLegend from "./AirLegend.jsx";
import Settings from "./Settings.jsx";
import Notepad from "./Notepad.jsx";
import { useT } from "./i18n.js";

let _camUid = 1;

const BASEMAP_LABELS = {
  fr: { dark: "2D Sombre", streets: "Rues", satellite: "2D Satellite", globe: "3D Globe", google3d: "3D Google" },
  en: { dark: "2D Dark", streets: "Streets", satellite: "2D Satellite", globe: "3D Globe", google3d: "3D Google" },
  ar: { dark: "داكن 2D", streets: "شوارع", satellite: "قمر صناعي 2D", globe: "كرة أرضية 3D", google3d: "غوغل 3D" },
  ru: { dark: "2D Тёмная", streets: "Улицы", satellite: "2D Спутник", globe: "3D Глобус", google3d: "3D Google" },
};
const BASEMAP_KEYS = ["dark", "streets", "satellite", "globe", "google3d"];

const QUAD_COLORS = { 1: "#3fb950", 2: "#58a6ff", 3: "#d29922", 4: "#f85149" };

function buildQuery(f) {
  const p = new URLSearchParams({ limit: "3000" });
  if (f.quad_class) p.set("quad_class", f.quad_class);
  if (f.country) p.set("country", f.country.toUpperCase());
  if (f.actor) p.set("actor", f.actor);
  return p.toString();
}

const _P = new URLSearchParams(window.location.search);
const _pon = (k) => _P.get(k) === "1";

function _loadUI() {
  try {
    return JSON.parse(localStorage.getItem("osint_ui") || "{}");
  } catch {
    return {};
  }
}
const _UI = _loadUI();
const _init = (k, fb) => (_UI[k] !== undefined ? _UI[k] : fb);

export default function App() {
  const [lang, setLang] = useState(_P.get("lang") || _init("lang", "fr"));
  const t = useT(lang);
  const [tab, setTab] = useState("map");
  const [filters, setFilters] = useState(_init("applied", { quad_class: "", country: "", actor: "" }));
  const [applied, setApplied] = useState(_init("applied", { quad_class: "", country: "", actor: "" }));
  const [version, setVersion] = useState(0); // manual apply/reset (filters)
  const [autoTick, setAutoTick] = useState(0); // silent auto-refresh (data only)
  const [hours, setHours] = useState(_init("hours", 0)); // 0 = all time
  const [stats, setStats] = useState(null);
  const [count, setCount] = useState(0);
  const [chatOpen, setChatOpen] = useState(false);
  const [camPlayers, setCamPlayers] = useState([]);
  const [addrQ, setAddrQ] = useState("");
  const [routeFrom, setRouteFrom] = useState("");
  const [routeTo, setRouteTo] = useState("");
  const [routeInfo, setRouteInfo] = useState(null);
  const [routeGeo, setRouteGeo] = useState(null);
  const [markerMode, setMarkerMode] = useState(false);
  const [markers, setMarkers] = useState([]);

  async function geocodeOne(q) {
    const r = await fetch(`/api/geocode?q=${encodeURIComponent(q)}&limit=1`).then((x) => x.json());
    return r.results && r.results[0];
  }
  async function planRoute() {
    if (routeFrom.trim().length < 2 || routeTo.trim().length < 2) return;
    setRouteInfo("loading");
    try {
      const [a, b] = await Promise.all([geocodeOne(routeFrom), geocodeOne(routeTo)]);
      if (!a || !b) { setRouteInfo(null); return; }
      const d = await fetch(`/api/route?from=${a.lat},${a.lon}&to=${b.lat},${b.lon}`).then((x) => x.json());
      if (d.error) { setRouteInfo(null); return; }
      setRouteInfo(d);
      setRouteGeo(d.geometry);
    } catch {
      setRouteInfo(null);
    }
  }
  function clearRoute() { setRouteGeo(null); setRouteInfo(null); }
  function handleMapClick(pt) {
    if (!markerMode) return;
    setMarkers((ms) => [...ms, { id: `m${Date.now()}`, lat: pt.lat, lon: pt.lon, label: `Point ${ms.length + 1}` }]);
  }

  async function goAddress() {
    const q = addrQ.trim();
    if (q.length < 2) return;
    try {
      const r = await fetch(`/api/geocode?q=${encodeURIComponent(q)}&limit=1`).then((x) => x.json());
      const hit = r.results && r.results[0];
      if (hit) setFocus({ lat: hit.lat, lon: hit.lon, zoom: 15, _t: Date.now() });
    } catch {
      /* ignore */
    }
  }

  function addCamera(cam) {
    setCamPlayers((ps) => {
      if (ps.length >= 6) return ps;
      const n = ps.length;
      return [...ps, { ...cam, uid: _camUid++, x: 80 + n * 30, y: 80 + n * 30, w: 340 }];
    });
  }
  // the AI analyst can drive the UI: open cameras, recenter the map, toggle layers
  function handleActions(actions) {
    const setters = {
      showFires: setShowFires, showQuakes: setShowQuakes, showEonet: setShowEonet,
      showVessels: setShowVessels, showFlights: setShowFlights, showDisasters: setShowDisasters,
      showSat: setShowSat, showSats: setShowSats, showCams: setShowCams, showTraffic: setShowTraffic,
      showRoads: setShowRoads, showWeather: setShowWeather, showCyber: setShowCyber,
      showInfra: setShowInfra, showPower: setShowPower, showAir: setShowAir,
    };
    for (const a of actions) {
      if (a.type === "open_camera" && a.camera) {
        addCamera({
          id: a.camera.id, title: a.camera.title || "Camera",
          place: `${a.camera.source || ""}${a.camera.city ? " · " + a.camera.city : ""}${a.camera.country ? ", " + a.camera.country : ""}`,
          image: a.camera.image || null, stream: a.camera.stream || null,
          mp4: a.camera.mp4 || null, embed: a.camera.embed || null,
        });
        if (a.camera.lat != null) setFocus({ lat: a.camera.lat, lon: a.camera.lon, zoom: 11, _t: Date.now() });
      } else if (a.type === "focus_map") {
        setFocus({ lat: a.lat, lon: a.lon, zoom: a.zoom || 9, _t: Date.now() });
      } else if (a.type === "toggle_layer" && setters[a.layer]) {
        setters[a.layer](a.on);
      } else if (a.type === "apply_filters" && a.filters) {
        const nf = { quad_class: "", country: "", actor: "" };
        if (a.filters.quad_class) nf.quad_class = String(a.filters.quad_class);
        if (a.filters.country) nf.country = a.filters.country;
        if (a.filters.actor) nf.actor = a.filters.actor;
        setFilters(nf); setApplied(nf);
        if (a.filters.hours != null) setHours(a.filters.hours);
        setVersion((v) => v + 1);
      }
    }
  }
  const closeCam = (uid) => setCamPlayers((ps) => ps.filter((p) => p.uid !== uid));
  const updateCam = (uid, patch) => setCamPlayers((ps) => ps.map((p) => (p.uid === uid ? { ...p, ...patch } : p)));
  const _mobile = typeof window !== "undefined" && window.innerWidth < 768;
  const [showFires, setShowFires] = useState(_init("showFires", true));
  const [showQuakes, setShowQuakes] = useState(_init("showQuakes", true));
  const [showEonet, setShowEonet] = useState(_init("showEonet", true));
  const [showVessels, setShowVessels] = useState(_init("showVessels", !_mobile));
  const [showFlights, setShowFlights] = useState(_init("showFlights", !_mobile));
  const [showDisasters, setShowDisasters] = useState(_init("showDisasters", true));
  const [showSat, setShowSat] = useState(_init("showSat", _pon("sat")));
  const [showSats, setShowSats] = useState(_init("showSats", true));
  const [showCams, setShowCams] = useState(_init("showCams", !_mobile));
  const [showTraffic, setShowTraffic] = useState(_init("showTraffic", !_mobile));
  const [showRoads, setShowRoads] = useState(_init("showRoads", !_mobile));
  const [showWeather, setShowWeather] = useState(_init("showWeather", _pon("weather")));
  const [showCyber, setShowCyber] = useState(_init("showCyber", true));
  const [showInfra, setShowInfra] = useState(_init("showInfra", true));
  const [showPower, setShowPower] = useState(_init("showPower", !_mobile));
  const [showAir, setShowAir] = useState(_init("showAir", _pon("air")));
  const [airProduct, setAirProduct] = useState("no2");
  const [wxMode, setWxMode] = useState("precip");
  const [netOpen, setNetOpen] = useState(false);
  const [wxOpen, setWxOpen] = useState(false);
  const [newsOpen, setNewsOpen] = useState(false);
  const [airOpen, setAirOpen] = useState(false);
  const [cyberNewsOpen, setCyberNewsOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [notepadOpen, setNotepadOpen] = useState(false);
  const [publicMode, setPublicMode] = useState(false);
  useEffect(() => { fetch("/api/config").then((r) => r.json()).then((c) => setPublicMode(!!c.public_mode)).catch(() => {}); }, []);
  const [showGoogleHD, setShowGoogleHD] = useState(false);
  const [basemap, setBasemap] = useState(_P.get("basemap") || _init("basemap", "globe"));
  const [menuOpen, setMenuOpen] = useState(false);
  const sidebarRef = useRef(null);
  useEffect(() => {
    const el = sidebarRef.current; if (!el) return;
    let st = null;
    const onStart = (e) => {
      if (e.touches.length === 2) st = { two: true, y: (e.touches[0].clientY + e.touches[1].clientY) / 2 };
      else st = { x: e.touches[0].clientX, y: e.touches[0].clientY, drag: false };
    };
    const onMove = (e) => {
      if (!st) return;
      if (e.touches.length === 2) {
        const ay = (e.touches[0].clientY + e.touches[1].clientY) / 2;
        if (st.two) { el.scrollTop += st.y - ay; st.y = ay; e.preventDefault(); }
        return;
      }
      if (st.two) return;
      const dx = e.touches[0].clientX - st.x, dy = e.touches[0].clientY - st.y;
      if (!st.drag && Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 8) { st.drag = true; el.style.transition = "none"; }
      if (st.drag && dx < 0) { el.style.transform = "translateX(" + dx + "px)"; e.preventDefault(); }
    };
    const onEnd = (e) => {
      if (!st) return; const s0 = st; st = null;
      if (s0.two) return;
      el.style.transition = ""; el.style.transform = "";
      const end = e.changedTouches[0] ? e.changedTouches[0].clientX : s0.x;
      if (s0.drag && end - s0.x < -70) setMenuOpen(false);
    };
    el.addEventListener("touchstart", onStart, { passive: true });
    el.addEventListener("touchmove", onMove, { passive: false });
    el.addEventListener("touchend", onEnd, { passive: true });
    return () => { el.removeEventListener("touchstart", onStart); el.removeEventListener("touchmove", onMove); el.removeEventListener("touchend", onEnd); };
  }, []);
  const [autoRefresh, setAutoRefresh] = useState(_init("autoRefresh", true));
  const [sidebarW, setSidebarW] = useState(_init("sidebarW", 340));

  function startSidebarResize(e) {
    e.preventDefault();
    const startX = e.clientX, start = sidebarW;
    const move = (ev) => setSidebarW(Math.max(260, Math.min(620, start + (ev.clientX - startX))));
    const up = () => { window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up); };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  }
  const [lastUpdate, setLastUpdate] = useState(Date.now());
  const [screenQ, setScreenQ] = useState("");
  const [screenRes, setScreenRes] = useState(null);
  const [hotspots, setHotspots] = useState(null);
  const [focus, setFocus] = useState(null);
  const [alerts, setAlerts] = useState(null);
  const [markets, setMarkets] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [cyberIp, setCyberIp] = useState("");
  const [cyberRes, setCyberRes] = useState(null);
  const [geoIp, setGeoIp] = useState("");
  const [geoRes, setGeoRes] = useState(null);
  const [finQ, setFinQ] = useState("");
  const [finRes, setFinRes] = useState(null);
  const [resQ, setResQ] = useState("");
  const [resRes, setResRes] = useState(null);

  // persist UI state so a page reload restores layers/filters/language/basemap
  useEffect(() => {
    try {
      localStorage.setItem(
        "osint_ui",
        JSON.stringify({
          lang, basemap, autoRefresh, hours, applied, sidebarW,
          showFires, showQuakes, showEonet, showVessels, showFlights, showDisasters, showSat, showSats, showCams, showTraffic, showRoads, showWeather, showCyber, showInfra, showPower, showAir,
        })
      );
    } catch {
      /* private mode / storage disabled */
    }
  }, [lang, basemap, autoRefresh, hours, applied, sidebarW, showFires, showQuakes, showEonet, showVessels, showFlights, showDisasters, showSat, showSats, showCams, showTraffic, showRoads, showWeather, showCyber, showInfra, showPower, showAir]);

  useEffect(() => {
    fetch("/api/stats").then((r) => r.json()).then(setStats).catch(() => {});
    fetch("/api/markets").then((r) => r.json()).then(setMarkets).catch(() => {});
    fetch("/api/prediction-markets?limit=12").then((r) => r.json()).then((d) => setPrediction(d.markets || [])).catch(() => {});
  }, [version, autoTick]);

  // automatic refresh — silently updates live data every 90s WITHOUT disturbing
  // the UI (no graph re-simulation, camera/panels/filters preserved).
  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(() => {
      setAutoTick((t) => t + 1);
      setLastUpdate(Date.now());
    }, 90000);
    return () => clearInterval(id);
  }, [autoRefresh]);

  function apply() {
    setApplied(filters);
    setVersion((v) => v + 1);
  }
  function reset() {
    const empty = { quad_class: "", country: "", actor: "" };
    setFilters(empty);
    setApplied(empty);
    setVersion((v) => v + 1);
  }

  async function screen() {
    const q = screenQ.trim();
    if (q.length < 2) return;
    try {
      const r = await fetch(`/api/sanctions/search?q=${encodeURIComponent(q)}&limit=20`).then((x) => x.json());
      setScreenRes(r);
    } catch {
      setScreenRes({ count: 0, results: [] });
    }
  }

  function fmtUsd(v) {
    if (v == null) return "—";
    if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
    if (v >= 1e6) return `$${(v / 1e6).toFixed(0)}M`;
    if (v >= 1e3) return `$${(v / 1e3).toFixed(0)}k`;
    return `$${v}`;
  }
  async function researchSearch() {
    const q = resQ.trim();
    if (q.length < 2) return;
    try {
      const r = await fetch(`/api/research/search?q=${encodeURIComponent(q)}&limit=15`).then((x) => x.json());
      setResRes(r);
    } catch {
      setResRes({ count: 0, results: [] });
    }
  }

  async function financeSearch() {
    const q = finQ.trim();
    if (q.length < 2) return;
    try {
      const r = await fetch(`/api/finance/awards?q=${encodeURIComponent(q)}&limit=15`).then((x) => x.json());
      setFinRes(r);
    } catch {
      setFinRes({ count: 0, results: [] });
    }
  }

  async function cyberLookup() {
    const ip = cyberIp.trim();
    if (ip.length < 3) return;
    try {
      const r = await fetch(`/api/cyber/host?ip=${encodeURIComponent(ip)}`).then((x) => x.json());
      setCyberRes(r);
    } catch {
      setCyberRes({ found: false });
    }
  }

  async function geolocateIp() {
    const ip = geoIp.trim();
    if (ip.length < 3) return;
    try {
      const r = await fetch(`/api/geoip?ip=${encodeURIComponent(ip)}`).then((x) => x.json());
      setGeoRes(r);
      if (r.found && r.lat != null) setFocus({ lat: r.lat, lon: r.lon, zoom: 10, _t: Date.now() });
    } catch {
      setGeoRes({ found: false });
    }
  }

  async function loadAlerts() {
    try {
      const r = await fetch("/api/alerts?hours=48&limit=40").then((x) => x.json());
      setAlerts(r.alerts || []);
    } catch {
      setAlerts([]);
    }
  }

  useEffect(() => {
    if (alerts !== null) loadAlerts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [version, autoTick]);

  async function loadHotspots() {
    try {
      const r = await fetch("/api/hotspots?window_hours=48&limit=12").then((x) => x.json());
      setHotspots(r.hotspots || []);
    } catch {
      setHotspots([]);
    }
  }

  const query = buildQuery(applied) + (hours ? `&since_hours=${hours}` : "");
  const QUAD_LABELS = { 1: t("q1"), 2: t("q2"), 3: t("q3"), 4: t("q4") };
  const maxScore = hotspots && hotspots.length ? hotspots[0].score : 1;

  return (
    <div className="app" style={{ gridTemplateColumns: `${sidebarW}px 1fr` }}>
      <button className="menu-toggle" onClick={() => setMenuOpen((v) => !v)} aria-label="Menu">☰</button>
      {menuOpen && <div className="sidebar-backdrop" onClick={() => setMenuOpen(false)} />}
      <div className="sidebar-resize" style={{ left: sidebarW - 3 }} onMouseDown={startSidebarResize} title="Redimensionner la barre latérale" />
      <aside ref={sidebarRef} className={"sidebar" + (menuOpen ? " open" : "")} dir={lang === "ar" ? "rtl" : "ltr"}>
        <div className="brand-row">
          <div className="brand"><span className="brand-name">OROD<span className="brand-acc">RUIN</span></span></div>
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            {!publicMode && <button className="brand-gear" onClick={() => setSettingsOpen(true)} title={lang === "fr" ? "Paramètres (clés API)" : "Settings (API keys)"}>⚙</button>}
            <div className="lang-switch">
              <button className={lang === "fr" ? "on" : ""} onClick={() => setLang("fr")}>FR</button>
              <button className={lang === "en" ? "on" : ""} onClick={() => setLang("en")}>EN</button>
              <button className={lang === "ar" ? "on" : ""} onClick={() => setLang("ar")}>ع</button>
              <button className={lang === "ru" ? "on" : ""} onClick={() => setLang("ru")}>RU</button>
            </div>
          </div>
        </div>
        <div className="tagline">{t("tagline")}</div>

        <div className="tabs">
          <button className={tab === "map" ? "tab active" : "tab"} onClick={() => setTab("map")}>{t("map")}</button>
          <button className={tab === "graph" ? "tab active" : "tab"} onClick={() => setTab("graph")}>{t("graph")}</button>
        </div>

        <label>{t("goAddress")}</label>
        <input
          value={addrQ}
          placeholder={t("addressPlaceholder")}
          onChange={(e) => setAddrQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && goAddress()}
        />

        <label>{t("routeLabel")}</label>
        <input value={routeFrom} placeholder={t("routeFrom")} onChange={(e) => setRouteFrom(e.target.value)} onKeyDown={(e) => e.key === "Enter" && planRoute()} />
        <input value={routeTo} placeholder={t("routeTo")} style={{ marginTop: 5 }} onChange={(e) => setRouteTo(e.target.value)} onKeyDown={(e) => e.key === "Enter" && planRoute()} />
        <div style={{ display: "flex", gap: 6 }}>
          <button style={{ flex: 1 }} onClick={planRoute}>{t("routeGo")}</button>
          {routeGeo && <button className="secondary" style={{ flex: 1 }} onClick={clearRoute}>{t("routeClear")}</button>}
        </div>
        {routeInfo === "loading" && <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>{t("routeCalc")}</div>}
        {routeInfo && routeInfo !== "loading" && (
          <div className="route-panel">
            <div className="route-line-row"><span>{t("routeDist")}</span><span>{routeInfo.distance_km} km</span></div>
            <div className="route-line-row"><span>{t("routeTime")}</span><span>{Math.floor(routeInfo.time_min / 60)}h{String(routeInfo.time_min % 60).padStart(2, "0")}</span></div>
            {routeInfo.traffic_delay_min > 0 && <div className="route-line-row delay"><span>{t("routeTraffic")}</span><span>+{routeInfo.traffic_delay_min} min</span></div>}
            <div className="route-line-row"><span>{t("routeEta")}</span><span>{routeInfo.arrival ? new Date(routeInfo.arrival).toLocaleTimeString(lang === "fr" ? "fr-FR" : "en-GB", { hour: "2-digit", minute: "2-digit" }) : "—"}</span></div>
            {routeInfo.fuel_cost != null && <div className="route-line-row"><span>{t("routeFuel")}</span><span>{routeInfo.fuel_liters} L · ~{routeInfo.fuel_cost} €</span></div>}
          </div>
        )}

        <label className="switch-row" style={{ marginTop: 10 }}>
          <input type="checkbox" checked={markerMode} onChange={(e) => setMarkerMode(e.target.checked)} />
          <span>{t("markerMode")}</span>
        </label>
        {markers.length > 0 && (
          <button className="secondary" onClick={() => setMarkers([])}>{t("markerClear")} ({markers.length})</button>
        )}

        <label>{t("eventClass")}</label>
        <select value={filters.quad_class} onChange={(e) => setFilters({ ...filters, quad_class: e.target.value })}>
          <option value="">{t("allClasses")}</option>
          <option value="1">{t("q1")}</option>
          <option value="2">{t("q2")}</option>
          <option value="3">{t("q3")}</option>
          <option value="4">{t("q4")}</option>
        </select>

        <label>{t("countryLabel")}</label>
        <input value={filters.country} placeholder="UP" onChange={(e) => setFilters({ ...filters, country: e.target.value })} />

        <label>{t("actorLabel")}</label>
        <input value={filters.actor} placeholder="MILITARY" onChange={(e) => setFilters({ ...filters, actor: e.target.value })} />

        <label>{t("timeWindow")}</label>
        <select
          value={hours}
          onChange={(e) => {
            setHours(Number(e.target.value));
            setVersion((v) => v + 1);
          }}
        >
          <option value={0}>{t("allTime")}</option>
          <option value={1}>1 h</option>
          <option value={3}>3 h</option>
          <option value={6}>6 h</option>
          <option value={12}>12 h</option>
          <option value={24}>24 h</option>
          <option value={48}>48 h</option>
        </select>

        <button onClick={apply}>{t("apply")}</button>
        <button className="secondary" onClick={reset}>{t("reset")}</button>
        <button className="llm" onClick={() => setChatOpen(true)}>
          {t("synthesis")}
        </button>
        <button className="secondary" onClick={() => setNotepadOpen(true)}>{t("notepad")}</button>

        {tab === "map" && (
          <>
            <div className="section-title">{t("layers")}</div>
            <label className="switch-row">
              <input type="checkbox" checked={showSat} onChange={(e) => setShowSat(e.target.checked)} />
              <span>{t("showSat")}</span>
            </label>
            <label className="switch-row">
              <input type="checkbox" checked={showSats} onChange={(e) => setShowSats(e.target.checked)} />
              <span>{t("showSats")}</span>
            </label>
            <label className="switch-row">
              <input type="checkbox" checked={showCams} onChange={(e) => setShowCams(e.target.checked)} />
              <span>{t("showCams")}</span>
            </label>
            <label className="switch-row">
              <input type="checkbox" checked={showTraffic} onChange={(e) => setShowTraffic(e.target.checked)} />
              <span>{t("showTraffic")}</span>
            </label>
            <label className="switch-row">
              <input type="checkbox" checked={showRoads} onChange={(e) => setShowRoads(e.target.checked)} />
              <span>{t("showRoads")}</span>
            </label>
            <label className="switch-row">
              <input type="checkbox" checked={showWeather} onChange={(e) => setShowWeather(e.target.checked)} />
              <span>{t("showWeather")}</span>
              <button className="layer-winbtn" onClick={(e) => { e.preventDefault(); setWxOpen(true); }} title={t("winInfo")}>i</button>
            </label>
            <label className="switch-row">
              <input type="checkbox" checked={showCyber} onChange={(e) => setShowCyber(e.target.checked)} />
              <span>{t("showCyber")}</span>
            </label>
            <label className="switch-row">
              <input type="checkbox" checked={showInfra} onChange={(e) => setShowInfra(e.target.checked)} />
              <span>{t("showInfra")}</span>
              <button className="layer-winbtn" onClick={(e) => { e.preventDefault(); setNetOpen(true); }} title={t("winInfo")}>i</button>
            </label>
            <label className="switch-row">
              <input type="checkbox" checked={showPower} onChange={(e) => setShowPower(e.target.checked)} />
              <span>{t("showPower")}</span>
            </label>
            <label className="switch-row">
              <input type="checkbox" checked={showAir} onChange={(e) => setShowAir(e.target.checked)} />
              <span>{t("showAir")}</span>
              <button className="layer-winbtn" onClick={(e) => { e.preventDefault(); setAirOpen(true); }} title={t("winInfo")}>i</button>
            </label>
            <label className="switch-row">
              <input type="checkbox" checked={newsOpen} onChange={(e) => setNewsOpen(e.target.checked)} />
              <span>{t("showNews")}</span>
            </label>
            <label className="switch-row">
              <input type="checkbox" checked={cyberNewsOpen} onChange={(e) => setCyberNewsOpen(e.target.checked)} />
              <span>{t("showCyberNews")}</span>
            </label>
            <label className="switch-row">
              <input type="checkbox" checked={showFires} onChange={(e) => setShowFires(e.target.checked)} />
              <span>{t("showFires")}</span>
            </label>
            <label className="switch-row">
              <input type="checkbox" checked={showQuakes} onChange={(e) => setShowQuakes(e.target.checked)} />
              <span>{t("showQuakes")}</span>
            </label>
            <label className="switch-row">
              <input type="checkbox" checked={showEonet} onChange={(e) => setShowEonet(e.target.checked)} />
              <span>{t("showEonet")}</span>
            </label>
            <label className="switch-row">
              <input type="checkbox" checked={showVessels} onChange={(e) => setShowVessels(e.target.checked)} />
              <span>{t("showVessels")}</span>
            </label>
            <label className="switch-row">
              <input type="checkbox" checked={showFlights} onChange={(e) => setShowFlights(e.target.checked)} />
              <span>{t("showFlights")}</span>
            </label>
            <label className="switch-row">
              <input type="checkbox" checked={showDisasters} onChange={(e) => setShowDisasters(e.target.checked)} />
              <span>{t("showDisasters")}</span>
            </label>
          </>
        )}

        <div className="section-title">{t("autoRefresh")}</div>
        <label className="switch-row">
          <input type="checkbox" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} />
          <span>
            {autoRefresh ? "ON" : "OFF"} · {t("updated")} {new Date(lastUpdate).toLocaleTimeString()}
          </span>
        </label>

        <div className="section-title">{t("alertFeed")}</div>
        <button className={alerts ? "alert-btn on" : "alert-btn"} onClick={() => (alerts ? setAlerts(null) : loadAlerts())}>
          {alerts ? `${t("alertFeed")} (${alerts.length})` : t("alertFeed")}
        </button>
        {alerts && (
          <div className="alert-list">
            {alerts.length === 0 && <div className="muted" style={{ fontSize: 12, padding: 4 }}>{t("noAlerts")}</div>}
            {alerts.slice(0, 25).map((a, i) => (
              <div
                key={i}
                className="alert-row"
                onClick={() => a.lat != null && setFocus({ lat: a.lat, lon: a.lon, zoom: 5, _t: Date.now() })}
              >
                <span className={`sev sev-${a.severity}`} />
                <div className="alert-body">
                  <div className="alert-title">{a.title}</div>
                  <div className="alert-meta">{a.place || a.source}</div>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="section-title">{t("hotspots")}</div>
        <button className="secondary" onClick={() => (hotspots ? setHotspots(null) : loadHotspots())}>
          {t("hotspots")}
        </button>
        {hotspots && (
          <div className="hotspot-list">
            {hotspots.map((h, i) => (
              <div
                key={i}
                className="hotspot-row"
                onClick={() => setFocus({ lat: h.lat, lon: h.lon, zoom: 5, _t: Date.now() })}
                title={`${h.events} ${t("events")}${h.fires ? " · " + h.fires + " " + t("showFires") : ""}`}
              >
                <div className="hotspot-bar" style={{ width: `${Math.max(8, (h.score / maxScore) * 100)}%` }} />
                <div className="hotspot-text">
                  <span className="hotspot-rank">{i + 1}</span>
                  <span className="hotspot-place">{h.place || h.country || `${h.lat},${h.lon}`}</span>
                  <span className="hotspot-score">{h.score}</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {markets && (
          <Collapsible title={t("markets")} defaultOpen={false}>
            {[["indices", "mIndices"], ["commodities", "mCommodities"], ["crypto", "mCrypto"], ["forex", "mForex"]].map(([key, label]) => (
              <div key={key} className="mkt-group">
                <div className="mkt-label">{t(label)}</div>
                {(markets[key] || []).map((q) => (
                  <div key={q.symbol} className="mkt-row">
                    <span className="mkt-name">{q.name}</span>
                    <span className="mkt-price">{q.price != null ? Number(q.price).toLocaleString(undefined, { maximumFractionDigits: q.price < 10 ? 4 : 2 }) : "—"}</span>
                    <span className={`mkt-chg ${q.change_pct >= 0 ? "up" : "down"}`}>
                      {q.change_pct != null ? `${q.change_pct >= 0 ? "+" : "−"}${Math.abs(q.change_pct).toFixed(2)}%` : "—"}
                    </span>
                  </div>
                ))}
              </div>
            ))}
          </Collapsible>
        )}

        {prediction && prediction.length > 0 && (
          <Collapsible title={t("prediction")} defaultOpen={false}>
            <div className="pred-list">
              {prediction.map((m) => (
                <a
                  key={m.slug}
                  className="pred-item"
                  href={`https://polymarket.com/event/${m.slug}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  title={m.question}
                >
                  <div className="pred-top">
                    <span className="pred-prob">{m.probability}%</span>
                    <span className="pred-q">{m.question}</span>
                  </div>
                  <div className="pred-meta">
                    {m.leader} · {t("predVolume")} {fmtUsd(m.volume)}
                  </div>
                </a>
              ))}
            </div>
          </Collapsible>
        )}

        <Collapsible title={t("osintTools")} defaultOpen={false}>
        <div className="section-title">{t("screening")}</div>
        <div className="screen-box">
          <input
            value={screenQ}
            placeholder={t("screenPlaceholder")}
            onChange={(e) => setScreenQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && screen()}
          />
          {screenRes && (
            <div className="screen-results">
              <div className={screenRes.count ? "screen-hit" : "screen-clear"}>
                {screenRes.count ? `${screenRes.count} ${t("matches")}` : t("noMatch")}
              </div>
              {screenRes.results.slice(0, 10).map((r, i) => (
                <a
                  key={i}
                  className="screen-item"
                  href={r.link}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <div className="screen-name">
                    <span className={`screen-src src-${r.source === "OFAC" ? "ofac" : "os"}`}>{r.source}</span>
                    {r.name}
                  </div>
                  <div className="screen-prog">
                    {r.type || "?"}{r.countries ? " · " + r.countries : ""} · {(r.program || "—").slice(0, 60)}
                  </div>
                </a>
              ))}
            </div>
          )}
        </div>

        <div className="section-title">{t("cyber")}</div>
        <div className="screen-box">
          <input
            value={cyberIp}
            placeholder={t("cyberPlaceholder")}
            onChange={(e) => setCyberIp(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && cyberLookup()}
          />
          {cyberRes && (
            <div className="screen-results">
              {cyberRes.found ? (
                <>
                  <div className="cyber-ip">{cyberRes.ip}</div>
                  <div className="cyber-line"><b>{t("cyberPorts")}:</b> {(cyberRes.ports || []).join(", ") || "—"}</div>
                  {cyberRes.hostnames?.length > 0 && (
                    <div className="cyber-line cyber-host">{cyberRes.hostnames.slice(0, 4).join(", ")}</div>
                  )}
                  {cyberRes.vulns?.length > 0 && (
                    <div className="cyber-line">
                      <b>{t("cyberVulns")} ({cyberRes.vulns.length}{cyberRes.kev_count ? `, ${cyberRes.kev_count} KEV` : ""}):</b>{" "}
                      {cyberRes.vulns.slice(0, 12).map((v) => (
                        <a
                          key={v.id}
                          className={v.kev ? "cve-badge kev" : "cve-badge"}
                          href={`https://nvd.nist.gov/vuln/detail/${v.id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          title={v.kev ? "Activement exploitée (CISA KEV)" : v.id}
                        >
                          {v.id}
                        </a>
                      ))}
                    </div>
                  )}
                  {cyberRes.tags?.length > 0 && (
                    <div className="cyber-line"><b>Tags:</b> {cyberRes.tags.join(", ")}</div>
                  )}
                </>
              ) : (
                <div className="screen-clear">{t("cyberNone")}</div>
              )}
            </div>
          )}
        </div>

        <div className="section-title">{t("geoip")}</div>
        <div className="screen-box">
          <input
            value={geoIp}
            placeholder={t("geoipPlaceholder")}
            onChange={(e) => setGeoIp(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && geolocateIp()}
          />
          <button className="secondary" onClick={geolocateIp} style={{ marginTop: 6 }}>{t("geoipLocate")}</button>
          {geoRes && (
            <div className="screen-results">
              {geoRes.found ? (
                <>
                  <div className="cyber-ip">{geoRes.ip}</div>
                  <div className="cyber-line">{geoRes.city ? geoRes.city + ", " : ""}{geoRes.region ? geoRes.region + ", " : ""}{geoRes.country}</div>
                  <div className="cyber-line cyber-host">{geoRes.org || geoRes.isp}</div>
                  <div className="cyber-line cyber-host">{geoRes.asn}</div>
                </>
              ) : (
                <div className="screen-hit">{t("noMatch")}</div>
              )}
            </div>
          )}
        </div>

        <div className="section-title">{t("finance")}</div>
        <div className="screen-box">
          <input
            value={finQ}
            placeholder={t("financePlaceholder")}
            onChange={(e) => setFinQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && financeSearch()}
          />
          {finRes && (
            <div className="screen-results">
              {finRes.results.length === 0 ? (
                <div className="screen-clear">{t("financeNone")}</div>
              ) : (
                finRes.results.slice(0, 10).map((a, i) => (
                  <div key={i} className="fin-item">
                    <div className="fin-top">
                      <span className="fin-amount">{fmtUsd(a.amount)}</span>
                      <span className="fin-recip">{a.recipient}</span>
                    </div>
                    <div className="fin-agency">{a.agency}</div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        <div className="section-title">{t("research")}</div>
        <div className="screen-box">
          <input
            value={resQ}
            placeholder={t("researchPlaceholder")}
            onChange={(e) => setResQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && researchSearch()}
          />
          {resRes && (
            <div className="screen-results">
              {resRes.results.length === 0 ? (
                <div className="screen-clear">{t("researchNone")}</div>
              ) : (
                resRes.results.slice(0, 8).map((p, i) => (
                  <a key={i} className="res-item" href={p.link} target="_blank" rel="noopener noreferrer">
                    <div className="res-title">{p.title}</div>
                    <div className="res-meta">{p.published} · {p.category} · {(p.authors || []).slice(0, 2).join(", ")}</div>
                  </a>
                ))
              )}
            </div>
          )}
        </div>

        </Collapsible>

        <div className="section-title">{t("legend")}</div>
        <div className="legend">
          {Object.entries(QUAD_LABELS).map(([k, v]) => (
            <div className="legend-item" key={k}>
              <span className="dot" style={{ background: QUAD_COLORS[k] }} />{v}
            </div>
          ))}
          {[
            ["#f8552b", "showFires", showFires, setShowFires],
            ["#d24dff", "showQuakes", showQuakes, setShowQuakes],
            ["#4dabff", "showEonet", showEonet, setShowEonet],
            ["#f0a020", "showVessels", showVessels, setShowVessels],
            ["#00e5ff", "showFlights", showFlights, setShowFlights],
            ["#ff8c1a", "showDisasters", showDisasters, setShowDisasters],
            ["#3fa7c8", "showRoads", showRoads, setShowRoads],
            ["#e5484d", "showCyber", showCyber, setShowCyber],
            ["#57c7e8", "showInfra", showInfra, setShowInfra],
            ["#d8973b", "showPower", showPower, setShowPower],
          ].map(([color, key, on, setter]) => (
            <div
              key={key}
              className={`legend-item legend-toggle${on ? "" : " off"}`}
              onClick={() => setter(!on)}
              title={tab === "map" ? "" : t("map")}
            >
              <span className="dot" style={{ background: color }} />{t(key)}
            </div>
          ))}
        </div>

        <div className="stats">
          <div className="stat-row">
            <span>{tab === "map" ? t("eventsOnMap") : t("actorsInGraph")}</span>
            <span>{count.toLocaleString()}</span>
          </div>
          {stats && (
            <>
              <div className="stat-row"><span>{t("totalEvents")}</span><span>{stats.events.toLocaleString()}</span></div>
              <div className="stat-row"><span>{t("distinctActors")}</span><span>{stats.actors.toLocaleString()}</span></div>
              <div className="section-title">{t("topCountries")}</div>
              {stats.top_countries.slice(0, 8).map((c) => (
                <div className="stat-row" key={c.country}><span>{c.country}</span><span>{c.count.toLocaleString()}</span></div>
              ))}
            </>
          )}
        </div>
      </aside>

      <div className="map-wrap">
        <LiveTV />
        {tab === "map" && (
          <div className="basemap-col">
            <div className="basemap-switch">
              {BASEMAP_KEYS.map((k) => (
                <button key={k} className={basemap === k ? "on" : ""} onClick={() => setBasemap(k)}>
                  {(BASEMAP_LABELS[lang] || BASEMAP_LABELS.en)[k]}
                </button>
              ))}
            </div>
            <Clock lang={lang} />
            <button
              className={showGoogleHD ? "ghd-btn on" : "ghd-btn"}
              onClick={() => setShowGoogleHD((v) => !v)}
              title="Basculer sur les textures Google HD (zoom max) — nécessite Map Tiles API activée"
            >
              Google HD
            </button>
          </div>
        )}

        {tab === "map" ? (
          basemap === "google3d" ? (
            <Suspense fallback={<div className="globe-error">Chargement du globe Google 3D…</div>}>
              <GoogleGlobe
                query={query}
                showFires={showFires} showQuakes={showQuakes} showEonet={showEonet}
                showVessels={showVessels} showFlights={showFlights} showDisasters={showDisasters}
                showCams={showCams} showCyber={showCyber} showPower={showPower}
                showSats={showSats} showInfra={showInfra}
              />
            </Suspense>
          ) : (
            <MapView
              query={query}
              version={version}
              tick={autoTick}
              onCount={setCount}
              lang={lang}
              showFires={showFires}
              showQuakes={showQuakes}
              showEonet={showEonet}
              showVessels={showVessels}
              showFlights={showFlights}
              showDisasters={showDisasters}
              showSat={showSat}
              showSats={showSats}
              showCams={showCams}
              showTraffic={showTraffic}
              showRoads={showRoads}
              showWeather={showWeather}
              showCyber={showCyber}
              showInfra={showInfra}
              showPower={showPower}
              showAir={showAir}
              airProduct={airProduct}
              wxMode={wxMode}
              showGoogleHD={showGoogleHD}
              onCamera={addCamera}
              basemap={basemap}
              focus={focus}
              route={routeGeo}
              markers={markers}
              onMapClick={handleMapClick}
            />
          )
        ) : (
          <GraphView query={query} version={version} onCount={setCount} lang={lang}
            onActorFilter={(name) => {
              const nf = { ...applied, actor: name };
              setFilters(nf); setApplied(nf); setTab("map"); setVersion((v) => v + 1);
            }} />
        )}

        <div className="credit-footer">
          <a className="credit-gh" href="https://github.com/Dev-next-gen/orodruin" target="_blank" rel="noopener noreferrer" title="Code source sur GitHub" aria-label="GitHub">
            <svg viewBox="0 0 16 16" width="20" height="20" fill="currentColor" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
          </a>
          <span className="credit-dev">{t("devNotice")}</span>
          <span className="credit-line">
            <span className="credit-by">Developed by</span>{" "}
            <a className="credit-brand" href="https://nextgen-labs.net/" target="_blank" rel="noopener noreferrer">NextGen Lab's</a>
            {" · "}
            <a className="credit-brand" href="https://github.com/Dev-next-gen/orodruin" target="_blank" rel="noopener noreferrer">GitHub</a>
          </span>
        </div>

        <NewsTicker lang={lang} />
      </div>

      <CamPlayers players={camPlayers} onClose={closeCam} onChange={updateCam} />
      {netOpen && <NetworkStatus lang={lang} onClose={() => setNetOpen(false)} />}
      {wxOpen && <WeatherLegend lang={lang} center={focus} mode={wxMode} setMode={setWxMode} onClose={() => setWxOpen(false)} />}
      {newsOpen && <NewsFeed lang={lang} onClose={() => setNewsOpen(false)} />}
      {airOpen && <AirLegend lang={lang} product={airProduct} setProduct={setAirProduct} onClose={() => setAirOpen(false)} />}
      {cyberNewsOpen && <NewsFeed lang={lang} category="cyber" title={lang === "fr" ? "Cyber-menaces — temps réel" : "Cyber threats — live"} onClose={() => setCyberNewsOpen(false)} />}
      {settingsOpen && <Settings lang={lang} onClose={() => setSettingsOpen(false)} />}
      {notepadOpen && <Notepad lang={lang} onClose={() => setNotepadOpen(false)} />}

      <ChatBox
        lang={lang}
        open={chatOpen}
        setOpen={setChatOpen}
        onActions={handleActions}
        labels={{
          analyst: t("chatAnalyst"),
          hint: t("chatHint"),
          placeholder: t("chatPlaceholder"),
          thinking: t("chatThinking"),
          clear: t("chatClear"),
        }}
      />
    </div>
  );
}
