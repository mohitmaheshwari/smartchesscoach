/**
 * Motif-drill board construction — the normalized contract (2026-08-13).
 *
 * Extracted from MotifDrill.jsx so the legality invariant is testable without
 * rendering the component. The bug this guards: the API used to return `fen`
 * (the position AFTER the user's blunder) paired with `solution` (the best move
 * in the position BEFORE it). 92% of own-game rows therefore advertised a move
 * that could not be played on the board being displayed.
 *
 * Payload contract:
 *   position_fen      board to display — user to move; solution_san legal here
 *   solution_san      the move the user should have found
 *   user_blunder_move what they played instead — legal in position_fen
 *   opp_creates_motif opponent's punishing reply — legal ONLY after the blunder
 */
import { Chess } from "chess.js";

/**
 * @returns {{board: Chess|null, trapBoard: Chess|null, orientation: "white"|"black"}}
 *   board      — position_fen, oriented to the user (the side to move)
 *   trapBoard  — position after replaying blunder THEN the opponent's motif move,
 *                or null when the drill carries no replay pair
 */
export function buildDrillBoards(drill) {
  const empty = { board: null, trapBoard: null, orientation: "white" };
  if (!drill || !drill.position_fen) return empty;

  let board;
  try {
    board = new Chess(drill.position_fen);
  } catch {
    return empty;
  }

  // position_fen has the USER to move, so this orients to the player's own side.
  const orientation = board.turn() === "w" ? "white" : "black";

  let trapBoard = null;
  if (drill.opp_creates_motif && drill.user_blunder_move) {
    try {
      const t = new Chess(drill.position_fen);
      t.move(drill.user_blunder_move); // must come first
      t.move(drill.opp_creates_motif); // legal only now
      trapBoard = t;
    } catch {
      trapBoard = null;
    }
  }

  return { board, trapBoard, orientation };
}

/** True when solution_san is actually playable on the board we display. */
export function isDrillPlayable(drill) {
  if (!drill || !drill.position_fen || !drill.solution_san) return false;
  try {
    const b = new Chess(drill.position_fen);
    return b.move(drill.solution_san) !== null;
  } catch {
    return false;
  }
}

/** Drop any row we cannot honestly serve, rather than showing an illegal move. */
export function usableDrills(drills) {
  return (drills || []).filter(isDrillPlayable);
}
