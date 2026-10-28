/**
 * The same recommendation animates once per game, not every time it recurs.
 *
 * The case is real: in game_fcee5af2 the engine's move is Rxf4 at moves 31,
 * 32 and 35, because the player kept not playing it, so the identical line
 * would animate three times in one review.
 */
import {
  cardCanAnimate,
  recommendationKey,
  shouldAnimateCard,
} from "./animationSchedule";

const card = (over = {}) => ({
  is_user_move: true,
  is_best_move: false,
  tactic_trigger: { attacker: "rook", victim: "knight", square: "f4",
                    defenders: ["e5"] },
  best_move_uci: "f1f4",
  best_move_san: "Rxf4",
  ...over,
});

describe("shouldAnimateCard", () => {
  test("the first card carrying a recommendation animates", () => {
    expect(shouldAnimateCard([card()], 0)).toBe(true);
  });

  test("the same recommendation later in the game does not", () => {
    const cards = [card(), card(), card()];
    expect(cards.map((_, i) => shouldAnimateCard(cards, i)))
      .toEqual([true, false, false]);
  });

  test("a different recommendation still animates", () => {
    const cards = [
      card(),
      card({ best_move_uci: "g1h3", best_move_san: "Nxh3+",
             tactic_trigger: { attacker: "knight", victim: "pawn",
                               square: "h3", defenders: ["g2"] } }),
    ];
    expect(cards.map((_, i) => shouldAnimateCard(cards, i)))
      .toEqual([true, true]);
  });

  test("the decision does not depend on how you got there", () => {
    const cards = [card(), card()];
    // Asked repeatedly and out of order, the answers never move.
    for (const i of [1, 0, 1, 1, 0]) {
      expect(shouldAnimateCard(cards, i)).toBe(i === 0);
    }
  });

  // A card with no trigger is not a showing, so it must not consume the
  // first slot and leave the real one suppressed.
  test("a card without a trigger does not count as having shown it", () => {
    const cards = [card({ tactic_trigger: null }), card()];
    expect(cards.map((_, i) => shouldAnimateCard(cards, i)))
      .toEqual([false, true]);
  });

  test("the opponent's cards do not count either", () => {
    const cards = [card({ is_user_move: false }), card()];
    expect(cards.map((_, i) => shouldAnimateCard(cards, i)))
      .toEqual([false, true]);
  });

  test("a card where you played the engine's move never animates", () => {
    expect(shouldAnimateCard([card({ is_best_move: true })], 0)).toBe(false);
  });

  test("no trigger, no animation", () => {
    expect(shouldAnimateCard([card({ tactic_trigger: null })], 0)).toBe(false);
    expect(shouldAnimateCard([], 0)).toBe(false);
    expect(shouldAnimateCard(null, 0)).toBe(false);
  });
});

describe("recommendationKey", () => {
  test("it is the thing being taken, not the move", () => {
    expect(recommendationKey(card())).toBe("knight@f4");
  });

  // The case this exists for. game_fcee5af2: "take the knight on f4" at
  // moves 31, 32 and 35, but the rook moves in between -- g4f4, g4f4, h4f4
  // -- so a from+to key calls the third one new and replays the lesson.
  test("the same target from a different square is the same lesson", () => {
    const cards = [
      card({ best_move_uci: "g4f4" }),
      card({ best_move_uci: "g4f4" }),
      card({ best_move_uci: "h4f4" }),
    ];
    expect(new Set(cards.map(recommendationKey)).size).toBe(1);
    expect(cards.map((_, i) => shouldAnimateCard(cards, i)))
      .toEqual([true, false, false]);
  });

  test("a different target is a different lesson", () => {
    const a = card();
    const b = card({ tactic_trigger: { attacker: "rook", victim: "bishop",
                                       square: "d3", defenders: ["c2"] } });
    expect(recommendationKey(a)).not.toBe(recommendationKey(b));
  });

  test("the move is the fallback when there is no trigger detail", () => {
    const bare = card({ tactic_trigger: {} });
    expect(recommendationKey(bare)).toBe("f1f4");
    expect(recommendationKey(card({ tactic_trigger: {}, best_move_uci: null })))
      .toBe("san:Rxf4");
  });

  test("a card naming nothing at all has no key", () => {
    expect(recommendationKey(card({ tactic_trigger: {}, best_move_uci: null,
                                    best_move_san: null, best_move: null })))
      .toBe(null);
  });
});

describe("cardCanAnimate", () => {
  test("it needs all four things", () => {
    expect(cardCanAnimate(card())).toBe(true);
    expect(cardCanAnimate(card({ is_user_move: false }))).toBe(false);
    expect(cardCanAnimate(card({ is_best_move: true }))).toBe(false);
    expect(cardCanAnimate(card({ tactic_trigger: null }))).toBe(false);
    expect(cardCanAnimate(null)).toBe(false);
  });
});
