import { useEffect, useRef, useState } from "react";

const MIN_W = 300, MIN_H = 260, MAX_W = 900, MAX_H = 900;

function mdToHtml(text) {
  const esc = (t) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const inline = (t) =>
    esc(t)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/`(.+?)`/g, "<code>$1</code>");
  const lines = (text || "").split(/\r?\n/);
  let html = "";
  let inList = false;
  const closeList = () => { if (inList) { html += "</ul>"; inList = false; } };
  for (const raw of lines) {
    const line = raw.trimEnd();
    if (!line.trim()) { closeList(); html += "<div class='sp'></div>"; continue; }
    let m;
    if ((m = line.match(/^#{1,6}\s+(.*)/))) { closeList(); html += `<div class="h">${inline(m[1])}</div>`; }
    else if ((m = line.match(/^\s*[-*]\s+(.*)/))) { if (!inList) { html += "<ul>"; inList = true; } html += `<li>${inline(m[1])}</li>`; }
    else if ((m = line.match(/^\s*\d+[.)]\s+(.*)/))) { if (!inList) { html += "<ul>"; inList = true; } html += `<li>${inline(m[1])}</li>`; }
    else { closeList(); html += `<div>${inline(line)}</div>`; }
  }
  closeList();
  return html;
}

export default function ChatBox({ lang, labels, open, setOpen, onActions }) {
  const swipeRef = useRef(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [pos, setPos] = useState({ x: null, y: null });
  const [size, setSize] = useState({ w: 400, h: 460 });
  const drag = useRef(null);
  const rez = useRef(null);
  const bodyRef = useRef(null);

  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
  }, [messages, loading]);

  async function send() {
    const q = input.trim();
    if (!q || loading) return;
    const next = [...messages, { role: "user", content: q }];
    setMessages(next);
    setInput("");
    setLoading(true);
    try {
      const r = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lang, messages: next }),
      }).then((x) => x.json());
      setMessages([...next, { role: "assistant", content: r.reply, tools: r.tools_used }]);
      if (r.actions && r.actions.length && onActions) onActions(r.actions);
    } catch {
      setMessages([...next, { role: "assistant", content: "Erreur de connexion." }]);
    } finally {
      setLoading(false);
    }
  }

  // drag
  function onDown(e) {
    if (e.target.closest(".chat-nodrag")) return;
    const x = pos.x ?? window.innerWidth - size.w - 20;
    const y = pos.y ?? window.innerHeight - size.h - 60;
    drag.current = { dx: e.clientX - x, dy: e.clientY - y };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }
  function onMove(e) {
    if (!drag.current) return;
    setPos({ x: e.clientX - drag.current.dx, y: e.clientY - drag.current.dy });
  }
  function onUp() {
    drag.current = null;
    window.removeEventListener("mousemove", onMove);
    window.removeEventListener("mouseup", onUp);
  }
  // resize
  function onRDown(e) {
    e.stopPropagation();
    rez.current = { x: e.clientX, y: e.clientY, w: size.w, h: size.h };
    window.addEventListener("mousemove", onRMove);
    window.addEventListener("mouseup", onRUp);
  }
  function onRMove(e) {
    if (!rez.current) return;
    setSize({
      w: Math.max(MIN_W, Math.min(MAX_W, rez.current.w + (e.clientX - rez.current.x))),
      h: Math.max(MIN_H, Math.min(MAX_H, rez.current.h + (e.clientY - rez.current.y))),
    });
  }
  function onRUp() {
    rez.current = null;
    window.removeEventListener("mousemove", onRMove);
    window.removeEventListener("mouseup", onRUp);
  }

  if (!open) {
    return (
      <button className="chat-toggle" onClick={() => setOpen(true)}>
        {labels.analyst}
      </button>
    );
  }

  const style = {
    width: size.w,
    height: size.h,
    left: pos.x ?? undefined,
    top: pos.y ?? undefined,
    right: pos.x == null ? 20 : undefined,
    bottom: pos.y == null ? 56 : undefined,
  };

  return (
    <div className="chat-win" style={style}
      onTouchStart={(e) => { swipeRef.current = { x: e.touches[0].clientX, y: e.touches[0].clientY, el: e.currentTarget, drag: false }; }}
      onTouchMove={(e) => {
        const t = swipeRef.current; if (!t) return;
        const dx = e.touches[0].clientX - t.x, dy = e.touches[0].clientY - t.y;
        if (!t.drag && Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 8) { t.drag = true; t.el.style.transition = "none"; }
        if (t.drag && dx > 0) { t.el.style.transform = "translateX(" + dx + "px)"; }
      }}
      onTouchEnd={(e) => {
        const t = swipeRef.current; if (!t) return; swipeRef.current = null;
        t.el.style.transition = ""; t.el.style.transform = "";
        const end = e.changedTouches[0] ? e.changedTouches[0].clientX : t.x;
        if (t.drag && end - t.x > 70) setOpen(false);
      }}>
      <div className="chat-head" onMouseDown={onDown}>
        <span className="chat-head-title">{labels.analyst}</span>
        <div className="chat-nodrag chat-head-btns">
          <button onClick={() => setMessages([])} title={labels.clear}>{labels.clear}</button>
          <button onClick={() => setOpen(false)} title="Fermer">×</button>
        </div>
      </div>
      <div className="chat-body" ref={bodyRef}>
        {messages.length === 0 && <div className="chat-hint">{labels.hint}</div>}
        {messages.map((m, i) => (
          <div key={i} className={`chat-msg ${m.role}`}>
            {m.role === "assistant" && m.tools?.length > 0 && (
              <div className="chat-tools">{m.tools.join(", ")}</div>
            )}
            {m.role === "assistant" ? (
              <div className="chat-text md" dangerouslySetInnerHTML={{ __html: mdToHtml(m.content) }} />
            ) : (
              <div className="chat-text">{m.content}</div>
            )}
          </div>
        ))}
        {loading && <div className="chat-msg assistant"><div className="chat-text chat-loading">{labels.thinking}</div></div>}
      </div>
      <div className="chat-input chat-nodrag">
        <textarea
          value={input}
          placeholder={labels.placeholder}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
          rows={2}
        />
        <button onClick={send} disabled={loading} title="Envoyer">→</button>
      </div>
      <div className="chat-resize chat-nodrag" onMouseDown={onRDown}>◢</div>
    </div>
  );
}
