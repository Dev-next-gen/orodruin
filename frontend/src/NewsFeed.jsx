import { useEffect, useState } from "react";
import FloatingWindow from "./FloatingWindow.jsx";

// Live RSS aggregation window (freshest world news), semi-transparent + movable.
export default function NewsFeed({ lang, onClose, category, title }) {
  const [items, setItems] = useState(null);
  const feed = category || lang;

  useEffect(() => {
    let alive = true;
    const load = () =>
      fetch(`/api/news?lang=${feed}&limit=60`)
        .then((r) => r.json())
        .then((d) => alive && setItems(d.items || []))
        .catch(() => alive && setItems([]));
    load();
    const id = setInterval(load, 3 * 60 * 1000);
    return () => { alive = false; clearInterval(id); };
  }, [feed]);

  return (
    <FloatingWindow
      title={title || (lang === "fr" ? "Flux RSS — temps réel" : "RSS feed — live")}
      onClose={onClose}
      className="fwin-glass"
      initial={{ x: 210, y: 130, w: 360, h: 420 }}
    >
      {!items ? (
        <div className="muted" style={{ fontSize: 12 }}>{lang === "fr" ? "Chargement…" : "Loading…"}</div>
      ) : items.length === 0 ? (
        <div className="muted" style={{ fontSize: 12 }}>{lang === "fr" ? "Aucune actualité" : "No news"}</div>
      ) : (
        <div className="news-list">
          {items.map((it, i) => (
            <a key={i} className="news-item" href={it.link} target="_blank" rel="noopener noreferrer">
              <span className="news-src">{it.source}</span>
              <span className="news-title">{it.title}</span>
            </a>
          ))}
        </div>
      )}
    </FloatingWindow>
  );
}
