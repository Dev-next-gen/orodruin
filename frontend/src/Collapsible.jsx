import { useState } from "react";

export default function Collapsible({ title, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="collap">
      <button className="collap-head" onClick={() => setOpen(!open)}>
        <span className="collap-arrow">{open ? "▾" : "▸"}</span>
        <span>{title}</span>
      </button>
      {open && <div className="collap-body">{children}</div>}
    </div>
  );
}
