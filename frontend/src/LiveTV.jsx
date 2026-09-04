import { useEffect, useRef, useState } from "react";
import Hls from "hls.js";

// Live TV via the open iptv-org catalog (thousands of public channels worldwide,
// direct HLS streams) served + grouped by the backend. Each channel carries up to
// 3 stream URLs so a dead source can fall back to the next automatically.

const MAX = 4;
const MIN_W = 240;
const MAX_W = 820;

let uid = 1;
let _catalogPromise = null;

function loadCatalog(category) {
  if (!_catalogPromise) {
    _catalogPromise = fetch(`/api/tv/channels?category=${category}&limit=2400`)
      .then((r) => r.json())
      .then((d) => d.countries || [])
      .catch(() => []);
  }
  return _catalogPromise;
}

export default function LiveTV() {
  const [players, setPlayers] = useState([]);
  const [catalog, setCatalog] = useState(null);

  useEffect(() => { loadCatalog("news").then(setCatalog); }, []);

  const add = () =>
    setPlayers((ps) =>
      ps.length >= MAX
        ? ps
        : [...ps, { id: uid++, x: 12 + ps.length * 34, y: 12 + ps.length * 34, w: 340 }]
    );
  const close = (id) => setPlayers((ps) => ps.filter((p) => p.id !== id));
  const update = (id, patch) =>
    setPlayers((ps) => ps.map((p) => (p.id === id ? { ...p, ...patch } : p)));

  if (players.length === 0) {
    return (
      <button className="tv-toggle" onClick={add}>
        TV Live
      </button>
    );
  }

  return (
    <>
      {players.map((p) => (
        <TVPlayer
          key={p.id}
          player={p}
          catalog={catalog}
          canAdd={players.length < MAX}
          onAdd={add}
          onClose={() => close(p.id)}
          onChange={(patch) => update(p.id, patch)}
        />
      ))}
    </>
  );
}

function TVPlayer({ player, catalog, canAdd, onAdd, onClose, onChange }) {
  const [resizing, setResizing] = useState(false);
  const [country, setCountry] = useState(null); // country code
  const [chanId, setChanId] = useState(null);
  const [srcIdx, setSrcIdx] = useState(0);
  const [status, setStatus] = useState("");
  const drag = useRef(null);
  const rez = useRef(null);
  const videoRef = useRef(null);
  const h = Math.round(player.w * 9 / 16);

  // pick a sensible default country/channel once the catalog arrives
  useEffect(() => {
    if (!catalog || !catalog.length || country) return;
    const pref = catalog.find((g) => ["France", "United States", "United Kingdom"].includes(g.name)) || catalog[0];
    setCountry(pref.code);
    setChanId(pref.channels[0]?.id || null);
  }, [catalog, country]);

  const group = catalog?.find((g) => g.code === country);
  const channel = group?.channels.find((c) => c.id === chanId);
  const urls = channel?.urls || [];
  const url = urls[srcIdx];

  // (re)attach HLS whenever the target URL changes
  useEffect(() => {
    const video = videoRef.current;
    if (!video || !url) return;
    setStatus("");
    let hls;
    if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = url;
      video.play().catch(() => {});
    } else if (Hls.isSupported()) {
      hls = new Hls({ maxBufferLength: 12, liveSyncDurationCount: 3 });
      hls.loadSource(url);
      hls.attachMedia(video);
      hls.on(Hls.Events.MANIFEST_PARSED, () => video.play().catch(() => {}));
      hls.on(Hls.Events.ERROR, (_e, data) => {
        if (!data.fatal) return;
        // try the next source URL for this channel, else report unavailable
        setSrcIdx((i) => {
          if (i + 1 < urls.length) return i + 1;
          setStatus("Flux indisponible — essayez une autre chaîne");
          return i;
        });
      });
    } else {
      setStatus("HLS non supporté");
    }
    return () => { if (hls) hls.destroy(); };
  }, [url, urls.length]);

  function pickCountry(code) {
    const g = catalog.find((x) => x.code === code);
    setCountry(code);
    setChanId(g?.channels[0]?.id || null);
    setSrcIdx(0);
  }
  function pickChannel(id) { setChanId(id); setSrcIdx(0); }
  function nextSource() { if (urls.length > 1) setSrcIdx((i) => (i + 1) % urls.length); }

  function onDown(e) {
    const tag = e.target.tagName;
    if (tag === "SELECT" || tag === "OPTION" || tag === "BUTTON" || tag === "VIDEO") return;
    drag.current = { dx: e.clientX - player.x, dy: e.clientY - player.y };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }
  function onMove(e) {
    if (!drag.current) return;
    onChange({ x: e.clientX - drag.current.dx, y: e.clientY - drag.current.dy });
  }
  function onUp() {
    drag.current = null;
    window.removeEventListener("mousemove", onMove);
    window.removeEventListener("mouseup", onUp);
  }
  function onResizeDown(e) {
    e.stopPropagation();
    rez.current = { startX: e.clientX, startW: player.w };
    setResizing(true);
    window.addEventListener("mousemove", onResizeMove);
    window.addEventListener("mouseup", onResizeUp);
  }
  function onResizeMove(e) {
    if (!rez.current) return;
    const nw = rez.current.startW + (e.clientX - rez.current.startX);
    onChange({ w: Math.max(MIN_W, Math.min(MAX_W, nw)) });
  }
  function onResizeUp() {
    rez.current = null;
    setResizing(false);
    window.removeEventListener("mousemove", onResizeMove);
    window.removeEventListener("mouseup", onResizeUp);
  }

  return (
    <div className="tv-panel" style={{ left: player.x, top: player.y, width: player.w }}>
      <div className="tv-head tv-drag" onMouseDown={onDown}>
        <span className="tv-grip" title="Déplacer">⠿</span>
        <select value={country || ""} onChange={(e) => pickCountry(e.target.value)} title="Pays">
          {!catalog && <option>Chargement…</option>}
          {catalog?.map((g) => (
            <option key={g.code} value={g.code}>{g.name} ({g.channels.length})</option>
          ))}
        </select>
        <select value={chanId || ""} onChange={(e) => pickChannel(e.target.value)} title="Chaîne">
          {group?.channels.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
        {urls.length > 1 && (
          <button onClick={nextSource} title="Source suivante">{`SRC ${srcIdx + 1}/${urls.length}`}</button>
        )}
        <button onClick={onAdd} disabled={!canAdd} title="Ouvrir un autre lecteur (max 4)">+</button>
        <button onClick={onClose} title="Fermer">×</button>
      </div>
      <div className="tv-video" style={{ height: h }}>
        <video ref={videoRef} muted autoPlay playsInline controls style={{ width: "100%", height: "100%", background: "#000" }} />
        {status && <div className="tv-status">{status}</div>}
        {resizing && <div className="tv-shield" />}
      </div>
      <div className="tv-resize" onMouseDown={onResizeDown} title="Redimensionner">◢</div>
    </div>
  );
}
