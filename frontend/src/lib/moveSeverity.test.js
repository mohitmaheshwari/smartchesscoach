/**
 * The board must be able to show a move the caption names.
 *
 * Mohit 2026-10-28 asked whether his Nxe4 card draws an arrow. It did not:
 * the card stored best_move_arrows (f6->e4, with the FEN they are true of)
 * and the only thing that draws them hung off a severity test listing three
 * of the engine's five tiers. Both halves of that bug are asserted here,
 * because neither was visible from reading the component.
 */
import {
  FAULTED_SEVERITIES,
  gradeOf,
  isFaultedCard,
  isFaultedSeverity,
  namesMoveInText,
  whyButtonLabel,
} from "./moveSeverity";

describe("the why button's words follow the badge", () => {
  // 2d86e1f9 move 4...Bc5: badge Good, engine grade inaccuracy.
  const bc5 = { severity: "good", severity_canonical: "inaccuracy", best_move_san: "Nf6" };

  test("a Good card asks about the better move, never 'bad'", () => {
    expect(isFaultedCard(bc5)).toBe(true);           // the button still shows
    expect(whyButtonLabel(bc5)).toBe("Why is Nf6 better?");
  });

  test("a real mistake keeps 'Why was this bad?'", () => {
    expect(whyButtonLabel({ ...bc5, severity: "mistake" })).toBe("Why was this bad?");
    expect(whyButtonLabel({ ...bc5, severity: "inaccuracy" })).toBe("Why was this bad?");
  });

  test("opponent cards and cards with no better move are unchanged", () => {
    expect(whyButtonLabel(bc5, true)).toBe("Why was this bad?");
    expect(whyButtonLabel({ ...bc5, best_move_san: "" })).toBe("Why was this bad?");
  });
});

describe("the engine's severity tiers", () => {
  // backend/services/severity.py:73 TIER_ORDER
  test.each(["inaccuracy", "mistake", "serious", "blunder"])(
    "%s is a faulted move",
    (tier) => {
      expect(isFaultedSeverity(tier)).toBe(true);
    }
  );

  test("good is not, and neither is a missing grade", () => {
    expect(isFaultedSeverity("good")).toBe(false);
    expect(isFaultedSeverity(null)).toBe(false);
    expect(isFaultedSeverity(undefined)).toBe(false);
  });

  // The regression this set exists for. `serious` is 250-399cp, the
  // second-worst grade the engine assigns; the card used to test
  // blunder/mistake/inaccuracy inline, so 54 cards over 60 of Mohit's games,
  // median 314cp lost, got none of the treatment a faulted move gets.
  test("serious is not forgotten again", () => {
    expect(FAULTED_SEVERITIES.has("serious")).toBe(true);
  });

  // An `inaccuracy` card is graded `good` in the practical tier and carries
  // the canonical word elsewhere, so the set keeps it even though stored
  // cards rarely say it. Dropping it would silently narrow the gate again.
  test("inaccuracy stays in the set", () => {
    expect(FAULTED_SEVERITIES.has("inaccuracy")).toBe(true);
  });
});

describe("namesMoveInText", () => {
  const NXE4 =
    "You develop the bishop, bringing a new piece into the game. Though " +
    "Nxe4 was a bit stronger, it gives up material, and dxe4 wins the " +
    "knight on e4.";

  test("finds the better move Mohit's card names", () => {
    expect(namesMoveInText(NXE4, "Nxe4")).toBe(true);
  });

  test("a move the caption never mentions is not found", () => {
    expect(namesMoveInText(NXE4, "Qh5")).toBe(false);
  });

  // Word-bounded, or "d5" matches inside "Nd5" and the board offers a move
  // the player never read about.
  test("does not match inside a longer SAN", () => {
    expect(namesMoveInText("You post the knight on Nd5 here.", "d5")).toBe(false);
    expect(namesMoveInText("Though dxe4 was stronger", "e4")).toBe(false);
    expect(namesMoveInText("Rxf5 is a serious mistake.", "f5")).toBe(false);
  });

  test("matches a bare SAN next to punctuation", () => {
    expect(namesMoveInText("d5 forks the bishop and the knight.", "d5")).toBe(true);
    expect(namesMoveInText("Stronger was Be3.", "Be3")).toBe(true);
    expect(namesMoveInText("(Nf3) holds", "Nf3")).toBe(true);
  });

  // These carry characters a built regex reads as syntax. The helper scans
  // instead of building one, so they are found rather than throwing from
  // inside a render.
  test("castling, check and mate SANs are safe", () => {
    expect(namesMoveInText("O-O was better here.", "O-O")).toBe(true);
    expect(namesMoveInText("Qh5+ was stronger.", "Qh5+")).toBe(true);
    expect(namesMoveInText("Rf8# ends it.", "Rf8#")).toBe(true);
    expect(namesMoveInText("exd8=Q promotes.", "exd8=Q")).toBe(true);
  });

  test("empty inputs are not a match", () => {
    expect(namesMoveInText("", "Nf3")).toBe(false);
    expect(namesMoveInText("Nf3 was better", null)).toBe(false);
    expect(namesMoveInText(null, null)).toBe(false);
  });
});

