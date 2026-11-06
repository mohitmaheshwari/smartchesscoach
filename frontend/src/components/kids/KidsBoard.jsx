/**
 * The kids board: a wooden board, pieces with faces that slide and hop, gems
 * on squares found, stars to collect. It only shows; the page decides what a
 * tap means (and the server decides whether it was right).
 */
import { useEffect, useRef } from "react";
import { Piece, Star } from "@/components/kids/KidsArt";

const FILES = "abcdefgh";

export function parseFen(fen) {
  const pieces = {};
  const rows = String(fen || "").split(" ")[0].split("/");
  rows.forEach((row, i) => {
    let file = 0;
    for (const ch of row) {
      if (/\d/.test(ch)) { file += Number(ch); continue; }
      pieces[`${FILES[file]}${8 - i}`] = { type: ch.toLowerCase(), white: ch === ch.toUpperCase() };
      file += 1;
    }
  });
  return pieces;
}

/** Moves between two positions, by colour: [[from, to], ...]. Used to slide pieces into place. */
export function diffMoves(before, after) {
  const a = parseFen(before);
  const b = parseFen(after);
  const out = [];
  for (const white of [true, false]) {
    const gone = Object.keys(a).filter((s) => a[s].white === white && !(b[s] && b[s].white === white && b[s].type === a[s].type));
    const came = Object.keys(b).filter((s) => b[s].white === white && !(a[s] && a[s].white === white && a[s].type === b[s].type));
    if (gone.length === 1 && came.length === 1) out.push([gone[0], came[0]]);
  }
  return out;
}

const ARROW = { red: "#e2543a", green: "#2f9e6d", blue: "#3f5f8f", gold: "#e69a12" };

function Arrows({ arrows, circles, flip }) {
  if (!arrows.length && !circles.length) return null;
  const c = (sq) => { const p = place(sq, flip); return [p.col * 100 + 50, p.row * 100 + 50]; };
  return (
    <svg className="kids-arrows" viewBox="0 0 800 800" aria-hidden="true">
      <defs>
        {Object.entries(ARROW).map(([name, colour]) => (
          <marker key={name} id={`kids-head-${name}`} viewBox="0 0 10 10" refX="5" refY="5" markerWidth="3.2" markerHeight="3.2" orient="auto-start-reverse">
            <path d="M0 0 L10 5 L0 10 Z" fill={colour} />
          </marker>
        ))}
      </defs>
      {circles.map(([sq, colour], i) => {
        const [x, y] = c(sq);
        return <circle key={`c${i}`} cx={x} cy={y} r="42" fill="none" stroke={ARROW[colour] || ARROW.red} strokeWidth="9" opacity=".9" />;
      })}
      {arrows.map(([from, to, colour], i) => {
        const [x0, y0] = c(from);
        const [x1, y1] = c(to);
        const len = Math.hypot(x1 - x0, y1 - y0) || 1;
        const x2 = x1 - ((x1 - x0) / len) * 26;
        const y2 = y1 - ((y1 - y0) / len) * 26;
        const name = ARROW[colour] ? colour : "red";
        return <line key={`a${i}`} x1={x0} y1={y0} x2={x2} y2={y2} stroke={ARROW[name]} strokeWidth="16" strokeLinecap="round"
          opacity=".88" markerEnd={`url(#kids-head-${name})`} />;
      })}
    </svg>
  );
}

function place(sq, flip) {
  const f = FILES.indexOf(sq[0]);
  const r = Number(sq[1]) - 1;
  const col = flip ? 7 - f : f;
  const row = flip ? r : 7 - r;
  return { left: `${col * 12.5}%`, top: `${row * 12.5}%`, col, row };
}

/**
 * marks: { square: "found" | "show" | "marked" | "last" }
 * slides: [[from, to], ...] the moves just made, animated into place
 * effects: { hop, wiggle, flash, beams, shake, seq } one-shot effects; seq replays them
 */
