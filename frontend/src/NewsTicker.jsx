import { useEffect, useState } from "react";

// Aggregated news RSS ticker, refreshed every 15 minutes.
export default function NewsTicker({ lang }) {
  const [items, setItems] = useState([]);

  useEffect(() => {
    let alive = true;
    const load = () =>
      fetch(`/api/news?lang=${lang}&limit=60`)
        .then((r) => r.json())
        .then((d) => alive && setItems(d.items || []))
        .catch(() => {});
    load();
    const id = setInterval(load, 15 * 60 * 1000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [lang]);

  if (!items.length) return null;
  const seq = items.concat(items); // duplicate for a seamless loop

  return (
    <div className="ticker">
      <div className="ticker-label"><span className="live-dot" />{lang === "fr" ? "DIRECT" : "LIVE"}</div>
      <div className="ticker-viewport">
        <div className="ticker-track">
          {seq.map((it, i) => (
            <a key={i} className="ticker-item" href={it.link} target="_blank" rel="noopener noreferrer">
              <span className="ticker-src">{it.source}</span>
              {it.title}
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
