/**
 * Frontend regression test for the motif got_positions contract fix (2026-08-13).
 *
 * Proves the thing that was broken in production: a reconstructed drill's advertised
 * solution can actually be PLAYED on the board the user is shown. Before the fix the
 * endpoint paired the position AFTER the user's blunder with the best move from BEFORE
 * it, so 511 of 558 stored fork rows (92%) advertised an unplayable move — and
 * PrescribedTraining graded users against exactly those moves.
 *
 * Exercises the real module MotifDrill.jsx imports, not a re-implementation.
 */
import { Chess } from "chess.js";
import { buildDrillBoards, isDrillPlayable, usableDrills } from "./motifDrill";

// The same verified fixture as backend/tests/test_motif_drill_contract.py:
// Black (the user) plays Rh8??, White answers Nf7 forking queen d8 and rook h8.
const FEN_BEFORE = "3q4/k6r/8/4N3/8/8/8/4K3 b - - 0 1";
const FEN_AFTER = "3q3r/k7/8/4N3/8/8/8/4K3 w - - 1 2";

const RECONSTRUCTED = {
  position_fen: FEN_BEFORE,
  solution_san: "Qd5",
  user_blunder_move: "Rh8",
  opp_creates_motif: "Nf7",
  fen_after: FEN_AFTER,
  game_id: "g1",
  move_number: 21,
  source: "own",
};

// What the endpoint used to return, and what a never-backfilled row still looks like.
const LEGACY_BROKEN = {
  fen: FEN_AFTER,
  solution: "Qd5", // belongs to FEN_BEFORE, not to fen
  source: "own",
};

describe("motif drill contract", () => {
  test("the advertised solution is playable on the displayed board", () => {
    const { board } = buildDrillBoards(RECONSTRUCTED);
    expect(board).not.toBeNull();
    expect(board.fen()).toBe(FEN_BEFORE);
    // The assertion the old contract failed:
    expect(() => board.move(RECONSTRUCTED.solution_san)).not.toThrow();
  });

  test("the same solution is NOT playable on the pre-fix board", () => {
    // Guards against a regression that quietly reverts position_fen to fen_after.
    const after = new Chess(FEN_AFTER);
    expect(() => after.move("Qd5")).toThrow();
  });

  test("the trap board replays the blunder before the opponent's motif move", () => {
    const { trapBoard } = buildDrillBoards(RECONSTRUCTED);
    expect(trapBoard).not.toBeNull();
    // Knight reached f7 — the fork actually happened on the board we render.
    expect(trapBoard.get("f7")).toEqual(
      expect.objectContaining({ type: "n", color: "w" })
    );
  });

  test("playing the opponent's move directly from position_fen fails", () => {
    // This is why the trap panel never rendered before the fix.
    const b = new Chess(FEN_BEFORE);
    expect(() => b.move("Nf7")).toThrow();
  });

  test("the board is oriented to the user, not the opponent", () => {
    const { orientation } = buildDrillBoards(RECONSTRUCTED);
    expect(orientation).toBe("black"); // black is the user, and is to move
  });

  test("legacy un-backfilled rows are filtered out, not rendered", () => {
    expect(isDrillPlayable(LEGACY_BROKEN)).toBe(false);
    expect(usableDrills([LEGACY_BROKEN, RECONSTRUCTED])).toEqual([RECONSTRUCTED]);
  });

  test("community rows survive the same filter", () => {
    const community = {
      position_fen: FEN_BEFORE,
      solution_san: "Qd5",
      source: "community",
    };
    expect(isDrillPlayable(community)).toBe(true);
    const { board, trapBoard } = buildDrillBoards(community);
    expect(board).not.toBeNull();
    expect(trapBoard).toBeNull(); // no replay pair — panel simply hides
  });

  test("malformed input degrades quietly", () => {
    expect(buildDrillBoards(null).board).toBeNull();
    expect(buildDrillBoards({}).board).toBeNull();
    expect(buildDrillBoards({ position_fen: "not a fen" }).board).toBeNull();
    expect(usableDrills(undefined)).toEqual([]);
  });
});
