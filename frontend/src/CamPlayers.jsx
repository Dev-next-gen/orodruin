import { useEffect, useRef, useState } from "react";
import Hls from "hls.js";

const MIN_W = 220, MAX_W = 760;

export default function CamPlayers({ players, onClose, onChange }) {
  return (
    <>
      {players.map((p) => (
        <CamWindow key={p.uid} player={p} onClose={() => onClose(p.uid)} onChange={(patch) => onChange(p.uid, patch)} />
      ))}
    </>
  );
}

function CamWindow({ player, onClose, onChange }) {
  const [resizing, setResizing] = useState(false);
  const [tick, setTick] = useState(0); // snapshot refresh counter
  const [hlsFailed, setHlsFailed] = useState(false);
  const drag = useRef(null);
  const rez = useRef(null);
  const videoRef = useRef(null);
  const h = Math.round(player.w * 9 / 16);

  // media type priority: live HLS > rolling MP4 > iframe embed > refreshing JPEG.
  // If a live stream dies (common on DOT feeds), fall back to the JPEG snapshot.
  const mode = hlsFailed && player.image ? "image"
    : player.stream ? "hls" : player.mp4 ? "mp4" : player.embed ? "embed" : player.image ? "image" : "none";

  // refreshing JPEG snapshot: re-fetch every 5s with a cache-buster
  useEffect(() => {
    if (mode !== "image") return;
    const id = setInterval(() => setTick((t) => t + 1), 5000);
    return () => clearInterval(id);
  }, [mode]);

  // attach hls.js for live streams
  useEffect(() => {
    if (mode !== "hls") return;
    const video = videoRef.current;
    if (!video) return;
    let hls;
    if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = player.stream;
      video.play().catch(() => {});
    } else if (Hls.isSupported()) {
      hls = new Hls({ maxBufferLength: 12, liveSyncDurationCount: 3 });
      hls.loadSource(player.stream);
      hls.attachMedia(video);
      hls.on(Hls.Events.MANIFEST_PARSED, () => video.play().catch(() => {}));
      hls.on(Hls.Events.ERROR, (_e, data) => { if (data.fatal) setHlsFailed(true); });
    }
    return () => { if (hls) hls.destroy(); };
  }, [mode, player.stream]);

  function onDown(e) {
    if (e.target.tagName === "BUTTON") return;
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
  function onRDown(e) {
    e.stopPropagation();
    rez.current = { x: e.clientX, w: player.w };
    setResizing(true);
    window.addEventListener("mousemove", onRMove);
    window.addEventListener("mouseup", onRUp);
  }
  function onRMove(e) {
    if (!rez.current) return;
    onChange({ w: Math.max(MIN_W, Math.min(MAX_W, rez.current.w + (e.clientX - rez.current.x))) });
  }
  function onRUp() {
    rez.current = null;
    setResizing(false);
    window.removeEventListener("mousemove", onRMove);
    window.removeEventListener("mouseup", onRUp);
  }

  const sep = player.image && player.image.includes("?") ? "&" : "?";
  const imgSrc = mode === "image" ? `${player.image}${sep}_t=${tick}` : null;
  const fill = { width: "100%", height: "100%", objectFit: "cover", display: "block", background: "#000" };

  return (
    <div className="tv-panel cam-panel" style={{ left: player.x, top: player.y, width: player.w }}>
      <div className="tv-head cam-head" onMouseDown={onDown}>
        <span className="cam-title">{player.title}</span>
        <button onClick={onClose} title="Fermer">×</button>
      </div>
      {player.place && <div className="cam-place">{player.place}</div>}
      <div className="tv-video" style={{ height: h }}>
        {mode === "hls" && <video ref={videoRef} muted autoPlay playsInline controls style={fill} />}
        {mode === "mp4" && <video key={player.mp4} src={player.mp4} muted autoPlay loop playsInline controls style={fill} />}
        {mode === "embed" && <iframe title={`cam-${player.uid}`} src={player.embed} allow="autoplay; fullscreen" allowFullScreen loading="lazy" style={{ width: "100%", height: "100%", border: 0 }} />}
        {mode === "image" && <img src={imgSrc} alt={player.title} style={fill} />}
        {mode === "none" && <div className="cam-noembed">Flux indisponible</div>}
        {resizing && <div className="tv-shield" />}
      </div>
      <div className="tv-resize" onMouseDown={onRDown} title="Redimensionner">◢</div>
    </div>
  );
}
