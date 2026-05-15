/**
 * ClickableCaption — renders a caption with embedded chess moves as
 * clickable buttons. Validates each candidate SAN against the move's
 * position (fen_before) using chess.js; only legal moves become
 * clickable. Click fires onMoveSelect(san, fromSquare, toSquare) so
 * the parent can draw an arrow on the board.
 *
 * Differs from ClickableLine in two ways:
 *   1. Doesn't require "the line goes:" prefix — moves anywhere are
 *      clickable (V5 LLM captions name moves anywhere in the sentence).
 *   2. Validates each candidate against the actual position, so we
 *      don't make a literal "d5" clickable when it's not a legal move
 *      from this FEN (e.g., a square reference vs a pawn push).
 */

import React, { useMemo } from "react";
import { Chess } from "chess.js";

// Same SAN pattern ClickableLine uses; matches piece moves, captures,
// promotions, castling, and check/mate markers.
const SAN_PATTERN = /\b([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]*|O-O-O|O-O)\b/g;

/**
 * Parse caption text into alternating text/move parts, validating each
 * candidate SAN against `fen` (the position the move would be played from).
 *
 * Returns array of:
 *   { type: "text", content }
 *   { type: "move", content, from, to }
 */
export function parseClickableCaption(text, fen) {
  if (!text) return [];
  if (!fen) {
    // No position to validate against — render as plain text.
    return [{ type: "text", content: text }];
  }

  // Single Chess instance reused per parse. We do `.move()` to test
  // and then `.undo()` so the instance stays at the original FEN.
  let chess;
  try {
    chess = new Chess(fen);
  } catch {
    return [{ type: "text", content: text }];
  }

  const parts = [];
  let lastIndex = 0;
  let match;

  // Reset the regex (it's a global, lastIndex carries over).
  SAN_PATTERN.lastIndex = 0;

  while ((match = SAN_PATTERN.exec(text)) !== null) {
    // Text before this candidate.
    if (match.index > lastIndex) {
      parts.push({ type: "text", content: text.slice(lastIndex, match.index) });
    }

    const candidate = match[0];
    // Try to parse it as a legal move in the position.
    // chess.js v0.x: move() returns null on illegal; v1.x throws.
    let parsed = null;
    try {
      parsed = chess.move(candidate, { sloppy: true });
    } catch {
      parsed = null;
    }
    if (parsed) {
      parts.push({
        type: "move",
        content: candidate,
        from: parsed.from,
        to: parsed.to,
      });
      chess.undo();  // restore position so the next test sees the same FEN
    } else {
      // Not a legal move from this position — render as plain text.
      parts.push({ type: "text", content: candidate });
    }

    lastIndex = match.index + candidate.length;
  }

  if (lastIndex < text.length) {
    parts.push({ type: "text", content: text.slice(lastIndex) });
  }
  return parts;
}

/**
 * ClickableCaption component.
 *
 * Props:
 *   text          : caption string
 *   fen           : position FEN the moves would be played from
 *   onMoveSelect  : (san, fromSquare, toSquare) => void
 *   className     : optional wrapper className
 *
 * Renders the text inline; legal-move SANs become buttons. Click
 * fires onMoveSelect so the parent can draw an arrow on the board.
 */
export default function ClickableCaption({
  text,
  fen,
  onMoveSelect,
  className = "",
}) {
  const parts = useMemo(() => parseClickableCaption(text, fen), [text, fen]);

  return (
    <span className={className}>
      {parts.map((p, i) => {
        if (p.type === "move") {
          return (
            <button
              key={i}
              onClick={() => onMoveSelect && onMoveSelect(p.content, p.from, p.to)}
              className="font-mono font-semibold text-amber-500 hover:text-amber-400 hover:underline cursor-pointer transition-colors mx-0.5"
              title={`Click to highlight ${p.content} on the board (${p.from}→${p.to})`}
            >
              {p.content}
            </button>
          );
        }
        return <span key={i}>{p.content}</span>;
      })}
    </span>
  );
}
