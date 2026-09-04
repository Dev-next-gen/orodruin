import { useEffect, useState } from "react";
import FloatingWindow from "./FloatingWindow.jsx";

// Precipitation colour legend + live wind/conditions at a point (map centre).
const BANDS = [
  ["#a0d8ef", "Très faible", "Very light"],
  ["#3fb950", "Faible", "Light"],
  ["#d8c93b", "Modérée", "Moderate"],
  ["#e8952b", "Forte", "Heavy"],
  ["#e5484d", "Violente", "Intense"],
  ["#b048d8", "Extrême / grêle", "Extreme / hail"],
];

function windDirLabel(deg, fr) {
  if (deg == null) return "—";
  const dirsFr = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"];
  const dirsEn = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  const i = Math.round(deg / 45) % 8;
  return (fr ? dirsFr : dirsEn)[i];
}

const MODES = [
  ["precip", { fr: "Précip.", en: "Precip.", ru: "Осадки", ar: "أمطار" }],
  ["temp", { fr: "Temp.", en: "Temp.", ru: "Темп.", ar: "حرارة" }],
  ["wind", { fr: "Vent", en: "Wind", ru: "Ветер", ar: "رياح" }],
  ["clouds", { fr: "Nuages", en: "Clouds", ru: "Облака", ar: "غيوم" }],
];

export default function WeatherLegend({ lang, center, mode = "precip", setMode, onClose }) {
  const [w, setW] = useState(null);
  const fr = lang === "fr";
  const lat = center?.lat ?? 48.85;
  const lon = center?.lon ?? 2.35;

  useEffect(() => {
    fetch(`/api/weather?lat=${lat.toFixed(3)}&lon=${lon.toFixed(3)}`)
      .then((r) => r.json()).then(setW).catch(() => setW({ found: false }));
  }, [lat, lon]);

  return (
    <FloatingWindow
      title={fr ? "Radar météo — légende & vent" : "Weather radar — legend & wind"}
      onClose={onClose}
      initial={{ x: 180, y: 120, w: 300, h: 340 }}
    >
      <div className="ns-sec">{fr ? "Couche (mondiale)" : "Layer (global)"}</div>
      <div className="air-products">
        {MODES.map(([key, lbl]) => (
          <button key={key} className={`air-prod-btn ${mode === key ? "on" : ""}`} onClick={() => setMode && setMode(key)}>
            {lbl[lang] || lbl.en}
          </button>
        ))}
      </div>
      {mode !== "precip" && (
        <div className="ns-note" style={{ margin: "6px 0 0" }}>
          {fr ? "Vent/température/nuages = OpenWeatherMap (clé requise dans Paramètres ⚙)." : "Wind/temp/clouds = OpenWeatherMap (key required in Settings ⚙)."}
        </div>
      )}

      <div className="ns-sec">{fr ? "Intensité des précipitations" : "Precipitation intensity"}</div>
      <div className="wx-legend">
        {BANDS.map(([c, tfr, ten]) => (
          <div className="wx-band" key={c}>
            <span className="wx-swatch" style={{ background: c }} />
            <span>{fr ? tfr : ten}</span>
          </div>
        ))}
      </div>
      <div className="ns-sec">{fr ? "Conditions au centre de la carte" : "Conditions at map centre"}</div>
      {!w ? (
        <div className="muted" style={{ fontSize: 12 }}>{fr ? "Chargement…" : "Loading…"}</div>
      ) : w.found === false ? (
        <div className="muted" style={{ fontSize: 12 }}>{fr ? "Indisponible" : "Unavailable"}</div>
      ) : (
        <div>
          <div className="stat-row"><span>{fr ? "Conditions" : "Conditions"}</span><span>{w.condition}</span></div>
          <div className="stat-row"><span>{fr ? "Température" : "Temperature"}</span><span>{w.temp}°C</span></div>
          <div className="stat-row"><span>{fr ? "Vent" : "Wind"}</span><span>{w.wind_speed} km/h {windDirLabel(w.wind_dir, fr)}</span></div>
          <div className="stat-row"><span>{fr ? "Rafales" : "Gusts"}</span><span>{w.wind_gusts} km/h</span></div>
          <div className="stat-row"><span>{fr ? "Précip." : "Precip."}</span><span>{w.precip} mm</span></div>
          <div className="stat-row"><span>{fr ? "Nuages" : "Clouds"}</span><span>{w.clouds}%</span></div>
          <div className="stat-row"><span>{fr ? "Pression" : "Pressure"}</span><span>{w.pressure} hPa</span></div>
        </div>
      )}
    </FloatingWindow>
  );
}
