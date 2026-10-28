/**
 * Which cards in one review may animate.
 *
 * Mohit 2026-10-28, on the measurement rather than on the screen: the same
 * recommendation comes back on consecutive cards when the player keeps
 * missing it. In one game Rxf4 is the engine's move at moves 31, 32 and 35,
 * and Nxh3+ at 19, 20 and 21 of another -- so the identical line would play
 * three times in one review. The second showing teaches nothing the first
 * did not, and three is the thing that makes a feature feel broken.
 *
 * Decided by position in the game, never by what has been watched. A
 * "seen" set would mean a card animates or not depending on how the player
 * arrived at it, and arrowing back would silently change the page. Here the
 * first card carrying a recommendation always animates and the later ones
 * never do, however you reach them.
 */

/**
 * What makes two cards the same recommendation: the thing being taken.
 *
 * Not the move. Picked from the data, not from taste. In the game that
 * prompted this, the engine says "take the knight on f4" at moves 31, 32
 * and 35, but the rook has moved in between -- g4f4, g4f4, h4f4 -- so a key
 * of from+to treats the third as new and plays the same lesson again.
 * Measured over 201 games: from+to suppresses 10 firings, the target
 * suppresses 13, and keying on the landing square alone suppresses the same
 * 13, which says no two of these ever take different pieces on one square.
 * The target is the more specific of the two for the same result, so it is
 * the one used.
 *
 * It comes off tactic_trigger rather than the move, so the four cards that
 * ship no best_move_uci are covered too.
 */
export const recommendationKey = (card) => {
  const trigger = card?.tactic_trigger;
  if (trigger?.victim && trigger?.square) {
    return `${trigger.victim}@${trigger.square}`;
  }
  const uci = card?.best_move_uci;
  if (uci && String(uci).length >= 4) return String(uci).slice(0, 4);
  const san = card?.best_move_san || card?.best_move;
  return san ? `san:${san}` : null;
};

/** Is this card one the board may animate at all? */
export const cardCanAnimate = (card) =>
  Boolean(card && card.is_user_move && !card.is_best_move && card.tactic_trigger);

/**
 * True only for the first card in the game that carries this recommendation.
 */
export const shouldAnimateCard = (cards, index) => {
  const card = cards?.[index];
  if (!cardCanAnimate(card)) return false;
  const key = recommendationKey(card);
  if (!key) return true;
  for (let i = 0; i < index; i += 1) {
    const earlier = cards[i];
    if (!cardCanAnimate(earlier)) continue;
    if (recommendationKey(earlier) === key) return false;
  }
  return true;
};
