/**
 * `derived.active.trained_pattern` was referenced exactly once in the whole
 * codebase and never assigned anywhere — the `active` weakness object only
 * ever sets `.pattern`. The "Practise this with me" button navigated to
 * `/training/pattern/undefined` for every user, for whichever pattern was
 * active, not just one. Reported live 2026-09-09 via the time-discipline
 * card ("it says that's the fix, but it loads nothing, no puzzle").
 *
 * A full render test of this page's data pipeline is a large lift for a
 * one-field typo; this is a cheap, fast source-level guard against the
 * typo coming back, in the spirit of this repo's existing caption-guard
 * pre-commit check.
 */
const fs = require("fs");
const path = require("path");

const source = fs.readFileSync(
  path.join(__dirname, "UnifiedProgress.jsx"),
  "utf8"
);

test("the Practise-this-with-me button navigates with the field the active object actually sets", () => {
  expect(source).not.toContain("trained_pattern");
  expect(source).toContain("derived.active.pattern");
});
