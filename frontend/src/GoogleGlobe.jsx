import { useEffect, useRef, useState } from "react";
import {
  Viewer,
  GoogleMaps,
  createGooglePhotorealistic3DTileset,
  Cartesian3,
  Color,
  PointPrimitiveCollection,
  GeoJsonDataSource,
  Ellipsoid,
  EllipsoidalOccluder,
} from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";

const QUAD = { 1: "#3fb950", 2: "#58a6ff", 3: "#d29922", 4: "#f85149" };
const FUEL = {
  Coal: "#6b7280", Gas: "#d8973b", Oil: "#8a5a2b", Nuclear: "#e5484d", Hydro: "#3fa7c8",
  Solar: "#f0d020", Wind: "#3fa870", Geothermal: "#b048d8", Biomass: "#7d9a3b",
};
const disasterColor = (lvl) => (lvl === "Red" ? "#f85149" : lvl === "Orange" ? "#ff8c1a" : "#d29922");

const LAYERS = (query) => [
  { key: "events", url: `/api/events/geojson?${query}`, size: 9, limit: 2000, color: (p) => QUAD[p.quad_class] || "#8b949e" },
  { key: "showFires", url: "/api/fires/geojson?limit=6000", size: 5, color: () => "#f8552b" },
  { key: "showQuakes", url: "/api/quakes/geojson", size: 8, color: () => "#d24dff" },
  { key: "showEonet", url: "/api/eonet/geojson?limit=500", size: 8, color: () => "#4dabff" },
  { key: "showVessels", url: "/api/vessels/geojson?limit=6000", size: 5, color: () => "#f0a020" },
  { key: "showFlights", url: "/api/flights/geojson?limit=8000", size: 5, color: () => "#00e5ff" },
  { key: "showDisasters", url: "/api/disasters/geojson", size: 11, color: (p) => disasterColor(p.alert_level) },
  { key: "showCams", url: "/api/cameras/geojson?limit=9000", size: 5, color: () => "#c17aff" },
  { key: "showCyber", url: "/api/ransomware?limit=250&geo=true", size: 8, color: () => "#e5484d" },
  { key: "showPower", url: "/api/powerplants/geojson?min_mw=1", size: 4, color: (p) => FUEL[p.fuel] || "#8b949e" },
  { key: "showSats", url: "/api/satellites/geojson", size: 5, color: () => "#57c7e8" },
];

