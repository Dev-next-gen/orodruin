import { useEffect, useState } from "react";
import FloatingWindow from "./FloatingWindow.jsx";

// Settings — paste API keys without editing files. Values are write-only: the
// backend never returns them, only whether each key is set.
export default function Settings({ lang, onClose }) {
  const [keys, setKeys] = useState(null);
  const [drafts, setDrafts] = useState({});
  const [saving, setSaving] = useState("");
  const [llm, setLlm] = useState(null);
  const [llmDraft, setLlmDraft] = useState({ base_url: "", model: "", api_key: "" });
  const fr = lang === "fr";

  function load() {
    fetch("/api/settings/keys").then((r) => r.json()).then((d) => setKeys(d.keys || [])).catch(() => setKeys([]));
    fetch("/api/settings/llm").then((r) => r.json()).then((d) => {
      setLlm(d);
      setLlmDraft({ base_url: d.base_url || "", model: d.model || "", api_key: "" });
    }).catch(() => {});
  }
  useEffect(load, []);

  async function saveLlm() {
    setSaving("llm");
    try {
      const body = { base_url: llmDraft.base_url, model: llmDraft.model };
      if (llmDraft.api_key) body.api_key = llmDraft.api_key;
      await fetch("/api/settings/llm", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      load();
    } finally {
      setSaving("");
    }
  }

  async function save(env) {
    const value = drafts[env];
    if (value == null) return;
    setSaving(env);
    try {
      await fetch("/api/settings/keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ env, value }),
      });
      setDrafts((d) => ({ ...d, [env]: "" }));
      load();
    } finally {
      setSaving("");
    }
  }

  return (
    <FloatingWindow
      title={fr ? "Paramètres — clés API" : "Settings — API keys"}
      onClose={onClose}
      initial={{ x: 120, y: 70, w: 420, h: 460 }}
    >
      <div className="ns-note" style={{ marginTop: 0, marginBottom: 10 }}>
        {fr
          ? "Colle tes clés API gratuites ci-dessous. Elles sont écrites dans backend/.env et appliquées immédiatement. Les valeurs ne sont jamais réaffichées."
          : "Paste your free API keys below. They are written to backend/.env and applied immediately. Values are never shown back."}
      </div>
      <div className="ns-sec">{fr ? "Modèle IA (analyste)" : "AI model (analyst)"}</div>
      {llm && (
        <div className="set-row" style={{ marginBottom: 12 }}>
          <div className="ns-note" style={{ margin: "0 0 6px" }}>
            {fr ? "N'importe quel endpoint compatible OpenAI (local, OpenAI, OpenRouter, Groq…)." : "Any OpenAI-compatible endpoint (local, OpenAI, OpenRouter, Groq…)."}
          </div>
          <label style={{ margin: "4px 0 2px" }}>Base URL</label>
          <input value={llmDraft.base_url} placeholder="https://api.openai.com/v1"
                 onChange={(e) => setLlmDraft((d) => ({ ...d, base_url: e.target.value }))} />
          <label style={{ margin: "6px 0 2px" }}>{fr ? "Modèle" : "Model"}</label>
          <input value={llmDraft.model} placeholder="gpt-4o-mini"
                 onChange={(e) => setLlmDraft((d) => ({ ...d, model: e.target.value }))} />
          <label style={{ margin: "6px 0 2px" }}>API key {llm.api_key_set ? (fr ? "(définie)" : "(set)") : ""}</label>
          <input type="password" value={llmDraft.api_key}
                 placeholder={fr ? "vide = LLM local sans clé" : "empty = local, no key"}
                 onChange={(e) => setLlmDraft((d) => ({ ...d, api_key: e.target.value }))} />
          <button className="fwin-btn" style={{ marginTop: 8 }} disabled={saving === "llm"} onClick={saveLlm}>
            {saving === "llm" ? "…" : fr ? "Enregistrer le modèle" : "Save model"}
          </button>
        </div>
      )}

      <div className="ns-sec">{fr ? "Clés des sources de données" : "Data source keys"}</div>
      {!keys ? (
        <div className="muted" style={{ fontSize: 12 }}>{fr ? "Chargement…" : "Loading…"}</div>
      ) : (
        <div className="set-list">
          {keys.map((k) => (
            <div className="set-row" key={k.env}>
              <div className="set-head">
                <span className={`set-badge ${k.set ? "on" : "off"}`}>{k.set ? "SET" : "—"}</span>
                <span className="set-label">{k.label}</span>
                <a className="set-help" href={k.help} target="_blank" rel="noopener noreferrer">?</a>
              </div>
              <div className="set-input">
                <input
                  type={k.secret ? "password" : "text"}
                  placeholder={k.set ? (fr ? "•••• (définie) — remplacer" : "•••• (set) — replace") : k.env}
                  value={drafts[k.env] || ""}
                  onChange={(e) => setDrafts((d) => ({ ...d, [k.env]: e.target.value }))}
                  onKeyDown={(e) => e.key === "Enter" && save(k.env)}
                />
                <button className="fwin-btn" disabled={!drafts[k.env] || saving === k.env} onClick={() => save(k.env)}>
                  {saving === k.env ? "…" : fr ? "OK" : "OK"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </FloatingWindow>
  );
}
