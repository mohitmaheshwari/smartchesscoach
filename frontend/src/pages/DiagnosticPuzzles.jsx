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
import ChessLoader from "@/components/ChessLoader";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { ArrowRight, CheckCircle2, AlertCircle, TrendingUp } from "lucide-react";

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
  // Keep the next server payload separate until the learner finishes reading.
  const [pendingResponse, setPendingResponse] = useState(null);
  const [playedFen, setPlayedFen] = useState(null);
  const [attemptError, setAttemptError] = useState(null);
  const [continuationError, setContinuationError] = useState(null);
  const feedbackSessionRef = useRef(null);
  const submissionInFlightRef = useRef(false);
  const [submitting, setSubmitting] = useState(false);
  const [conceptProgress, setConceptProgress] = useState({}); // per-concept verdicts
  const [showExitConfirm, setShowExitConfirm] = useState(false);
  // The unmount cleanup below closes over its first render, so it needs a ref
  // rather than the state value to know whether a diagnosis already exists.
  const diagnosisRef = useRef(null);
  const boardRef = useRef(null);
  const navigateRef = useRef(navigate);
  // Analytics (2026-08-05 residency, revised event list -- "where does
  // commitment break," not every answer). Refs, not state: firing must
  // never trigger a re-render.
  const firstAnswerFiredRef = useRef(false);

  useEffect(() => {
    navigateRef.current = navigate;
  }, [navigate]);

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
          navigateRef.current(`/login?redirect_to=${encodeURIComponent('/diagnostic')}`);
          return;
        }
        if (!res.ok) {
          setError(`Could not start diagnostic (${res.status}).`);
          setLoading(false);
          return;
        }
        const data = await res.json();
        feedbackSessionRef.current = data.feedback_protocol === "explicit_v1" ? data.feedback_session : null;
        if (data.status === "feedback" && data.puzzle && data.feedback) {
          setPuzzle(data.puzzle);
          setPuzzleNumber(data.current_index || 1);
          setPlayedFen(data.played_fen);
          setPendingResponse(data.feedback);
          const saved = data.feedback;
          setVerdict({
            verdict: saved.step_verdict || saved.verdict || (
              typeof saved.is_correct === "boolean" ? (saved.is_correct ? "UNDERSTOOD" : "MISSING") : null),
            explanation: saved.explanation, cp_loss: saved.cp_loss,
          });
          if (saved.status === "complete") diagnosisRef.current = saved.diagnosis || { complete: true };
          setLoading(false);
          return;
        }
        if (data.status === "superseded") {
          // User has 10+ analyzed games — diagnostic isn't needed.
          navigateRef.current("/home");
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

  // Leaving without pressing "finish" used to throw the answers away. The
  // backend has always been willing to score a partial run -- /diagnostic/exit
  // says so in as many words -- but only the confirm-dialog button ever called
  // it, so navigating away, hitting back or closing the tab left the session
  // stuck in_progress forever. Measured on production: 34 of 40 sessions were
  // stranded that way, holding 104 answered puzzles between them, one of them
  // 19 answers deep.
  //
  // Report the partial run on the way out instead. keepalive lets the request
  // finish after the page is gone, and the backend no-ops when the session is
  // already finished, so a normal completion is unaffected.
  const answeredRef = useRef(0);
  const reportedRef = useRef(false);
  useEffect(() => {
    answeredRef.current = Math.max(0, puzzleNumber - 1) + (verdict && !pendingResponse?.multi_move ? 1 : 0);
  }, [puzzleNumber, verdict, pendingResponse]);
  useEffect(() => {
    diagnosisRef.current = diagnosis;
  }, [diagnosis]);
  useEffect(() => {
    const reportPartialRun = () => {
      if (reportedRef.current) return;
      if (answeredRef.current < 1) return;   // nothing to score
      if (diagnosisRef.current) return;      // already scored
      reportedRef.current = true;
      try {
        // checkpoint=true: score what they answered, leave the run open so
        // they can still finish it later.
        fetch(`${API}/diagnostic/exit?checkpoint=true`, {
          method: "POST",
          credentials: "include",
          keepalive: true,
        }).catch(() => {});
      } catch { /* leaving anyway */ }
    };
    window.addEventListener("pagehide", reportPartialRun);
    return () => {
      window.removeEventListener("pagehide", reportPartialRun);
      reportPartialRun();
    };
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
    if (!puzzle || verdict || attemptError || submitting || submissionInFlightRef.current) return;
    const san = moveToSan(puzzle.fen, moveData.from, moveData.to, moveData.promotion);
    if (!san) return;

    submissionInFlightRef.current = true;
    const playedBoard = new Chess(puzzle.fen);
    playedBoard.move(san);
    setPlayedFen(playedBoard.fen());
    setSubmitting(true);
    try {
      const res = await fetch(`${API}/diagnostic/attempt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          puzzle_id: puzzle.puzzle_id,
          user_move_san: san,
          ...(feedbackSessionRef.current ? {
            feedback_session: feedbackSessionRef.current, feedback_fen: puzzle.fen,
          } : {}),
        }),
      });
      if (!res.ok) {
        // A failed response is not a chess verdict and may follow a saved move.
        setAttemptError(res.status === 409
          ? "I can't verify this answer right now. This is not a judgment about your move."
          : "I couldn't confirm whether your answer was saved. Check the saved position before trying again.");
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
      if (!data.multi_move) {
        track(ANALYTICS_EVENTS.DIAGNOSTIC_PUZZLE_COMPLETED, { puzzle_number: puzzleNumber });
      }

      // Show the verdict card so the user gets feedback.
      // Intermediate V2 steps and legacy answers use different contracts.
      const moveVerdict = data.step_verdict || data.verdict || (
        typeof data.is_correct === "boolean"
          ? (data.is_correct ? "UNDERSTOOD" : "MISSING") : null
      );
      setVerdict({
        verdict: moveVerdict,
        explanation: data.explanation,
        cp_loss: data.cp_loss,
      });
      setPendingResponse(data);

      // Update concept progress
      if (data.concept_progress) {
        setConceptProgress(data.concept_progress);
      }

      if (data.status === "complete") {
        track(ANALYTICS_EVENTS.DIAGNOSTIC_COMPLETED, { exited_early: false, puzzle_count: puzzleNumber });
        // Saved completion does not dismiss the last move's feedback.
        diagnosisRef.current = data.diagnosis || { complete: true };
      }
    } catch (e) {
      setAttemptError("The connection was interrupted. Your answer may have saved; check the saved position before trying again.");
    } finally {
      setSubmitting(false);
      submissionInFlightRef.current = false;
    }
  };

  const continueAfterFeedback = async () => {
    if (!pendingResponse || submissionInFlightRef.current) return;
    // Do not acknowledge a response that cannot supply the promised next screen.
    if ((pendingResponse.status === "complete" && !pendingResponse.diagnosis)
        || (pendingResponse.status !== "complete" && !pendingResponse.puzzle)) {
      setAttemptError("Your answer was saved, but the next step is unavailable. Check the saved position to continue.");
      return;
    }
    if (pendingResponse.feedback_id) {
      submissionInFlightRef.current = true;
      setSubmitting(true);
      setContinuationError(null);
      try {
        const res = await fetch(`${API}/diagnostic/feedback/continue`, {
          method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
          body: JSON.stringify({ feedback_id: pendingResponse.feedback_id }),
        });
        if (!res.ok) throw new Error("Feedback acknowledgement failed");
        const saved = await res.json();
        if (saved.feedback_id !== pendingResponse.feedback_id) throw new Error("Feedback changed");
      } catch {
        setContinuationError("I couldn't confirm Continue. Your answer is saved. Please try Continue again.");
        return;
      } finally {
        submissionInFlightRef.current = false;
        setSubmitting(false);
      }
    }
    if (pendingResponse.status === "complete") {
      if (!pendingResponse.diagnosis) {
        setAttemptError("Your answers were saved, but the summary is unavailable. Check the saved position to continue.");
        return;
      }
      setDiagnosis(pendingResponse.diagnosis);
      setPuzzle(null);
    } else {
      if (!pendingResponse.puzzle) {
        setAttemptError("Your answer was recorded, but the next position is unavailable. Check the saved position to continue.");
        return;
      }
      setPuzzle(pendingResponse.puzzle);
      setPuzzleNumber(pendingResponse.current_index ?? (
        (pendingResponse.puzzle_number ?? puzzleNumber) + (pendingResponse.multi_move ? 0 : 1)
      ));
    }
    setVerdict(null);
    setPendingResponse(null);
    setPlayedFen(null);
  };

  // ── Finish early — score whatever's solved and STILL build the profile ──
  const handleExit = async () => {
    if (submitting || submissionInFlightRef.current) return;
    if (pendingResponse?.status === "complete") {
      setShowExitConfirm(false);
      continueAfterFeedback();
      return;
    }
    setSubmitting(true);
    reportedRef.current = true;  // the explicit path owns the report now
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
          setShowExitConfirm(false);
          setSubmitting(false);
          return;
        }
      }
    } catch { /* recover below without abandoning the board */ }
    reportedRef.current = false;
    setSubmitting(false);
    setShowExitConfirm(false);
    setAttemptError("I couldn't finish the session. Check the saved position before continuing.");
  };

  // ──────────────────────────────────────────────────────────────
  // Loading state
  // ──────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <Layout>
        <div className="min-h-[60vh] flex flex-col items-center justify-center">
          <ChessLoader label="Choosing a few positions that will help me understand you." />
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
    const hasReadout = Object.keys(per_concept || {}).length > 0;

    // Sort by level: Solid > Developing > Missing
    const levelOrder = { solid: 0, developing: 1, missing: 2 };
    const sortedConcepts = Object.entries(per_concept || {})
      .sort((a, b) => levelOrder[a[1].level] - levelOrder[b[1].level]);

    const levelLabel = {
      solid: "Handled well in these positions",
      developing: "Worth another look together",
      missing: "A possible place to practise",
    };

    return (
      <Layout>
        <div className="experience-page experience-diagnostic-page cg-page max-w-3xl">
          <div className="cg-hero mb-8">
            <p className="cg-eyebrow">
              {hasReadout ? "I’ve seen enough to begin" : "Thanks for playing those through"}
            </p>
            <h1 className="cg-title">
              {hasReadout
                ? "Here’s a starting point for our coaching."
                : "Let’s keep discovering what helps you."}
            </h1>
            <p className="cg-lede">
              {summary ||
                (hasReadout
                  ? ""
                  : "Those positions were not enough for me to say something honest about how you play. Play a game with me and I will build it from your own moves.")}
            </p>
            <p className="text-sm text-muted-foreground mt-3">
              These positions are a starting clue, not a rating or proof of what you know. Your games and later attempts will help me adjust.
            </p>
          </div>

          {/* Per-concept breakdown */}
          {hasReadout && (
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
          )}

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
                    Let’s explore {CONCEPT_DISPLAY[headline_gap] || headline_gap}. Your answers suggest it is worth a closer look—not that you need every lesson on it.
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
                if (headline_gap) navigate(`/training/pattern/${headline_gap}`);
                else if (!hasReadout) navigate("/play-with-coach");
                else navigate("/training");
              }}
              data-testid="diagnostic-start-training"
            >
              {hasReadout ? "Start with your coach" : "Play a game with me"}
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
          <ChessLoader />
        </div>
      </Layout>
    );
  }

  // Whose move it is, taken from the position itself. The server states it,
  // but the board must never be able to contradict the board: a missing field
  // used to render "Black to move" over a White position, on every puzzle the
  // legacy path served.
  const sideToMove = (() => {
    try {
      return new Chess(puzzle.fen).turn() === "w" ? "white" : "black";
    } catch {
      return puzzle.side_to_move || null;
    }
  })();
  // Show the board from the side the player is being asked to move.
  const orientation =
    (puzzle.user_color || sideToMove || "white") === "black" ? "black" : "white";

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
            disabled={submitting || !!attemptError}
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
                fen={playedFen || puzzle.fen}
                orientation={orientation}
                interactive={!verdict && !submitting && !attemptError}
                viewOnly={!!verdict || submitting || !!attemptError}
                onMove={handleMove}
              />
            </div>
          </div>

          <div className="lg:w-72">
            {attemptError && (
              <div role="alert" className="rounded-lg border border-amber-500/40 bg-card p-4 mb-4">
                <p className="text-sm text-foreground">{attemptError}</p>
                <Button className="mt-3" variant="outline" onClick={() => window.location.reload()}>
                  Check saved position
                </Button>
              </div>
            )}
            {submitting && !showExitConfirm && !verdict && (
              <p role="status" className="text-sm text-foreground mb-4">Checking your move…</p>
            )}
            {verdict ? (
              <div
                role="status"
                aria-live="polite"
                data-testid="diagnostic-feedback"
                className={`rounded-lg border p-4 ${
                  verdict.verdict === "UNDERSTOOD"
                    ? "border-emerald-500/40 bg-emerald-500/5"
                    : verdict.verdict === "PARTIAL"
                      ? "border-amber-500/40 bg-amber-500/5"
                      : verdict.verdict === "MISSING"
                        ? "border-rose-500/40 bg-rose-500/5" : "border-border bg-card"
                }`}
              >
                <div className="flex items-center gap-2 mb-2">
                  {verdict.verdict === "UNDERSTOOD" ? (
                    <CheckCircle2 className="w-5 h-5 text-emerald-500 flex-shrink-0" />
                  ) : verdict.verdict === "PARTIAL" ? (
                    <AlertCircle className="w-5 h-5 text-amber-500 flex-shrink-0" />
                  ) : (
                    <AlertCircle className={`w-5 h-5 flex-shrink-0 ${verdict.verdict === "MISSING" ? "text-rose-500" : "text-muted-foreground"}`} />
                  )}
                  <span
                    className={`text-sm font-semibold ${
                      verdict.verdict === "UNDERSTOOD"
                        ? "text-emerald-600"
                        : verdict.verdict === "PARTIAL"
                          ? "text-amber-600"
                          : verdict.verdict === "MISSING" ? "text-rose-600" : "text-foreground"
                    }`}
                  >
                    {verdict.verdict === "UNDERSTOOD"
                      ? "Yes — your move works here"
                      : verdict.verdict === "PARTIAL"
                        ? "There’s a stronger move to consider"
                        : verdict.verdict === "MISSING" ? "Let’s look once more" : "Your move was recorded"}
                  </span>
                </div>
                <p className="text-[13px] text-foreground leading-snug">
                  {verdict.explanation}
                </p>
                {continuationError && <p role="alert" className="text-sm text-foreground mt-3">{continuationError}</p>}
                {pendingResponse?.multi_move?.opponent_reply_san && (
                  <p className="text-sm text-foreground mt-3">
                    Next, your opponent plays {pendingResponse.multi_move.opponent_reply_san}. The position isn't finished yet.
                  </p>
                )}
                <Button
                  className="cg-primary-action mt-4 w-full"
                  onClick={continueAfterFeedback}
                  disabled={!!attemptError || submitting}
                  data-testid="diagnostic-feedback-continue"
                >
                  {pendingResponse?.status === "complete" ? "See what we can work on"
                    : pendingResponse?.multi_move ? "Continue this position" : "Next position"}
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </div>
            ) : (
              <div className="rounded-lg border border-border p-4 bg-card">
                <p className="text-[10.5px] uppercase tracking-[0.22em] font-semibold text-muted-foreground mb-2">
                  Take your time
                </p>
                <p className="text-sm text-foreground/85">
                  {sideToMove === "black" ? "Black" : "White"} to move.
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
              You can stop here. I’ll keep your saved answers, and we can use more positions or your games to decide what is worth practising.
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
                disabled={submitting}
                data-testid="diagnostic-exit-confirm"
              >
                Finish for now
              </Button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
};

export default DiagnosticPuzzles;
