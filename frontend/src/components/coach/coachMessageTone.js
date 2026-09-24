/**
 * What tone should a coaching message be shown in?
 *
 * CoachPlaySidebar currently decides this with a 184-line ternary chain that
 * maps 41 message types to 12 different hues. The suffix already carries the
 * meaning and does so consistently:
 *
 *   *_affirm   -> emerald, all 10 of them
 *   *_nag      -> orange,  all 12 of them
 *   *_warning  -> varies BY TOPIC: piece_safety teal, king_safety red,
 *                 piece_activity indigo, endgame amber, pawn_structure slate,
 *                 missed_tactic yellow, calculation_depth purple
 *   *_streak   -> the same topic hue again
 *
 * So the rainbow is not semantic, it is a topic index. A player would have to
 * learn seven topic colours to read their own sidebar, and the topics are our
 * internal cognitive-gap taxonomy rather than anything they think in. The
 * approved design spends its accent on ONE thing at a time.
 *
 * Four tones instead, derived from the suffix so a new message type gets the
 * right treatment without anyone editing a chain:
 *
 *   good     something went right
 *   nudge    a habit to watch, said quietly
 *   warn     the coach is concerned about this position
 *   info     teaching or context, carrying no verdict
 *
 * Tone maps to the existing --pwc-ok / --pwc-warn / --pwc-bad tokens and a
 * neutral panel, so it follows the theme instead of hardcoding hues.
 */

export const TONES = ["good", "nudge", "warn", "info"];

/** Types whose tone the suffix rule would get wrong. */
const EXPLICIT = {
  v5_teaching: "info",
  habit_prompt: "info",
  opening_announcement: "info",
  opening_critical_moment: "warn",
  impulse_warning: "warn",
  pre_move_nag: "nudge",
  pace_check: "nudge",
  focus_coach: "info",
  fast_good_affirm: "good",
};

/** Tone for a coaching message type. Unknown types read as neutral. */
export const toneForMessageType = (type) => {
  const t = String(type || "");
  if (!t) return "info";
  if (EXPLICIT[t]) return EXPLICIT[t];
  if (t.endsWith("_affirm")) return "good";
  if (t.endsWith("_nag")) return "nudge";
  // A streak is the same concern repeating, not a louder one. Same tone as a
  // warning; repetition is said in words, not by escalating colour, because a
  // sidebar that gets redder as the game goes on is a failure scoreboard.
  if (t.endsWith("_warning") || t.endsWith("_streak")) return "warn";
  return "info";
};

/** Panel classes for a tone. One accent at a time; neutral by default. */
export const panelClassForTone = (tone) => {
  switch (tone) {
    case "good":
      return "border-[color:var(--pwc-ok)]/35 bg-[color:var(--pwc-ok)]/[0.07]";
    case "warn":
      return "border-[color:var(--pwc-warn)]/40 bg-[color:var(--pwc-warn)]/[0.08]";
    case "nudge":
      return "border-border bg-muted/40";
    case "info":
    default:
      return "border-border bg-muted/25";
  }
};

export const panelClassForMessageType = (type) =>
  panelClassForTone(toneForMessageType(type));

export default toneForMessageType;
