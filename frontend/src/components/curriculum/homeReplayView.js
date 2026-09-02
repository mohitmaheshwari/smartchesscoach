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
 * Whether the move was right, and separately whether it was materially sound.
 *
 * TWO graders reach this function and they prove DIFFERENT things, so the
 * headline must never borrow a claim the answering grader did not establish:
 *
 *   home_replay_diagnostic.v2  -> target_result pass/fail. Proves what happened
 *                                 to the moved piece. May claim piece safety.
 *   verified_puzzle_admission  -> correct true/false only. Proves the move
 *                                 matched the frozen accepted answer, and
 *                                 NOTHING about whether a piece is safe.
 *
 * The second grader is what the concept lessons actually run, and it returns
 * no target_result. Reading only target_result therefore returned null for
 * every real lesson move and the player was told nothing at all -- reported
 * 2026-09-02 as "it doesn't tell me the move is right or wrong".
 *
 * Returns null only when the result is genuinely unmeasured -- silence rather
 * than a guess, but never silence when the backend did decide.
 */
export function moveVerdict(session) {
  const target = session?.target_result;
  const soundness = (session?.soundness || {}).status;
  const soundnessNote =
    soundness === "serious_problem"
      ? "Separately, this move loses material for another reason."
      : null;

  if (target === "pass" || target === "fail") {
    const kept = target === "pass";
    return {
      kept,
      headline: kept
        ? "Every piece stayed safe."
        : "That left a piece where it can be taken.",
      soundnessNote,
      answerSan: session?.answer_san || null,
    };
  }

  // The puzzle grader decided, but only about the answer -- not piece safety.
  if (target === undefined || target === null) {
    if (session?.correct === true) {
      return {
        kept: true,
        headline: "That's the move.",
        soundnessNote,
        answerSan: session?.answer_san || null,
      };
    }
    if (session?.correct === false) {
      const answer = session?.answer_san;
      return {
        kept: false,
        headline: answer
          ? `Not this one — ${answer} was the move.`
          : "Not this one.",
        soundnessNote,
        answerSan: answer || null,
      };
    }
  }

  return null;
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
