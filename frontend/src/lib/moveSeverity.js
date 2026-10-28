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

/** Did the engine fault this move? */
export const isFaultedSeverity = (severity) =>
  FAULTED_SEVERITIES.has(String(severity || "good"));

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
