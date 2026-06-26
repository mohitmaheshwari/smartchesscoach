/**
 * BoardCoordinates — name EVERY square (a1, a2, …, h8) so the reader
 * can match an annotation ("Nxc5") to the board square at a glance.
 *
 * Iteration 4 (Mohit 2026-06-03): per-square full labels, not just
 * corners or edges. Labels sit in the top-left corner of each square in
 * a small font so the piece (centered in the square) doesn't fight them.
 *
 * Iteration 5 (Mohit 2026-06-27): SIZE-GATED. On short/small boards (PWC,
 * review, the dashboard preview) 64 labels look cluttered and shitty, so
 * we only render them when the board is rendered big enough that the
 * squares are large. The overlay measures its own width (it's inset-0 over
 * the board) and shows labels only at/above `minWidth` px. Below that the
 * board stays clean. Tune `minWidth` per call if a specific board wants a
 * different cutoff.
 *
 * Orientation-aware — "c5" always names the actual c5 square; the label
 * just renders in the flipped visual position when the board is shown
 * from black's perspective.
 */
import { useLayoutEffect, useRef, useState } from "react";

const LIGHT_SQUARE_TEXT = "#000000";  // black on cream
const DARK_SQUARE_TEXT = "#ffffff";   // white on tan
const FILES = "abcdefgh";

// Below this rendered board width (px), per-square labels clutter the board —
// so coordinates show only on bigger boards. ~52px/square at the cutoff.
const MIN_WIDTH_PX = 420;

const BoardCoordinates = ({ orientation = "white", minWidth = MIN_WIDTH_PX }) => {
  const ref = useRef(null);
  const [bigEnough, setBigEnough] = useState(false);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => setBigEnough(el.offsetWidth >= minWidth);
    measure();
    let ro;
    if (typeof ResizeObserver !== "undefined") {
      ro = new ResizeObserver(measure);
      ro.observe(el);
    }
    return () => ro && ro.disconnect();
  }, [minWidth]);

  const squares = [];
  for (let rank = 1; rank <= 8; rank++) {
    for (let fileIdx = 0; fileIdx < 8; fileIdx++) {
      const file = FILES[fileIdx];
      const label = `${file}${rank}`;
      // a1 is a dark square. (fileIdx + rank) odd → dark, even → light.
      const isDark = (fileIdx + rank) % 2 === 1;
      // Visual screen position (0..7 in each axis).
      const visualX = orientation === "white" ? fileIdx : 7 - fileIdx;
      const visualY = orientation === "white" ? 8 - rank : rank - 1;
      squares.push({ label, isDark, visualX, visualY });
    }
  }

  return (
    <div
      ref={ref}
      className="pointer-events-none absolute inset-0 z-30 select-none"
      data-testid="board-coordinates"
    >
      {bigEnough &&
        squares.map((sq) => (
          <span
            key={sq.label}
            className="absolute font-semibold"
            style={{
              left: `${sq.visualX * 12.5}%`,
              top: `${sq.visualY * 12.5}%`,
              width: "12.5%",
              paddingLeft: "3px",
              paddingTop: "2px",
              fontSize: "0.6rem",
              lineHeight: 1,
              color: sq.isDark ? DARK_SQUARE_TEXT : LIGHT_SQUARE_TEXT,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {sq.label}
          </span>
        ))}
    </div>
  );
};

export default BoardCoordinates;
