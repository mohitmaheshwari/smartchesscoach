/**
 * Progress no longer owns pattern-practice routing. Learn owns the lesson;
 * Progress consumes its canonical destination and owns transfer evidence.
 */
const fs = require("fs");
const path = require("path");

const source = fs.readFileSync(
  path.join(__dirname, "UnifiedProgress.jsx"),
  "utf8"
);

test("Progress does not reconstruct a pattern-training route from weakness fields", () => {
  expect(source).not.toContain("trained_pattern");
  expect(source).not.toContain("/training/pattern/");
  expect(source).toContain("primary?.destination?.href");
  expect(source).toContain("/progress/complete-coaching");
});
