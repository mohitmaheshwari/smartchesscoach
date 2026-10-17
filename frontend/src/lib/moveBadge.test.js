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

describe("the badge does not contradict the caption", () => {
  // Mohit 2026-10-17, move 12 d4 of 8d05d6b9: the board said Mistake above a
  // card reading "d4 is fine - you're still winning." at +7.4.
  // severity='mistake', severity_practical='good', is_mistake=false, and the
  // engine's own row said evaluation='good'. Three fields said fine; the
  // badge read the fourth.
  test("a mistake the caption calls fine is badged good", () => {
    expect(resolveBadgeTier({
      severity: "mistake",
      severity_practical: "good",
      is_user_move: true,
    })).toBe("good");
  });

  test("a blunder badge never survives on a forced best move", () => {
    // "You were in check with only 2 legal moves, and Kh1 is the best of
    // them." -- badged Blunder before this.
    expect(resolveBadgeTier({
      severity: "blunder",
      severity_practical: "good",
      is_user_move: true,
    })).toBe("good");
  });

  test("but a caption that DOES say inaccuracy keeps its badge", () => {
    // "Opponent's Rxd2 is an inaccuracy. Play g5." -- here the badge and the
    // words already agree, and softening would re-open the gap the other way.
    expect(resolveBadgeTier({
      severity: "inaccuracy",
      severity_practical: "good",
      caption_severity_word: "inaccuracy",
      is_user_move: false,
    })).toBe("inaccuracy");
  });

  test("nothing is hardened: a gentler severity is left alone", () => {
    expect(resolveBadgeTier({
      severity: "good",
      severity_practical: "inaccuracy",
      is_user_move: true,
    })).toBe("good");
  });

  test("a real mistake still badges as one", () => {
    expect(resolveBadgeTier({
      severity: "mistake",
      severity_practical: "mistake",
      is_user_move: true,
    })).toBe("mistake");
  });

  test("no practical tier at all changes nothing", () => {
    expect(resolveBadgeTier({
      severity: "mistake",
      is_user_move: true,
    })).toBe("mistake");
  });
});
