import { useEffect, useState } from "react";
import FloatingWindow from "./FloatingWindow.jsx";

// Global network-status board: submarine-cable backbone + space weather.
export default function NetworkStatus({ lang, onClose }) {
  const [s, setS] = useState(null);
  useEffect(() => {
    fetch("/api/infra/status").then((r) => r.json()).then(setS).catch(() => setS({}));
  }, []);

  const fr = lang === "fr";
  const scaleTxt = (v) => (v === "0" || v == null ? (fr ? "calme" : "quiet") : `S${v}`);
  const sw = s?.space_weather;

  return (
    <FloatingWindow
      title={fr ? "État du réseau mondial" : "Global network status"}
      onClose={onClose}
      initial={{ x: 150, y: 100, w: 320, h: 320 }}
    >
      {!s ? (
        <div className="muted" style={{ fontSize: 12 }}>{fr ? "Chargement…" : "Loading…"}</div>
      ) : (
        <div className="ns-grid">
          <div className="ns-sec">{fr ? "Dorsale sous-marine" : "Submarine backbone"}</div>
          <div className="stat-row"><span>{fr ? "Systèmes de câbles" : "Cable systems"}</span><span>{(s.cable_systems ?? 0).toLocaleString()}</span></div>
          <div className="stat-row"><span>{fr ? "Segments" : "Segments"}</span><span>{(s.cable_segments ?? 0).toLocaleString()}</span></div>
          <div className="stat-row"><span>{fr ? "Points d'atterrissage" : "Landing points"}</span><span>{(s.landing_points ?? 0).toLocaleString()}</span></div>

          <div className="ns-sec">{fr ? "Météo spatiale (NOAA)" : "Space weather (NOAA)"}</div>
          <div className="stat-row"><span>Kp index</span><span>{sw?.kp ?? "—"}</span></div>
          <div className="stat-row"><span>{fr ? "Blackout radio (R)" : "Radio blackout (R)"}</span><span>{scaleTxt(sw?.scales?.R)}</span></div>
          <div className="stat-row"><span>{fr ? "Orage solaire (S)" : "Solar storm (S)"}</span><span>{scaleTxt(sw?.scales?.S)}</span></div>
          <div className="stat-row"><span>{fr ? "Géomagnétique (G)" : "Geomagnetic (G)"}</span><span>{scaleTxt(sw?.scales?.G)}</span></div>
          <div className="stat-row"><span>{fr ? "Alertes actives" : "Active alerts"}</span><span>{sw?.alerts ?? 0}</span></div>
          <div className="ns-note">{fr
            ? "La météo spatiale dégrade HF, GPS et satcom."
            : "Space weather degrades HF, GPS and satcom."}</div>
        </div>
      )}
    </FloatingWindow>
  );
}
