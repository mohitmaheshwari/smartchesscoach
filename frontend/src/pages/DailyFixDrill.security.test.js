import fs from "fs";
import path from "path";

describe("Daily Fix verified completion boundary", () => {
  const source = fs.readFileSync(path.join(__dirname, "DailyFixDrill.jsx"), "utf8");

  test("grades each move on the server", () => {
    expect(source).toContain("/training/puzzle-attempt");
    expect(source).toContain("puzzle_id: drill.puzzle_id");
    expect(source).toContain("played_uci: uci");
    expect(source).toContain('setPhase(grade.correct ? "correct" : "wrong")');
  });

  test("has no skip or local answer comparison", () => {
    expect(source).not.toContain(">Skip<");
    expect(source).not.toContain("drill.best_move");
    expect(source).not.toContain("drill.best_move_uci");
  });

  test("shows done only after server completion succeeds", () => {
    const completion = source.slice(source.indexOf("const next = useCallback"));
    expect(completion).toContain("if (!res.ok)");
    expect(completion.indexOf('setPhase("done")')).toBeGreaterThan(
      completion.indexOf("if (!res.ok)")
    );
    expect(source).toContain("setCompletionError");
  });
});
