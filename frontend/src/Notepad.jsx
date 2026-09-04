import { useEffect, useRef, useState } from "react";
import FloatingWindow from "./FloatingWindow.jsx";

// Draggable notepad — auto-saved to the browser, downloadable as a .txt file.
export default function Notepad({ lang, onClose }) {
  const fr = lang === "fr";
  const [text, setText] = useState("");
  const [saved, setSaved] = useState(false);
  const first = useRef(true);

  useEffect(() => {
    try { setText(localStorage.getItem("osint_notes") || ""); } catch { /* ignore */ }
  }, []);

  // autosave to the browser
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    const id = setTimeout(() => {
      try { localStorage.setItem("osint_notes", text); setSaved(true); setTimeout(() => setSaved(false), 1200); } catch { /* ignore */ }
    }, 500);
    return () => clearTimeout(id);
  }, [text]);

  function download() {
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `notes-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.txt`;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <FloatingWindow
      title={fr ? "Bloc-notes" : lang === "ru" ? "Блокнот" : lang === "ar" ? "المفكرة" : "Notepad"}
      onClose={onClose}
      className="fwin-glass"
      initial={{ x: 160, y: 110, w: 340, h: 360 }}
    >
      <textarea
        className="notepad-area"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={fr ? "Prends tes notes ici… (sauvegarde automatique)" : "Type your notes here… (auto-saved)"}
      />
      <div className="notepad-bar">
        <span className="notepad-status">{saved ? (fr ? "Enregistré" : "Saved") : ""}</span>
        <button className="fwin-btn" onClick={download}>{fr ? "Télécharger .txt" : "Download .txt"}</button>
      </div>
    </FloatingWindow>
  );
}
