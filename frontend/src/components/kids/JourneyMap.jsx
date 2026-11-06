/**
 * The journey map: the eight first-steps classes as islands on a winding path.
 * Done islands are gold with stars, the next one bobs with a flag, the rest are locked.
 */
import { useEffect, useRef } from "react";
import { CLASS_ART, pieceMarkup, starMarkup } from "@/components/kids/KidsArt";
import { burst, centerOf, sfx } from "@/components/kids/kidsFx";

const W = 400;
const H = 620;
const SPOTS = [[0.26, 0.86], [0.66, 0.77], [0.34, 0.66], [0.72, 0.555], [0.3, 0.45], [0.68, 0.345], [0.34, 0.245], [0.62, 0.12]];
const TREES = [[40, 520], [360, 600], [372, 440], [28, 330], [380, 230], [30, 140], [200, 560], [210, 300], [120, 60], [300, 40]];

function curve(pts, upto) {
  let d = `M${pts[0][0]} ${pts[0][1]}`;
  for (let i = 1; i <= upto && i < pts.length; i += 1) {
    const [x0, y0] = pts[i - 1];
    const [x1, y1] = pts[i];
    d += ` C${x0} ${(y0 + y1) / 2 + 10}, ${x1} ${(y0 + y1) / 2 - 10}, ${x1} ${y1}`;
  }
  return d;
}

function emblem(id, x, y) {
  if (id === "check") {
    return `<g transform="translate(${x + 16} ${y - 30})"><circle r="11" fill="#ff7a59" stroke="#fff" stroke-width="3"/><path d="M0 -5 V5 M-5 0 H5" stroke="#fff" stroke-width="3.5" stroke-linecap="round"/></g>`;
  }
  if (id === "checkmate") {
    return `<g transform="translate(${x + 14} ${y - 34})"><path d="M-9 -8 H9 V-2 C9 6 4 9 0 9 C-4 9 -9 6 -9 -2 Z" fill="#ffc23d" stroke="#1f2a44" stroke-width="2.5"/><path d="M-4 9 H4 L5 14 H-5 Z" fill="#ffc23d" stroke="#1f2a44" stroke-width="2.5" stroke-linejoin="round"/></g>`;
  }
  return "";
}

export default function JourneyMap({ classes, nextId, celebrate = false, onPlay }) {
  const pts = SPOTS.map(([x, y]) => [x * W, y * H]);
  const doneCount = classes.filter((c) => c.passed || c.skipped).length;
  const ref = useRef(null);

  useEffect(() => {
    if (!celebrate || !ref.current) return undefined;
    const t = setTimeout(() => {
      sfx.fanfare();
      const node = ref.current && ref.current.querySelector(".node.current .ring");
      if (node) { const [x, y] = centerOf(node); burst(x, y, 30); }
    }, 900);
    return () => clearTimeout(t);
  }, [celebrate]);

  const nodes = classes.map((c, i) => {
    const [x, y] = pts[i];
    const state = c.passed || c.skipped ? "done" : c.id === nextId ? "current" : "locked";
    const ring = state === "done" ? "#ffc23d" : state === "current" ? "#ff7a59" : "#c9d3cf";
    const fill = state === "locked" ? "#e7ece9" : "#fffaf0";
    const art = CLASS_ART[c.id] || CLASS_ART.rook;
    const inner = `
      <ellipse cx="${x}" cy="${y + 30}" rx="40" ry="11" fill="rgba(31,42,68,.16)"/>
      <g class="bob">
        <g class="ring"><circle cx="${x}" cy="${y}" r="36" fill="${ring}"/><circle cx="${x}" cy="${y - 3}" r="30" fill="${fill}"/>
          <circle cx="${x}" cy="${y}" r="36" fill="none" stroke="#fff" stroke-width="3" opacity=".7"/></g>
        <g transform="translate(${x - 24} ${y - 30}) scale(.48)" opacity="${state === "locked" ? 0.35 : 1}">${pieceMarkup(art.piece)}</g>
        ${state === "locked" ? "" : emblem(c.id, x, y)}
        ${state === "locked" ? `<g><rect x="${x + 12}" y="${y + 8}" width="22" height="18" rx="5" fill="#8a95a8" stroke="#55607a" stroke-width="2.5"/><path d="M${x + 16} ${y + 8} v-5 a7 7 0 0 1 14 0 v5" fill="none" stroke="#55607a" stroke-width="3"/></g>` : ""}
        ${state === "done" ? [0, 1, 2].map((k) => `<g transform="translate(${x - 30 + k * 20} ${y + 24}) scale(.2)">${starMarkup()}</g>`).join("") : ""}
        ${state === "current" ? `<path d="M${x + 24} ${y - 60} v40" stroke="#5e3b20" stroke-width="4" stroke-linecap="round"/><path class="flag" d="M${x + 26} ${y - 60} h26 l-7 8 l7 8 h-26 z" fill="#ff7a59"/>` : ""}
      </g>
      <text x="${x}" y="${y + 58}" text-anchor="middle" font-family="Fredoka, sans-serif" font-weight="600" font-size="16" fill="#1f2a44" stroke="#fffaf0" stroke-width="5" paint-order="stroke">${c.title}</text>`;
    const label = `${c.title}: ${state === "done" ? (c.skipped ? "you know this" : "finished") : state === "current" ? "play now" : "locked"}`;
    return (
      <g key={c.id} className={`node ${state}`} data-class={c.id} tabIndex={state === "current" ? 0 : -1} role="button" aria-label={label}
        onClick={() => { if (state === "current") onPlay(); else if (state === "locked") sfx.wrong(); }}
        onKeyDown={(e) => { if (state === "current" && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onPlay(); } }}
        dangerouslySetInnerHTML={{ __html: inner }} />
    );
  });

  return (
    <div className="kids-map" ref={ref}>
      <svg className="map" viewBox={`0 0 ${W} ${H}`} aria-label="Your journey through eight classes">
        <path d={`M0 ${H * 0.18} Q ${W * 0.3} ${H * 0.12} ${W * 0.55} ${H * 0.2} T ${W} ${H * 0.16} V0 H0 Z`} fill="#a9dff0" opacity=".7" />
        {TREES.map(([x, y], k) => (
          <g key={`t${k}`} transform={`translate(${x} ${y})`}>
            <rect x="-3" y="4" width="6" height="12" rx="2" fill="#8a5a33" />
            <circle r={12 + (k % 3) * 3} fill={k % 2 ? "#4fa863" : "#5fbf6e"} />
            <circle cx="-4" cy="-5" r="5" fill="#8fd88a" opacity=".7" />
          </g>
        ))}
        <path d={curve(pts, 7)} fill="none" stroke="#fffaf0" strokeWidth="20" strokeLinecap="round" opacity=".85" />
        <path d={curve(pts, 7)} fill="none" stroke="#e8d7b5" strokeWidth="20" strokeLinecap="round" strokeDasharray="2 22" opacity=".9" />
        {doneCount > 0 && (
          <path d={curve(pts, Math.min(doneCount, 7))} pathLength="1" className={`trail ${celebrate ? "draw" : ""}`}
            fill="none" stroke="#ffc23d" strokeWidth="8" strokeLinecap="round" />
        )}
        {nodes}
      </svg>
      <h1>Your journey</h1>
    </div>
  );
}
