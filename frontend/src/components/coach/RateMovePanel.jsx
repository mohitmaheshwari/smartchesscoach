/**
 * RateMovePanel — "Rate Your Move" self-grade (PWC premium, twin of PredictMovePanel).
 *
 * After the student moves, before the verdict shows, they grade their own move (Good / Inaccuracy /
 * Mistake-or-Blunder). The actual quality is already known (from the V5 feedback) and held by the parent;
 * this panel withholds it, takes the guess, logs it (/rate-move/log), then reveals. Fail-open: on any
 * error it just reveals the verdict. See docs/rate_your_move_scope.md.
 */
import { useState } from "react";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { ClipboardCheck, CheckCircle2, ChevronRight } from "lucide-react";

const OPTIONS = [
  { key: "good", label: "Good" },
  { key: "inaccuracy", label: "Inaccuracy" },
  { key: "mistake_blunder", label: "Mistake / Blunder" },
];

const QUALITY_PHRASE = {
  best: "a strong move",
  good: "a good move",
  inaccuracy: "an inaccuracy",
  mistake: "a mistake",
  blunder: "a blunder",
};

const RateMovePanel = ({ playedMove, fenBefore, actualQuality, revealText, sessionId, onComplete }) => {
  const [guess, setGuess] = useState(null);
  const [result, setResult] = useState(null); // { correct }
  const [submitting, setSubmitting] = useState(false);

  const submit = async (bucketKey) => {
    if (submitting || result) return;
    setGuess(bucketKey);
    setSubmitting(true);
    try {
      const res = await fetch(`${API}/coach/play/rate-move/log`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: sessionId,
          guessed_quality: bucketKey,
          actual_quality: actualQuality,
          fen_before: fenBefore,
          played_move: playedMove,
          options: OPTIONS.map((o) => o.key),
        }),
      });
      const data = res.ok ? await res.json() : { correct: false };
      setResult({ correct: !!data.correct });
    } catch {
      setResult({ correct: false }); // fail-open: still reveal
    } finally {
      setSubmitting(false);
    }
  };

  const phrase = QUALITY_PHRASE[(actualQuality || "").toLowerCase()] || "worth a look";

  // ── Grade (no guess yet) ───────────────────────────────────────────────
  if (!result) {
    return (
      <div
        className="rounded-xl border border-amber-500/30 bg-gradient-to-b from-amber-500/10 to-transparent shadow-sm overflow-hidden"
        data-testid="rate-move-panel"
      >
        <div className="px-3.5 py-2.5 flex items-center gap-2 border-b border-amber-500/20 bg-amber-500/10">
          <ClipboardCheck className="w-4 h-4 text-amber-500" />
          <span className="text-xs font-semibold text-amber-600 dark:text-amber-400 uppercase tracking-wide">
            Rate Your Move
          </span>
        </div>
        <div className="p-3.5 space-y-3">
          <p className="text-sm font-medium text-foreground leading-relaxed">
            You played <span className="font-mono font-bold">{playedMove}</span>. How was that move?
          </p>
          <div className="grid grid-cols-1 gap-2">
            {OPTIONS.map((o) => (
              <button
                key={o.key}
                onClick={() => submit(o.key)}
                disabled={submitting}
                data-testid={`rate-option-${o.key}`}
                className="rounded-lg border border-border bg-card px-3 py-2.5 text-left text-sm font-semibold text-foreground transition-all hover:border-amber-500 hover:bg-amber-500/10 hover:shadow-md disabled:opacity-50"
              >
                {o.label}
              </button>
            ))}
          </div>
          <p className="text-[11px] text-muted-foreground italic">No pressure — this trains your eye.</p>
        </div>
      </div>
    );
  }

  // ── Reveal ─────────────────────────────────────────────────────────────
  const correct = result.correct;
  return (
    <div
      className={`rounded-xl border shadow-sm overflow-hidden ${
        correct
          ? "border-emerald-500/40 bg-gradient-to-b from-emerald-500/10 to-transparent"
          : "border-amber-500/30 bg-gradient-to-b from-amber-500/5 to-transparent"
      }`}
      data-testid="rate-move-reveal"
    >
      <div
        className={`px-3.5 py-2.5 flex items-center gap-2 border-b ${
          correct ? "border-emerald-500/20 bg-emerald-500/10" : "border-amber-500/20 bg-amber-500/10"
        }`}
      >
        {correct ? (
          <CheckCircle2 className="w-4 h-4 text-emerald-500" />
        ) : (
          <ClipboardCheck className="w-4 h-4 text-amber-500" />
        )}
        <span
          className={`text-xs font-semibold uppercase tracking-wide ${
            correct ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"
          }`}
        >
          {correct ? "You read it right" : "Take another look"}
        </span>
      </div>
      <div className="p-3.5 space-y-3">
        <p className="text-sm text-foreground">
          {correct ? "Right — that was " : "Actually, that was "}
          <span className="font-semibold">{phrase}</span>.
        </p>
        {revealText && (
          <p className="text-sm text-muted-foreground leading-relaxed border-l-2 border-amber-500/40 pl-3 italic">
            {revealText}
          </p>
        )}
        <Button
          onClick={() => onComplete?.(result)}
          size="sm"
          className="w-full bg-amber-600 hover:bg-amber-700 text-white"
          data-testid="rate-continue"
        >
          Got it <ChevronRight className="w-4 h-4 ml-1" />
        </Button>
      </div>
    </div>
  );
};

export default RateMovePanel;
