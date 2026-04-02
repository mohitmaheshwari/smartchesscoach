/**
 * EscapeSquaresQuiz — Interactive "Count the Escape Squares" prompt
 *
 * Appears in the coaching sidebar when the position is a good
 * teaching moment for counting escape squares.
 */

import { useState } from "react";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Crown, CheckCircle2, XCircle, ChevronRight, Eye } from "lucide-react";

const EscapeSquaresQuiz = ({ quiz, sessionId, onComplete }) => {
  const [selected, setSelected] = useState(null);
  const [result, setResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (selected === null) return;
    setSubmitting(true);
    try {
      const res = await fetch(`${API}/coach/play/escape-squares/answer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: sessionId,
          answer: selected,
          quiz_data: quiz,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setResult(data.result);
      }
    } catch (e) {
      console.error("Quiz submit error:", e);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDismiss = () => {
    onComplete?.(result);
  };

  // Answer choices: 0 through 6
  const choices = [0, 1, 2, 3, 4, 5, 6];

  return (
    <div
      className="rounded-lg border border-amber-500/30 bg-amber-500/5 overflow-hidden"
      data-testid="escape-squares-quiz"
    >
      {/* Header */}
      <div className="px-3 py-2 bg-amber-500/10 border-b border-amber-500/20 flex items-center gap-2">
        <Crown className="w-4 h-4 text-amber-500" />
        <span className="text-xs font-semibold text-amber-600 uppercase tracking-wide">
          Count Escape Squares
        </span>
      </div>

      <div className="p-3 space-y-3">
        {/* Prompt */}
        <p className="text-sm text-foreground leading-relaxed" data-testid="escape-quiz-prompt">
          {quiz.prompt}
        </p>

        {/* Hint */}
        {quiz.hint && !result && (
          <p className="text-xs text-muted-foreground italic flex items-center gap-1">
            <Eye className="w-3 h-3" />
            {quiz.hint}
          </p>
        )}

        {/* Answer Buttons */}
        {!result && (
          <div className="flex flex-wrap gap-1.5" data-testid="escape-quiz-choices">
            {choices.map((n) => (
              <button
                key={n}
                onClick={() => setSelected(n)}
                disabled={submitting}
                className={`w-9 h-9 rounded-lg text-sm font-medium transition-all border ${
                  selected === n
                    ? "bg-amber-500 text-white border-amber-600 shadow-sm"
                    : "bg-background border-border hover:border-amber-500/50 hover:bg-amber-500/10"
                }`}
                data-testid={`escape-choice-${n}`}
              >
                {n}
              </button>
            ))}
          </div>
        )}

        {/* Submit */}
        {!result && (
          <Button
            size="sm"
            className="w-full"
            disabled={selected === null || submitting}
            onClick={handleSubmit}
            data-testid="escape-quiz-submit"
          >
            {submitting ? "Checking..." : "Submit Answer"}
            {!submitting && <ChevronRight className="w-3 h-3 ml-1" />}
          </Button>
        )}

        {/* Result */}
        {result && (
          <div
            className={`p-3 rounded-lg border ${
              result.correct
                ? "bg-emerald-500/10 border-emerald-500/30"
                : "bg-red-500/10 border-red-500/30"
            }`}
            data-testid="escape-quiz-result"
          >
            <div className="flex items-center gap-2 mb-1">
              {result.correct ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
              ) : (
                <XCircle className="w-4 h-4 text-red-500" />
              )}
              <span
                className={`text-sm font-medium ${
                  result.correct ? "text-emerald-600" : "text-red-600"
                }`}
              >
                {result.correct ? "Correct!" : "Not quite"}
              </span>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              {result.message}
            </p>
            {result.escape_squares?.length > 0 && (
              <div className="flex gap-1 mt-2">
                {result.escape_squares.map((sq) => (
                  <Badge
                    key={sq}
                    variant="outline"
                    className="text-[10px] font-mono"
                  >
                    {sq}
                  </Badge>
                ))}
              </div>
            )}

            <Button
              size="sm"
              variant="ghost"
              className="mt-2 h-7 text-xs w-full"
              onClick={handleDismiss}
              data-testid="escape-quiz-dismiss"
            >
              Continue
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};

export default EscapeSquaresQuiz;
