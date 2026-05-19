/**
 * DiagnosticPuzzles.jsx — 20-puzzle onboarding diagnostic.
 *
 * Spec: memory/project_diagnostic_onboarding_20_puzzles.md
 *
 * Walks the user through 20 stratified puzzles drawn from
 * community_puzzles. After each move:
 *   - Show whether it was correct (no toast spam, no score)
 *   - Move to the next puzzle
 * After all 20:
 *   - Show a real diagnosis: rating range + per-category labels
 *   - CTA: continue to home / training based on growth area
 *
 * No timer. No streak. No "X correct so far" counter. The user is
 * being assessed, not entertained.
 */

import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Chess } from "chess.js";
import { API } from "@/App";
import LichessBoard from "@/components/LichessBoard";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { ArrowRight, CheckCircle2, XCircle, Loader2 } from "lucide-react";

const TOTAL = 20;

const DiagnosticPuzzles = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [puzzle, setPuzzle] = useState(null);
  const [currentIndex, setCurrentIndex] = useState(1);
  const [resultBanner, setResultBanner] = useState(null); // null | {correct, best_move_san}
  const [diagnosis, setDiagnosis] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const boardRef = useRef(null);

  // ── Start the diagnostic on mount ──────────────────────────────
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API}/diagnostic/start`, {
          method: "POST",
          credentials: "include",
        });
        if (!res.ok) {
          setError(`Could not start diagnostic (${res.status}).`);
          setLoading(false);
          return;
        }
        const data = await res.json();
        if (data.status === "superseded") {
          // User has 10+ analyzed games — diagnostic isn't needed.
          navigate("/home");
          return;
        }
        if (data.status === "no_pool") {
          setError(data.message || "No puzzles available yet.");
          setLoading(false);
          return;
        }
        if (data.status === "in_progress" && data.puzzle) {
          setPuzzle(data.puzzle);
          setCurrentIndex(data.current_index || 1);
          setLoading(false);
          return;
        }
        if (data.status === "complete") {
          // Edge case: server says already complete. Fetch the result.
          await loadResult();
          setLoading(false);
          return;
        }
        setError("Unexpected response from server.");
        setLoading(false);
      } catch (e) {
        setError("Network error.");
        setLoading(false);
      }
    })();
  }, []);

  const loadResult = async () => {
    try {
      const res = await fetch(`${API}/diagnostic/result`, {
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        setDiagnosis(data.diagnosis);
      }
    } catch { /* non-fatal */ }
  };

  // ── Convert chessground move to SAN ────────────────────────────
  const moveToSan = (fen, from, to, promotion) => {
    try {
      const board = new Chess(fen);
      const result = board.move({ from, to, promotion: promotion || "q" });
      return result ? result.san : null;
    } catch {
      return null;
    }
  };

  // ── Submit an attempt ──────────────────────────────────────────
  const handleMove = async (moveData) => {
    if (!puzzle || submitting) return;
    const san = moveToSan(puzzle.fen, moveData.from, moveData.to, moveData.promotion);
    if (!san) return;

    setSubmitting(true);
    try {
      const res = await fetch(`${API}/diagnostic/attempt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          puzzle_id: puzzle.puzzle_id,
          user_move_san: san,
        }),
      });
      if (!res.ok) {
        setError(`Could not record your answer (${res.status}).`);
        setSubmitting(false);
        return;
      }
      const data = await res.json();

      // Show the per-puzzle banner so the user gets one beat of feedback.
      setResultBanner({
        correct: !!data.is_correct,
        best_move_san: data.best_move_san,
        user_move_san: san,
      });

      if (data.status === "complete") {
        // Hold the banner briefly, then reveal the diagnosis.
        setTimeout(() => {
          setDiagnosis(data.diagnosis);
          setPuzzle(null);
          setResultBanner(null);
          setSubmitting(false);
        }, 1500);
        return;
      }

      // Move to next puzzle after a short reveal.
      setTimeout(() => {
        setPuzzle(data.puzzle);
        setCurrentIndex(data.current_index || (currentIndex + 1));
        setResultBanner(null);
        setSubmitting(false);
      }, 1500);
    } catch (e) {
      setError("Network error submitting your answer.");
      setSubmitting(false);
    }
  };

  // ── Skip the diagnostic ────────────────────────────────────────
  const handleSkip = async () => {
    try {
      await fetch(`${API}/diagnostic/skip`, {
        method: "POST",
        credentials: "include",
      });
    } catch { /* non-fatal */ }
    navigate("/home");
  };

  // ──────────────────────────────────────────────────────────────
  // Loading state
  // ──────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <Layout>
        <div className="min-h-[60vh] flex flex-col items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          <p className="mt-3 text-sm text-muted-foreground">Setting up your diagnostic.</p>
        </div>
      </Layout>
    );
  }

  // ──────────────────────────────────────────────────────────────
  // Error state
  // ──────────────────────────────────────────────────────────────
  if (error) {
    return (
      <Layout>
        <div className="min-h-[60vh] flex flex-col items-center justify-center px-6 max-w-md mx-auto text-center">
          <p className="text-sm text-foreground/85">{error}</p>
          <Button className="mt-6" onClick={() => navigate("/home")}>
            Continue to home
          </Button>
        </div>
      </Layout>
    );
  }

  // ──────────────────────────────────────────────────────────────
  // Diagnosis screen (after 20 puzzles)
  // ──────────────────────────────────────────────────────────────
  if (diagnosis) {
    const { rating_estimate, per_category, summary_line, total_correct, total_attempted } = diagnosis;
    const sortedCats = Object.entries(per_category || {}).sort((a, b) => {
      const order = { "Strong": 0, "Mixed": 1, "Needs work": 2 };
      return (order[a[1].label] || 99) - (order[b[1].label] || 99);
    });

    return (
      <Layout>
        <div className="min-h-screen px-6 py-10 max-w-2xl mx-auto">
          <p className="text-[11px] uppercase tracking-[0.22em] font-semibold text-muted-foreground mb-2">
            Diagnostic complete
          </p>
          <h1 className="text-2xl font-serif font-medium text-foreground mb-1">
            Your starting picture
          </h1>
          <p className="text-sm text-muted-foreground mb-8">
            Based on {total_attempted} puzzles. This sharpens as your real games get analyzed.
          </p>

          <div className="rounded-xl border border-border p-5 mb-6 bg-card">
            <p className="text-[10.5px] uppercase tracking-[0.22em] font-semibold text-muted-foreground mb-1">
              Rating estimate
            </p>
            <p className="text-3xl font-serif text-foreground">
              {rating_estimate?.low}–{rating_estimate?.high}
            </p>
            <p className="font-serif text-[15px] text-foreground/85 mt-3 leading-snug">
              {summary_line}
            </p>
          </div>

          <div className="space-y-2 mb-8">
            <p className="text-[10.5px] uppercase tracking-[0.22em] font-semibold text-muted-foreground mb-2">
              By area
            </p>
            {sortedCats.map(([key, cat]) => (
              <div
                key={key}
                className="flex items-center justify-between py-2 border-b border-border/40 last:border-0"
              >
                <span className="text-sm text-foreground">{cat.display_name}</span>
                <span
                  className={`text-[11px] font-semibold uppercase tracking-wider ${
                    cat.label === "Strong"
                      ? "text-emerald-500"
                      : cat.label === "Mixed"
                        ? "text-amber-500"
                        : "text-rose-500"
                  }`}
                >
                  {cat.label}
                </span>
              </div>
            ))}
          </div>

          <div className="flex gap-3">
            <Button
              variant="default"
              className="flex-1"
              onClick={() => navigate("/home")}
              data-testid="diagnostic-continue-home"
            >
              Continue to home
              <ArrowRight className="w-4 h-4 ml-1.5" />
            </Button>
          </div>
        </div>
      </Layout>
    );
  }

  // ──────────────────────────────────────────────────────────────
  // Puzzle screen (during diagnostic)
  // ──────────────────────────────────────────────────────────────
  if (!puzzle) {
    return (
      <Layout>
        <div className="min-h-[60vh] flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin" />
        </div>
      </Layout>
    );
  }

  const orientation = (puzzle.user_color || "white") === "black" ? "black" : "white";

  return (
    <Layout>
      <div className="min-h-screen px-4 py-6 max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-baseline justify-between mb-5">
          <div>
            <p className="text-[10.5px] uppercase tracking-[0.22em] font-semibold text-muted-foreground">
              Diagnostic · {currentIndex} of {TOTAL}
            </p>
            <h1 className="text-xl font-serif font-medium text-foreground mt-0.5">
              Find the best move
            </h1>
          </div>
          <button
            onClick={handleSkip}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            data-testid="diagnostic-skip-btn"
          >
            Skip for now
          </button>
        </div>

        {/* Progress strip — flat dots, no percentage, no streak */}
        <div className="flex gap-1 mb-6">
          {Array.from({ length: TOTAL }).map((_, i) => (
            <div
              key={i}
              className={`flex-1 h-0.5 rounded-full ${
                i < currentIndex - 1 ? "bg-foreground/60" : "bg-border"
              }`}
            />
          ))}
        </div>

        {/* Board + side info */}
        <div className="flex flex-col lg:flex-row gap-6">
          <div className="flex-1">
            <div className="w-full max-w-[560px] aspect-square mx-auto relative">
              <LichessBoard
                ref={boardRef}
                fen={puzzle.fen}
                orientation={orientation}
                interactive={!resultBanner && !submitting}
                viewOnly={!!resultBanner || submitting}
                onMove={handleMove}
              />
              {resultBanner && (
                <div
                  className={`absolute bottom-2 left-2 right-2 px-3 py-2 rounded text-sm flex items-center gap-2 ${
                    resultBanner.correct
                      ? "bg-emerald-600/90 text-white"
                      : "bg-zinc-900/85 text-white"
                  }`}
                  data-testid="diagnostic-result-banner"
                >
                  {resultBanner.correct ? (
                    <>
                      <CheckCircle2 className="w-4 h-4" />
                      <span>Correct — {resultBanner.best_move_san}.</span>
                    </>
                  ) : (
                    <>
                      <XCircle className="w-4 h-4 text-rose-400" />
                      <span>
                        Best was{" "}
                        <span className="font-mono">{resultBanner.best_move_san}</span>.
                      </span>
                    </>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="lg:w-72">
            <div className="rounded-xl border border-border p-4 bg-card">
              <p className="text-[10.5px] uppercase tracking-[0.22em] font-semibold text-muted-foreground mb-2">
                Position
              </p>
              <p className="text-sm text-foreground/85">
                {orientation === "white" ? "White" : "Black"} to move.
              </p>
              <p className="text-xs text-muted-foreground mt-3 leading-relaxed">
                Pick the move you'd play. No timer — take as long as you like.
                We're building a picture of what you see well and what you'd
                benefit from working on.
              </p>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default DiagnosticPuzzles;
