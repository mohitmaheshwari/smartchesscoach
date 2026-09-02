/**
 * The three defects a real user hit on 2026-09-02, none of which the existing
 * 88 frontend tests caught, because they assert that the component RENDERS --
 * not that it does the thing:
 *
 *   1. the board never changed after a submitted move (the piece "didn't move")
 *   2. no right/wrong feedback was ever shown, in a DIAGNOSTIC
 *   3. the same sentence appeared three times on one screen
 */
import { Chess } from "chess.js";
import { fenAfterMove, moveVerdict, dedupeAnchors } from "./homeReplayView";

const START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

// --- 1. the board must show the played move -----------------------------

test("the position changes after a move", () => {
  const after = fenAfterMove(START, "e4");
  expect(after).not.toBeNull();
  expect(after).not.toBe(START);
});

test("the moved piece actually leaves its origin square", () => {
  const after = fenAfterMove(START, "e4");
  const before = new Chess(START);
  const now = new Chess(after);
  expect(before.get("e2")).toEqual({ type: "p", color: "w" });
  expect(now.get("e2")).toBeFalsy();      // the bug: piece stayed put
  expect(now.get("e4")).toEqual({ type: "p", color: "w" });
});

test("a bishop capture removes the captured piece", () => {
  // The reported case: a bishop capture rendered with the bishop still on its
  // old square. FEN and move verified legal on a board before use.
  const fen = "rnbqkb1r/pppppp1p/5np1/8/8/1P4P1/PBPPPP1P/RN1QKBNR w KQkq - 0 1";
  const after = fenAfterMove(fen, "Bxf6");
  expect(after).not.toBeNull();
  const now = new Chess(after);
  expect(now.get("f6")).toEqual({ type: "b", color: "w" });
  expect(now.get("b2")).toBeFalsy();
});

test("an illegal or unparseable move leaves the board alone rather than throwing", () => {
  expect(fenAfterMove(START, "Qz9")).toBeNull();
  expect(fenAfterMove(START, "")).toBeNull();
  expect(fenAfterMove("not a fen", "e4")).toBeNull();
  expect(fenAfterMove(null, null)).toBeNull();
});

// --- 2. the player must be told whether the move worked ------------------

test("a passing move is reported as safe", () => {
  const v = moveVerdict({ target_result: "pass", soundness: { status: "sound" } });
  expect(v).not.toBeNull();
  expect(v.kept).toBe(true);
  expect(v.headline).toMatch(/safe/i);
});

test("a failing move says a piece can be taken", () => {
  const v = moveVerdict({ target_result: "fail", soundness: { status: "sound" } });
  expect(v.kept).toBe(false);
  expect(v.headline).toMatch(/taken/i);
});

test("a separate material problem is reported separately from the target idea", () => {
  const v = moveVerdict({
    target_result: "pass",
    soundness: { status: "serious_problem" },
  });
  expect(v.kept).toBe(true);                  // the taught idea was satisfied
  expect(v.soundnessNote).toMatch(/loses material/i);
});

test("an unmeasured move claims nothing", () => {
  expect(moveVerdict({ target_result: "unmeasured" })).toBeNull();
  expect(moveVerdict({})).toBeNull();
  expect(moveVerdict(null)).toBeNull();
});

// --- 3. no sentence may appear twice ------------------------------------

test("an anchor repeating why_now is dropped", () => {
  const repeated = "Your last answer shows that one of your pieces was left where it could be taken.";
  const out = dedupeAnchors([{ type: "a", message: repeated }], repeated);
  expect(out).toHaveLength(0);
});

test("duplicate anchors collapse to one", () => {
  const msg = "Same sentence twice.";
  const out = dedupeAnchors(
    [{ type: "a", message: msg }, { type: "b", message: msg }],
    "something else"
  );
  expect(out).toHaveLength(1);
});

test("distinct anchors survive", () => {
  const out = dedupeAnchors(
    [{ type: "a", message: "First." }, { type: "b", message: "Second." }],
    "why now"
  );
  expect(out).toHaveLength(2);
});

test("empty anchors are dropped rather than rendered blank", () => {
  const out = dedupeAnchors(
    [{ type: "a", message: "" }, { type: "b", message: "   " }],
    "why"
  );
  expect(out).toHaveLength(0);
});

// --- the training lesson uses the same verdict helper -------------------
// Reported 2026-09-02: after making a move the lesson said "You found it" or
// nothing at all, never whether the piece ended up safe.

test("a graded move reports what happened to the piece, not just pass/fail", () => {
  const backendFeedback = {
    correct: true,
    target_result: "pass",
    soundness: { status: "sound" },
    feedback: "Nice scan.",
  };
  const v = moveVerdict(backendFeedback);
  expect(v.headline).toBe("Every piece stayed safe.");
  expect(v.headline).not.toMatch(/you found it/i);
});

test("a move that hangs a piece says so plainly", () => {
  const v = moveVerdict({ correct: false, target_result: "fail", soundness: { status: "sound" } });
  expect(v.headline).toMatch(/left a piece where it can be taken/i);
});

test("the taught idea and material loss are reported as separate facts", () => {
  const v = moveVerdict({
    target_result: "pass",
    soundness: { status: "serious_problem" },
  });
  expect(v.kept).toBe(true);
  expect(v.soundnessNote).toBeTruthy();
  expect(v.headline).not.toMatch(/loses material/i);
});

// --- the grader the concept lessons ACTUALLY run -------------------------
// Reported 2026-09-02 ("it doesn't tell me the move is right or wrong"):
// /training?personalized=1 supplies items from the community pools, which
// grade through verified_puzzle_admission.v2. That grader returns `correct`
// and an answer but NO target_result, so a target_result-only verdict showed
// the player nothing whatsoever. Shapes below are real returns captured from
// the deployed grader.

test("a correct puzzle answer is reported even without target_result", () => {
  const v = moveVerdict({
    correct: true,
    answer_san: "Qe5",
    feedback: "Yes — Qe5.",
    grader_version: "verified_puzzle_admission.v2",
  });
  expect(v).not.toBeNull();          // the bug: silence
  expect(v.kept).toBe(true);
  expect(v.headline).toMatch(/that's the move/i);
});

test("a wrong puzzle answer names the move that was right", () => {
  const v = moveVerdict({
    correct: false,
    answer_san: "exd4",
    grader_version: "verified_puzzle_admission.v2",
  });
  expect(v.kept).toBe(false);
  expect(v.headline).toMatch(/exd4/);
});

test("a wrong answer with no known better move still says it was wrong", () => {
  const v = moveVerdict({ correct: false, answer_san: null });
  expect(v.kept).toBe(false);
  expect(v.headline).toMatch(/not this one/i);
});

test("the puzzle grader never claims the piece is safe", () => {
  // It verified the ANSWER, not piece safety. Borrowing the diagnostic's
  // wording here would assert something no grader checked.
  for (const correct of [true, false]) {
    const v = moveVerdict({ correct, answer_san: "Qe5" });
    expect(v.headline).not.toMatch(/stayed safe|can be taken/i);
  }
});

test("an explicitly unmeasured result still claims nothing", () => {
  expect(moveVerdict({ target_result: "unmeasured", correct: false })).toBeNull();
});

test("the diagnostic grader keeps its stronger, verified claim", () => {
  const v = moveVerdict({ target_result: "pass", correct: true, soundness: { status: "sound" } });
  expect(v.headline).toMatch(/stayed safe/i);
});
