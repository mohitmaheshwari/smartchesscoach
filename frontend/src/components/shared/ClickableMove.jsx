/**
 * ClickableMoves — makes chess move notation in text clickable.
 *
 * When a move like "Ne5" or "Bxd5" is clicked, it shows an arrow
 * on the board from the piece's current square to the destination.
 *
 * Usage:
 *   <ClickableMoves text="Bf4 is fine, but Ne5 is better" fen={currentFen} onShowArrow={setCoachArrows} />
 */

import { Chess } from "chess.js";

// Regex to find chess moves in text (SAN notation)
// Matches: e4, Nf3, Bxd5, O-O, O-O-O, Qxf7+, Rfe1, cxd5, etc.
const MOVE_REGEX = /\b([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|O-O-O|O-O)\b/g;

const ClickableMoves = ({ text, fen, onShowArrow, className = "" }) => {
  if (!text) return null;

  const handleMoveClick = (moveSan) => {
    if (!fen || !onShowArrow) return;

    try {
      const chess = new Chess(fen);
      const move = chess.move(moveSan);
      if (move) {
        // Show arrow from source to destination
        onShowArrow([[move.from, move.to, "blue"]]);
        // Clear arrow after 4 seconds
        setTimeout(() => onShowArrow([]), 4000);
      }
    } catch {
      // Move not legal in this position — try without check/mate symbols
      try {
        const clean = moveSan.replace(/[+#]/g, "");
        const chess2 = new Chess(fen);
        const move2 = chess2.move(clean);
        if (move2) {
          onShowArrow([[move2.from, move2.to, "blue"]]);
          setTimeout(() => onShowArrow([]), 4000);
        }
      } catch {
        // Not a valid move in this position — ignore
      }
    }
  };

  // Split text into parts: regular text and move tokens
  const parts = [];
  let lastIndex = 0;
  let match;

  const regex = new RegExp(MOVE_REGEX.source, "g");
  while ((match = regex.exec(text)) !== null) {
    // Add text before the match
    if (match.index > lastIndex) {
      parts.push({ type: "text", value: text.slice(lastIndex, match.index) });
    }
    // Add the move
    parts.push({ type: "move", value: match[0] });
    lastIndex = regex.lastIndex;
  }
  // Add remaining text
  if (lastIndex < text.length) {
    parts.push({ type: "text", value: text.slice(lastIndex) });
  }

  return (
    <span className={className}>
      {parts.map((part, i) =>
        part.type === "move" ? (
          <span
            key={i}
            onClick={() => handleMoveClick(part.value)}
            className="font-mono font-semibold text-blue-600 cursor-pointer hover:text-blue-800 hover:underline transition-colors"
            title={`Click to see ${part.value} on the board`}
          >
            {part.value}
          </span>
        ) : (
          <span key={i}>{part.value}</span>
        )
      )}
    </span>
  );
};

export default ClickableMoves;
