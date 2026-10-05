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
    expect(read("pages/HomePageNew.jsx")).toContain("<ChancesCard />");
    expect(read("components/curriculum/CurriculumHome.jsx")).toContain(
      "<ChancesCard />"
    );
  });

  test("the dashboard mounts it AFTER the focus branch closes", () => {
    const src = read("pages/HomePageNew.jsx");
    const branch = src.indexOf("{canonicalContext ? (");
    const card = src.indexOf("<ChancesCard />");
    expect(branch).toBeGreaterThan(-1);
    expect(card).toBeGreaterThan(-1);

    // Everything between the start of the ternary and its close belongs to one
    // branch or the other. The card has to come after the whole thing.
    const navTiles = src.indexOf("NAVIGATION TILES");
    expect(navTiles).toBeGreaterThan(-1);
    expect(card).toBeGreaterThan(branch);
    expect(card).toBeLessThan(navTiles);

    // and specifically not inside the `pic` arm, which is where it was wrong
    const picArm = src.indexOf(") : pic ? (");
    const picArmEnd = src.indexOf("          )}", picArm);
    expect(picArm).toBeGreaterThan(-1);
    expect(card > picArm && card < picArmEnd).toBe(false);
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
