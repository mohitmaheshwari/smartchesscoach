/**
 * BoardCoordinates — file letters (a–h) + rank numbers (1–8) overlay,
 * styled to match Lichess: each label sits in the corner of an edge
 * square and uses the OPPOSITE square's color, so it always contrasts.
 *
 * On a dark tan square → label is cream (light-square color).
 * On a light cream square → label is tan (dark-square color).
 *
 * Built 2026-06-03 after Parth's request and iteration vs Lichess's
 * visual baseline.
 */

// Brown theme palette — must match chessground.brown.css
// (light squares #f0d9b5 cream, dark squares #b58863 tan).
const LIGHT_SQUARE = "#f0d9b5";
const DARK_SQUARE = "#b58863";

const FILES_WHITE = ["a", "b", "c", "d", "e", "f", "g", "h"];
const FILES_BLACK = [...FILES_WHITE].reverse();
const RANKS_WHITE = ["8", "7", "6", "5", "4", "3", "2", "1"]; // top→bottom
const RANKS_BLACK = [...RANKS_WHITE].reverse();

const BoardCoordinates = ({ orientation = "white" }) => {
  const files = orientation === "black" ? FILES_BLACK : FILES_WHITE;
  const ranks = orientation === "black" ? RANKS_BLACK : RANKS_WHITE;

  // Bottom-row square color pattern: position 0 (leftmost) is dark, then
  // alternates. Holds for both orientations because flipping the board
  // also flips the bottom-row file ordering (a1 dark in white-orient →
  // h8 dark in black-orient, same physical square).
  const fileSquareIsDark = (i) => i % 2 === 0;
  // Leftmost-column square color: position 0 (top) is light, alternates.
  const rankSquareIsDark = (i) => i % 2 === 1;

  // Text color is the OPPOSITE square's color — always contrasts cleanly.
  const fileTextColor = (i) => (fileSquareIsDark(i) ? LIGHT_SQUARE : DARK_SQUARE);
  const rankTextColor = (i) => (rankSquareIsDark(i) ? LIGHT_SQUARE : DARK_SQUARE);

  return (
    <div
      className="pointer-events-none absolute inset-0 z-30 select-none"
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
            paddingLeft: "4px",
            paddingBottom: "2px",
            textAlign: "left",
            fontSize: "0.72rem",
            lineHeight: 1,
            color: fileTextColor(i),
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
            paddingLeft: "4px",
            paddingTop: "3px",
            fontSize: "0.72rem",
            lineHeight: 1,
            color: rankTextColor(i),
          }}
        >
          {number}
        </span>
      ))}
    </div>
  );
};

export default BoardCoordinates;
