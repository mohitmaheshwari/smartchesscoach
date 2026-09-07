import { buildTrainingFeedbackView } from "./trainingFeedback";

describe("buildTrainingFeedbackView", () => {
  test("a safe non-answer is acknowledged without leaking the solution", () => {
    const view = buildTrainingFeedbackView({
      puzzleState: "concept_pass",
      userMove: "Rxa2",
      sourceMove: "Ne3+",
      verifiedSolution: null,
      patternType: "piece_safety",
      coaching: {
        why: "Rxa2 keeps your rook safe on a2.",
        remember: "Look again at the pawns on d6 and e5.",
      },
      fallback: "Check every piece.",
    });

    expect(view.outcome).toBe("safe");
    expect(view.san).toBe("Rxa2 (you played)");
    expect(view.san).not.toContain("dxe5");
    expect(view.showSolution).toBe(false);
    expect(view.canReveal).toBe(true);
  });

  test("an explicit reveal compares the source mistake with the safer move", () => {
    const view = buildTrainingFeedbackView({
      puzzleState: "revealed",
      userMove: "Rxa2",
      sourceMove: "Ne3+",
      verifiedSolution: "dxe5",
      patternType: "piece_safety",
      coaching: {
        why: "Ne3+ put the knight on e3, where Nxe3 could take it.",
      },
      fallback: "Check every piece.",
    });

    expect(view.outcome).toBe("revealed");
    expect(view.san).toBe("Ne3+ (from the game) · dxe5 (safer move)");
    expect(view.showSolution).toBe(true);
  });

  test("a first miss never displays a known answer", () => {
    const view = buildTrainingFeedbackView({
      puzzleState: "incorrect",
      userMove: "Qd5",
      sourceMove: "Qd5",
      verifiedSolution: "Qa4",
      patternType: "piece_safety",
      coaching: { why: "Your queen can be won on d5." },
      fallback: "Check the destination.",
    });

    expect(view.outcome).toBe("retry");
    expect(view.san).toBe("Qd5 (you played)");
    expect(view.san).not.toContain("Qa4");
    expect(view.showSolution).toBe(false);
  });
});
