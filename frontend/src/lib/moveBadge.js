// Which badge the board draws on a reviewed move, and whether it draws one.
//
// Pulled out of the JSX closure in GameDecryptionV5 on 2026-09-29 so it can be
// tested. Behaviour is unchanged except for the opp_ prefix, noted below.

export const BADGE_TIERS = new Set([
  "brilliant", "best", "excellent", "good", "book",
  "inaccuracy", "mistake", "blunder", "miss",
]);

/** The severity word R12 used in the caption, so badge and words agree. */
export function tierFromCaption(move) {
  if (!move) return null;
  if (move.caption_severity_word) return move.caption_severity_word;
  // Legacy documents written before that field existed still carry the word
  // in their text; they get backfilled on the next V5 re-render.
  const narrative = (move.narrative || "").toLowerCase();
  if (narrative.includes("is a major blunder")) return "blunder";
  if (narrative.includes("is a serious mistake")) return "mistake";
  if (narrative.includes("is a mistake")) return "mistake";
  if (narrative.includes("is an inaccuracy")) return "inaccuracy";
  return null;
}

/**
 * The badge tier for a move, or null for no badge.
 *
 * The opp_ strip is the fix for Mohit 2026-09-29: "some opponent moves just
 * doesn't tell if they are good, blunder or you know?" The backend names the
 * opponent's tiers opp_inaccuracy / opp_mistake / opp_blunder, and the board's
 * icon table has no such keys, so those cards drew nothing at all. An opponent
 * move was badged only when its caption text happened to contain "is a
 * mistake" or "is an inaccuracy" for the parse above to catch -- which is why
 * Qd6 (76cp) and Qa5 (352cp) were badged and Bg4 (53cp), captioned "Lines up
 * the knight on f3 in front of the queen", was silent.
 */
export function resolveBadgeTier(move) {
  if (!move) return null;

  const fromCaption = tierFromCaption(move);
  if (fromCaption) return fromCaption;

  let severity = move.severity;
  if (typeof severity === "string" && severity.startsWith("opp_")) {
    severity = severity.slice(4);
  }

  // Nothing usable on an opponent card: say how the move went from its cost,
  // rather than leaving the player unable to tell good from bad.
  if ((!severity || severity === "context" || severity === "good") && !move.is_user_move) {
    const cpLoss = Math.abs(move.cp_loss || 0);
    if (cpLoss >= 200) severity = "blunder";
    else if (cpLoss >= 100) severity = "mistake";
    else if (cpLoss >= 50) severity = "inaccuracy";
    else if (cpLoss <= 5) severity = "best";
    else severity = "good";
  }

  if (!severity || severity === "context") return null;
  // A tier the board cannot draw is the same as no badge, so never return one.
  return BADGE_TIERS.has(severity) ? severity : null;
}
