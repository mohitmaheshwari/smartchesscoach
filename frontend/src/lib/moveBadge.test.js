/**
 * An opponent's move must say how it went.
 *
 * Mohit 2026-09-29, on a card reading "Bg4 [Opponent] — Bg4. Lines up the
 * knight on f3 in front of the queen." with no verdict anywhere on it:
 * "some opponent moves just doesn't tell if they are good, blunder or you
 * know?"
 *
 * Bg4 is 53cp, which the backend tiers as opp_inaccuracy. The board's icon
 * table has keys for inaccuracy/mistake/blunder and none beginning opp_, so
 * the lookup missed and nothing was drawn. Qd6 (76cp) and Qa5 (352cp) WERE
 * badged only because their captions contain "is an inaccuracy" and "is a
 * major blunder" for the text parse to catch.
 */
import { BADGE_TIERS, resolveBadgeTier, tierFromCaption } from "./moveBadge";

const opp = (over) => ({ is_user_move: false, ...over });

describe("the reported card", () => {
  test("Bg4 at 53cp is badged instead of silent", () => {
    expect(
      resolveBadgeTier(opp({ severity: "opp_inaccuracy", cp_loss: 53, narrative: "Bg4. Lines up the knight on f3 in front of the queen." }))
    ).toBe("inaccuracy");
  });

  test("every opponent tier maps onto a tier the board can draw", () => {
    for (const [backend, expected] of [
      ["opp_inaccuracy", "inaccuracy"],
      ["opp_mistake", "mistake"],
      ["opp_blunder", "blunder"],
    ]) {
      const tier = resolveBadgeTier(opp({ severity: backend, cp_loss: 150 }));
      expect(tier).toBe(expected);
      expect(BADGE_TIERS.has(tier)).toBe(true);
    }
  });

  test("a tier the board has no icon for is treated as no badge, never passed through", () => {
    expect(resolveBadgeTier(opp({ severity: "opp_serious", cp_loss: 0 }))).not.toBe("serious");
  });
});

describe("an opponent move that was fine still says so", () => {
  test("a near-best move reads as best", () => {
    expect(resolveBadgeTier(opp({ severity: "context", cp_loss: 2 }))).toBe("best");
  });

  test("a small drift reads as good", () => {
    expect(resolveBadgeTier(opp({ severity: "context", cp_loss: 20 }))).toBe("good");
  });
});

describe("the caption keeps the last word", () => {
  test("the severity word R12 used wins over the tier", () => {
    expect(
      resolveBadgeTier(opp({ caption_severity_word: "blunder", severity: "opp_inaccuracy", cp_loss: 53 }))
    ).toBe("blunder");
  });

  test("legacy documents are read from their text", () => {
    expect(tierFromCaption({ narrative: "Opponent's Qa5 is a major blunder." })).toBe("blunder");
    expect(tierFromCaption({ narrative: "Opponent's Qd6 is an inaccuracy." })).toBe("inaccuracy");
    expect(tierFromCaption({ narrative: "Bg4. Lines up the knight." })).toBeNull();
  });
});

describe("your own moves are unchanged", () => {
  test("a user move with no severity draws nothing", () => {
    expect(resolveBadgeTier({ is_user_move: true, severity: "context", cp_loss: 300 })).toBeNull();
  });

  test("a user move keeps its own tier", () => {
    expect(resolveBadgeTier({ is_user_move: true, severity: "blunder", cp_loss: 523 })).toBe("blunder");
  });

  test("no move at all draws nothing", () => {
    expect(resolveBadgeTier(null)).toBeNull();
  });
});
