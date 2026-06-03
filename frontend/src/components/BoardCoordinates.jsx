/**
 * BoardCoordinates — corner-square labels (a1, h1, a8, h8) overlay.
 *
 * Iteration 3 (Mohit 2026-06-03): replace the per-edge a–h / 1–8 labels
 * with FULL coordinate labels on just the four corner squares in a
 * larger font. Reader gets an instant orientation anchor (a1 is here,
 * h8 is there) without 16 small labels littering the edges.
 *
 * Each label sits in the OUTERMOST corner of its corner square so it
 * doesn't fight the rook that's almost always on those squares. Color
 * uses the opposite-square trick: cream text on dark squares, tan text
 * on light squares — same brown-theme contrast Lichess uses.
 *
 * Orientation-aware: the label always names the actual chess square, so
 * when the board is flipped to black-on-bottom, "a1" still says "a1"
 * — it just renders in the top-right corner of the visual board.
 */

const LIGHT_SQUARE = "#f0d9b5"; // cream — brown theme light
const DARK_SQUARE = "#b58863";  // tan — brown theme dark

const CORNERS = [
  { file: "a", rank: 1, label: "a1", isDark: true },   // queenside-back rank 1
  { file: "h", rank: 1, label: "h1", isDark: false },  // kingside-back rank 1
  { file: "a", rank: 8, label: "a8", isDark: false },  // black queenside back
  { file: "h", rank: 8, label: "h8", isDark: true },   // black kingside back
];

const BoardCoordinates = ({ orientation = "white" }) => {
  return (
    <div
      className="pointer-events-none absolute inset-0 z-30 select-none"
      data-testid="board-coordinates"
    >
      {CORNERS.map((corner) => {
        const fileIdx = corner.file.charCodeAt(0) - "a".charCodeAt(0); // 0 or 7
        const rankIdx = corner.rank - 1; // 0 or 7
        // Visual position of the square on screen (0..7 in each axis).
        const visualX =
          orientation === "white" ? fileIdx : 7 - fileIdx;
        const visualY =
          orientation === "white" ? 7 - rankIdx : rankIdx;
        // Anchor label to the OUTERMOST corner of the square so it sits
        // furthest from the rook that lives on that square.
        const anchorLeft = visualX === 0;
        const anchorTop = visualY === 0;
        const textColor = corner.isDark ? LIGHT_SQUARE : DARK_SQUARE;
        return (
          <div
            key={corner.label}
            className="absolute flex font-bold"
            style={{
              left: `${visualX * 12.5}%`,
              top: `${visualY * 12.5}%`,
              width: "12.5%",
              height: "12.5%",
              alignItems: anchorTop ? "flex-start" : "flex-end",
              justifyContent: anchorLeft ? "flex-start" : "flex-end",
              padding: "4px",
              fontSize: "0.95rem",
              lineHeight: 1,
              color: textColor,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {corner.label}
          </div>
        );
      })}
    </div>
  );
};

export default BoardCoordinates;
