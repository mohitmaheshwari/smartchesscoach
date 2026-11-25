/**
 * The Play-vs-Human entry must actually be reachable from the setup screen.
 *
 * Written 2026-11-25 after shipping the feature and finding no way into it.
 * The first version put the entry in CoachPlay.jsx as a sibling rendered just
 * before <CoachPlaySetup>. The code deployed, the string was in the bundle,
 * and the button was nowhere a player would look. A feature nobody can click
 * is not shipped.
 *
 * What this test checks: the chain CoachPlay -> CoachPlaySetup ->
 * UnifiedCoachPlaySetup is actually connected, and the entry exists on BOTH
 * setup screens (the unified one and the legacy one), so neither path loses it
 * silently.
 *
 * What it does NOT check: that the button is visible on screen. That needs a
 * real render of UnifiedCoachPlaySetup, which drags in the router and the app
 * Layout. This is a wiring test, and it is honest about being one -- it would
 * have caught the actual bug (an entry that no screen renders), but it cannot
 * catch CSS that hides it.
 */

import fs from "fs";
import path from "path";

const SRC = path.resolve(__dirname, "../..");

const read = (relative) =>
  fs.readFileSync(path.join(SRC, relative), "utf8");

describe("the way into Play vs Human", () => {
  const coachPlay = read("pages/CoachPlay.jsx");
  const setup = read("components/coach/CoachPlaySetup.jsx");
  const unified = read("components/coach/UnifiedCoachPlaySetup.jsx");

  it("CoachPlay hands the setup screen a way to open it", () => {
    expect(coachPlay).toMatch(/onPlayVsHuman=\{\(\) => setPlayVsHuman\(true\)\}/);
    // and renders the section when that state is set
    expect(coachPlay).toMatch(/if \(!gameStarted && playVsHuman\)/);
    expect(coachPlay).toMatch(/<PlayVsHuman onExit=/);
  });

  it("CoachPlaySetup accepts it and forwards it to the unified screen", () => {
    expect(setup).toMatch(/^\s*onPlayVsHuman,\s*$/m);
    expect(setup).toMatch(/onPlayVsHuman=\{onPlayVsHuman\}/);
  });

  it("the unified screen renders it as a mode choice beside the others", () => {
    expect(unified).toMatch(/onPlayVsHuman/);
    expect(unified).toMatch(/testId="unified-mode-human"/);
    expect(unified).toMatch(/Play a Human/);
    // It must sit in the same radiogroup as the other two, not somewhere else
    // on the page: that is where a player looks to choose how to play.
    const group = unified.slice(
      unified.indexOf('role="radiogroup"'),
      unified.indexOf("</section>", unified.indexOf('role="radiogroup"'))
    );
    expect(group).toMatch(/unified-mode-coach/);
    expect(group).toMatch(/unified-mode-play/);
    expect(group).toMatch(/unified-mode-human/);
  });

  it("the legacy setup screen has the entry too", () => {
    expect(setup).toMatch(/data-testid="play-vs-human-entry"/);
  });

  it("promises no coaching during the game, on every entry point", () => {
    // The copy is the player's only warning that the app will go quiet. If it
    // is dropped, the guard's 403s read as the product being broken.
    //
    // Whitespace-tolerant on purpose: JSX collapses a line break in text into
    // a single space when rendered, so a literal-space regex fails on copy
    // that merely wraps in the source. That is a test bug, not a copy bug.
    const promise = /No coaching while you\s+play/;
    expect(unified).toMatch(promise);
    expect(setup).toMatch(promise);
  });
});
