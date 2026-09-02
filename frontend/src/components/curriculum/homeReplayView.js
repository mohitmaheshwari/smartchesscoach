/**
 * View logic for the Home replay diagnostic, kept out of the component so it
 * can be tested directly.
 *
 * Each function here exists because of a defect a real user hit on 2026-09-02:
 * the board never showed the played move, the diagnostic never said whether the
 * move worked, and one sentence rendered three times on a single screen.
 */
import { Chess } from "chess.js";

/**
 * The position AFTER the player's move, or null when it cannot be derived.
 *
 * The component previously re-rendered the ORIGINAL fen forever, so a submitted
 * move left the piece visibly sitting on its old square while the text claimed
 * a move had been played.
 *
 * Returns null rather than throwing: an unparseable fen or illegal move must
 * leave the board showing the original position, never crash the lesson.
 */
export function fenAfterMove(fen, moveSan) {
  if (!fen || !moveSan) return null;
  try {
    const board = new Chess(fen);
    const played = board.move(moveSan, { sloppy: true });
    return played ? board.fen() : null;
  } catch (_error) {
    return null;
  }
}

/**
 * Whether the move satisfied the idea being taught, and separately whether it
 * was materially sound.
 *
 * The backend already returns `target_result` and `soundness` and explicitly
 * keeps the target result visible; the UI simply never rendered them, so a
 * diagnostic told the player nothing about their own move.
 *
 * The two are reported separately on purpose: a move can satisfy the taught
 * idea (every piece safe) while still losing material for an unrelated reason,
 * and collapsing those into one verdict would teach the wrong lesson.
 *
 * Returns null when the result is unmeasured — silence rather than a guess.
 */
export function moveVerdict(session) {
  const target = session?.target_result;
  if (target !== "pass" && target !== "fail") return null;
  const soundness = (session?.soundness || {}).status;
  const kept = target === "pass";
  return {
    kept,
    headline: kept
      ? "Every piece stayed safe."
      : "That left a piece where it can be taken.",
    soundnessNote:
      soundness === "serious_problem"
        ? "Separately, this move loses material for another reason."
        : null,
  };
}

/**
 * Anchors with nothing already on screen repeated back.
 *
 * `why_now` and an anchor frequently carry the identical sentence, which
 * rendered it twice in the evidence panel and a third time in the page header.
 */
export function dedupeAnchors(anchors, whyNow) {
  const seen = new Set();
  const already = String(whyNow || "").trim();
  return (anchors || []).filter((anchor) => {
    const message = String(anchor?.message || "").trim();
    if (!message || message === already || seen.has(message)) return false;
    seen.add(message);
    return true;
  });
}
