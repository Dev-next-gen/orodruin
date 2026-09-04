import { useEffect, useRef, useState } from "react";

// Actor co-occurrence graph: nodes = actors, edges link actors appearing together
// in events. Size = connections, edge width = frequency, colour = country.
// Zoom (wheel), pan (drag), click a node for details. Force-directed, no deps.
export default function GraphView({ query, version, onCount, lang = "fr", onActorFilter }) {
  const canvasRef = useRef(null);
  const stateRef = useRef({ nodes: [], edges: [], adj: [], raf: 0, runId: 0, hover: -1 });
  const viewRef = useRef({ scale: 1, ox: 0, oy: 0 });
  const dragRef = useRef(null);
  const [empty, setEmpty] = useState(false);
  const [legend, setLegend] = useState([]);
  const [tip, setTip] = useState(null);
  const [sel, setSel] = useState(null);
  const fr = lang === "fr";

  useEffect(() => {
    load();
    const onResize = () => { sizeCanvas(); render(); };
    window.addEventListener("resize", onResize);
    return () => {
      cancelAnimationFrame(stateRef.current.raf);
      stateRef.current.runId++;
      window.removeEventListener("resize", onResize);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [version]);

  function sizeCanvas() {
    const c = canvasRef.current;
    if (!c) return [0, 0];
    const W = (c.width = c.offsetWidth || c.parentElement?.offsetWidth || 0);
    const H = (c.height = c.offsetHeight || c.parentElement?.offsetHeight || 0);
    return [W, H];
  }

  async function load() {
    const params = new URLSearchParams();
    const q = new URLSearchParams(query);
    if (q.get("country")) params.set("country", q.get("country"));
    params.set("limit", "180");
    let data;
    try { data = await fetch(`/api/graph?${params}`).then((r) => r.json()); }
    catch { setEmpty(true); return; }
    const nodesIn = data.nodes || [];
    const edgesIn = data.edges || data.links || [];
    onCount?.(nodesIn.length);
    setEmpty(nodesIn.length === 0);
    setSel(null);
    viewRef.current = { scale: 1, ox: 0, oy: 0 };
    const c0 = canvasRef.current;
    if (!nodesIn.length) { if (c0) c0.getContext("2d").clearRect(0, 0, c0.width, c0.height); setLegend([]); return; }

    let [W, H] = sizeCanvas();
    if (!W || !H) { W = 800; H = 600; }

    const idx = new Map();
    const nodes = nodesIn.map((n, i) => {
      idx.set(n.id, i);
      const ang = (i / nodesIn.length) * Math.PI * 2;
      return { ...n, x: W / 2 + Math.cos(ang) * 220, y: H / 2 + Math.sin(ang) * 180, vx: 0, vy: 0, deg: 0, nb: [] };
    });
    const adj = nodes.map(() => new Set());
    const edges = edgesIn
      .filter((e) => idx.has(e.source) && idx.has(e.target))
      .map((e) => {
        const s = idx.get(e.source), t = idx.get(e.target);
        nodes[s].deg += e.weight; nodes[t].deg += e.weight;
        adj[s].add(t); adj[t].add(s);
        nodes[s].nb.push(nodes[t].name); nodes[t].nb.push(nodes[s].name);
        return { s, t, w: e.weight };
      });

    const cc = {};
    for (const n of nodes) { const k = n.country || "?"; cc[k] = (cc[k] || 0) + 1; }
    setLegend(Object.entries(cc).sort((a, b) => b[1] - a[1]).slice(0, 7)
      .map(([code, count]) => ({ code, count, color: colorFor(code === "?" ? "" : code) })));

    cancelAnimationFrame(stateRef.current.raf);
    const runId = stateRef.current.runId + 1;
    stateRef.current = { nodes, edges, adj, raf: 0, runId, hover: -1 };
    step(0, runId);
  }

  function step(tick, runId) {
    const st = stateRef.current;
    if (runId !== st.runId) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const W = canvas.width || 800, H = canvas.height || 600;
    const { nodes, edges } = st;
    const REPULSE = 2600, SPRING = 0.02, REST = 62, CENTER = 0.02, DAMP = 0.82, MAXV = 22, M = 26;
    for (let i = 0; i < nodes.length; i++) {
      const a = nodes[i];
      for (let j = i + 1; j < nodes.length; j++) {
        const b = nodes[j];
        let dx = a.x - b.x, dy = a.y - b.y, d2 = dx * dx + dy * dy;
        if (d2 < 1) { dx = Math.random() - 0.5; dy = Math.random() - 0.5; d2 = 1; }
        const d = Math.sqrt(d2), f = REPULSE / d2;
        a.vx += (dx / d) * f; a.vy += (dy / d) * f; b.vx -= (dx / d) * f; b.vy -= (dy / d) * f;
      }
    }
    for (const e of edges) {
      const a = nodes[e.s], b = nodes[e.t];
      const dx = b.x - a.x, dy = b.y - a.y, d = Math.sqrt(dx * dx + dy * dy) || 1;
      const f = (d - REST) * SPRING * Math.min(1 + e.w * 0.15, 3);
      a.vx += (dx / d) * f; a.vy += (dy / d) * f; b.vx -= (dx / d) * f; b.vy -= (dy / d) * f;
    }
    let energy = 0;
    for (const n of nodes) {
      n.vx += (W / 2 - n.x) * CENTER; n.vy += (H / 2 - n.y) * CENTER;
      n.vx = Math.max(-MAXV, Math.min(MAXV, n.vx * DAMP));
      n.vy = Math.max(-MAXV, Math.min(MAXV, n.vy * DAMP));
      n.x = Math.max(M, Math.min(W - M, n.x + n.vx));
      n.y = Math.max(M, Math.min(H - M, n.y + n.vy));
      energy += n.vx * n.vx + n.vy * n.vy;
    }
    render(tick);
    if (tick < 500 && energy / nodes.length > 0.05) st.raf = requestAnimationFrame(() => step(tick + 1, runId));
  }

  function radius(n) { return Math.min(4 + Math.sqrt(n.deg) * 1.7, 20); }
  function toWorld(mx, my) { const v = viewRef.current; return [(mx - v.ox) / v.scale, (my - v.oy) / v.scale]; }
  function pick(mx, my) {
    const [wx, wy] = toWorld(mx, my);
    const { nodes } = stateRef.current;
    let best = -1, bestD = 1e9;
    for (let i = 0; i < nodes.length; i++) {
      const n = nodes[i], dx = n.x - wx, dy = n.y - wy, d = dx * dx + dy * dy, r = radius(n) + 5;
      if (d < r * r && d < bestD) { best = i; bestD = d; }
    }
    return best;
  }

  function render(tick = 999) {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const W = canvas.width, H = canvas.height, v = viewRef.current;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, W, H);
    ctx.setTransform(v.scale, 0, 0, v.scale, v.ox, v.oy);
    const { nodes, edges, adj, hover } = stateRef.current;
    const focusIdx = sel ? sel.idx : hover;
    const hi = focusIdx >= 0;
    const near = hi ? adj[focusIdx] : null;
    for (const e of edges) {
      const on = hi && (e.s === focusIdx || e.t === focusIdx);
      ctx.strokeStyle = hi ? (on ? "rgba(87,199,232,0.6)" : "rgba(120,140,160,0.04)") : "rgba(63,167,200,0.16)";
      ctx.lineWidth = (on ? Math.min(1 + e.w * 0.4, 4) : Math.min(0.4 + e.w * 0.22, 3)) / v.scale;
      const a = nodes[e.s], b = nodes[e.t];
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
    }
    for (let i = 0; i < nodes.length; i++) {
      const n = nodes[i], r = radius(n);
      const focus = !hi || i === focusIdx || near.has(i);
      ctx.globalAlpha = focus ? 1 : 0.18;
      ctx.beginPath(); ctx.fillStyle = colorFor(n.country); ctx.arc(n.x, n.y, r, 0, Math.PI * 2); ctx.fill();
      if (i === focusIdx) { ctx.lineWidth = 2.5 / v.scale; ctx.strokeStyle = "#e9eff6"; ctx.stroke(); }
      if ((r > 9 && !hi) || (hi && focus) || (!hi && tick > 300 && r > 7)) {
        ctx.globalAlpha = focus ? 0.95 : 0.25;
        ctx.fillStyle = "#c4cdd8"; ctx.font = `${11 / v.scale}px system-ui, sans-serif`;
        ctx.fillText((n.name || "").slice(0, 24), n.x + r + 3, n.y + 3.5);
      }
    }
    ctx.globalAlpha = 1;
  }

  function onMove(e) {
    const mx = e.nativeEvent.offsetX, my = e.nativeEvent.offsetY;
    const d = dragRef.current;
    if (d) {
      d.moved += Math.abs(e.movementX) + Math.abs(e.movementY);
      if (!d.node || d.moved > 4) {
        const v = viewRef.current; v.ox = d.ox + (mx - d.mx); v.oy = d.oy + (my - d.my);
        setTip(null); render();
      }
      return;
    }
    const best = pick(mx, my);
    if (best !== stateRef.current.hover) {
      stateRef.current.hover = best;
      if (best >= 0) { const n = stateRef.current.nodes[best]; setTip({ x: mx, y: my, name: n.name, country: n.country, deg: stateRef.current.adj[best].size }); }
      else setTip(null);
      cancelAnimationFrame(stateRef.current.raf);
      render();
    }
  }
  function onDown(e) {
    const mx = e.nativeEvent.offsetX, my = e.nativeEvent.offsetY;
    const v = viewRef.current;
    dragRef.current = { mx, my, ox: v.ox, oy: v.oy, node: pick(mx, my) >= 0 ? pick(mx, my) : null, moved: 0 };
  }
  function onUp() {
    const d = dragRef.current; dragRef.current = null;
    if (d && d.node != null && d.moved < 5) {
      const n = stateRef.current.nodes[d.node];
      const nb = [...new Set(n.nb)].slice(0, 12);
      setSel({ idx: d.node, name: n.name, country: n.country, deg: stateRef.current.adj[d.node].size, neighbors: nb });
      render();
    }
  }
  function onLeave() { dragRef.current = null; if (stateRef.current.hover !== -1) { stateRef.current.hover = -1; setTip(null); render(); } }
  function onWheel(e) {
    const v = viewRef.current, mx = e.nativeEvent.offsetX, my = e.nativeEvent.offsetY;
    const [wx, wy] = toWorld(mx, my);
    const ns = Math.max(0.35, Math.min(6, v.scale * (e.deltaY < 0 ? 1.15 : 1 / 1.15)));
    v.scale = ns; v.ox = mx - wx * ns; v.oy = my - wy * ns;
    setTip(null); render();
  }
  function zoomBtn(f) {
    const c = canvasRef.current, v = viewRef.current;
    const mx = (c?.width || 800) / 2, my = (c?.height || 600) / 2;
    const [wx, wy] = toWorld(mx, my);
    const ns = Math.max(0.35, Math.min(6, v.scale * f));
    v.scale = ns; v.ox = mx - wx * ns; v.oy = my - wy * ns; render();
  }

  return (
    <div style={{ position: "absolute", inset: 0, background: "#080b10" }}>
      <canvas ref={canvasRef} onMouseMove={onMove} onMouseDown={onDown} onMouseUp={onUp} onMouseLeave={onLeave} onWheel={onWheel}
        style={{ width: "100%", height: "100%", display: "block", cursor: dragRef.current ? "grabbing" : (tip ? "pointer" : "grab") }} />

      {!empty && (
        <div className="graph-legend">
          <div className="graph-legend-title">{fr ? "Graphe de co-occurrence d'acteurs" : "Actor co-occurrence graph"}</div>
          <div className="graph-legend-desc">
            {fr ? "Deux acteurs sont reliés s'ils apparaissent ensemble dans des événements. Taille = connexions · épaisseur = fréquence · couleur = pays. Molette : zoom · glisser : déplacer · clic : détails."
                : "Two actors are linked when they co-occur in events. Size = connections · width = frequency · colour = country. Wheel: zoom · drag: pan · click: details."}
          </div>
          {legend.length > 0 && (
            <div className="graph-legend-cc">
              {legend.map((l) => (<span className="graph-cc" key={l.code}><span className="graph-sw" style={{ background: l.color }} />{l.code} <em>{l.count}</em></span>))}
            </div>
          )}
        </div>
      )}

      <div className="graph-zoom">
        <button onClick={() => zoomBtn(1.3)}>+</button>
        <button onClick={() => zoomBtn(1 / 1.3)}>−</button>
        <button onClick={() => { viewRef.current = { scale: 1, ox: 0, oy: 0 }; render(); }} title="Reset">⌂</button>
      </div>

      {tip && !sel && (
        <div className="graph-tip" style={{ left: tip.x + 14, top: tip.y + 14 }}>
          <div className="graph-tip-name">{tip.name}</div>
          <div className="graph-tip-meta">{tip.country || "?"} · {tip.deg} {fr ? "connexions" : "connections"}</div>
        </div>
      )}

      {sel && (
        <div className="graph-panel">
          <div className="graph-panel-head">
            <span className="graph-panel-name">{sel.name}</span>
            <button className="graph-panel-x" onClick={() => { setSel(null); render(); }}>×</button>
          </div>
          <div className="graph-panel-meta">{sel.country || "?"} · {sel.deg} {fr ? "connexions" : "connections"}</div>
          {onActorFilter && (
            <button className="graph-panel-btn" onClick={() => onActorFilter(sel.name)}>
              {fr ? "Voir ses événements sur la carte" : "See its events on the map"}
            </button>
          )}
          <div className="graph-panel-sub">{fr ? "Acteurs liés" : "Linked actors"}</div>
          <div className="graph-panel-list">
            {sel.neighbors.map((nm, i) => <div key={i} className="graph-panel-item">{nm}</div>)}
          </div>
        </div>
      )}

      {empty && (
        <div style={{ position: "absolute", top: 20, left: 20, color: "#61707f" }}>
          {fr ? "Aucun acteur lié — ingère plus d'événements ou élargis les filtres." : "No linked actors yet."}
        </div>
      )}
    </div>
  );
}

function colorFor(country) {
  if (!country) return "#8b949e";
  let h = 0;
  for (const c of country) h = (h * 31 + c.charCodeAt(0)) % 360;
  return `hsl(${h}, 62%, 60%)`;
}
