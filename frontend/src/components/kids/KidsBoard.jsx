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
export default function KidsBoard({ fen, flip = false, marks = {}, stars = [], picked = null, slides = [], effects = {}, onTap }) {
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
          {row === 7 && <span className="co f">{FILES[file]}</span>}
          {col === 0 && <span className="co r">{rank}</span>}
        </button>,
      );
    }
  }
  const moved = Object.fromEntries(slides.filter(Boolean).map(([from, to]) => [to, from]));
  const beams = effects.beams ? place(effects.beams, flip) : null;
  return (
    <div ref={wrap} className="kids-board-wrap">
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
      </div>
    </div>
  );
}
