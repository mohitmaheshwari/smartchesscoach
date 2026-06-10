/**
 * PredictMovePanel — "Call My Move" interactive prediction (PWC premium S2).
 *
 * Before the coach reveals its move, the student guesses it from 2-3 candidate options.
 * Tap a guess -> reveal (the coach's actual move + hit/miss + a one-line why). Every guess is
 * logged server-side (the student model's evidence). See docs/predict_coach_move_scope.md.
 *
 * Flow-independent + self-contained: it takes `options` + `sessionId`, calls /predict-move/answer
 * itself (mirrors EscapeSquaresQuiz), and hands the result to `onComplete` so the parent can apply
 * the coach's (now-revealed) move + advance the board.
 */
import { useState } from "react";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Sparkles, CheckCircle2, ChevronRight } from "lucide-react";

const PredictMovePanel = ({ options = [], prompt, sessionId, onComplete }) => {
  const [guess, setGuess] = useState(null);
  const [result, setResult] = useState(null); // { correct, coach_move, reveal, ... }
  const [submitting, setSubmitting] = useState(false);

  const submit = async (move) => {
    if (submitting || result) return;
    setGuess(move);
    setSubmitting(true);
    try {
      const res = await fetch(`${API}/coach/play/predict-move/answer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ session_id: sessionId, guessed_move: move }),
      });
      if (res.ok) {
        setResult(await res.json());
      } else {
        onComplete?.(null); // fail open — never block the game on a prediction
      }
    } catch {
      onComplete?.(null);
    } finally {
      setSubmitting(false);
    }
  };

  // ── Prompt (no guess yet) ──────────────────────────────────────────────
  if (!result) {
    return (
      <div
        className="rounded-xl border border-indigo-500/30 bg-gradient-to-b from-indigo-500/10 to-transparent shadow-sm overflow-hidden"
        data-testid="predict-move-panel"
      >
        <div className="px-3.5 py-2.5 flex items-center gap-2 border-b border-indigo-500/20 bg-indigo-500/10">
          <Sparkles className="w-4 h-4 text-indigo-500" />
          <span className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 uppercase tracking-wide">
            Call My Move
          </span>
        </div>
        <div className="p-3.5 space-y-3">
          <p className="text-sm font-medium text-foreground leading-relaxed">
            {prompt || "I'm about to move — what do you think I'll play?"}
          </p>
          <div className="grid grid-cols-3 gap-2">
            {options.map((mv) => (
              <button
                key={mv}
                onClick={() => submit(mv)}
                disabled={submitting}
                data-testid={`predict-option-${mv}`}
                className="rounded-lg border border-border bg-card px-2 py-3 text-center font-mono text-base font-semibold text-foreground transition-all hover:border-indigo-500 hover:bg-indigo-500/10 hover:shadow-md hover:-translate-y-0.5 active:translate-y-0 disabled:opacity-50"
              >
                {mv}
              </button>
            ))}
          </div>
          <p className="text-[11px] text-muted-foreground italic">
            Just a read on what you're seeing — no pressure.
          </p>
        </div>
      </div>
    );
  }

  // ── Reveal (after the guess) ───────────────────────────────────────────
  const correct = !!result.correct;
  return (
    <div
      className={`rounded-xl border shadow-sm overflow-hidden ${
        correct
          ? "border-emerald-500/40 bg-gradient-to-b from-emerald-500/10 to-transparent"
          : "border-indigo-500/30 bg-gradient-to-b from-indigo-500/5 to-transparent"
      }`}
      data-testid="predict-move-reveal"
    >
      <div
        className={`px-3.5 py-2.5 flex items-center gap-2 border-b ${
          correct ? "border-emerald-500/20 bg-emerald-500/10" : "border-indigo-500/20 bg-indigo-500/10"
        }`}
      >
        {correct ? (
          <CheckCircle2 className="w-4 h-4 text-emerald-500" />
        ) : (
          <Sparkles className="w-4 h-4 text-indigo-500" />
        )}
        <span
          className={`text-xs font-semibold uppercase tracking-wide ${
            correct ? "text-emerald-600 dark:text-emerald-400" : "text-indigo-600 dark:text-indigo-400"
          }`}
        >
          {correct ? "You called it" : "Here's what I played"}
        </span>
      </div>
      <div className="p-3.5 space-y-3">
        <div className="flex items-baseline gap-2 text-sm flex-wrap">
          <span className="font-semibold text-foreground">I played</span>
          <span className="font-mono text-base font-bold text-foreground">{result.coach_move}</span>
          {correct ? (
            <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400 text-xs font-medium">
              <CheckCircle2 className="w-3.5 h-3.5" /> nice — you saw it
            </span>
          ) : (
            guess && (
              <span className="text-xs text-muted-foreground">
                you guessed <span className="font-mono">{guess}</span>
              </span>
            )
          )}
        </div>
        {result.reveal && (
          <p className="text-sm text-muted-foreground leading-relaxed border-l-2 border-indigo-500/40 pl-3 italic">
            {result.reveal}
          </p>
        )}
        <Button
          onClick={() => onComplete?.(result)}
          size="sm"
          className="w-full bg-indigo-600 hover:bg-indigo-700 text-white"
          data-testid="predict-continue"
        >
          My move <ChevronRight className="w-4 h-4 ml-1" />
        </Button>
      </div>
    </div>
  );
};

export default PredictMovePanel;
