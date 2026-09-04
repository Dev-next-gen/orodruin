import { useEffect, useState } from "react";

export default function Clock({ lang }) {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const loc = lang === "fr" ? "fr-FR" : "en-GB";
  const date = now.toLocaleDateString(loc, { weekday: "short", day: "2-digit", month: "short", timeZone: "UTC" });
  const time = now.toLocaleTimeString(loc, { hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone: "UTC" });

  return (
    <div className="utc-clock" title="Heure universelle (UTC) — pilote la face jour/nuit">
      <span className="utc-badge">UTC</span>
      <span className="utc-date">{date}</span>
      <span className="utc-time">{time}</span>
    </div>
  );
}
