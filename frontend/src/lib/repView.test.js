/**
 * Tests for coaching-rep view logic.
 *
 * The contract that matters: the board the player looks at must agree with the
 * question being asked. `is_safe` asks about a move not yet played, so it shows
 * the position BEFORE with the candidate as an arrow. `who_takes` asks about the
 * position AFTER, so the move must already be on the board. Getting that
 * backwards is invisible in code review and obvious to a confused player.
 *
 * Positions are the same hand-checked ones as backend/tests/test_rep_generator.py:
 *
 *   8/8/4p3/8/8/8/8/3QK2k w - - 0 1
 *   White queen d1, black pawn e6. Qd5 walks onto the pawn; exd5 wins the queen.
 */
import { Chess } from "chess.js";
import {
  PRE_MOVE_TYPES,
  SQUARE_ANSWER_TYPES,
  buildRepView,
  isAnswerCorrect,
  repArrows,
  revealHighlights,
} from "./repView";

const FEN = "8/8/4p3/8/8/8/8/3QK2k w - - 0 1";

const isSafeRep = {
  rep_type: "is_safe",
  fen: FEN,
  move_uci: "d1d5",
  move_san: "Qd5",
  prompt: "You want to play Qd5.",
  answer: "not_safe",
  demonstration: { capture_uci: "e6d5", highlight: ["e6", "d5"], caption: "The pawn takes it." },
};

const whoTakesRep = {
  rep_type: "who_takes",
  fen: FEN,
  move_uci: "d1d5",
  prompt: "After Qd5, who takes it?",
  answer: "e6",
  demonstration: { capture_uci: "e6d5", highlight: ["e6", "d5"], caption: "The pawn on e6." },
};

describe("buildRepView", () => {
  test("is_safe shows the position BEFORE the move", () => {
    const v = buildRepView(isSafeRep);
    expect(v.displayFen).toBe(FEN);
    expect(new Chess(v.displayFen).get("d5")).toBeFalsy(); // queen has not moved yet
  });

  test("is_safe draws the candidate move as an arrow", () => {
    expect(buildRepView(isSafeRep).candidateArrow).toEqual(["d1", "d5"]);
  });

  test("who_takes shows the position AFTER the move", () => {
    const v = buildRepView(whoTakesRep);
    expect(v.displayFen).not.toBe(FEN);
    const after = new Chess(v.displayFen);
    expect(after.get("d5")).toMatchObject({ type: "q", color: "w" });
    expect(after.get("d1")).toBeFalsy();
  });

  test("who_takes never draws a candidate arrow (the move is already played)", () => {
    expect(buildRepView(whoTakesRep).candidateArrow).toBeNull();
  });

  test("orientation follows the side to move", () => {
    expect(buildRepView(isSafeRep).orientation).toBe("white");
    const blackToMove = { ...isSafeRep, fen: "4k3/8/8/8/8/8/4P3/4K1b1 b - - 0 1", move_uci: "g1e3" };
    expect(buildRepView(blackToMove).orientation).toBe("black");
  });

  test("a malformed rep degrades instead of throwing", () => {
    expect(buildRepView(null).displayFen).toBeNull();
    expect(buildRepView({ rep_type: "is_safe" }).displayFen).toBeNull();
    expect(buildRepView({ rep_type: "is_safe", fen: "not-a-fen" }).displayFen).toBeNull();
  });

  test("an unplayable move falls back to the original position", () => {
    // d1a8 is not a queen line; the board must not silently disagree with the prompt.
    const bad = { ...whoTakesRep, move_uci: "d1a8" };
    expect(buildRepView(bad).displayFen).toBe(FEN);
  });
});

describe("isAnswerCorrect", () => {
  test("grades button answers", () => {
    expect(isAnswerCorrect(isSafeRep, "not_safe")).toBe(true);
    expect(isAnswerCorrect(isSafeRep, "safe")).toBe(false);
  });

  test("grades square answers", () => {
    expect(isAnswerCorrect(whoTakesRep, "e6")).toBe(true);
    expect(isAnswerCorrect(whoTakesRep, "d5")).toBe(false);
  });

  test("no answer is not a correct answer", () => {
    expect(isAnswerCorrect(whoTakesRep, null)).toBe(false);
    expect(isAnswerCorrect(null, "e6")).toBe(false);
  });
});

describe("reveal behaviour", () => {
  test("nothing is highlighted before the answer", () => {
    expect(revealHighlights(isSafeRep, false)).toEqual([]);
  });

  test("the demonstration squares appear after the answer", () => {
    expect(revealHighlights(isSafeRep, true)).toEqual(["e6", "d5"]);
  });

  test("the capture is drawn on the board after the answer", () => {
    expect(repArrows(isSafeRep, true)).toEqual([["e6", "d5", "rgb(239,68,68)"]]);
  });

  test("before the answer only the candidate arrow shows, never the capture", () => {
    const arrows = repArrows(isSafeRep, false);
    expect(arrows).toEqual([["d1", "d5", "rgb(100,116,139)"]]);
    expect(arrows.some(([from]) => from === "e6")).toBe(false);
  });

  test("who_takes shows no arrow at all before the answer", () => {
    expect(repArrows(whoTakesRep, false)).toEqual([]);
  });
});

describe("type sets", () => {
  test("square-answer and pre-move sets do not overlap", () => {
    [...SQUARE_ANSWER_TYPES].forEach((t) => expect(PRE_MOVE_TYPES.has(t)).toBe(false));
  });
});