// Mohit 2026-10-28: "for move from both sides, inaccuracy, mistakes or
// blunders". The why button used to test `isUser && (blunder || mistake)`,
// which missed their moves entirely, our `serious` tier, and our
// inaccuracies -- which the practical tier files under `good`.
describe("faulted moves on either side", () => {
  // Measured over 120 games: opponent cards carry opp_inaccuracy (521),
  // opp_mistake (275), opp_serious (64), opp_blunder (84).
  test.each(["opp_inaccuracy", "opp_mistake", "opp_serious", "opp_blunder"])(
    "%s is a faulted move",
    (tier) => {
      expect(isFaultedSeverity(tier)).toBe(true);
    }
  );

  test("their quiet moves are not", () => {
    expect(isFaultedSeverity("context")).toBe(false);
    expect(isFaultedSeverity("opp_good")).toBe(false);
  });

  // 600 of 2,389 of his `good` cards are canonically inaccuracies, 5 a
  // game. Reading severity alone calls those fine moves.
  test("our own inaccuracy hides under good, in severity_canonical", () => {
    const card = { severity: "good", severity_canonical: "inaccuracy" };
    expect(isFaultedSeverity(card.severity)).toBe(false);
    expect(gradeOf(card)).toBe("inaccuracy");
    expect(isFaultedCard(card)).toBe(true);
  });

  test("a genuinely good move stays good", () => {
    const card = { severity: "good", severity_canonical: "good" };
    expect(gradeOf(card)).toBe("good");
    expect(isFaultedCard(card)).toBe(false);
    expect(isFaultedCard({ severity: "context" })).toBe(false);
    expect(isFaultedCard({})).toBe(false);
    expect(isFaultedCard(null)).toBe(false);
  });

  test("the practical grade wins when it is already a fault", () => {
    // A blunder whose canonical grade is milder must stay a blunder.
    expect(gradeOf({ severity: "blunder", severity_canonical: "mistake" }))
      .toBe("blunder");
    expect(gradeOf({ severity: "opp_blunder" })).toBe("opp_blunder");
  });

  test.each(["mistake", "serious", "blunder"])(
    "our %s still qualifies", (tier) => {
      expect(isFaultedCard({ severity: tier })).toBe(true);
    });

  // 2026-11-05, Be2 at move 6 of 5e68fc88: the book-move gate withdrew both
  // grades to good, the caption still read "Be2 was a mistake", the badge
  // (which reads the caption's word first) said Mistake, and the card had no
  // why button. 998 stored cards across 20,139 games had that shape.
  test("a card whose own caption calls the move a fault gets the button", () => {
    const card = { severity: "good", severity_canonical: "good", caption_severity_word: "mistake" };
    expect(gradeOf(card)).toBe("mistake");
    expect(isFaultedCard(card)).toBe(true);
    expect(isFaultedCard({ severity: "good", severity_canonical: "good", caption_severity_word: "inaccuracy" })).toBe(true);
  });

  test("a caption word that is not a fault changes nothing", () => {
    expect(isFaultedCard({ severity: "good", caption_severity_word: "good" })).toBe(false);
    expect(isFaultedCard({ severity: "good", caption_severity_word: null })).toBe(false);
    expect(gradeOf({ severity: "good", caption_severity_word: "best" })).toBe("good");
  });
});
