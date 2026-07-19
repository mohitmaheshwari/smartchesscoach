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
  const boardRef = useRef(null);

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
    try {
      const res = await fetch(`${API}/diagnostic/exit`, {
        method: "POST",
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        if (data.diagnosis) { setDiagnosis(data.diagnosis); return; }
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
  // Diagnosis screen (after all puzzles)
  // ──────────────────────────────────────────────────────────────
  if (diagnosis) {
    const { rating_estimate, per_concept, headline_gap, summary } = diagnosis;

    // Sort by level: Solid > Developing > Missing
    const levelOrder = { solid: 0, developing: 1, missing: 2 };
    const sortedConcepts = Object.entries(per_concept || {})
      .sort((a, b) => levelOrder[a[1].level] - levelOrder[b[1].level]);

    const levelColor = {
      solid: "text-emerald-500",
      developing: "text-amber-500",
      missing: "text-rose-500",
    };

    const levelLabel = {
      solid: "Solid ✓",
      developing: "Developing ◐",
      missing: "Missing ✗",
    };

    return (
      <Layout>
        <div className="min-h-screen px-6 py-10 max-w-2xl mx-auto">
          <p className="text-[11px] uppercase tracking-[0.22em] font-semibold text-muted-foreground mb-2">
            Your Chess DNA
          </p>
          <h1 className="text-2xl font-serif font-medium text-foreground mb-1">
            Your diagnostic results
          </h1>
          <p className="text-sm text-muted-foreground mb-8">
            A profile of 10 chess concepts. This refines as you play real games and we analyze them.
          </p>

          {/* Rating estimate */}
          <div className="rounded-xl border border-border p-5 mb-6 bg-card">
            <p className="text-[10.5px] uppercase tracking-[0.22em] font-semibold text-muted-foreground mb-1">
              Estimated rating
            </p>
            <p className="text-3xl font-serif text-foreground">
              {rating_estimate?.low}–{rating_estimate?.high}
            </p>
            <p className="text-[13px] text-foreground/85 mt-3 leading-snug">
              {summary}
            </p>
          </div>

          {/* Per-concept breakdown */}
          <div className="space-y-3 mb-8">
            <p className="text-[10.5px] uppercase tracking-[0.22em] font-semibold text-muted-foreground mb-3">
              By concept
            </p>
            {sortedConcepts.map(([key, concept]) => (
              <div
                key={key}
                className="rounded-lg border border-border p-4 bg-card"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium text-foreground">
                        {CONCEPT_DISPLAY[key] || key}
                      </span>
                      <span className={`text-[11px] font-semibold uppercase tracking-wider ${levelColor[concept.level]}`}>
                        {levelLabel[concept.level]}
                      </span>
                    </div>
                    {/* Verdict dots */}
                    <div className="flex gap-1 mt-2">
                      {concept.verdicts.map((v, i) => (
                        <span
                          key={i}
                          className={`inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-semibold ${
                            v === "✓"
                              ? "bg-emerald-500/20 text-emerald-600"
                              : v === "◐"
                                ? "bg-amber-500/20 text-amber-600"
                                : "bg-rose-500/20 text-rose-600"
                          }`}
                        >
                          {v}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Headline gap focus area */}
          {headline_gap && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4 mb-8">
              <div className="flex items-start gap-3">
                <TrendingUp className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-[11px] uppercase tracking-[0.22em] font-semibold text-amber-700 mb-1">
                    🎯 Your focus area
                  </p>
                  <p className="text-[13px] text-foreground leading-snug">
                    {CONCEPT_DISPLAY[headline_gap] || headline_gap} needs attention.
                    Practice this concept to unlock your next rating tier.
                  </p>
                </div>
              </div>
            </div>
          )}

          <div className="flex gap-3">
            <Button
              variant="default"
              className="flex-1"
              onClick={() => headline_gap ? navigate(`/training/pattern/${headline_gap}`) : navigate("/training")}
              data-testid="diagnostic-start-training"
            >
              Start training
              <ArrowRight className="w-4 h-4 ml-1.5" />
            </Button>
            <Button
              variant="outline"
              className="flex-1"
              onClick={() => navigate("/home")}
              data-testid="diagnostic-continue-home"
            >
              Go to home
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
              Diagnostic · Puzzle {puzzleNumber} of 25
            </p>
            <h1 className="text-xl font-serif font-medium text-foreground mt-0.5">
              Find the best move in {CONCEPT_DISPLAY[puzzle.concept] || puzzle.concept}
            </h1>
          </div>
          <button
            onClick={handleExit}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            data-testid="diagnostic-skip-btn"
          >
            Finish early
          </button>
        </div>

        {/* Concept progress chips */}
        <div className="flex flex-wrap gap-2 mb-6">
          {Object.entries(CONCEPT_DISPLAY).map(([key, label]) => {
            const progress = conceptProgress[key] || [];
            return (
              <div
                key={key}
                className={`flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium ${
                  key === puzzle.concept
                    ? "bg-foreground/10 border border-foreground/30"
                    : "bg-border/40"
                }`}
              >
                <span className="text-foreground/70">{label}</span>
                <div className="flex gap-0.5">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <span
                      key={i}
                      className={`inline-block w-1.5 h-1.5 rounded-full ${
                        progress[i] === "✓"
                          ? "bg-emerald-500"
                          : progress[i] === "◐"
                            ? "bg-amber-500"
                            : progress[i] === "✗"
                              ? "bg-rose-500"
                              : "bg-border"
                      }`}
                    />
                  ))}
                </div>
              </div>
            );
          })}
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
                      ? "✓ Correct"
                      : verdict.verdict === "PARTIAL"
                        ? "◐ Partially correct"
                        : "✗ Incorrect"}
                  </span>
                </div>
                <p className="text-[13px] text-foreground leading-snug">
                  {verdict.explanation}
                </p>
              </div>
            ) : (
              <div className="rounded-lg border border-border p-4 bg-card">
                <p className="text-[10.5px] uppercase tracking-[0.22em] font-semibold text-muted-foreground mb-2">
                  Position
                </p>
                <p className="text-sm text-foreground/85">
                  {puzzle.side_to_move === "white" ? "White" : "Black"} to move.
                </p>
                <p className="text-xs text-muted-foreground mt-3 leading-relaxed">
                  Pick the move you'd play. No timer — take as long as you like.
                  We're measuring your understanding of chess fundamentals.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default DiagnosticPuzzles;
