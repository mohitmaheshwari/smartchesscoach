import fs from "fs";
import path from "path";

describe("Game Review verified grading boundary", () => {
  const source = fs.readFileSync(path.join(__dirname, "LabV2.jsx"), "utf8");
  const start = source.indexOf("fetch(`${API}/lab/evaluate-move`");
  const end = source.indexOf("// Clear interactive mode", start);
  const gradingBlock = source.slice(start, end);

  test("sends only puzzle identity and the learner move", () => {
    expect(start).toBeGreaterThan(-1);
    expect(gradingBlock).toContain("puzzle_id:");
    expect(gradingBlock).toContain("user_move:");
    expect(gradingBlock).not.toMatch(/\bfen\s*:/);
    expect(gradingBlock).not.toMatch(/\bbest_move\s*:/);
    expect(gradingBlock).not.toMatch(/\boriginal_move\s*:/);
  });

  test("has no local correctness or invented-punishment fallback", () => {
    expect(gradingBlock).not.toContain("userMoveUci === bestMoveUci");
    expect(gradingBlock).not.toContain("allMoves.filter");
    expect(gradingBlock).not.toContain("falling back to local check");
    expect(gradingBlock).toContain("will not count until the coach can verify it");
  });
});