export default function GoogleGlobe(props) {
  const { query } = props;
  const ref = useRef(null);
  const viewerRef = useRef(null);
  const colRef = useRef({});
  const loadedRef = useRef({});
  const spinRef = useRef(true);
  const feedRef = useRef([]);        // globe-feed items {title,sev,lat,lon,url}
  const activeRef = useRef([]);      // currently shown notes
  const pickTsRef = useRef(0);
  const [error, setError] = useState(null);
  const [notes, setNotes] = useState([]); // projected note cards

  useEffect(() => {
    let destroyed = false;
    (async () => {
      let cfg;
      try { cfg = await fetch("/api/config").then((r) => r.json()); }
      catch { setError("Config API injoignable."); return; }
      if (!cfg.google_maps_key) { setError("Clé Google Maps absente."); return; }
      GoogleMaps.defaultApiKey = cfg.google_maps_key;

      const viewer = new Viewer(ref.current, {
        baseLayerPicker: false, geocoder: false, homeButton: false, sceneModePicker: false,
        navigationHelpButton: false, timeline: false, animation: false, fullscreenButton: false,
        selectionIndicator: false, infoBox: false, globe: false,
      });
      viewer.scene.skyAtmosphere.show = true;
      viewerRef.current = viewer;

      try {
        const tileset = await createGooglePhotorealistic3DTileset();
        if (destroyed) return;
        viewer.scene.primitives.add(tileset);
      } catch {
        setError("Tuiles 3D Google indisponibles (active Map Tiles API + facturation).");
      }
      viewer.camera.flyTo({ destination: Cartesian3.fromDegrees(15, 20, 24_000_000), duration: 0 });

      // stop the spin as soon as the user interacts; right-click restarts it
      const canvas = viewer.scene.canvas;
      const stop = () => { spinRef.current = false; };
      canvas.addEventListener("mousedown", stop);
      canvas.addEventListener("wheel", stop);
      canvas.addEventListener("contextmenu", (e) => { e.preventDefault(); spinRef.current = true; });

      // auto-rotate + refresh floating notifications
      viewer.scene.postRender.addEventListener(() => {
        if (spinRef.current) viewer.camera.rotate(Cartesian3.UNIT_Z, -0.0016);
        const now = performance.now();
        if (now - pickTsRef.current > 150) { pickTsRef.current = now; updateNotes(); }
      });

      loadFeed();
      const feedTimer = setInterval(loadFeed, 60000);
      const pickTimer = setInterval(pickNotes, 3500);
      viewer._osintTimers = [feedTimer, pickTimer];

      if (!destroyed) reconcile();
    })();

    return () => {
      destroyed = true;
      const v = viewerRef.current;
      if (v && v._osintTimers) v._osintTimers.forEach(clearInterval);
      if (v && !v.isDestroyed()) v.destroy();
      viewerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadFeed() {
    try {
      const d = await fetch("/api/globe-feed?limit=140").then((r) => r.json());
      feedRef.current = (d.items || []).filter((a) => a.lat != null && a.lon != null);
      pickNotes();
    } catch { /* ignore */ }
  }

  // pick a random set of items on the visible hemisphere
  function pickNotes() {
    const viewer = viewerRef.current;
    if (!viewer) return;
    const occ = new EllipsoidalOccluder(Ellipsoid.WGS84, viewer.camera.positionWC);
    const vis = feedRef.current.filter((a) => {
      const c = Cartesian3.fromDegrees(a.lon, a.lat);
      return occ.isPointVisible(c);
    });
    for (let i = vis.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [vis[i], vis[j]] = [vis[j], vis[i]]; }
    activeRef.current = vis.slice(0, 6);
  }

  // project active notes to screen coordinates each frame
  function updateNotes() {
    const viewer = viewerRef.current;
    if (!viewer) return;
    const occ = new EllipsoidalOccluder(Ellipsoid.WGS84, viewer.camera.positionWC);
    const W = viewer.scene.canvas.clientWidth;
    const H = viewer.scene.canvas.clientHeight;
    const CARD_W = 220;
    const out = [];
    activeRef.current.forEach((a, i) => {
      const c = Cartesian3.fromDegrees(a.lon, a.lat, 0);
      if (!occ.isPointVisible(c)) return;
      const px = viewer.scene.cartesianToCanvasCoordinates(c);
      if (!px) return;
      const side = px.x < W / 2 ? "left" : "right";
      // place the card as a short callout right next to its point (like the 3D globe)
      let cardX = side === "left" ? px.x - CARD_W - 34 : px.x + 34;
      cardX = Math.max(8, Math.min(W - CARD_W - 8, cardX));
      let cardY = px.y - 16 + (i % 2 ? 22 : -22); // tiny stagger to reduce overlap
      cardY = Math.max(56, Math.min(H - 46, cardY));
      out.push({ id: `${a.type}-${i}`, title: a.title, sev: a.sev, url: a.url, lat: a.lat, lon: a.lon,
                 x: px.x, y: px.y, cardX, cardY, side });
    });
    setNotes(out);
  }

  function flyToNote(n) {
    const viewer = viewerRef.current;
    if (!viewer) return;
    spinRef.current = false;
    viewer.camera.flyTo({ destination: Cartesian3.fromDegrees(n.lon, n.lat, 800000), duration: 1.4 });
  }

  async function loadLayer(layer) {
    const viewer = viewerRef.current;
    if (!viewer || loadedRef.current[layer.key]) return;
    loadedRef.current[layer.key] = true;
    try {
      const geo = await fetch(layer.url).then((r) => r.json());
      if (!viewerRef.current) return;
      const col = viewer.scene.primitives.add(new PointPrimitiveCollection());
      colRef.current[layer.key] = col;
      for (const f of (geo.features || []).slice(0, layer.limit || 40000)) {
        const c = f.geometry && f.geometry.coordinates;
        if (!c || c.length < 2) continue;
        col.add({
          position: Cartesian3.fromDegrees(c[0], c[1], 60),
          color: Color.fromCssColorString(layer.color(f.properties || {})),
          pixelSize: layer.size, outlineColor: Color.BLACK, outlineWidth: 0.6,
        });
      }
    } catch { loadedRef.current[layer.key] = false; }
  }

  function clearLayer(key) {
    const viewer = viewerRef.current;
    const col = colRef.current[key];
    if (viewer && col && !viewer.isDestroyed()) viewer.scene.primitives.remove(col);
    delete colRef.current[key];
    loadedRef.current[key] = false;
  }

  function reconcile() {
    if (!viewerRef.current) return;
    for (const layer of LAYERS(query)) {
      const on = layer.key === "events" ? true : !!props[layer.key];
      if (on && !loadedRef.current[layer.key]) loadLayer(layer);
      else if (!on && loadedRef.current[layer.key]) clearLayer(layer.key);
    }
  }

  const infraRef = useRef(null);
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    if (props.showInfra && !infraRef.current) {
      GeoJsonDataSource.load("/api/infra/cables", { stroke: Color.fromCssColorString("#57c7e8"), strokeWidth: 1.5, clampToGround: false })
        .then((ds) => { if (viewerRef.current) { viewer.dataSources.add(ds); infraRef.current = ds; } });
    } else if (!props.showInfra && infraRef.current) {
      viewer.dataSources.remove(infraRef.current); infraRef.current = null;
    }
  }, [props.showInfra]);

  useEffect(() => {
    if (loadedRef.current.events) clearLayer("events");
    reconcile();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);
  useEffect(() => { reconcile(); });

  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <div ref={ref} style={{ position: "absolute", inset: 0 }} />
      {notes.length > 0 && (
        <div className="globe-notes">
          <svg className="globe-lines">
            {notes.map((n) => (
              <g key={n.id}>
                <line x1={n.side === "left" ? n.cardX + 220 : n.cardX} y1={n.cardY + 16} x2={n.x} y2={n.y} className={`gline s${n.sev}`} />
                <circle cx={n.x} cy={n.y} r={n.url ? 6 : 4} className={`gdot s${n.sev}`}
                  style={{ pointerEvents: n.url ? "auto" : "none", cursor: n.url ? "pointer" : "default" }}
                  onClick={() => n.url && window.open(n.url, "_blank", "noopener")} />
              </g>
            ))}
          </svg>
          {notes.map((n) => (
            <div key={n.id} className={`globe-note s${n.sev}`} style={{ left: n.cardX, top: n.cardY, width: 220, cursor: "pointer" }}
              onClick={() => flyToNote(n)} title="Cliquer : aller au point">
              <span className="gsev" />
              <span className="gtitle">{n.title}</span>
              {n.url && <a className="gsrc" href={n.url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()} title="Source">↗</a>}
            </div>
          ))}
        </div>
      )}
      {error && <div className="globe-error">{error}</div>}
    </div>
  );
}
