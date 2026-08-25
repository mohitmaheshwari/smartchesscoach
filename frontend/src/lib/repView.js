/**
 * Pure view logic for a coaching rep.
 *
 * Extracted from RepRunner.jsx so it can be unit-tested: CI runs
 * `src/lib/*.test.js` only and never renders components, so any logic left
 * inside the component ships untested.
 *
 * The one non-obvious rule lives here: `is_safe` asks about a move the player
 * has NOT made yet, so its board shows the position BEFORE the move with the
 * candidate drawn as an arrow. Every other rep type asks about the position
 * AFTER the move, so the move is played first. Getting this backwards shows the
 * player a board that contradicts the question.
 */

import { Chess } from "chess.js";

/** Rep types answered by tapping a square rather than pressing a button. */
export const SQUARE_ANSWER_TYPES = new Set(["who_takes", "find_loose"]);

/** Rep types whose board shows the position before the move is played. */
export const PRE_MOVE_TYPES = new Set(["is_safe"]);

/**
 * @param {object} rep  a rep from the backend generator
 * @returns {{displayFen: string|null, orientation: "white"|"black",
 *            candidateArrow: [string,string]|null}}
 */
export function buildRepView(rep) {
  const empty = { displayFen: null, orientation: "white", candidateArrow: null };
  if (!rep || !rep.fen) return empty;

  let board;
  try {
    board = new Chess(rep.fen);
  } catch {
    return empty;
  }

  // The player is always the side to move in the stored position.
  const orientation = board.turn() === "w" ? "white" : "black";
  const uci = typeof rep.move_uci === "string" ? rep.move_uci : "";
  const from = uci.slice(0, 2);
  const to = uci.slice(2, 4);
  const hasMove = from.length === 2 && to.length === 2;

  if (PRE_MOVE_TYPES.has(rep.rep_type)) {
    return {
      displayFen: rep.fen,
      orientation,
      candidateArrow: hasMove ? [from, to] : null,
    };
  }

  if (hasMove) {
    try {
      board.move({ from, to, promotion: "q" });
    } catch {
      // An unplayable move means the rep is malformed; show the original
      // position rather than a board that silently disagrees with the prompt.
      return { displayFen: rep.fen, orientation, candidateArrow: null };
    }
  }
  return { displayFen: board.fen(), orientation, candidateArrow: null };
}

/**
 * Compare an answer against the rep. String comparison throughout: square
 * answers are strings ("e6") and button answers are strings ("safe").
 */
export function isAnswerCorrect(rep, value) {
  if (!rep || value == null) return false;
  return String(value) === String(rep.answer);
}

/** Squares to highlight once the answer is revealed. Never before. */
export function revealHighlights(rep, revealed) {
  if (!revealed || !rep) return [];
  const demo = rep.demonstration || {};
  return (demo.highlight || []).filter(Boolean);
}

/**
 * Arrows for the board. Before the answer, `is_safe` shows the candidate move
 * so the player can see what is being asked. After the answer, the winning
 * capture is drawn — the demonstration happens on the board, not in prose.
 */
export function repArrows(rep, revealed) {
  const view = buildRepView(rep);
  if (!revealed) {
    return view.candidateArrow ? [[...view.candidateArrow, "rgb(100,116,139)"]] : [];
  }
  const cap = (rep?.demonstration || {}).capture_uci;
  if (typeof cap !== "string" || cap.length < 4) return [];
  return [[cap.slice(0, 2), cap.slice(2, 4), "rgb(239,68,68)"]];
}
