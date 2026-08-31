/**
 * DiagnosticPuzzles.jsx — Diagnostic V2: consequence-based grading.
 *
 * 25-puzzle diagnostic that measures chess understanding, not engine-move compliance.
 * Grading: consequence-based (UNDERSTOOD/PARTIAL/MISSING based on move outcome).
 * UI: concept progress chips + per-puzzle verdict + results breakdown per-concept.
 *
 * Spec: docs/diagnostic_v2_scope.md
 */

import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Chess } from "chess.js";
import { API } from "@/App";
import { ANALYTICS_EVENTS, track } from "@/lib/analytics";
import LichessBoard from "@/components/LichessBoard";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { ArrowRight, CheckCircle2, AlertCircle, Loader2, TrendingUp } from "lucide-react";

const CONCEPT_DISPLAY = {
  piece_safety: "Piece Safety",
  forks: "Forks",
  pins: "Pins & Skewers",
  mate_patterns: "Mate Patterns",
  threat_response: "Threat Response",
  calculation_depth: "Calculation",
  endgame_technique: "Endgame",
  opening_principles: "Opening",
  winning_technique: "Winning",
  piece_activity: "Piece Activity",
};

const DiagnosticPuzzles = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [puzzle, setPuzzle] = useState(null);
  const [puzzleNumber, setPuzzleNumber] = useState(1);
  const [verdict, setVerdict] = useState(null); // {verdict, explanation, cp_loss, concept_progress}
  const [diagnosis, setDiagnosis] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [conceptProgress, setConceptProgress] = useState({}); // per-concept verdicts
  const [showExitConfirm, setShowExitConfirm] = useState(false);
  const boardRef = useRef(null);
  // Analytics (2026-08-05 residency, revised event list -- "where does
  // commitment break," not every answer). Refs, not state: firing must
  // never trigger a re-render.
  const firstAnswerFiredRef = useRef(false);

  // ── Start the diagnostic on mount ──────────────────────────────
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API}/diagnostic/start`, {
          method: "POST",
          credentials: "include",
        });
        if (res.status === 401) {
          // Not authenticated - redirect to login with redirect_to parameter
          navigate(`/login?redirect_to=${encodeURIComponent('/diagnostic')}`);
          return;
        }
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
          // Fresh (puzzle 1) vs. a real return to an already-started
          // session are different user stories -- don't conflate them
          // into one "started" event.
          if ((data.current_index || 1) <= 1) {
            track(ANALYTICS_EVENTS.DIAGNOSTIC_STARTED);
          } else {
            track(ANALYTICS_EVENTS.DIAGNOSTIC_RESUMED, { puzzle_number: data.current_index });
          }
          setPuzzle(data.puzzle);
          setPuzzleNumber(data.current_index || 1);
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
        console.error("Diagnostic error:", e);
        setError(`Network error: ${e.message}`);
        setLoading(false);
      }
    })();
  }, []);

  // A tab backgrounded mid-puzzle is a different user story from a
  // session resumed days later -- "interrupted" vs. "came back." Only
  // fires while an unanswered puzzle is actually on screen.
  useEffect(() => {
    const onVisibility = () => {
      if (document.hidden && puzzle && !verdict) {
        track(ANALYTICS_EVENTS.DIAGNOSTIC_PAUSE, { puzzle_number: puzzleNumber });
      }
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, [puzzle, verdict, puzzleNumber]);

  // The diagnosis screen is the current candidate for "a personal insight
  // was delivered" -- fire once when it first renders. source is fixed at
  // "diagnostic" on purpose; see the vocabulary note in analytics.js for
  // why Home/Review aren't wired in yet.
  const insightShownFiredRef = useRef(false);
  useEffect(() => {
    if (diagnosis && !insightShownFiredRef.current) {
      insightShownFiredRef.current = true;
      track(ANALYTICS_EVENTS.INSIGHT_SHOWN, {
        insight_id: "diagnostic_headline_gap",
        source: "diagnostic",
        version: 1,
      });
    }
  }, [diagnosis]);

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

      if (!firstAnswerFiredRef.current) {
        firstAnswerFiredRef.current = true;
        track(ANALYTICS_EVENTS.DIAGNOSTIC_FIRST_ANSWER);
      }
      // Deliberately no verdict/correctness in the props -- per the
      // residency review, the funnel question is "where does commitment
      // break," not "grade every answer." puzzle_number is enough to
      // plot the drop-off curve.
      track(ANALYTICS_EVENTS.DIAGNOSTIC_PUZZLE_COMPLETED, { puzzle_number: puzzleNumber });

      // Show the verdict card so the user gets feedback.
      setVerdict({
        verdict: data.verdict,
        explanation: data.explanation,
        cp_loss: data.cp_loss,
      });

      // Update concept progress
      if (data.concept_progress) {
        setConceptProgress(data.concept_progress);
      }

      if (data.status === "complete") {
        track(ANALYTICS_EVENTS.DIAGNOSTIC_COMPLETED, { exited_early: false, puzzle_count: puzzleNumber });
        // Hold the verdict briefly, then reveal the diagnosis.
        setTimeout(() => {
          setDiagnosis(data.diagnosis);
          setPuzzle(null);
          setVerdict(null);
          setSubmitting(false);
        }, 2000);
        return;
      }

      // Move to next puzzle after a short reveal.
      setTimeout(() => {
        setPuzzle(data.puzzle);
        setPuzzleNumber(data.puzzle_number);
        setVerdict(null);
        setSubmitting(false);
      }, 2000);
    } catch (e) {
      setError("Network error submitting your answer.");
      setSubmitting(false);
    }
  };

  // ── Finish early — score whatever's solved and STILL build the profile ──
  const handleExit = async () => {
    track(ANALYTICS_EVENTS.DIAGNOSTIC_ABANDONED, { puzzle_number: puzzleNumber });
    try {
      const res = await fetch(`${API}/diagnostic/exit`, {
        method: "POST",
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        if (data.diagnosis) {
          track(ANALYTICS_EVENTS.DIAGNOSTIC_COMPLETED, { exited_early: true, puzzle_count: puzzleNumber - 1 });
          setDiagnosis(data.diagnosis);
          return;
        }
      }
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
          <p className="mt-3 text-sm text-muted-foreground">Choosing a few positions that will help me understand you.</p>
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
  // Diagnosis screen (after all puzzles)
  // ──────────────────────────────────────────────────────────────
  if (diagnosis) {
    const { per_concept, headline_gap, summary } = diagnosis;

    // Sort by level: Solid > Developing > Missing
    const levelOrder = { solid: 0, developing: 1, missing: 2 };
    const sortedConcepts = Object.entries(per_concept || {})
      .sort((a, b) => levelOrder[a[1].level] - levelOrder[b[1].level]);

    const levelLabel = {
      solid: "This already feels familiar",
      developing: "This is taking shape",
      missing: "We’ll learn this together",
    };

    return (
      <Layout>
        <div className="experience-page experience-diagnostic-page cg-page max-w-3xl">
          <div className="cg-hero mb-8">
            <p className="cg-eyebrow">I’ve seen enough to begin</p>
            <h1 className="cg-title">Here’s what I understand about your chess.</h1>
            <p className="cg-lede">{summary}</p>
          </div>

          {/* Per-concept breakdown */}
          <div className="space-y-3 mb-8">
            <p className="cg-eyebrow mb-3">
              What we’ll build on
            </p>
            {sortedConcepts.map(([key, concept]) => (
              <div
                key={key}
                className="cg-panel !p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-start justify-between gap-4">
                      <span className="text-sm font-medium text-foreground">
                        {CONCEPT_DISPLAY[key] || key}
                      </span>
                      <span className="text-xs text-muted-foreground text-right">
                        {levelLabel[concept.level]}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Headline gap focus area */}
          {headline_gap && (
            <div className="cg-coach-card mb-8">
              <div className="flex items-start gap-3">
                <TrendingUp className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-[11px] uppercase tracking-[0.22em] font-semibold text-amber-700 mb-1">
                    Where we’ll start
                  </p>
                  <p className="text-[13px] text-foreground leading-snug">
                    We’ll begin with {CONCEPT_DISPLAY[headline_gap] || headline_gap}. I chose it because making this idea feel natural will help the rest of your chess become easier to understand.
                  </p>
                </div>
              </div>
            </div>
          )}

          <div className="flex gap-3">
            <Button
              variant="default"
              className="cg-primary-action flex-1"
              onClick={() => {
                track(ANALYTICS_EVENTS.DIAGNOSTIC_TRAINING_STARTED, { headline_gap: headline_gap || null });
                headline_gap ? navigate(`/training/pattern/${headline_gap}`) : navigate("/training");
              }}
              data-testid="diagnostic-start-training"
            >
              Start with your coach
              <ArrowRight className="w-4 h-4 ml-1.5" />
            </Button>
            <Button
              variant="outline"
              className="flex-1"
              onClick={() => navigate("/home")}
              data-testid="diagnostic-continue-home"
            >
              Take me home
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
      <div className="experience-page experience-diagnostic-page cg-page cg-page--wide">
        {/* Header */}
        <div className="flex items-baseline justify-between mb-5">
          <div>
            <p className="cg-eyebrow !mb-1">
              Let me watch how you think
            </p>
            <h1 className="text-xl font-serif font-medium text-foreground mt-0.5">
              What would you play here?
            </h1>
          </div>
          <button
            onClick={() => {
              track(ANALYTICS_EVENTS.DIAGNOSTIC_EXIT_INTENT_SHOWN, { puzzle_number: puzzleNumber });
              setShowExitConfirm(true);
            }}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            data-testid="diagnostic-skip-btn"
          >
            Finish early
          </button>
        </div>

        {/* Board + side info */}
        <div className="flex flex-col lg:flex-row gap-6">
          <div className="flex-1">
            <div className="w-full max-w-[560px] aspect-square mx-auto relative">
              <LichessBoard
                ref={boardRef}
                fen={puzzle.fen}
                orientation={orientation}
                interactive={!verdict && !submitting}
                viewOnly={!!verdict || submitting}
                onMove={handleMove}
              />
            </div>
          </div>

          <div className="lg:w-72">
            {verdict ? (
              <div
                className={`rounded-lg border p-4 ${
                  verdict.verdict === "UNDERSTOOD"
                    ? "border-emerald-500/40 bg-emerald-500/5"
                    : verdict.verdict === "PARTIAL"
                      ? "border-amber-500/40 bg-amber-500/5"
                      : "border-rose-500/40 bg-rose-500/5"
                }`}
              >
                <div className="flex items-center gap-2 mb-2">
                  {verdict.verdict === "UNDERSTOOD" ? (
                    <CheckCircle2 className="w-5 h-5 text-emerald-500 flex-shrink-0" />
                  ) : verdict.verdict === "PARTIAL" ? (
                    <AlertCircle className="w-5 h-5 text-amber-500 flex-shrink-0" />
                  ) : (
                    <AlertCircle className="w-5 h-5 text-rose-500 flex-shrink-0" />
                  )}
                  <span
                    className={`text-sm font-semibold ${
                      verdict.verdict === "UNDERSTOOD"
                        ? "text-emerald-600"
                        : verdict.verdict === "PARTIAL"
                          ? "text-amber-600"
                          : "text-rose-600"
                    }`}
                  >
                    {verdict.verdict === "UNDERSTOOD"
                      ? "Yes—that idea works"
                      : verdict.verdict === "PARTIAL"
                        ? "You found part of it"
                        : "Let’s look once more"}
                  </span>
                </div>
                <p className="text-[13px] text-foreground leading-snug">
                  {verdict.explanation}
                </p>
              </div>
            ) : (
              <div className="rounded-lg border border-border p-4 bg-card">
                <p className="text-[10.5px] uppercase tracking-[0.22em] font-semibold text-muted-foreground mb-2">
                  Take your time
                </p>
                <p className="text-sm text-foreground/85">
                  {puzzle.side_to_move === "white" ? "White" : "Black"} to move.
                </p>
                <p className="text-xs text-muted-foreground mt-3 leading-relaxed">
                  Pick the move you would really play. There is no timer. I’m listening for how you understand the position, not how quickly you answer.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Exit-intent confirmation — explains the cost of stopping early
          instead of silently discarding the rest of the read. No
          gamification/guilt language, just what actually happens. */}
      {showExitConfirm && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center px-4">
          <div className="w-full max-w-sm rounded-lg border border-border bg-card p-5 shadow-xl">
            <h2 className="text-[15px] font-serif font-medium text-foreground mb-2">
              Finish the diagnostic?
            </h2>
            <p className="text-[13px] text-muted-foreground leading-relaxed mb-4">
              I can already begin a plan from what you’ve shown me. A few more positions will help me distinguish an unfamiliar idea from a simple oversight.
            </p>
            <div className="flex gap-2">
              <Button
                variant="default"
                className="flex-1"
                onClick={() => setShowExitConfirm(false)}
                data-testid="diagnostic-exit-cancel"
              >
                Show me another position
              </Button>
              <Button
                variant="outline"
                className="flex-1"
                onClick={handleExit}
                data-testid="diagnostic-exit-confirm"
              >
                Exit anyway
              </Button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
};

export default DiagnosticPuzzles;