export default function KidsBoard({ fen, flip = false, marks = {}, stars = [], picked = null, slides = [], effects = {}, onTap,
  arrows = [], circles = [], coordinates = true }) {
  const pieces = parseFen(fen);
  const seq = effects.seq || 0;
  const wrap = useRef(null);
  useEffect(() => {
    if (!effects.shake || !wrap.current || !wrap.current.animate) return;
    wrap.current.animate([
      { transform: "translateX(0)" }, { transform: "translateX(-7px) rotate(-.6deg)" }, { transform: "translateX(6px) rotate(.5deg)" },
      { transform: "translateX(-4px)" }, { transform: "translateX(3px)" }, { transform: "translateX(0)" }], { duration: 400 });
  }, [seq, effects.shake]);
  const squares = [];
  for (let row = 0; row < 8; row += 1) {
    for (let col = 0; col < 8; col += 1) {
      const rank = flip ? row + 1 : 8 - row;
      const file = flip ? 7 - col : col;
      const sq = `${FILES[file]}${rank}`;
      const p = pieces[sq];
      const mark = marks[sq];
      const cls = ["kids-sq", (file + rank) % 2 ? "l" : "d"];
      if (mark === "marked" || mark === "last") cls.push(mark);
      if (effects.flash === sq) cls.push("flash");
      const label = `${sq}${p ? ` ${p.white ? "white" : "black"} ${{ k: "king", q: "queen", r: "rook", b: "bishop", n: "knight", p: "pawn" }[p.type]}` : stars.includes(sq) ? " star" : ""}`;
      squares.push(
        <button key={effects.flash === sq ? `${sq}-${seq}` : sq} type="button" className={cls.join(" ")} data-sq={sq} aria-label={label}
          onClick={(e) => onTap && onTap(sq, e.currentTarget)}>
          {(mark === "found" || mark === "show") && <span key={`${sq}-${mark}`} className={`kids-gem ${mark === "show" ? "show" : ""}`} />}
          {coordinates && row === 7 && <span className="co f">{FILES[file]}</span>}
          {coordinates && col === 0 && <span className="co r">{rank}</span>}
        </button>,
      );
    }
  }
  const moved = Object.fromEntries(slides.filter(Boolean).map(([from, to]) => [to, from]));
  const beams = effects.beams ? place(effects.beams, flip) : null;
  return (
    <div ref={wrap} className="kids-board-wrap" data-testid="board" data-fen={fen} data-arrows={JSON.stringify(arrows)}>
      <div className="kids-board">
        {squares}
        {beams && (
          <>
            <div key={`bh-${seq}`} className="kids-beam h" style={{ top: beams.top }} />
            <div key={`bv-${seq}`} className="kids-beam v" style={{ left: beams.left }} />
          </>
        )}
      </div>
      <div className="kids-layer">
        {stars.map((sq) => (
          <div key={`star-${sq}`} className="kids-star-token" data-star={sq} style={place(sq, flip)}><Star /></div>
        ))}
        {Object.entries(pieces).map(([sq, p]) => {
          const at = place(sq, flip);
          const from = moved[sq];
          const style = { left: at.left, top: at.top };
          let cls = "kids-piece";
          if (from) {
            const was = place(from, flip);
            style["--dx"] = `${(was.col - at.col) * 100}%`;
            style["--dy"] = `${(was.row - at.row) * 100}%`;
            cls += " slide";
          }
          if (effects.hop === sq) cls += " hop";
          if (effects.wiggle === sq) cls += " wiggle";
          if (picked === sq) cls += " picked";
          const replay = from || effects.hop === sq || effects.wiggle === sq ? `-${seq}` : "";
          return (
            <div key={`${sq}-${p.type}-${p.white}${replay}`} className={cls} style={style} data-piece={sq}>
              <div className="inner"><Piece type={p.type} white={p.white} /></div>
            </div>
          );
        })}
        <Arrows arrows={arrows} circles={circles} flip={flip} />
      </div>
    </div>
  );
}
