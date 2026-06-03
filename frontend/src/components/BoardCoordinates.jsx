/**
 * BoardCoordinates — name EVERY square (a1, a2, …, h8) so the reader
 * can match an annotation ("Nxc5") to the board square at a glance.
 *
 * Iteration 4 (Mohit 2026-06-03): per-square full labels, not just
 * corners or edges. Labels sit in the top-left corner of each square in
 * a small font so the piece (centered in the square) doesn't fight them.
 * Color uses the opposite-square trick (cream text on dark squares, tan
 * text on light squares) so contrast is consistent across the board.
 *
 * Orientation-aware — "c5" always names the actual c5 square; the label
 * just renders in the flipped visual position when the board is shown
 * from black's perspective.
 */

const LIGHT_SQUARE = "#f0d9b5"; // cream — brown theme light
const DARK_SQUARE = "#b58863";  // tan  — brown theme dark
const FILES = "abcdefgh";

const BoardCoordinates = ({ orientation = "white" }) => {
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
      className="pointer-events-none absolute inset-0 z-30 select-none"
      data-testid="board-coordinates"
    >
      {squares.map((sq) => (
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
            color: sq.isDark ? LIGHT_SQUARE : DARK_SQUARE,
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
