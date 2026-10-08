/**
 * The chances card must not be mounted inside a focus branch.
 *
 * docs/home_merge_scope.md
 *
 * This has gone wrong three times in two days and never failed a test, because
 * every test rendered the component directly and the component was always fine.
 * What was wrong was WHERE it was mounted:
 *
 *   the practice link  -> added below `if (coaching_context) return`, so it was
 *                         null for the 51 of 52 users who have one
 *   the chances card   -> added inside the `pic` branch of
 *                         `canonicalContext ? ... : pic ? ...`, so it rendered
 *                         for almost nobody
 *
 * The reading does not depend on which focus shape a player has, so it must not
 * sit inside a test for one. This is a source contract, in the same style as
 * CurriculumSurfaceContract.test.js, because the failure is structural and no
 * render test can see it.
 */
const fs = require("fs");
const path = require("path");

const read = (p) => fs.readFileSync(path.join(__dirname, "..", "..", p), "utf8");

describe("the chances card reaches every player", () => {
  test("both home surfaces mount it", () => {
    // It is no longer a card of its own on either surface: it is passed into
    // movement one as the `assessment` slot, because the reading IS part of
    // what the coach knows about you. docs/home_as_a_coach_scope.md. Still
    // mounted, still outside every focus branch — which is the thing this file
    // has always been guarding.
    expect(read("pages/HomePageNew.jsx")).toContain(
      "assessment={<ChancesCard />}"
    );
    expect(read("components/curriculum/CurriculumHome.jsx")).toContain(
      "assessment={<ChancesCard />}"
    );
  });

  test("the dashboard mounts it OUTSIDE the focus branch", () => {
    const src = read("pages/HomePageNew.jsx");
    const branch = src.indexOf("{canonicalContext ? (");
    const card = src.indexOf("assessment={<ChancesCard />}");
    expect(branch).toBeGreaterThan(-1);
    expect(card).toBeGreaterThan(-1);

    // It now sits ABOVE the ternary rather than after it. Either side of the
    // whole thing is fine; inside one arm is not, which is the only failure
    // this test was ever written to catch.
    const picArm = src.indexOf(") : pic ? (");
    expect(picArm).toBeGreaterThan(-1);
    const picArmEnd = src.indexOf("          )}", picArm);
    expect(card > branch && card < picArmEnd).toBe(false);
  });

  test("the coaching session is mounted on the branch users actually take", () => {
    // Measured 2026-10-07: all 128 users fall through to HomePageNew, because
    // PERSONAL_CURRICULUM_ENABLED is unset on prod so `curriculum.enabled` is
    // false for everyone. The session was built into CurriculumHome first and
    // would have reached nobody — the fourth surface this session wired into a
    // branch users do not take.
    expect(read("pages/HomePageNew.jsx")).toContain("<CoachMovements ");
  });

  test("the dead runners-up block is gone", () => {
    const src = read("pages/HomePageNew.jsx");
    // It read a field the canonical payload never sends AND sat in the branch
    // 51 of 52 users never reach.
    expect(src).not.toContain("runners_up");
    expect(src).not.toContain("also-showing");
  });

  test("the nav tiles are still there", () => {
    // An earlier draft of the merge scope deleted these as "duplicates of the
    // sidebar". They are not: /openings and /training appear nowhere in
    // Layout, so these tiles are the only route to either section.
    const src = read("pages/HomePageNew.jsx");
    expect(src).toContain('href: "/openings"');
    expect(src).toContain('href: "/training"');

    const layout = read("components/Layout.jsx");
    const sidebarHasThem =
      layout.includes("href: '/openings'") || layout.includes("href: '/training'");
    expect(sidebarHasThem).toBe(false);
  });
});
