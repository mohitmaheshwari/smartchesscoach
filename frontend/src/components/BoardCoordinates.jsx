/**
 * BoardCoordinates — file letters (a–h) + rank numbers (1–8) overlay for
 * any chessboard that disables chessground's built-in coordinates.
 *
 * Why this exists: chessground's `coordinates: true` renders labels INSIDE
 * the edge squares, where they overlap pieces with our cburnett piece set
 * (the original "tester reported file letters overlapping pieces" bug
 * referenced in LichessBoard.jsx). This component renders them in the
 * tiny corner gaps where pieces don't sit, with low-contrast styling that
 * doesn't fight the board art.
 *
 * Parth (the reviewer) requested this 2026-06-03 so authored captions can
 * reference squares (e.g. "Bb2 walks into Nb7") and the reader can verify
 * by eye without counting from the corner.
 *
 * Drop into any board wrapper as an absolutely-positioned child. The parent
 * must have `position: relative` and be the same size as the playable area.
 */
const FILES_WHITE = ["a", "b", "c", "d", "e", "f", "g", "h"];
const FILES_BLACK = [...FILES_WHITE].reverse();
const RANKS_WHITE = ["8", "7", "6", "5", "4", "3", "2", "1"]; // top→bottom
const RANKS_BLACK = [...RANKS_WHITE].reverse();

const BoardCoordinates = ({ orientation = "white" }) => {
  const files = orientation === "black" ? FILES_BLACK : FILES_WHITE;
  const ranks = orientation === "black" ? RANKS_BLACK : RANKS_WHITE;

  // Each label sits in the corner of its edge square, where pieces don't
  // render. Pointer-events disabled so it never blocks board interaction.
  return (
    <div
      className="pointer-events-none absolute inset-0 z-10 select-none"
      data-testid="board-coordinates"
    >
      {files.map((letter, i) => (
        <span
          key={`file-${letter}`}
          className="absolute font-semibold tabular-nums"
          style={{
            left: `${i * 12.5}%`,
            bottom: 0,
            width: "12.5%",
            paddingRight: "3px",
            paddingBottom: "1px",
            textAlign: "right",
            fontSize: "0.65rem",
            lineHeight: 1,
            // Bottom-row squares alternate: file a is dark, b light, ...
            // (when white is on bottom). Light squares need dark text and
            // vice versa. The first bottom square is dark on white-orient
            // when i is even — keep a single readable mid-tone instead.
            color: "rgba(255, 255, 255, 0.78)",
            textShadow: "0 1px 1px rgba(0,0,0,0.55)",
          }}
        >
          {letter}
        </span>
      ))}
      {ranks.map((number, i) => (
        <span
          key={`rank-${number}`}
          className="absolute font-semibold tabular-nums"
          style={{
            top: `${i * 12.5}%`,
            left: 0,
            height: "12.5%",
            paddingLeft: "3px",
            paddingTop: "1px",
            fontSize: "0.65rem",
            lineHeight: 1,
            color: "rgba(255, 255, 255, 0.78)",
            textShadow: "0 1px 1px rgba(0,0,0,0.55)",
          }}
        >
          {number}
        </span>
      ))}
    </div>
  );
};

export default BoardCoordinates;
