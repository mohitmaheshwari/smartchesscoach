import fs from "fs";
import path from "path";

describe("MissionRunner server-owned grading boundary", () => {
  const source = fs.readFileSync(path.join(__dirname, "MissionRunner.jsx"), "utf8");

  test("submits puzzle identity and learner move to the mission grader", () => {
    expect(source).toContain("/attempt`");
    expect(source).toContain("puzzle_id: currentPosition.puzzle_id");
    expect(source).toContain("played_uci: playedUci");
  });

  test("does not grade against a browser-visible answer", () => {
    expect(source).not.toContain("currentPosition.best_move");
    expect(source).not.toContain("currentPosition.best_move_uci");
    expect(source).not.toContain("Show Answer");
    expect(source).toContain("setFeedback(grade.correct");
  });

  test("does not submit a browser score at completion", () => {
    expect(source).toContain("body: JSON.stringify({})");
    expect(source).not.toContain("body: JSON.stringify({ score");
  });
});
