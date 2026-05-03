/**
 * PrescribedTraining - Puzzles prescribed based on user's weaknesses
 * 
 * This is the IMPROVEMENT engine:
 * - Shows puzzles targeted at user's specific weaknesses
 * - Includes puzzles from user's OWN games
 * - Provides coaching context for each puzzle
 * - Tracks progress over time
 */

import { useState, useEffect, useRef } from "react";
import { useNavigate, useSearchParams, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import LichessBoard from "@/components/LichessBoard";
import { Chess } from "chess.js";
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  ChevronRight,
  Loader2,
  Trophy,
  AlertCircle,
  RotateCcw,
  Eye,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { API } from "@/App";

// Encouraging messages for puzzle completion
const PUZZLE_ENCOURAGEMENTS = {
  correct: [
    "Nice! You're building the habit.",
    "That's the pattern! Keep going.",
    "Excellent! Your eyes are getting sharper.",
    "Great recognition! This is how you improve.",
    "Perfect! You won't miss this in a real game.",
  ],
  incorrect: [
    "Almost! The pattern is tricky, but you'll get it.",
    "Not quite, but keep trying. This is exactly the training you need.",
    "Take another look. The solution involves the same weakness you're working on.",
  ],
  streak: [
    "You're on fire! 🔥",
    "Three in a row - your pattern recognition is improving!",
    "Streak! This weakness is becoming your strength.",
  ],
  complete: [
    "Training session complete! Every puzzle makes you stronger.",
    "Great work! You've done your training for today.",
    "Session done! Come back tomorrow to keep the momentum.",
  ]
};

const getEncouragement = (type, streak = 0) => {
  if (streak >= 3 && type === "correct") {
    return PUZZLE_ENCOURAGEMENTS.streak[Math.floor(Math.random() * PUZZLE_ENCOURAGEMENTS.streak.length)];
  }
  const messages = PUZZLE_ENCOURAGEMENTS[type] || PUZZLE_ENCOURAGEMENTS.correct;
  return messages[Math.floor(Math.random() * messages.length)];
};

export default function PrescribedTraining() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  // Weakness can come from either:
  //   1. ?weakness=X query param (canonical: /training?weakness=X)
  //   2. :pattern URL segment (legacy: /training/pattern/:pattern)
  //   3. default to "current" — backend resolves to user's active focus
  const { pattern: patternFromUrl } = useParams();
  const weakness = searchParams.get("weakness") || patternFromUrl || "current";
  
  // Data state
  const [trainingData, setTrainingData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Puzzle state
  const [currentPuzzleIndex, setCurrentPuzzleIndex] = useState(0);
  const [puzzleState, setPuzzleState] = useState("thinking"); // thinking, correct, incorrect, revealed
  const [userMove, setUserMove] = useState(null);
  const [showSolution, setShowSolution] = useState(false);
  const [solvedCount, setSolvedCount] = useState(0);
  const [streak, setStreak] = useState(0);
  const [encouragement, setEncouragement] = useState("");
  // Per-move coaching from build_miss_coaching — populated when the
  // user gets a puzzle wrong. Carries position_summary, played_critique,
  // best_move_idea, takeaway. Cleared on next puzzle / retry.
  const [missCoaching, setMissCoaching] = useState(null);
  
  // Board state
  const [game, setGame] = useState(new Chess());
  const [boardOrientation, setBoardOrientation] = useState("white");
  const boardRef = useRef(null);
  
  // Fetch prescribed training
  useEffect(() => {
    const fetchTraining = async () => {
      setLoading(true);
      try {
        const response = await fetch(
          `${API}/training/prescribed/${weakness}?num_puzzles=10`,
          { credentials: "include" }
        );
        if (response.ok) {
          const data = await response.json();
          setTrainingData(data);
          
          // Set up first puzzle
          if (data.puzzles && data.puzzles.length > 0) {
            const firstPuzzle = data.puzzles[0];
            if (firstPuzzle.fen) {
              const newGame = new Chess(firstPuzzle.fen);
              setGame(newGame);
              // Set orientation based on whose turn it is
              const turn = firstPuzzle.fen.split(" ")[1];
              setBoardOrientation(turn === "w" ? "white" : "black");
            }
          }
        } else {
          setError("Failed to load training");
        }
      } catch (err) {
        console.error("Error fetching training:", err);
        setError("Failed to load training");
      } finally {
        setLoading(false);
      }
    };
    
    fetchTraining();
  }, [weakness]);
  
  // Current puzzle
  const currentPuzzle = trainingData?.puzzles?.[currentPuzzleIndex];
  
  // Handle move attempt
  const onDrop = async (sourceSquare, targetSquare) => {
    if (puzzleState !== "thinking") return false;
    if (!currentPuzzle) return false;

    let move;
    try {
      move = game.move({
        from: sourceSquare,
        to: targetSquare,
        promotion: "q",
      });
    } catch (e) {
      return false;
    }
    if (move === null) return false;

    setUserMove(move.san);
    const userMoveUci = `${sourceSquare}${targetSquare}${move.promotion || ""}`;

    // Binary-match fallback — used if the graduated evaluator fails. Keeps
    // the puzzle usable even when Stockfish is slow/unavailable.
    const solution = currentPuzzle.solution || [];
    const binaryCorrect =
      move.san === solution[0] ||
      move.san === currentPuzzle.solution_san ||
      userMoveUci === solution[0] ||
      move.lan?.toLowerCase() === solution[0]?.toLowerCase();

    // Optimistic UI: mark evaluating while Stockfish runs (~100-200ms).
    setPuzzleState("evaluating");

    let result = null;
    try {
      const res = await fetch(`${API}/training/evaluate-puzzle-move`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          fen: currentPuzzle.fen,
          played_uci: userMoveUci,
          known_best_san: currentPuzzle.solution_san || solution[0] || "",
        }),
      });
      if (res.ok) {
        result = await res.json();
      }
    } catch (_e) {
      // Network error — we'll fall through to binary-match fallback.
    }

    // If the evaluator returned something usable, route by quality.
    if (result && result.quality && result.quality !== "invalid") {
      const bestSan = result.best_move_san || currentPuzzle.solution_san || "";
      const feedback = result.feedback || "";

      // Capture rich miss-coaching when the backend included it.
      // Cleared automatically on next puzzle / retry. Only meaningful
      // for non-best moves; backend skips it on best.
      if (result.miss_coaching) {
        setMissCoaching(result.miss_coaching);
      } else {
        setMissCoaching(null);
      }

      if (result.is_best) {
        setPuzzleState("correct");
        setSolvedCount((prev) => prev + 1);
        setStreak((prev) => prev + 1);
        setEncouragement(feedback || getEncouragement("correct", streak + 1));
        recordAttempt(currentPuzzle, true, result.quality);
      } else if (result.is_acceptable) {
        // Good enough to advance, but name the sharper move. No streak credit —
        // strict lesson: the specific tactic mattered.
        setPuzzleState("acceptable");
        setSolvedCount((prev) => prev + 1);
        setEncouragement(feedback || `Solid. ${bestSan} was sharper.`);
        recordAttempt(currentPuzzle, true, result.quality);
      } else {
        setPuzzleState("incorrect");
        setStreak(0);
        setEncouragement(feedback || getEncouragement("incorrect"));
        game.undo();
        setGame(new Chess(game.fen()));
        recordAttempt(currentPuzzle, false, result.quality);
      }
      return true;
    }

    // Fallback: evaluator unavailable → binary-match.
    if (binaryCorrect) {
      setPuzzleState("correct");
      setSolvedCount((prev) => prev + 1);
      setStreak((prev) => prev + 1);
      setEncouragement(getEncouragement("correct", streak + 1));
      recordAttempt(currentPuzzle, true);
    } else {
      setPuzzleState("incorrect");
      setStreak(0);
      setEncouragement(getEncouragement("incorrect"));
      game.undo();
      setGame(new Chess(game.fen()));
      recordAttempt(currentPuzzle, false);
    }
    return true;
  };
  
  // Record puzzle attempt. `quality` is optional — set when the graduated
  // evaluator ran; omitted on binary-match fallback.
  const recordAttempt = async (puzzle, solved, quality = null) => {
    try {
      await fetch(`${API}/training/puzzle-attempt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          puzzle_id: puzzle.puzzle_id || puzzle.game_id,
          correct: solved,
          time_taken_ms: 0, // TODO: track time
          weakness_type: weakness,
          quality,
        }),
      });
    } catch (e) {
      console.error("Error recording attempt:", e);
    }
  };
  
  // Next puzzle
  const nextPuzzle = () => {
    const nextIdx = currentPuzzleIndex + 1;
    if (nextIdx < trainingData.puzzles.length) {
      setCurrentPuzzleIndex(nextIdx);
      setPuzzleState("thinking");
      setUserMove(null);
      setShowSolution(false);
      setMissCoaching(null);

      const nextPuzzle = trainingData.puzzles[nextIdx];
      if (nextPuzzle.fen) {
        const newGame = new Chess(nextPuzzle.fen);
        setGame(newGame);
        const turn = nextPuzzle.fen.split(" ")[1];
        setBoardOrientation(turn === "w" ? "white" : "black");
      }
    }
  };

  // Retry puzzle
  const retryPuzzle = () => {
    if (currentPuzzle?.fen) {
      const newGame = new Chess(currentPuzzle.fen);
      setGame(newGame);
      setPuzzleState("thinking");
      setUserMove(null);
      setShowSolution(false);
      setMissCoaching(null);
    }
  };
  
  // Show solution
  const revealSolution = () => {
    setShowSolution(true);
    setPuzzleState("revealed");
  };
  
  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto mb-4" />
          <p className="text-muted-foreground">Loading your training...</p>
        </div>
      </div>
    );
  }
  
  if (error || !trainingData) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-8 h-8 text-red-500 mx-auto mb-4" />
          <p className="text-red-500">{error || "No training data available"}</p>
          <Button onClick={() => navigate("/home")} className="mt-4">
            Go Home
          </Button>
        </div>
      </div>
    );
  }
  
  // "acceptable" counts as solved for session-complete purposes — it was
  // good enough to advance, just not the sharpest.
  const isSolvedState = puzzleState === "correct" || puzzleState === "acceptable";
  const isComplete = currentPuzzleIndex >= trainingData.puzzles.length - 1 && isSolvedState;
  const totalPuzzles = trainingData.puzzles.length;
  const focusName =
    trainingData.coaching_intro?.lesson ||
    (weakness === "current" ? "Your focus" : weakness.replace(/_/g, " "));
  const solvedMoves = currentPuzzle?.solution_san || currentPuzzle?.solution?.[0];

  // Progress pips — solved ✓, missed ✗, current ●, upcoming ○
  // `attempts` list isn't tracked globally; we synthesize pips from solvedCount + current index.
  const pips = Array.from({ length: totalPuzzles }, (_, i) => {
    if (i < currentPuzzleIndex) return "solved";
    if (i === currentPuzzleIndex) {
      if (puzzleState === "correct" || puzzleState === "acceptable") return "solved";
      if (puzzleState === "incorrect") return "missed";
      return "current";
    }
    return "upcoming";
  });

  // Socratic question — use coaching.question if backend provides one, else a
  // weakness-aware template, else a safe default. Never fake context we don't have.
  const socraticQuestion =
    currentPuzzle?.coaching?.question ||
    (currentPuzzle?.source === "your_game"
      ? "Before you moved — what did you miss?"
      : {
          piece_safety: "Which of your pieces has no defender?",
          tactical_oversight: "What tactic is hiding in this position?",
          missed_tactic: "What tactic is available here?",
          missed_threat: "What's your opponent threatening?",
          opponent_threats: "What's your opponent threatening?",
          calculation_depth: "Look two moves ahead — what happens?",
          king_safety: "Is your king as safe as it looks?",
          poor_piece_safety: "Which piece can be taken for free?",
        }[weakness] ||
        "Find the best move.");

  // Color / side to move — parse from FEN
  const toMoveLabel = (() => {
    try {
      const turn = currentPuzzle?.fen?.split(" ")[1];
      return turn === "b" ? "Black to move" : "White to move";
    } catch {
      return "";
    }
  })();

  const puzzleRating = currentPuzzle?.rating || currentPuzzle?.avg_rating;

  return (
    <div className="min-h-screen bg-background text-foreground" data-testid="prescribed-training">
      <div className="max-w-[1080px] mx-auto px-6 md:px-10 py-8 md:py-12">

        {/* Back nav — subtle */}
        <button
          onClick={() => navigate(-1)}
          className="text-[11.5px] text-muted-foreground hover:text-foreground transition-colors inline-flex items-center gap-1.5 mb-8"
        >
          <ArrowLeft className="w-3 h-3" strokeWidth={1.75} />
          Back
        </button>

        {/* ─── Page head: focus + progress pips ─── */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-10 md:mb-14">
          <div className="flex items-baseline gap-4 md:gap-5 flex-wrap">
            <p className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold">
              Training · focus session
            </p>
            <span className="text-[13px] text-foreground font-medium capitalize">{focusName}</span>
          </div>
          <div className="flex items-center gap-5">
            <span className="text-[11px] text-muted-foreground tabular-nums">
              {Math.min(currentPuzzleIndex + 1, totalPuzzles)} of {totalPuzzles}
            </span>
            <Pips pips={pips} />
          </div>
        </div>

        {/* Pool-thin note: we returned fewer puzzles than the session target.
            Explains WHY so the user doesn't think the app is broken. Once
            solved, puzzles don't reappear — the pool grows as games get
            imported or other users contribute. */}
        {trainingData.pool_thin && (
          <div
            className="mb-8 md:mb-10 px-4 py-3 rounded-lg border border-amber-500/25 bg-amber-500/[0.04]"
            data-testid="pool-thin-notice"
          >
            <p className="text-[12px] text-amber-700 dark:text-amber-300/80 leading-relaxed">
              {totalPuzzles === 0 ? (
                <>
                  No puzzles for <span className="font-medium">{focusName}</span> yet.
                  Import more games or practice another pattern while the pool grows.
                </>
              ) : (
                <>
                  You've seen most of what we have for <span className="font-medium">{focusName}</span>.
                  Solved puzzles don't repeat — more will arrive as you (or the community)
                  add more games.
                </>
              )}
            </p>
          </div>
        )}

        {/* ─── Stage: board + coaching panel ─── */}
        <div className="grid grid-cols-1 lg:grid-cols-[minmax(320px,520px)_1fr] gap-8 lg:gap-14 items-start">

          {/* Board column */}
          <div className="w-full">
            {currentPuzzle?.fen ? (
              <div className="rounded-lg overflow-hidden ring-1 ring-border">
                <LichessBoard
                  ref={boardRef}
                  fen={game.fen()}
                  orientation={boardOrientation}
                  onMove={(moveData) => {
                    if (puzzleState === "thinking" && moveData) {
                      onDrop(moveData.from, moveData.to);
                    }
                  }}
                  interactive={puzzleState === "thinking"}
                  viewOnly={puzzleState !== "thinking"}
                  arrows={
                    (showSolution || puzzleState === "incorrect")
                      ? (() => {
                          const arrows = [];
                          if (currentPuzzle.solution?.[0]) {
                            arrows.push([
                              currentPuzzle.solution[0].slice(0, 2),
                              currentPuzzle.solution[0].slice(2, 4),
                              "green",
                            ]);
                          }
                          if (currentPuzzle.threat) {
                            const threat = currentPuzzle.threat;
                            if (threat.length === 4 && /^[a-h][1-8][a-h][1-8]$/.test(threat)) {
                              arrows.push([threat.slice(0, 2), threat.slice(2, 4), "orange"]);
                            }
                          }
                          return arrows;
                        })()
                      : []
                  }
                  highlights={
                    (showSolution || puzzleState === "incorrect")
                      ? (() => {
                          const highlights = [];
                          if (currentPuzzle.your_move_uci) {
                            highlights.push(currentPuzzle.your_move_uci.slice(0, 2));
                            highlights.push(currentPuzzle.your_move_uci.slice(2, 4));
                          }
                          if (currentPuzzle.threat) {
                            const threat = currentPuzzle.threat;
                            if (/^[a-h][1-8]$/.test(threat)) {
                              highlights.push(threat);
                            } else if (threat.includes("x")) {
                              const match = threat.match(/x([a-h][1-8])/);
                              if (match) highlights.push(match[1]);
                            }
                          }
                          return highlights;
                        })()
                      : []
                  }
                />
              </div>
            ) : currentPuzzle?.game_url ? (
              <div className="aspect-square bg-muted/40 rounded-lg flex items-center justify-center">
                <div className="text-center p-6">
                  <p className="text-muted-foreground mb-4">
                    This puzzle is from Lichess
                  </p>
                  <Button onClick={() => window.open(currentPuzzle.game_url, "_blank")}>
                    Solve on Lichess
                  </Button>
                </div>
              </div>
            ) : (
              <div className="aspect-square bg-muted/40 rounded-lg flex items-center justify-center">
                <p className="text-muted-foreground">No puzzle available</p>
              </div>
            )}
          </div>

          {/* Coaching panel */}
          <div className="pt-2 flex flex-col min-h-[480px]">
            {(puzzleState === "thinking" || puzzleState === "evaluating") ? (
              <PuzzlePrompt
                framing={
                  currentPuzzle?.framing_text ||
                  currentPuzzle?.context ||
                  (currentPuzzle?.source === "your_game"
                    ? `From your own game — you had this position and the coach thought you could do better.`
                    : `This puzzle trains ${weakness.replace(/_/g, " ")}. Keep solving similar patterns and the recognition sticks.`)
                }
                question={puzzleState === "evaluating" ? "Checking your move…" : socraticQuestion}
                toMoveLabel={toMoveLabel}
                missRateText={
                  currentPuzzle?.source !== "your_game" ? currentPuzzle?.miss_rate_text : null
                }
                rating={puzzleRating}
                onReveal={revealSolution}
                onSkip={nextPuzzle}
                isFromOwnGame={currentPuzzle?.source === "your_game"}
              />
            ) : (
              <FeedbackPanel
                outcome={
                  puzzleState === "correct"
                    ? "correct"
                    : puzzleState === "acceptable"
                      ? "correct"  // advance path — "solid but not sharpest"
                      : puzzleState === "revealed"
                        ? "revealed"
                        : "missed"
                }
                principle={
                  // "acceptable" always has the evaluator's feedback
                  // ("Solid. X was sharper"). "correct" uses feedback if
                  // provided, else the generic encouragement.
                  isSolvedState
                    ? encouragement ||
                      "You saw the pattern. That's exactly the instinct we're building."
                    : currentPuzzle?.coaching?.what_you_missed ||
                      "Before moving, always check what your opponent just threatened."
                }
                san={
                  isSolvedState
                    ? solvedMoves
                    : userMove && solvedMoves
                      ? `${userMove} (you played) · ${solvedMoves} (solution)`
                      : currentPuzzle?.your_move && solvedMoves
                        ? `${currentPuzzle.your_move} (originally) · ${solvedMoves} (solution)`
                        : solvedMoves
                }
                threat={currentPuzzle?.threat}
                streak={streak}
                isComplete={isComplete}
                onNext={nextPuzzle}
                onRetry={retryPuzzle}
                onComplete={() => navigate("/home")}
                missCoaching={missCoaching}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────────── */
/*  Design-system components (from redesign/03_Training.html)                 */
/* ────────────────────────────────────────────────────────────────────────── */

// Progress pips: solved/missed/current/upcoming
function Pips({ pips }) {
  return (
    <div className="flex items-center gap-1.5">
      {pips.map((p, i) => {
        if (p === "solved")
          return <span key={i} className="h-1.5 w-6 rounded-full bg-emerald-400/70" />;
        if (p === "missed")
          return <span key={i} className="h-1.5 w-6 rounded-full bg-rose-400/70" />;
        if (p === "current")
          return (
            <span
              key={i}
              className="h-1.5 w-6 rounded-full bg-violet-400 ring-2 ring-violet-400/20 ring-offset-2 ring-offset-background"
            />
          );
        return <span key={i} className="h-1.5 w-6 rounded-full bg-muted" />;
      })}
    </div>
  );
}

// Pre-solve: provenance + Socratic question + community signal
function PuzzlePrompt({
  framing,
  question,
  toMoveLabel,
  missRateText,
  rating,
  onReveal,
  onSkip,
  isFromOwnGame,
}) {
  return (
    <>
      {/* Provenance — the differentiator */}
      <div className="mb-8">
        <div className="text-[10.5px] uppercase tracking-[0.22em] text-amber-500/90 dark:text-amber-300/80 font-semibold mb-3">
          {isFromOwnGame ? "From your game" : "Why this puzzle"}
        </div>
        <p className="text-[13.5px] text-muted-foreground leading-relaxed max-w-[420px]">
          {framing}
        </p>
      </div>

      {/* Socratic question — heart of the page */}
      <motion.div
        key={question}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: "easeOut" }}
        className="mb-auto"
      >
        <p className="font-serif italic text-[22px] md:text-[26px] leading-[1.25] tracking-[-0.01em] text-foreground max-w-[440px]">
          {question}
        </p>
        {toMoveLabel && (
          <p className="mt-4 text-[12.5px] text-muted-foreground">
            {toMoveLabel}. Play the move on the board.
          </p>
        )}
      </motion.div>

      {/* Footer: community signal + escape hatches */}
      <div className="pt-8 mt-8 border-t border-border/60 space-y-5">
        {missRateText && (
          <div className="flex items-center gap-2.5">
            <span className="h-1 w-1 rounded-full bg-amber-500/80" />
            <span className="text-[11.5px] text-muted-foreground">{missRateText}</span>
          </div>
        )}
        <div className="flex items-center gap-5 text-[12.5px] flex-wrap">
          <button
            onClick={onReveal}
            className="text-muted-foreground hover:text-foreground transition-colors inline-flex items-center gap-1.5"
          >
            <Eye className="h-3.5 w-3.5" strokeWidth={1.75} />
            Show the solution
          </button>
          <span className="text-border">·</span>
          <button
            onClick={onSkip}
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            Skip this one
          </button>
          {rating && (
            <span className="ml-auto text-[11px] text-muted-foreground/70 font-mono tabular-nums">
              rated {Math.round(rating)}
            </span>
          )}
        </div>
      </div>
    </>
  );
}

// Post-solve: correct / missed / revealed
function FeedbackPanel({
  outcome,
  principle,
  san,
  threat,
  streak,
  isComplete,
  onNext,
  onRetry,
  onComplete,
  missCoaching,
}) {
  const isCorrect = outcome === "correct";
  const isRevealed = outcome === "revealed";
  const toneBorder = isCorrect
    ? "border-emerald-400/30 bg-emerald-500/[0.04]"
    : isRevealed
      ? "border-blue-400/30 bg-blue-500/[0.04]"
      : "border-rose-400/30 bg-rose-500/[0.04]";
  const label = isCorrect ? "Correct" : isRevealed ? "Solution" : "Missed";
  const toneAccent = isCorrect
    ? "text-emerald-600 dark:text-emerald-300"
    : isRevealed
      ? "text-blue-600 dark:text-blue-300"
      : "text-rose-600 dark:text-rose-300";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className={`rounded-2xl border p-6 md:p-7 ${toneBorder}`}
    >
      <div className="grid grid-cols-[auto_1fr] md:grid-cols-[auto_1fr_auto] gap-5 md:gap-6 items-start">
        {/* Glyph */}
        <div
          className={`h-10 w-10 rounded-full flex items-center justify-center border ${
            isCorrect
              ? "border-emerald-400/40 bg-emerald-500/10"
              : isRevealed
                ? "border-blue-400/40 bg-blue-500/10"
                : "border-rose-400/40 bg-rose-500/10"
          }`}
        >
          {isCorrect ? (
            <CheckCircle2 className="h-4 w-4 text-emerald-500" strokeWidth={2} />
          ) : isRevealed ? (
            <Eye className="h-4 w-4 text-blue-500" strokeWidth={2} />
          ) : (
            <XCircle className="h-4 w-4 text-rose-500" strokeWidth={2} />
          )}
        </div>

        {/* Copy */}
        <div>
          <div className="flex items-baseline gap-3 mb-3 flex-wrap">
            <span
              className={`text-[10.5px] uppercase tracking-[0.2em] font-semibold ${toneAccent}`}
            >
              {label}
            </span>
            {san && (
              <span className="font-mono text-[12px] text-muted-foreground">{san}</span>
            )}
            {isCorrect && streak >= 3 && (
              <span className="text-[10.5px] uppercase tracking-[0.18em] text-amber-500 font-semibold">
                {streak} streak
              </span>
            )}
          </div>
          <p className="font-serif text-[17px] md:text-[19px] leading-snug text-foreground max-w-[540px] mb-3">
            {principle}
          </p>
          {threat && !isCorrect && (
            <p className="text-[13px] text-muted-foreground leading-relaxed max-w-[560px] mb-3">
              <span className="font-medium text-foreground/80">Threat: </span>
              {threat}
            </p>
          )}

          {/* Bug 2 fix: rich per-move explanations from
              build_miss_coaching. Only render on miss/revealed paths
              (correct moves don't need a critique). Cards stay tight —
              one short paragraph per available field, no filler. */}
          {!isCorrect && missCoaching && (
            <div className="mt-3 space-y-2 max-w-[560px]">
              {missCoaching.played_critique && (
                <div className="rounded-lg border border-rose-400/20 bg-rose-500/[0.03] p-3">
                  <div className="text-[10px] uppercase tracking-[0.18em] text-rose-500/80 font-semibold mb-1">
                    Why your move falls short
                  </div>
                  <p className="text-[13px] text-foreground/85 leading-relaxed">
                    {missCoaching.played_critique}
                  </p>
                </div>
              )}
              {missCoaching.best_move_idea && (
                <div className="rounded-lg border border-emerald-400/20 bg-emerald-500/[0.03] p-3">
                  <div className="text-[10px] uppercase tracking-[0.18em] text-emerald-600/80 dark:text-emerald-300/80 font-semibold mb-1">
                    Why the best move works
                  </div>
                  <p className="text-[13px] text-foreground/85 leading-relaxed">
                    {missCoaching.best_move_idea}
                  </p>
                </div>
              )}
              {missCoaching.takeaway && (
                <p className="text-[12px] italic text-muted-foreground leading-relaxed pl-1">
                  {missCoaching.takeaway}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Next */}
        <div className="col-span-2 md:col-span-1 md:text-right mt-2 md:mt-0">
          {isComplete ? (
            <Button onClick={onComplete} className="h-10 px-5 rounded-lg font-medium">
              <Trophy className="mr-2 h-3.5 w-3.5" />
              Training complete
            </Button>
          ) : isCorrect || isRevealed ? (
            <Button onClick={onNext} className="h-10 px-5 rounded-lg font-medium">
              Next puzzle
              <ChevronRight className="ml-2 h-3.5 w-3.5" />
            </Button>
          ) : (
            <div className="flex md:flex-col items-center md:items-end gap-2">
              <Button onClick={onRetry} className="h-10 px-5 rounded-lg font-medium">
                <RotateCcw className="mr-2 h-3.5 w-3.5" />
                Try again
              </Button>
              <button
                onClick={onNext}
                className="text-[11.5px] text-muted-foreground hover:text-foreground transition-colors"
              >
                Move on →
              </button>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
