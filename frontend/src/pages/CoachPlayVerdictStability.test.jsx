/**
 * One verdict per move.
 *
 * Mohit, 2026-09-24: "i play a move and it showed inaccuracy first and then
 * after 2 seconds showed as good, best in the position, this is so unpremium."
 *
 * Three things wrote the badge for the same move. The first was
 * evaluate-pending, which is fast_eval -- a nodes-limited search around depth
 * 8. Measured over 25 games / 761 user moves, depth 8 and depth 14 disagree on
 * 20.5% of moves; on 67 the shallow search called a fault that the deep search
 * called good. So the fix is not "first write wins" -- that would pin the
 * least reliable verdict -- it is that the shallow search does not paint a
 * verdict at all, and the two remaining writers cannot contradict each other.
 *
 * These assert the source, because the behaviour lives across an async
 * boundary that a unit render cannot reach without standing up the whole page.
 */
import fs from "fs";
import path from "path";

const SOURCE = fs.readFileSync(
  path.join(__dirname, "CoachPlay.jsx"),
  "utf8"
);

describe("the shallow search does not paint the board", () => {
  it("evaluate-pending's moveQuality never reaches the badge", () => {
    // The badge reads v5Coaching.severity. moveQuality must not be written
    // into it from the evaluate-pending result.
    expect(SOURCE).not.toMatch(/setV5Coaching\(\{\s*severity:\s*moveQuality/);
    expect(SOURCE).not.toMatch(/applyV5Coaching\(\{\s*severity:\s*moveQuality/);
  });

  it("still reads moveQuality, so the interrupt keeps its input", () => {
    // The shallow search keeps its real job. Deleting it entirely would take
    // the pre-commit interrupt with it.
    expect(SOURCE).toMatch(/moveQuality/);
  });
});

describe("the remaining writers cannot contradict each other", () => {
  it("every badge write goes through the pin", () => {
    // Raw setV5Coaching may appear ONLY inside applyV5Coaching itself.
    const helperStart = SOURCE.indexOf("const applyV5Coaching");
    const helperEnd = SOURCE.indexOf("const [moveFeedback");
    expect(helperStart).toBeGreaterThan(-1);
    expect(helperEnd).toBeGreaterThan(helperStart);

    const raw = [...SOURCE.matchAll(/setV5Coaching\(/g)].map((m) => m.index);
    const outside = raw.filter((i) => i < helperStart || i > helperEnd);
    expect(outside).toEqual([]);
  });

  it("the pin keys on the move, not just the severity", () => {
    const helper = SOURCE.slice(SOURCE.indexOf("const moveVerdictKey"));
    expect(helper).toMatch(/move_san/);
    expect(helper).toMatch(/fen_before/);
  });

  it("a later write keeps the narrative but not a new verdict", () => {
    const helper = SOURCE.slice(
      SOURCE.indexOf("const applyV5Coaching"),
      SOURCE.indexOf("const [moveFeedback")
    );
    // spreads `next` (so narrative/arrows/question survive) and overrides
    // only severity with the pinned one
    expect(helper).toMatch(/\.\.\.next,\s*severity:\s*pin\.severity/);
  });

  it("clearing the coaching clears the pin, so a new game starts fresh", () => {
    // The first move of a new game has the same fen|san key as the first move
    // of the last one. A stranded pin would apply the old verdict to it.
    const helper = SOURCE.slice(
      SOURCE.indexOf("const applyV5Coaching"),
      SOURCE.indexOf("const [moveFeedback")
    );
    expect(helper).toMatch(/if \(!next\)/);
    expect(helper).toMatch(/pinnedVerdictRef\.current = \{ key: null, severity: null \}/);
  });
});
