/**
 * The engine's move grades, and whether a caption names a move.
 *
 * Both of these were inline in GameDecryptionV5.jsx, and both were wrong
 * there in a way reading the file could not show:
 *
 *  - the severity test listed three tiers of the five the backend assigns,
 *    so `serious` -- 250-399cp, the second-worst grade there is -- matched
 *    nothing, and 54 cards over 60 of Mohit's games were treated as if the
 *    move had been fine;
 *  - nothing checked whether the caption named the better move, so the
 *    "See on board" button, the only thing that draws best_move_arrows,
 *    never appeared on a card graded `good` whose text said "Though Nxe4
 *    was a bit stronger". The arrow was computed, stored, and shown to
 *    nobody (Mohit 2026-10-28: "does it also show arrow?").
 *
 * Kept here, with no imports, so they can be tested without standing up the
 * board, the router and the chart stack.
 */

/**
 * Everything but `good`, from backend/services/severity.py:73
 * (TIER_ORDER = good / inaccuracy / mistake / serious / blunder).
 */
export const FAULTED_SEVERITIES = new Set([
  "inaccuracy",
  "mistake",
  "serious",
  "blunder",
]);

/**
 * Did the engine fault this move, on either side?
 *
 * Opponent cards carry the same grades behind an `opp_` prefix
 * (opp_inaccuracy / opp_mistake / opp_serious / opp_blunder), measured
 * over 120 games. A test written for one side silently covers none of
 * the other, which is how the why button came to exist only for us.
 */
export const isFaultedSeverity = (severity) => {
  const s = String(severity || "good");
  return FAULTED_SEVERITIES.has(s.startsWith("opp_") ? s.slice(4) : s);
};

/**
 * The grade to judge a card by.
 *
 * On our own cards the practical tier files an inaccuracy under `good`
 * and keeps the real grade in severity_canonical -- 600 of 2,389 `good`
 * cards over 120 games, 5 a game. Reading `severity` alone therefore
 * calls an inaccuracy a fine move, which is why ours never got a why
 * button while the opponent's opp_inaccuracy cards would have.
 */
export const gradeOf = (card) => {
  const practical = String(card?.severity || "good");
  if (isFaultedSeverity(practical)) return practical;
  const canonical = String(card?.severity_canonical || "");
  if (isFaultedSeverity(canonical)) return canonical;
  // The word the caption itself used. The badge leads with it
  // (moveBadge.js tierFromCaption), so when both grades were withdrawn
  // but the sentence still says "was a mistake", the player is shown a
  // Mistake badge, a mistake caption and no way to ask why. Mohit
  // 2026-11-05 on Be2, move 6 of 5e68fc88 (book-move gate set both grades
  // to good, caption kept the word): "it doesn't show why bad button?".
  // 998 stored cards across 20,139 games had that shape. If the card says
  // it, the player can ask.
  const word = String(card?.caption_severity_word || "");
  return isFaultedSeverity(word) ? word : practical;
};

/** Does this card describe a move the engine faulted, either side? */
export const isFaultedCard = (card) => isFaultedSeverity(gradeOf(card));

/**
 * The why button's words.
 *
 * A card of ours whose lead grade is good still gets the button when the
 * engine's real grade is an inaccuracy (gradeOf above), and on that card
 * "Why was this bad?" contradicts the Good badge beside it. Mohit
 * 2026-11-11 on 4...Bc5 of 2d86e1f9 ("it's not a bad move"): ask about the
 * better move instead -- "Why is Nf6 better?".
 */
/**
 * Did a published coach study write this card's caption?
 *
 * Then the card says so ("Studied by the coach", the Why box's own words) and
 * shows no Why button: its answer would repeat the caption word for word.
 * docs/why_study_on_card_scope.md, 2026-11-12.
 */
export const COACH_STUDY_LABEL = "Studied by the coach";
export const isCoachStudyCard = (card) => card?.caption_source === "coach_study";

export const whyButtonLabel = (card, opponent = false) => {
  const best = String(card?.best_move_san || "").trim();
  if (!opponent && best && !isFaultedSeverity(card?.severity)) {
    return `Why is ${best} better?`;
  }
  return "Why was this bad?";
};

/**
 * Does this text name this move?
 *
 * Word-bounded, or the better move `d5` is found inside "Nd5" and the board
 * offers a move the player never read about. Scanned rather than matched
 * with a built regex: a SAN carries characters a regex reads as syntax
 * ("Qh5+", "O-O"), and one bad escape throws from inside a render instead of
 * just missing a button.
 */
export const namesMoveInText = (text, san) => {
  if (!text || !san) return false;
  const hay = String(text);
  const needle = String(san);
  const isWordChar = (ch) =>
    (ch >= "0" && ch <= "9") ||
    (ch >= "a" && ch <= "z") ||
    (ch >= "A" && ch <= "Z");
  for (let i = hay.indexOf(needle); i !== -1; i = hay.indexOf(needle, i + 1)) {
    const before = i > 0 ? hay[i - 1] : "";
    const after = i + needle.length < hay.length ? hay[i + needle.length] : "";
    if (!isWordChar(before) && !isWordChar(after)) return true;
  }
  return false;
};
