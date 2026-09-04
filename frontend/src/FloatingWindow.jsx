import { useRef, useState } from "react";

// Reusable draggable + resizable floating panel (Gotham styling via .fwin classes).
export default function FloatingWindow({ title, onClose, children, initial = {}, className = "" }) {
  const [pos, setPos] = useState({ x: initial.x ?? 120, y: initial.y ?? 90 });
  const [size, setSize] = useState({ w: initial.w ?? 320, h: initial.h ?? 300 });
  const drag = useRef(null);
  const rez = useRef(null);

  function onDown(e) {
    if (e.target.closest(".fwin-btn")) return;
    drag.current = { dx: e.clientX - pos.x, dy: e.clientY - pos.y };
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
  function onRDown(e) {
    e.stopPropagation();
    rez.current = { x: e.clientX, y: e.clientY, w: size.w, h: size.h };
    window.addEventListener("mousemove", onRMove);
    window.addEventListener("mouseup", onRUp);
  }
  function onRMove(e) {
    if (!rez.current) return;
    setSize({
      w: Math.max(220, Math.min(760, rez.current.w + (e.clientX - rez.current.x))),
      h: Math.max(160, Math.min(720, rez.current.h + (e.clientY - rez.current.y))),
    });
  }
  function onRUp() {
    rez.current = null;
    window.removeEventListener("mousemove", onRMove);
    window.removeEventListener("mouseup", onRUp);
  }

  return (
    <div className={`fwin ${className}`} style={{ left: pos.x, top: pos.y, width: size.w, height: size.h }}>
      <div className="fwin-head" onMouseDown={onDown}>
        <span className="fwin-title">{title}</span>
        <button className="fwin-btn" onClick={onClose} title="Fermer">×</button>
      </div>
      <div className="fwin-body">{children}</div>
      <div className="fwin-resize" onMouseDown={onRDown} title="Redimensionner">◢</div>
    </div>
  );
}
