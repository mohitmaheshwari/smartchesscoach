import React from "react";

/**
 * PunishmentPuzzleCard — interactive teaching moment.
 *
 * When the coach plays an exploitable move, the backend arms a
 * `active_puzzle` on the session and pushes a `puzzle_armed` event.
 * This card renders the prompt: observation + challenge. The user's
 * next move (whatever they play) is then evaluated by the backend
 * and returned in /move's `puzzle_feedback` field — at that point
 * we transition to the "resolved" state showing solved/close/missed
 * feedback.
 *
 * No buttons in MVP. The user just plays their next move on the
 * board; the card auto-transitions.
 *
 * Props:
 *   - puzzle:   { observation, challenge, target_square, pattern_type }
 *               null when no armed puzzle
 *   - feedback: { outcome, user_san, feedback_text, pattern_type }
 *               null until the user submits a response
 *   - flagCtx:  optional flag context for tester feedback button
 */
export default function PunishmentPuzzleCard({ puzzle, feedback, flagCtx }) {
  // Resolved state takes priority: once the user has answered, show
  // their outcome until the next coach move clears it.
  if (feedback) {
    const colorClasses =
      feedback.outcome === "solved"
        ? "border-emerald-400/35 from-emerald-500/[0.05]"
        : feedback.outcome === "close"
          ? "border-amber-400/35 from-amber-500/[0.05]"
          : "border-zinc-400/30 from-zinc-500/[0.04]";
    const eyebrowColor =
      feedback.outcome === "solved"
        ? "text-emerald-500 dark:text-emerald-300"
        : feedback.outcome === "close"
          ? "text-amber-500 dark:text-amber-300"
          : "text-zinc-500 dark:text-zinc-400";
    const eyebrow =
      feedback.outcome === "solved"
        ? "Solved"
        : feedback.outcome === "close"
          ? "Close"
          : "Almost";
    return (
      <article
        className={`rounded-2xl border ${colorClasses} bg-gradient-to-b to-transparent p-5 space-y-2`}
      >
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className={`text-[10.5px] uppercase tracking-[0.22em] font-semibold ${eyebrowColor}`}
          >
            {eyebrow}
          </span>
          {feedback.user_san && (
            <span className="font-mono text-[11.5px] text-muted-foreground tabular-nums">
              {feedback.user_san}
            </span>
          )}
        </div>
        <p className="font-serif text-[17px] leading-[1.3] tracking-[-0.005em] text-foreground">
          {feedback.feedback_text}
        </p>
      </article>
    );
  }

  // Armed state: show observation + challenge
  if (!puzzle) return null;

  return (
    <article className="rounded-2xl border border-blue-400/35 bg-gradient-to-b from-blue-500/[0.06] to-transparent p-5 space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-[10.5px] uppercase tracking-[0.22em] font-semibold text-blue-500 dark:text-blue-300">
          Find the move
        </span>
        {puzzle.target_square && (
          <span className="font-mono text-[11.5px] text-muted-foreground tabular-nums">
            target: {puzzle.target_square}
          </span>
        )}
      </div>
      <p className="font-serif text-[17px] leading-[1.3] tracking-[-0.005em] text-foreground">
        {puzzle.observation}
      </p>
      <p className="text-[14px] leading-[1.4] text-foreground/80 italic">
        {puzzle.challenge}
      </p>
      <p className="text-[12px] text-muted-foreground">
        Play your move on the board to see if you got it.
      </p>
    </article>
  );
}
