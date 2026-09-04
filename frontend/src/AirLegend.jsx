import FloatingWindow from "./FloatingWindow.jsx";

// Sentinel-5P air-quality legend + product selector (NO2 / CH4 / CO / aerosol).
const RAMP = [
  ["#0000a0", "Très faible", "Very low", "Очень низкий", "منخفض جداً"],
  ["#0099cc", "Faible", "Low", "Низкий", "منخفض"],
  ["#00cc66", "Modéré", "Moderate", "Средний", "متوسط"],
  ["#e6e600", "Élevé", "High", "Высокий", "مرتفع"],
  ["#ff8000", "Très élevé", "Very high", "Очень высокий", "مرتفع جداً"],
  ["#ff0000", "Extrême", "Extreme", "Экстремальный", "أقصى"],
];

const PRODUCTS = {
  no2: { fr: "NO₂ (dioxyde d'azote)", en: "NO₂ (nitrogen dioxide)", ru: "NO₂ (диоксид азота)", ar: "NO₂ (ثاني أكسيد النيتروجين)",
    descFr: "Émis par le trafic, l'industrie et la combustion — révèle l'activité économique/militaire." },
  ch4: { fr: "CH₄ (méthane)", en: "CH₄ (methane)", ru: "CH₄ (метан)", ar: "CH₄ (ميثان)",
    descFr: "Fuites de gaz, sites pétroliers/gaziers, décharges, agriculture." },
  co: { fr: "CO (monoxyde de carbone)", en: "CO (carbon monoxide)", ru: "CO (угарный газ)", ar: "CO (أول أكسيد الكربون)",
    descFr: "Feux de biomasse et combustion industrielle." },
  aer: { fr: "Aérosols (indice UV)", en: "Aerosols (UV index)", ru: "Аэрозоли (УФ-индекс)", ar: "الهباء الجوي",
    descFr: "Poussières, fumées, cendres volcaniques, pollution." },
};

const li = { fr: 1, en: 2, ru: 3, ar: 4 };

export default function AirLegend({ lang, product = "no2", setProduct, onClose }) {
  const fr = lang === "fr";
  const idx = li[lang] || 2;
  const p = PRODUCTS[product] || PRODUCTS.no2;

  return (
    <FloatingWindow
      title={fr ? "Qualité de l'air — légende" : lang === "ru" ? "Качество воздуха — легенда" : lang === "ar" ? "جودة الهواء — مفتاح" : "Air quality — legend"}
      onClose={onClose}
      initial={{ x: 200, y: 130, w: 310, h: 360 }}
    >
      <div className="ns-sec">{fr ? "Produit (Sentinel-5P)" : "Product (Sentinel-5P)"}</div>
      <div className="air-products">
        {Object.entries(PRODUCTS).map(([key, def]) => (
          <button
            key={key}
            className={`air-prod-btn ${product === key ? "on" : ""}`}
            onClick={() => setProduct && setProduct(key)}
          >
            {key.toUpperCase().replace("AER", "AÉR")}
          </button>
        ))}
      </div>
      <div className="ns-note" style={{ margin: "6px 0 4px" }}><b>{p[["", "fr", "en", "ru", "ar"][idx]]}</b></div>

      <div className="ns-sec">{fr ? "Intensité" : "Intensity"}</div>
      <div className="wx-legend">
        {RAMP.map((row) => (
          <div className="wx-band" key={row[0]}>
            <span className="wx-swatch" style={{ background: row[0] }} />
            <span>{row[idx]}</span>
          </div>
        ))}
      </div>
      <div className="ns-note">{p.descFr}{fr ? "" : ""} · TROPOMI, colonne récente.</div>
    </FloatingWindow>
  );
}
