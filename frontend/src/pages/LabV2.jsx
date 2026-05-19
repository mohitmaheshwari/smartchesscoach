/**
 * LabV2.jsx - Game Review Like a Coach
 * 
 * The Lab page redesigned to feel like a coaching session.
 * Top-to-bottom flow: Story → Learning → Action
 * 
 * NO engine dumps. NO cp values. Just coach talk.
 * 
 * Structure:
 * 1. Game Summary - The story
 * 2. Critical Moments - Interactive learning  
 * 3. Strategic Themes - Big picture
 * 4. Missed Tactics - Pattern recognition
 * 5. Habits to Improve - Homework
 */

import { useState, useEffect, useMemo, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Chess } from "chess.js";
import { motion } from "framer-motion";
import LichessBoard from "@/components/LichessBoard";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import Layout from "@/components/Layout";
import EvalBadge from "@/components/shared/EvalBadge";
import { InlineFlag } from "@/components/shared/FlagMoveDialog";
import { toast } from "sonner";
import {
  ArrowLeft,
  Play,
  Pause,
  ChevronLeft,
  ChevronRight,
  SkipBack,
  SkipForward,
  RotateCcw,
  Loader2,
  Brain,
  Target,
  Zap,
  BookOpen,
  MessageSquare,
  ChevronDown,
  History,
  Check,
  ArrowRight,
  Clock,
  XCircle,
  Flag
} from "lucide-react";

// Import new coach-style components
// import GameSummary from "@/components/lab/GameSummary";
// import CriticalMoments from "@/components/lab/CriticalMoments";
// import StrategicThemes from "@/components/lab/StrategicThemes";
// import MissedTactics from "@/components/lab/MissedTactics";
// import HabitsToImprove from "@/components/lab/HabitsToImprove";
// import OpeningFundamentals from "@/components/lab/OpeningFundamentals";
// import TrapAnalysis from "@/components/lab/TrapAnalysis";
// import DeepMemoryPanel from "@/components/DeepMemoryPanel";

// Feedback modal (reused from Lab.jsx)
import FeedbackModal from "@/components/FeedbackModal";
import GameDecryptionV5 from "@/components/GameDecryptionV5";
import CoachInsightPanel from "@/components/Lab/CoachInsightPanel";
import CoachSession from "@/components/coach/CoachSession";
import CoachAction from "@/components/Lab/CoachAction";
import CoachMovePanel from "@/components/coach/CoachMovePanel";

const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

// Sound effects using Web Audio API for chess moves
const useChessSounds = () => {
  const audioContextRef = useRef(null);
  
  const getAudioContext = useCallback(() => {
    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
    }
    return audioContextRef.current;
  }, []);
  
  // Play a "thud" sound for punishing moves
  const playPunishSound = useCallback(() => {
    try {
      const ctx = getAudioContext();
      const oscillator = ctx.createOscillator();
      const gainNode = ctx.createGain();
      
      oscillator.connect(gainNode);
      gainNode.connect(ctx.destination);
      
      // Low frequency "thud" sound
      oscillator.frequency.setValueAtTime(80, ctx.currentTime);
      oscillator.frequency.exponentialRampToValueAtTime(40, ctx.currentTime + 0.15);
      oscillator.type = 'sine';
      
      // Quick fade out for impact
      gainNode.gain.setValueAtTime(0.3, ctx.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.2);
      
      oscillator.start(ctx.currentTime);
      oscillator.stop(ctx.currentTime + 0.2);
    } catch (e) {
      console.log("Could not play sound:", e);
    }
  }, [getAudioContext]);
  
  // Play a "success" sound for correct moves
  const playSuccessSound = useCallback(() => {
    try {
      const ctx = getAudioContext();
      const oscillator = ctx.createOscillator();
      const gainNode = ctx.createGain();
      
      oscillator.connect(gainNode);
      gainNode.connect(ctx.destination);
      
      // Rising pleasant tone
      oscillator.frequency.setValueAtTime(440, ctx.currentTime);
      oscillator.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.15);
      oscillator.type = 'sine';
      
      gainNode.gain.setValueAtTime(0.2, ctx.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.2);
      
      oscillator.start(ctx.currentTime);
      oscillator.stop(ctx.currentTime + 0.2);
    } catch (e) {
      console.log("Could not play sound:", e);
    }
  }, [getAudioContext]);
  
  // Play a standard move sound (light click)
  const playMoveSound = useCallback(() => {
    try {
      const ctx = getAudioContext();
      const oscillator = ctx.createOscillator();
      const gainNode = ctx.createGain();
      
      oscillator.connect(gainNode);
      gainNode.connect(ctx.destination);
      
      oscillator.frequency.setValueAtTime(600, ctx.currentTime);
      oscillator.type = 'sine';
      
      gainNode.gain.setValueAtTime(0.1, ctx.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.05);
      
      oscillator.start(ctx.currentTime);
      oscillator.stop(ctx.currentTime + 0.05);
    } catch (e) {
      console.log("Could not play sound:", e);
    }
  }, [getAudioContext]);
  
  // Play an error sound for wrong moves
  const playErrorSound = useCallback(() => {
    try {
      const ctx = getAudioContext();
      const oscillator = ctx.createOscillator();
      const gainNode = ctx.createGain();
      
      oscillator.connect(gainNode);
      gainNode.connect(ctx.destination);
      
      // Descending "wrong" tone
      oscillator.frequency.setValueAtTime(300, ctx.currentTime);
      oscillator.frequency.exponentialRampToValueAtTime(150, ctx.currentTime + 0.15);
      oscillator.type = 'sawtooth';
      
      gainNode.gain.setValueAtTime(0.15, ctx.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15);
      
      oscillator.start(ctx.currentTime);
      oscillator.stop(ctx.currentTime + 0.15);
    } catch (e) {
      console.log("Could not play sound:", e);
    }
  }, [getAudioContext]);
  
  return { playPunishSound, playSuccessSound, playMoveSound, playErrorSound };
};

// Helper to convert FEN to position object
const fenToPositionObject = (fen) => {
  const chess = new Chess(fen);
  const board = chess.board();
  const position = {};
  
  for (let row = 0; row < 8; row++) {
    for (let col = 0; col < 8; col++) {
      const piece = board[row][col];
      if (piece) {
        const file = String.fromCharCode(97 + col);
        const rank = 8 - row;
        const square = `${file}${rank}`;
        const pieceCode = piece.color === 'w' 
          ? piece.type.toUpperCase() 
          : piece.type.toLowerCase();
        position[square] = pieceCode;
      }
    }
  }
  return position;
};

// Review completion overlay — shown after clicking "Done reviewing"
const ReviewCompleteOverlay = ({ summary, nextGame, navigate }) => {
  const { lesson_label, lesson, takeaway, concepts_learned, drills_solved } = summary || {};
  
  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="absolute inset-0 z-50 bg-background/95 backdrop-blur-sm flex items-center justify-center"
      data-testid="review-complete-overlay"
    >
      <motion.div 
        initial={{ opacity: 0, y: 20, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ delay: 0.1, duration: 0.3 }}
        className="max-w-md w-full mx-4"
      >
        {/* Check circle */}
        <div className="text-center mb-6">
          <div className="w-14 h-14 rounded-full bg-emerald-500/10 border-2 border-emerald-500/30 flex items-center justify-center mx-auto mb-4">
            <Check className="w-7 h-7 text-emerald-500" strokeWidth={2} />
          </div>
          <h2 className="text-xl font-semibold text-foreground tracking-tight" data-testid="review-complete-title">Review complete</h2>
        </div>
        
        {/* What you learned */}
        {(lesson || lesson_label) && (
          <div className="bg-card border border-border rounded-lg p-5 mb-4">
            {lesson_label && (
              <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-amber-700 dark:text-amber-400 block mb-1.5">
                {lesson_label}
              </span>
            )}
            {lesson && (
              <p className="text-sm text-foreground leading-relaxed">{lesson}</p>
            )}
            {takeaway && (
              <p className="text-xs text-muted-foreground mt-2 leading-relaxed">{takeaway}</p>
            )}
          </div>
        )}
        
        {/* Stats row */}
        {(concepts_learned > 0 || drills_solved > 0) && (
          <div className="flex gap-3 mb-6">
            {concepts_learned > 0 && (
              <div className="flex-1 bg-muted/40 rounded-lg py-3 text-center">
                <p className="text-lg font-bold text-foreground font-mono">{concepts_learned}</p>
                <p className="text-[10px] text-muted-foreground">concepts learned</p>
              </div>
            )}
            {drills_solved > 0 && (
              <div className="flex-1 bg-muted/40 rounded-lg py-3 text-center">
                <p className="text-lg font-bold text-foreground font-mono">{drills_solved}</p>
                <p className="text-[10px] text-muted-foreground">drills solved</p>
              </div>
            )}
          </div>
        )}
        
        {/* Actions */}
        <div className="space-y-2.5">
          {nextGame ? (
            <button
              onClick={() => navigate(`/game/${nextGame.game_id}`)}
              className="w-full py-3 rounded-lg bg-foreground text-background font-medium text-sm hover:opacity-90 transition-opacity flex items-center justify-center gap-2"
              data-testid="review-next-game-btn"
            >
              Next game: vs {nextGame.opponent}
              <ArrowRight className="w-4 h-4" />
            </button>
          ) : (
            <button
              onClick={() => navigate("/lab")}
              className="w-full py-3 rounded-lg bg-foreground text-background font-medium text-sm hover:opacity-90 transition-opacity"
              data-testid="review-back-to-lab-btn"
            >
              Back to Lab
            </button>
          )}
          
          <button
            onClick={() => navigate("/lab")}
            className="w-full py-2.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
            data-testid="review-go-lab-btn"
          >
            Go to Lab queue
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
};

// Result badge with semantic colors
const ResultBadge = ({ result, userColor }) => {
  const isWin = (result.includes("1-0") && userColor === "white") || (result.includes("0-1") && userColor === "black");
  const isDraw = result === "1/2-1/2";
  const label = isWin ? "Won" : isDraw ? "Draw" : "Lost";
  const cls = isWin 
    ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/30"
    : isDraw 
      ? "bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30"
      : "bg-red-500/15 text-red-700 dark:text-red-400 border-red-500/30";
  return (
    <span className={`px-2 py-0.5 text-xs font-semibold rounded border ${cls}`} data-testid="result-badge">
      {label}
    </span>
  );
};

const TerminationTag = ({ termination, result, userColor }) => {
  const isWin = (result.includes("1-0") && userColor === "white") || (result.includes("0-1") && userColor === "black");
  const isDraw = result === "1/2-1/2";

  const labels = {
    checkmate: isWin ? "by checkmate" : "by checkmate",
    resignation: isWin ? "by resignation" : "by resignation",
    timeout: isWin ? "on time" : "on time",
    abandonment: "abandoned",
    stalemate: "stalemate",
    draw_agreement: "by agreement",
    repetition: "by repetition",
    insufficient: "insufficient material",
  };

  const label = labels[termination];
  if (!label) return null;

  const isTimeout = termination === "timeout";
  const isAbandoned = termination === "abandonment";

  // Highlight timeout/abandoned losses as they're weaknesses
  const userLost = !isWin && !isDraw;
  if (userLost && isTimeout) {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-medium rounded border text-orange-500 dark:text-orange-400 bg-orange-500/10 border-orange-500/20">
        <Clock className="w-2.5 h-2.5" strokeWidth={2} />
        {label}
      </span>
    );
  }
  if (userLost && isAbandoned) {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-medium rounded border text-gray-500 dark:text-gray-400 bg-gray-500/10 border-gray-500/20">
        <XCircle className="w-2.5 h-2.5" strokeWidth={2} />
        {label}
      </span>
    );
  }

  return (
    <span className="px-1.5 py-0.5 text-[10px] text-muted-foreground border border-border/50 rounded">
      {label}
    </span>
  );
};

const LabV2 = ({ user }) => {
  const { gameId } = useParams();
  const navigate = useNavigate();
  
  // Sound effects
  const { playPunishSound, playSuccessSound, playMoveSound, playErrorSound } = useChessSounds();
  
  // Data states
  const [loading, setLoading] = useState(true);
  const [game, setGame] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [labData, setLabData] = useState(null);
  const [coachReview, setCoachReview] = useState(null);
  const [sessionDismissed, setSessionDismissed] = useState(false); // User explicitly dismissed
  const [deepStrategy, setDeepStrategy] = useState(null);
  const [loadingDeepStrategy, setLoadingDeepStrategy] = useState(false);
  const [focusModule, setFocusModule] = useState(null);
  
  // Board states
  const [moves, setMoves] = useState([]);
  const [allFens, setAllFens] = useState([START_FEN]);
  const [currentMoveIndex, setCurrentMoveIndex] = useState(-1);
  const [positionObject, setPositionObject] = useState(() => fenToPositionObject(START_FEN));
  const [boardOrientation, setBoardOrientation] = useState("white");
  const [lastMoveSquares, setLastMoveSquares] = useState({});
  const [isPlaying, setIsPlaying] = useState(false);
  const [boardArrows, setBoardArrows] = useState([]); // Arrows for the board
  const [isPlayingBestLine, setIsPlayingBestLine] = useState(false); // Auto-playing best line
  const [bestLineIndex, setBestLineIndex] = useState(0); // Current position in best line
  const [currentBestLine, setCurrentBestLine] = useState(null); // Current best line being played
  const [interactiveMoment, setInteractiveMoment] = useState(null); // Current moment user is trying to solve
  const [userAttemptResult, setUserAttemptResult] = useState(null); // Result of user's move attempt
  const [interactiveFen, setInteractiveFen] = useState(null); // FEN for interactive mode (to allow resetting)
  // Holds the pending "play the right line after a wrong answer" timeout so
  // handleTryAgain can cancel it if the user retries before the line fires.
  const wrongAnswerLineTimeoutRef = useRef(null);

  // UI states
  const [activeTab, setActiveTab] = useState("summary");
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [feedbackContext, setFeedbackContext] = useState(null);
  const [viewMode, setViewMode] = useState("decrypt"); // "decrypt" (primary) or "coach" (overview)
  
  // Review completion tracking
  const [reviewComplete, setReviewComplete] = useState(false);
  const [reviewSummary, setReviewSummary] = useState(null);
  const [completingReview, setCompletingReview] = useState(false);
  const tabsVisitedRef = useRef(new Set(["decrypt"])); // Track which tabs user visited
  
  // Track tab visits
  useEffect(() => {
    tabsVisitedRef.current.add(viewMode);
  }, [viewMode]);
  
  // Derived data
  const userColor = game?.user_color || "white";
  const result = game?.result || "1/2-1/2";
  const accuracy = analysis?.stockfish_analysis?.accuracy || labData?.accuracy;
  // Always show position AFTER the current move (standard behavior)
  // The coaching panel handles the "what should you have done" part
  const currentFen = allFens[currentMoveIndex + 1] || START_FEN;
  const coachSummary = analysis?.coach_summary || null;
  const coreLesson = labData?.core_lesson || null;
  
  // Fetch all data
  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch game
        const gameRes = await fetch(`${API}/games/${gameId}`, { credentials: "include" });
        if (!gameRes.ok) throw new Error("Game not found");
        const gameData = await gameRes.json();
        setGame(gameData);
        setBoardOrientation(gameData.user_color === "black" ? "black" : "white");
        
        // Fetch analysis (use enriched endpoint for coach layer)
        const analysisRes = await fetch(`${API}/analysis/${gameId}/enriched`, { credentials: "include" });
        if (analysisRes.ok) {
          setAnalysis(await analysisRes.json());
        } else {
          // Fallback to basic analysis
          const basicRes = await fetch(`${API}/analysis/${gameId}`, { credentials: "include" });
          if (basicRes.ok) {
            setAnalysis(await basicRes.json());
          }
        }
        
        // Fetch lab data
        const labRes = await fetch(`${API}/lab/${gameId}`, { credentials: "include" });
        if (labRes.ok) {
          setLabData(await labRes.json());
        }

        // Fetch coach review (phases, opening, behaviors, fundamentals)
        try {
          const crRes = await fetch(`${API}/games/${gameId}/coach-review`, { credentials: "include" });
          if (crRes.ok) setCoachReview(await crRes.json());
        } catch (e) { /* non-fatal */ }
        
        // Fetch focus module
        try {
          const focusRes = await fetch(`${API}/cognitive/training-priority`, { credentials: "include" });
          if (focusRes.ok) {
            const focusData = await focusRes.json();
            if (focusData.primary_focus) {
              setFocusModule(focusData.primary_focus);
            }
          }
        } catch (e) {
          // Focus module not critical
        }
        
      } catch (error) {
        toast.error("Failed to load game");
        navigate("/lab");
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
  }, [gameId, navigate]);
  
  // Fetch deep strategy (for critical moments detail)
  useEffect(() => {
    const fetchDeepStrategy = async () => {
      if (!gameId || deepStrategy || loadingDeepStrategy) return;
      
      setLoadingDeepStrategy(true);
      try {
        const res = await fetch(`${API}/lab/${gameId}/deep-strategy`, { credentials: "include" });
        if (res.ok) {
          setDeepStrategy(await res.json());
        }
      } catch (e) {
        console.log("Deep strategy not available");
      } finally {
        setLoadingDeepStrategy(false);
      }
    };
    
    fetchDeepStrategy();
  }, [gameId, deepStrategy, loadingDeepStrategy]);
  
  // Build moves and FENs from game
  useEffect(() => {
    if (!game?.pgn) return;
    
    try {
      const chess = new Chess();
      chess.loadPgn(game.pgn);
      const history = chess.history({ verbose: true });
      
      // Build FENs
      const fens = [START_FEN];
      const tempChess = new Chess();
      
      history.forEach(move => {
        tempChess.move(move.san);
        fens.push(tempChess.fen());
      });
      
      setMoves(history);
      setAllFens(fens);
      setPositionObject(fenToPositionObject(START_FEN));
    } catch (e) {
      console.error("Failed to parse PGN:", e);
    }
  }, [game?.pgn]);
  
  // Update position when move index changes — always show AFTER the move
  useEffect(() => {
    const fen = allFens[currentMoveIndex + 1] || START_FEN;
    setPositionObject(fenToPositionObject(fen));

    if (currentMoveIndex >= 0 && moves[currentMoveIndex]) {
      const move = moves[currentMoveIndex];
      setLastMoveSquares({
        [move.from]: { background: "rgba(255, 255, 0, 0.4)" },
        [move.to]: { background: "rgba(255, 255, 0, 0.4)" }
      });
    } else {
      setLastMoveSquares({});
    }
  }, [currentMoveIndex, allFens, moves]);
  
  // Navigation functions
  const goToMove = (index, clearArrows = true) => {
    setCurrentMoveIndex(Math.max(-1, Math.min(index, moves.length - 1)));
    setIsPlaying(false);
    if (clearArrows) {
      setBoardArrows([]); // Clear arrows on manual navigation
    }
  };
  
  const goToStart = () => goToMove(-1);
  const goToEnd = () => goToMove(moves.length - 1);

  // In Coach/Habits view: jump between important moves only
  // In Decrypt view: step through every move (handled by GameDecryptionV5)
  const findEvalForMove = (idx) => {
    const evals = analysis?.stockfish_analysis?.move_evaluations || [];
    if (idx < 0 || idx >= moves.length) return null;
    const m = moves[idx];
    const moveNum = Math.floor(idx / 2) + 1;
    return evals.find(e => e.move_number === moveNum && e.move === m.san)
        || evals.find(e => e.move === m.san)
        || null;
  };

  const isImportantMove = (idx) => {
    // Check user moves via move_evaluations
    const evalData = findEvalForMove(idx);
    if (evalData) {
      const c = (evalData.classification || evalData.evaluation || "").toLowerCase();
      if (c.includes("blunder") || c.includes("mistake") || c.includes("brilliant")) {
        return true;
      }
    }

    // Check opponent moves — detect blunders from cp_loss
    const isUserMove = (userColor === "white" && idx % 2 === 0) || (userColor === "black" && idx % 2 === 1);
    if (!isUserMove && idx < moves.length) {
      // For opponent moves: check if the NEXT user move's eval_before improved significantly
      // compared to the previous user move's eval_after (meaning opponent gave away advantage)
      const evals = analysis?.stockfish_analysis?.move_evaluations || [];
      const moveNum = Math.floor(idx / 2) + 1;

      // Find eval BEFORE this opponent move (from previous user move's eval_after)
      // and eval AFTER (from next user move's eval_before)
      const prevUserEvalIdx = isUserMove ? idx : idx - 1;
      const nextUserEvalIdx = isUserMove ? idx : idx + 1;

      const prevEval = findEvalForMove(prevUserEvalIdx);
      const nextEval = findEvalForMove(nextUserEvalIdx);

      if (prevEval && nextEval) {
        const evalBefore = prevEval.eval_after || 0;
        const evalAfter = nextEval.eval_before || 0;
        // Eval swing in user's favor = opponent blundered
        const userIsWhite = userColor === "white";
        const swingForUser = userIsWhite ? (evalAfter - evalBefore) : (evalBefore - evalAfter);
        // Normalize if float
        const swing = Math.abs(swingForUser) < 100 ? swingForUser * 100 : swingForUser;
        if (swing >= 150) return true; // Opponent lost 150+ cp
      }
    }

    return false;
  };

  const goToPrev = () => {
    if (viewMode === "decrypt") {
      goToMove(currentMoveIndex - 1);
      return;
    }
    // Coach/Habits: if we're on the mistake move, go back to the opponent's move before it
    if (currentMoveIndex >= 1 && isImportantMove(currentMoveIndex)) {
      goToMove(currentMoveIndex - 1);
      return;
    }
    // If we're on the opponent's move before a mistake, jump to the previous important move's opponent move
    let i = currentMoveIndex - 1;
    while (i >= 0 && !isImportantMove(i)) i--;
    if (i >= 1) {
      goToMove(i - 1); // Show opponent's move before the mistake
    } else {
      goToMove(Math.max(-1, i));
    }
  };

  const goToNext = () => {
    if (viewMode === "decrypt") {
      goToMove(currentMoveIndex + 1);
      return;
    }
    // Coach/Habits: two-step navigation per moment
    // Step 1: opponent's move (context) → Step 2: your mistake move (the moment)

    // If we're on the opponent's move before a mistake, advance to the mistake
    if (currentMoveIndex >= 0 && currentMoveIndex < moves.length - 1 && isImportantMove(currentMoveIndex + 1)) {
      goToMove(currentMoveIndex + 1);
      return;
    }

    // Otherwise find the next important move and show the opponent's move before it
    let i = currentMoveIndex + 1;
    while (i < moves.length && !isImportantMove(i)) i++;
    if (i < moves.length) {
      if (i >= 1) {
        goToMove(i - 1); // Show opponent's move first (context)
      } else {
        goToMove(i); // First move of the game
      }
    }
  };

  // Keyboard arrow navigation
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;
      switch (e.key) {
        case 'ArrowRight': e.preventDefault(); goToNext(); break;
        case 'ArrowLeft': e.preventDefault(); goToPrev(); break;
        case 'ArrowUp': e.preventDefault(); goToStart(); break;
        case 'ArrowDown': e.preventDefault(); goToEnd(); break;
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentMoveIndex, moves.length]);

  
  // Navigate to a specific move number (from critical moments) with optional arrows
  const navigateToMoveNumber = (moveNum, yourMove = null, bestMove = null) => {
    // Navigate to show the position where the user needs to make a decision
    // 
    // UI shows "Move X / 67" where X is the half-move count (0 = start, 1 = after White's 1st, etc.)
    // 
    // For move 22 White (it's White's turn at full move 22):
    // - Position is AFTER 21 full moves completed = after 42 half-moves
    // - UI should show "Move 42"
    // - goToMove index = 42 (since we pass the current move count)
    //
    // For move 22 Black (it's Black's turn at full move 22):
    // - Position is AFTER White's 22nd move = after 43 half-moves
    // - UI should show "Move 43"
    // - goToMove index = 43
    
    let targetMoveCount;
    if (userColor === "white") {
      // White's turn at move N: after (N-1) full moves = after 2*(N-1) half-moves
      targetMoveCount = (moveNum - 1) * 2;
    } else {
      // Black's turn at move N: after White's Nth move = after 2*(N-1)+1 = 2*N-1 half-moves
      targetMoveCount = (moveNum * 2) - 1;
    }
    
    // Ensure valid range
    targetMoveCount = Math.max(0, Math.min(targetMoveCount, moves.length));
    
    console.log(`Navigating: move ${moveNum}, userColor=${userColor}, targetMoveCount=${targetMoveCount}, totalMoves=${moves.length}`);
    
    // goToMove expects the index in the moves array, which is moveCount - 1
    // But if moveCount is 0, we want the start position (index -1)
    goToMove(targetMoveCount - 1, false);
    
    // Set arrows if moves are provided
    const newArrows = [];
    if (yourMove && yourMove.length >= 4) {
      // Red arrow for user's move (what they played)
      const from = yourMove.substring(0, 2);
      const to = yourMove.substring(2, 4);
      newArrows.push([from, to, "red"]);
    }
    if (bestMove && bestMove.length >= 4) {
      // Green arrow for best move (what they should have played)
      const from = bestMove.substring(0, 2);
      const to = bestMove.substring(2, 4);
      newArrows.push([from, to, "green"]);
    }
    setBoardArrows(newArrows);
  };
  
  // Complete review — save what was learned, mark as reviewed, get next game
  const completeReview = async (stats = {}) => {
    if (completingReview) return;
    setCompletingReview(true);
    try {
      const res = await fetch(`${API}/lab/${gameId}/complete-review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          concepts_learned: stats.conceptsLearned || 0,
          drills_solved: stats.drillsSolved || 0,
          tabs_visited: Array.from(tabsVisitedRef.current),
          moves_viewed: currentMoveIndex + 1,
          total_moves: moves.length,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setReviewSummary(data);
        setReviewComplete(true);
      } else {
        toast.error("Failed to save review");
      }
    } catch (e) {
      toast.error("Failed to save review");
    } finally {
      setCompletingReview(false);
    }
  };
  
  // Play Best Line - Shows the continuation after the best move
  // Compose a brief annotation for a played ply. Per the multi-move-review
  // spec (memory/project_multi_move_review_play_the_line.md): annotate ONLY
  // when the move adds meaning. Honest silence over fluffy commentary per
  // [[no-hollow-coverage]]. Returns string OR empty string.
  //
  // The chess.js move object exposes:
  //   .flags (string of letters: 'n' normal, 'b' bigpawn, 'e' en passant,
  //           'c' capture, 'p' promotion, 'k' kside castle, 'q' qside castle)
  //   .captured (piece letter if capture)
  //   .promotion (piece letter if promotion)
  //   .san (move with #/+ suffix for mate/check)
  const _annotateLineMove = (moveObj, indexInLine, totalMoves) => {
    if (!moveObj) return "";
    const san = moveObj.san || "";
    const flags = moveObj.flags || "";
    const isMate = san.endsWith("#");
    const isCheck = san.endsWith("+");
    const isCapture = flags.includes("c") || flags.includes("e");
    const isPromotion = flags.includes("p");
    const isCastle = flags.includes("k") || flags.includes("q");

    const PIECE_NAMES = { p: "pawn", n: "knight", b: "bishop", r: "rook", q: "queen", k: "king" };
    const capturedName = moveObj.captured ? PIECE_NAMES[moveObj.captured] || "piece" : "";

    if (isMate) return "Checkmate.";
    if (isCheck && isCapture) return `Check — takes the ${capturedName}.`;
    if (isCheck) return "Check forces the king.";
    if (isCapture && capturedName) return `Takes the ${capturedName}.`;
    if (isPromotion) return `Promotes to ${PIECE_NAMES[moveObj.promotion] || "queen"}.`;
    if (isCastle) return "Castles to safety.";
    // First move in the line gets a softer marker so the user sees the
    // "this is the engine pick" anchor; downstream silent moves are
    // forced/quiet and don't need annotation.
    if (indexInLine === 0 && totalMoves > 1) return "Engine's pick — continuation follows.";
    return "";
  };

  const playBestLine = (moment) => {
    if (!moment || !moment.fen || !moment.best_move) {
      return;
    }

    try {
      const chess = new Chess(moment.fen);
      const lineMoves = [];
      const lineFens = [moment.fen];

      // First, play the best move
      const bestMove = chess.move(moment.best_move, { sloppy: true });
      if (bestMove) {
        lineMoves.push({
          san: bestMove.san || moment.best_move,
          from: bestMove.from,
          to: bestMove.to,
          // Defer annotation — we need to know totalMoves first.
          _moveObj: bestMove,
        });
        lineFens.push(chess.fen());
      } else {
        console.log("Could not play best move:", moment.best_move);
        return;
      }

      // Then play the PV continuation if available
      const pvLine = moment.pv_after_best || moment.best_line?.split(/\s+/) || [];

      for (const moveStr of pvLine.slice(0, 5)) { // Limit to 5 more moves
        try {
          const move = chess.move(moveStr, { sloppy: true });
          if (move) {
            lineMoves.push({
              san: move.san || moveStr,
              from: move.from,
              to: move.to,
              _moveObj: move,
            });
            lineFens.push(chess.fen());
          } else {
            break;
          }
        } catch {
          break;
        }
      }

      // Length-aware behavior per the locked spec: if PV is single-move
      // (just the best move with no continuation), don't auto-animate —
      // the static "best move" display in the existing KeyMomentCard is
      // enough. Auto-animate only when there's a multi-move sequence to
      // demonstrate.
      if (lineMoves.length <= 1) {
        // Still show the best move on the board, but no auto-loop.
        // (Existing callers also use playBestLine for single-move cases;
        // we keep the behavior compatible — show + hold + reset.)
      }

      // Compute annotations now that we know the total length.
      const annotatedMoves = lineMoves.map((m, i) => ({
        san: m.san,
        from: m.from,
        to: m.to,
        note: _annotateLineMove(m._moveObj, i, lineMoves.length),
      }));

      if (annotatedMoves.length > 0) {
        setCurrentBestLine({
          startFen: moment.fen,
          moves: annotatedMoves,
          fens: lineFens,
        });
        setBestLineIndex(0);
        setIsPlayingBestLine(true);
        // Clear arrows while playing line
        setBoardArrows([]);
      }
    } catch (e) {
      console.log("Could not parse best line:", e);
    }
  };
  
  // Start interactive mode for a critical moment - user can try to find the best move
  const startInteractiveMoment = (moment) => {
    console.log("Starting interactive moment:", moment);
    console.log("Moment FEN:", moment?.fen);
    console.log("Best move:", moment?.best_move);
    
    setInteractiveMoment(moment);
    setUserAttemptResult(null);
    setInteractiveFen(moment.fen); // Set the FEN for interactive mode
    // Stop any playing line
    setIsPlayingBestLine(false);
    setCurrentBestLine(null);
    
    // Find the correct move index for this moment's position
    // The moment has the FEN, we need to find when this FEN appeared
    const momentFenPrefix = moment.fen?.split(' ')[0]; // Just the position part
    
    if (momentFenPrefix) {
      console.log("Looking for FEN prefix:", momentFenPrefix);
      // Find the move index where this position occurs
      for (let i = 0; i < allFens.length; i++) {
        if (allFens[i]?.startsWith(momentFenPrefix)) {
          console.log("Found FEN at index:", i);
          goToMove(i - 1, false); // -1 because allFens[0] is start position
          setBoardArrows([]);
          return;
        }
      }
      console.log("FEN not found in game history, using fallback");
    }
    
    // Fallback: Use move number based navigation
    // Show position BEFORE the user's move
    const baseIndex = (moment.move_number - 1) * 2;
    const targetIndex = userColor === "black" ? baseIndex : baseIndex - 1;
    console.log("Fallback: move number", moment.move_number, "-> index", targetIndex);
    goToMove(Math.max(-1, Math.min(targetIndex, moves.length - 1)), false);
    setBoardArrows([]);
  };
  
  // Handle user's move attempt on a critical moment
  // Now with smarter evaluation - not just "correct/wrong" but nuanced feedback
  const handleUserMoveAttempt = async (from, to) => {
    console.log("handleUserMoveAttempt called:", { from, to, interactiveMoment: !!interactiveMoment });
    if (!interactiveMoment) return false;
    
    const userMoveUci = from + to;
    
    // Get the best move in UCI format for local comparison
    let bestMoveUci = null;
    try {
      const chess = new Chess(interactiveMoment.fen);
      const bestMove = chess.move(interactiveMoment.best_move, { sloppy: true });
      if (bestMove) {
        bestMoveUci = bestMove.from + bestMove.to;
      }
    } catch (e) {
      console.log("Could not parse best move:", e);
    }
    
    // Call backend for smart move evaluation
    try {
      const evalResponse = await fetch(`${API}/lab/evaluate-move`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          fen: interactiveMoment.fen,
          user_move: userMoveUci,
          best_move: interactiveMoment.best_move,
          // key_moments from /coach-review use `move` for the user's
          // actually-played move; older callers use `your_move`.
          original_move: interactiveMoment.your_move || interactiveMoment.move || null
        })
      });
      
      if (evalResponse.ok) {
        const evalResult = await evalResponse.json();
        
        // Handle based on move quality
        if (evalResult.is_correct) {
          // Good enough move - play success
          playSuccessSound();
          
          // Determine arrow color based on quality
          const arrowColor = evalResult.quality === "best" ? "green" : 
                            evalResult.quality === "excellent" ? "green" :
                            evalResult.quality === "good" ? "rgb(34,197,94)" : "rgb(234,179,8)";
          
          setUserAttemptResult({
            correct: true,
            quality: evalResult.quality,
            symbol: evalResult.symbol,
            message: evalResult.message,
            feedback: evalResult.feedback,
            comparison: evalResult.comparison_to_original,
            userMove: userMoveUci,
            bestMove: bestMoveUci
          });
          
          setBoardArrows([[from, to, arrowColor]]);
          
          // Store the moment before clearing interactive state
          const momentToPlay = interactiveMoment;
          setInteractiveMoment(null);
          setInteractiveFen(null);
          
          // Play the line after a short delay
          setTimeout(() => playBestLine(momentToPlay), 1500);
          
          // Show appropriate toast
          if (evalResult.quality === "best") {
            toast.success("Perfect! You found the best move!");
          } else if (evalResult.comparison_to_original === "better") {
            toast.success(evalResult.feedback);
          } else {
            toast.info(evalResult.feedback);
          }
        } else {
          // Not good enough - show feedback with punishment
          playErrorSound();
          
          // Determine feedback based on quality
          const isOkay = evalResult.quality === "okay" || evalResult.quality === "inaccuracy";
          
          // Show user's move with appropriate color
          const arrowColor = isOkay ? "rgb(234,179,8)" : "red"; // Yellow for okay, red for bad
          setBoardArrows([[from, to, arrowColor]]);
          
          // Make the user's move on a temp board to show the position
          try {
            const tempChess = new Chess(interactiveMoment.fen);
            const userMove = tempChess.move({ from, to, promotion: 'q' });
            if (userMove) {
              setInteractiveFen(tempChess.fen());
              
              // For bad moves, show punishment animation
              if (!isOkay) {
                setTimeout(() => {
                  try {
                    const punishChess = new Chess(tempChess.fen());
                    const allMoves = punishChess.moves({ verbose: true });
                    let punishMove = null;
                    let punishMoveNotation = null;
                    
                    // Find a punishing move - priority: checkmates > checks > captures
                    const checkmates = allMoves.filter(m => {
                      const testChess = new Chess(punishChess.fen());
                      testChess.move(m);
                      return testChess.isCheckmate();
                    });
                    if (checkmates.length > 0) {
                      punishMove = punishChess.move(checkmates[0]);
                      punishMoveNotation = checkmates[0].san;
                    }
                    
                    if (!punishMove) {
                      const checks = allMoves.filter(m => {
                        const testChess = new Chess(punishChess.fen());
                        testChess.move(m);
                        return testChess.inCheck();
                      });
                      if (checks.length > 0) {
                        punishMove = punishChess.move(checks[0]);
                        punishMoveNotation = checks[0].san;
                      }
                    }
                    
                    if (!punishMove) {
                      const pieceValues = { q: 9, r: 5, b: 3, n: 3, p: 1 };
                      const captures = allMoves.filter(m => m.captured);
                      captures.sort((a, b) => (pieceValues[b.captured] || 0) - (pieceValues[a.captured] || 0));
                      if (captures.length > 0) {
                        punishMove = punishChess.move(captures[0]);
                        punishMoveNotation = captures[0].san;
                      }
                    }
                    
                    if (punishMove) {
                      playPunishSound();
                      setInteractiveFen(punishChess.fen());
                      setBoardArrows([
                        [from, to, arrowColor],
                        [punishMove.from, punishMove.to, "orange"]
                      ]);
                      
                      setUserAttemptResult(prev => ({
                        ...prev,
                        punishingMove: punishMoveNotation,
                        showPunishment: true
                      }));
                      
                      toast.error(`Opponent plays ${punishMoveNotation}!`, { duration: 3000 });
                    }
                  } catch (e) {
                    console.log("Could not calculate punishing move:", e);
                  }
                }, 1000);
              }
            }
          } catch (e) {
            console.log("Could not make user move:", e);
          }
          
          setUserAttemptResult({
            correct: false,
            quality: evalResult.quality,
            symbol: evalResult.symbol,
            message: evalResult.message,
            feedback: evalResult.feedback,
            comparison: evalResult.comparison_to_original,
            userMove: userMoveUci,
            bestMove: bestMoveUci,
            showTryAgain: isOkay, // Show try again immediately for okay moves
            showPunishment: false,
            punishingMove: null
          });
          
          // For bad moves, show Try Again after punishment, then auto-replay
          // the right line. Per the locked spec: wrong answers are exactly
          // when users most need to SEE the right line played, not just told.
          if (!isOkay) {
            setTimeout(() => {
              setUserAttemptResult(prev => prev ? ({
                ...prev,
                showTryAgain: true
              }) : null);
            }, 2500);

            const momentForLine = interactiveMoment;
            if (wrongAnswerLineTimeoutRef.current) {
              clearTimeout(wrongAnswerLineTimeoutRef.current);
            }
            // t=4500ms: after the 3s punishment toast clears, reset the board
            // to the original moment FEN and play the correct line.
            wrongAnswerLineTimeoutRef.current = setTimeout(() => {
              wrongAnswerLineTimeoutRef.current = null;
              if (momentForLine) {
                setBoardArrows([]);
                setInteractiveFen(momentForLine.fen);
                playBestLine(momentForLine);
              }
            }, 4500);
          }

          // Show appropriate toast
          if (isOkay) {
            toast.info(evalResult.feedback);
          } else {
            toast.error(evalResult.feedback);
          }
        }
        
        return evalResult.is_correct;
      }
    } catch (e) {
      console.log("Could not evaluate move, falling back to local check:", e);
    }
    
    // Fallback to simple local check if API fails
    const isCorrect = userMoveUci === bestMoveUci;
    
    if (isCorrect) {
      playSuccessSound();
      setUserAttemptResult({
        correct: true,
        quality: "best",
        symbol: "check",
        message: "Perfect!",
        userMove: userMoveUci,
        bestMove: bestMoveUci
      });
      setBoardArrows([[from, to, "green"]]);
      const momentToPlay = interactiveMoment;
      setInteractiveMoment(null);
      setInteractiveFen(null);
      setTimeout(() => playBestLine(momentToPlay), 1500);
      toast.success("Correct! Great find!");
    } else {
      playErrorSound();
      setBoardArrows([[from, to, "red"]]);
      setUserAttemptResult({
        correct: false,
        quality: "unknown",
        symbol: "close",
        message: "Not the best move",
        userMove: userMoveUci,
        bestMove: bestMoveUci,
        showTryAgain: true
      });
      toast.error("Not quite right. Try again!");

      // Local-fallback wrong path: no quality dimension, no punishment
      // animation. Still want the user to SEE the right line so they
      // understand what they missed.
      const momentForLine = interactiveMoment;
      if (wrongAnswerLineTimeoutRef.current) {
        clearTimeout(wrongAnswerLineTimeoutRef.current);
      }
      wrongAnswerLineTimeoutRef.current = setTimeout(() => {
        wrongAnswerLineTimeoutRef.current = null;
        if (momentForLine) {
          setBoardArrows([]);
          setInteractiveFen(momentForLine.fen);
          playBestLine(momentForLine);
        }
      }, 1500);
    }

    return isCorrect;
  };
  
  // Clear interactive mode
  const clearInteractiveMoment = () => {
    if (wrongAnswerLineTimeoutRef.current) {
      clearTimeout(wrongAnswerLineTimeoutRef.current);
      wrongAnswerLineTimeoutRef.current = null;
    }
    setInteractiveMoment(null);
    setUserAttemptResult(null);
    setInteractiveFen(null);
  };
  
  // Reset for try again - go back to original position
  const handleTryAgain = () => {
    // Cancel any pending or in-flight "play the right line" replay so the
    // user gets their fresh attempt instead of an animation barging in.
    if (wrongAnswerLineTimeoutRef.current) {
      clearTimeout(wrongAnswerLineTimeoutRef.current);
      wrongAnswerLineTimeoutRef.current = null;
    }
    if (isPlayingBestLine) {
      setIsPlayingBestLine(false);
      setCurrentBestLine(null);
      setBestLineIndex(0);
    }
    if (interactiveMoment) {
      setUserAttemptResult(null);
      setBoardArrows([]);
      setInteractiveFen(interactiveMoment.fen);
    }
  };
  
  // Auto-play best line
  useEffect(() => {
    if (!isPlayingBestLine || !currentBestLine) return;
    
    const interval = setInterval(() => {
      setBestLineIndex(prev => {
        if (prev >= currentBestLine.fens.length - 1) {
          // Keep showing the final position for 2 seconds, then reset
          setTimeout(() => {
            setIsPlayingBestLine(false);
            setCurrentBestLine(null);
          }, 2000);
          return prev;
        }
        return prev + 1;
      });
    }, 1200);
    
    return () => clearInterval(interval);
  }, [isPlayingBestLine, currentBestLine]);
  
  // Get the current FEN - either from best line, interactive moment, or game
  const displayFen = isPlayingBestLine && currentBestLine 
    ? currentBestLine.fens[bestLineIndex]
    : interactiveFen || currentFen;
  
  // Debug: Log when interactive mode is active
  if (interactiveFen) {
    console.log("Interactive FEN active:", interactiveFen.substring(0, 50));
    console.log("Display FEN:", displayFen.substring(0, 50));
    console.log("Current FEN:", currentFen?.substring(0, 50));
  }
  
  // Get the last move for highlighting
  const displayLastMove = isPlayingBestLine && currentBestLine && bestLineIndex > 0
    ? [currentBestLine.moves[bestLineIndex - 1].from, currentBestLine.moves[bestLineIndex - 1].to]
    : interactiveFen 
      ? null // No last move highlighting in interactive mode
      : (currentMoveIndex >= 0 && moves[currentMoveIndex] ? [moves[currentMoveIndex].from, moves[currentMoveIndex].to] : null);
  
  // Auto-play game review
  useEffect(() => {
    if (!isPlaying) return;
    
    const interval = setInterval(() => {
      setCurrentMoveIndex(prev => {
        if (prev >= moves.length - 1) {
          setIsPlaying(false);
          return prev;
        }
        return prev + 1;
      });
    }, 1000);
    
    return () => clearInterval(interval);
  }, [isPlaying, moves.length]);
  
  // Handle feedback
  const handleFeedback = (context) => {
    setFeedbackContext(context);
    setFeedbackOpen(true);
  };
  
  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      </Layout>
    );
  }
  
  // CoachSession removed — users click a game to see it immediately,
  // not to go through a guided wizard. The enriched decrypt view
  // provides all coaching inline with the moves.

  return (
    <Layout user={user} hideNav>
      <div className="h-screen flex flex-col overflow-hidden bg-background">
        {/* Top Bar */}
        <div className="shrink-0 border-b border-border">
          {/* Main header row */}
          <div className="flex items-center justify-between px-5 py-3">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => navigate("/lab")}
                className="h-8 w-8"
                data-testid="lab-back-btn"
              >
                <ArrowLeft className="w-4 h-4" />
              </Button>
              
              <div className="flex items-center gap-3">
                {/* Accuracy ring — shrunk to a peripheral indicator, not the headline */}
                {accuracy != null && (
                  <div className="relative w-8 h-8 shrink-0" data-testid="accuracy-ring">
                    <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
                      <circle cx="18" cy="18" r="15.5" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-border" />
                      <circle
                        cx="18" cy="18" r="15.5" fill="none" strokeWidth="2" strokeLinecap="round"
                        stroke={accuracy >= 80 ? '#10B981' : accuracy >= 60 ? '#F59E0B' : '#EF4444'}
                        strokeDasharray={`${accuracy * 0.975} 97.5`}
                      />
                    </svg>
                    <span className="absolute inset-0 flex items-center justify-center text-[10px] font-medium font-mono tabular-nums text-muted-foreground">
                      {accuracy.toFixed(0)}
                    </span>
                  </div>
                )}

                <div className="min-w-0">
                  <div className="flex items-center gap-2.5 flex-wrap">
                    <span className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold">
                      Review
                    </span>
                    <span className="font-serif text-[15px] text-foreground/90">
                      vs {game?.opponent_name || "Opponent"}
                    </span>
                    <ResultBadge result={result} userColor={userColor} />
                    {game?.termination && game.termination !== "unknown" && (
                      <TerminationTag termination={game.termination} result={result} userColor={userColor} />
                    )}
                  </div>
                  <p className="text-[11px] text-muted-foreground/70 mt-0.5 font-mono tabular-nums truncate">
                    {game?.opening_name || game?.opening || ""}
                    {game?.time_control && <span className="ml-2 opacity-70">· {game.time_control}s</span>}
                  </p>
                </div>
              </div>
            </div>
            
            {/* View Mode Toggle + Done Button */}
            <div className="flex items-center gap-3">
              <div className="flex items-center bg-muted/60 rounded-lg p-0.5" data-testid="view-mode-tabs">
                {[
                  { key: "decrypt", label: "Review", icon: BookOpen },
                  { key: "habits", label: "Insights", icon: Target },
                ].map(({ key, label, icon: Icon }) => (
                  <button
                    key={key}
                    onClick={() => setViewMode(key)}
                    className={`px-4 py-1.5 text-xs font-medium rounded-md transition-all duration-200 flex items-center gap-1.5 ${
                      viewMode === key
                        ? "bg-background text-foreground shadow-sm"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                    data-testid={`${key}-view-btn`}
                  >
                    <Icon className="w-3.5 h-3.5" strokeWidth={1.5} />
                    {label}
                  </button>
                ))}
              </div>
              
              {!game?.reviewed && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => completeReview()}
                  disabled={completingReview}
                  className="text-xs gap-1.5"
                  data-testid="done-reviewing-btn"
                >
                  {completingReview ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <Check className="w-3 h-3" />
                  )}
                  Done reviewing
                </Button>
              )}
            </div>
          </div>
          
          {/* Coach's verdict — one sentence, both tabs. Lead with the story. */}
          {coachSummary?.key_observation && (
            <div className="px-5 pb-4 pt-1">
              <p
                className="font-serif text-[16px] md:text-[19px] leading-[1.3] tracking-[-0.01em] text-foreground/90 max-w-[780px]"
                data-testid="coach-narrative-strip"
              >
                "{coachSummary.key_observation}"
              </p>
            </div>
          )}
        </div>
        
        {/* MAIN CONTENT - Conditional based on viewMode */}
        {viewMode === "decrypt" ? (
          /* Game Decryption View - Step-by-step explanations */
          <div className="flex-1 overflow-auto">
            <GameDecryptionV5
              gameId={gameId}
              analysis={analysis}
              pgn={game?.pgn}
              userColor={userColor}
              onBack={() => navigate(-1)}
              coachSummary={coachSummary}
              coreLesson={coreLesson}
              gameResult={result}
              opponentName={game?.opponent_name}
              coachReview={coachReview}
              onPlayBestLine={playBestLine}
            />
          </div>
        ) : (
        <div className="flex-1 flex overflow-hidden">
          {/* Left: Board and controls */}
          <div className="w-[55%] flex flex-col border-r border-border">
            {/* Board */}
            <div className="flex-1 flex items-center justify-center p-4">
              <div className="w-full max-w-[560px] aspect-square relative">
                <LichessBoard
                  fen={displayFen}
                  orientation={boardOrientation}
                  viewOnly={!interactiveMoment || isPlayingBestLine}
                  interactive={!!interactiveMoment && !isPlayingBestLine}
                  planMode={false}
                  movableColor={(interactiveMoment && !isPlayingBestLine) ? userColor : undefined}
                  lastMove={displayLastMove}
                  arrows={boardArrows}
                  onMove={(interactiveMoment && !isPlayingBestLine) ? (moveData) => {
                    handleUserMoveAttempt(moveData.from, moveData.to);
                  } : undefined}
                  moveClassification={
                    currentMoveIndex >= 0 && moves[currentMoveIndex]
                      ? (() => {
                          const m = moves[currentMoveIndex];
                          if (!m.to) return null;
                          const evals = analysis?.stockfish_analysis?.move_evaluations || [];
                          const moveNum = Math.floor(currentMoveIndex / 2) + 1;
                          const isUserMove = (userColor === "white" && currentMoveIndex % 2 === 0) ||
                                            (userColor === "black" && currentMoveIndex % 2 === 1);

                          // Find matching eval by move number and san — NO fallback to index
                          // evals only contains user moves, so index doesn't match PGN move index
                          const evalData = evals.find(e =>
                            e.move_number === moveNum && e.move === m.san
                          ) || evals.find(e => e.move === m.san);

                          if (evalData) {
                            const c = (evalData.classification || evalData.evaluation || "").toLowerCase().replace(/[_\s]/g, "");
                            const severity = c.includes("brilliant") ? "brilliant"
                              : c.includes("best") ? "best"
                              : c.includes("excellent") ? "excellent"
                              : c.includes("good") ? "good"
                              : c.includes("book") ? "book"
                              : c.includes("blunder") ? "blunder"
                              : c.includes("mistake") ? "mistake"
                              : c.includes("inaccuracy") ? "inaccuracy"
                              : null;
                            if (severity) return { square: m.to, type: severity };
                          }

                          // Fallback for moves without eval: derive from cp_loss
                          if (evalData?.cp_loss != null) {
                            const cpLoss = Math.abs(evalData.cp_loss);
                            const sev = cpLoss >= 200 ? "blunder"
                              : cpLoss >= 100 ? "mistake"
                              : cpLoss >= 50 ? "inaccuracy"
                              : cpLoss <= 5 ? "best"
                              : "good";
                            return { square: m.to, type: sev };
                          }

                          return null;
                        })()
                      : null
                  }
                />
                {/* Best Line indicator */}
                {isPlayingBestLine && currentBestLine && (
                  <div className="absolute top-2 left-2 bg-emerald-600/90 text-white px-3 py-1 rounded text-sm font-medium">
                    Best line: {bestLineIndex}/{currentBestLine.fens.length - 1}
                  </div>
                )}
                {/* Phase-3 / multi-move-review (2026-05-19):
                    Per-ply annotation surfaces alongside the line replay.
                    Annotation is computed in playBestLine via
                    _annotateLineMove (only non-empty for meaningful moves:
                    checks, captures, mate, promotion, castle). Per
                    [[no-hollow-coverage]], silent moves get no caption. */}
                {isPlayingBestLine && currentBestLine && bestLineIndex > 0 && (() => {
                  const playedMove = currentBestLine.moves[bestLineIndex - 1];
                  if (!playedMove || !playedMove.note) return null;
                  return (
                    <div
                      className="absolute bottom-2 left-2 right-2 bg-zinc-900/85 dark:bg-zinc-100/90 text-white dark:text-zinc-900 px-3 py-2 rounded text-sm"
                      data-testid="best-line-annotation"
                    >
                      <span className="font-mono mr-2">{playedMove.san}</span>
                      <span>{playedMove.note}</span>
                    </div>
                  );
                })()}
                {/* Interactive mode indicator */}
                {interactiveFen && !userAttemptResult && (
                  <div className="absolute top-2 left-2 bg-amber-600/90 text-white px-3 py-1 rounded text-sm font-medium animate-pulse">
                    Your turn - find the best move!
                  </div>
                )}
                {/* User attempt feedback - with smart symbols */}
                {userAttemptResult && interactiveMoment && (
                  <div className={`absolute top-2 left-2 px-3 py-1 rounded text-sm font-medium flex items-center gap-2 ${
                    userAttemptResult.correct 
                      ? userAttemptResult.quality === 'best' || userAttemptResult.quality === 'excellent'
                        ? 'bg-emerald-600/90 text-white' 
                        : 'bg-yellow-500/90 text-white'
                      : userAttemptResult.quality === 'okay' || userAttemptResult.quality === 'inaccuracy'
                        ? 'bg-yellow-500/90 text-white'
                        : 'bg-red-600/90 text-white'
                  }`}>
                    {userAttemptResult.correct 
                      ? userAttemptResult.quality === 'best' || userAttemptResult.quality === 'excellent'
                        ? <><svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M5 13l4 4L19 7" /></svg> {userAttemptResult.message || 'Correct!'}</>
                        : <><svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg> {userAttemptResult.message || 'Good!'}</>
                      : userAttemptResult.quality === 'okay' || userAttemptResult.quality === 'inaccuracy'
                        ? <><svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg> {userAttemptResult.message || 'Okay move'}</>
                        : <><svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 18L18 6M6 6l12 12" /></svg> {userAttemptResult.message || 'Try again'}</>
                    }
                  </div>
                )}
              </div>
            </div>
            
            {/* Move controls */}
            <div className="px-4 py-3 border-t border-border flex items-center justify-center gap-1.5">
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={goToStart} data-testid="board-start-btn">
                <SkipBack className="w-3.5 h-3.5" />
              </Button>
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={goToPrev} data-testid="board-prev-btn">
                <ChevronLeft className="w-3.5 h-3.5" />
              </Button>
              <Button 
                variant={isPlaying ? "secondary" : "default"} 
                size="icon"
                className="h-8 w-8"
                onClick={() => setIsPlaying(!isPlaying)}
                data-testid="board-play-btn"
              >
                {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
              </Button>
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={goToNext} data-testid="board-next-btn">
                <ChevronRight className="w-3.5 h-3.5" />
              </Button>
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={goToEnd} data-testid="board-end-btn">
                <SkipForward className="w-3.5 h-3.5" />
              </Button>
              <Button 
                variant="ghost" 
                size="icon"
                className="h-8 w-8 ml-2"
                onClick={() => setBoardOrientation(o => o === "white" ? "black" : "white")}
                data-testid="board-flip-btn"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </Button>
              
              <span className="ml-3 text-xs text-muted-foreground font-mono">
                {currentMoveIndex + 1} / {moves.length}
              </span>

              {/* Current position eval — label only, no numbers */}
              {(() => {
                const currentEval = currentMoveIndex >= 0 ? findEvalForMove(currentMoveIndex) : null;
                if (!currentEval?.eval_after && currentEval?.eval_after !== 0) return null;
                const evalCp = Math.round((currentEval.eval_after || 0) * 100);
                const categories = [
                  [900, "text-emerald-500", "Winning"],
                  [300, "text-emerald-400", "Clear edge"],
                  [100, "text-blue-400", "Slight edge"],
                  [-100, "text-muted-foreground", "Equal"],
                  [-300, "text-orange-400", "Worse"],
                  [-900, "text-red-400", "Losing"],
                  [-Infinity, "text-red-500", "Lost"],
                ];
                const userEval = userColor === "white" ? evalCp : -evalCp;
                const match = categories.find(([threshold]) => userEval >= threshold);
                const [, cls, lbl] = match || categories[categories.length - 1];
                return (
                  <span className={`ml-3 text-xs font-bold ${cls}`}>
                    {lbl}
                  </span>
                );
              })()}
            </div>

            {/* Move list (compact) */}
            <div className="h-28 overflow-y-auto px-4 py-2.5 border-t border-border bg-muted/20">
              <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-sm font-mono">
                {moves.map((move, idx) => {
                  const isWhite = idx % 2 === 0;
                  const moveNum = Math.floor(idx / 2) + 1;
                  
                  return (
                    <span key={idx} className="inline-flex items-center">
                      {isWhite && <span className="text-muted-foreground/50 mr-0.5 text-xs">{moveNum}.</span>}
                      <button
                        onClick={() => goToMove(idx)}
                        className={`px-1 py-0.5 rounded text-xs transition-colors ${
                          idx === currentMoveIndex 
                            ? "bg-primary/20 text-primary font-semibold" 
                            : "text-foreground/80 hover:bg-primary/10"
                        }`}
                        data-testid={`move-btn-${idx}`}
                      >
                        {move.san}
                      </button>
                    </span>
                  );
                })}
              </div>
            </div>
          </div>
          
          {/* Right Panel: Coach Move Panel (dynamic) OR Habits */}
          <div className="w-[45%] flex flex-col overflow-hidden">
            <div className="flex-1 overflow-y-auto">
              {/* Insights panel — phases, behaviors, key moments, fundamentals */}
              {true && (
                <div className="p-6 space-y-4">
                  {/* Phase Analysis — narrative ribbon (not three stacked cards).
                      A single horizontal bar colored by per-phase accuracy, with
                      the phase name + accuracy under its segment. Verdict text
                      becomes a single-line annotation beneath the ribbon. */}
                  {coachReview?.phases && (
                    <div>
                      <p className="text-[10.5px] uppercase tracking-[0.22em] font-semibold text-muted-foreground mb-3">
                        How the game flowed
                      </p>

                      {(() => {
                        const phaseKeys = ["opening", "middlegame", "endgame"].filter(
                          (k) => coachReview.phases[k]
                        );
                        const segColor = (acc) =>
                          acc >= 80
                            ? "bg-emerald-500/80"
                            : acc >= 60
                              ? "bg-amber-500/80"
                              : "bg-rose-500/80";
                        const segWeight = phaseKeys.map((k) =>
                          coachReview.phases[k].move_count || 1
                        );
                        const totalWeight = segWeight.reduce((a, b) => a + b, 0);

                        return (
                          <>
                            {/* Ribbon */}
                            <div className="flex h-1.5 rounded-full overflow-hidden bg-muted/40 ring-1 ring-border">
                              {phaseKeys.map((k, i) => {
                                const p = coachReview.phases[k];
                                const pct = (segWeight[i] / totalWeight) * 100;
                                return (
                                  <div
                                    key={k}
                                    className={segColor(p.accuracy)}
                                    style={{ width: `${pct}%` }}
                                    title={`${p.name} — ${p.accuracy}%`}
                                  />
                                );
                              })}
                            </div>

                            {/* Labels underneath */}
                            <div
                              className="grid gap-2 mt-2"
                              style={{
                                gridTemplateColumns: phaseKeys
                                  .map((_, i) => `${(segWeight[i] / totalWeight) * 100}fr`)
                                  .join(" "),
                              }}
                            >
                              {phaseKeys.map((k) => {
                                const p = coachReview.phases[k];
                                return (
                                  <div key={k} className="min-w-0">
                                    <div className="flex items-baseline gap-1.5">
                                      <span className="text-[11px] text-foreground font-medium capitalize">
                                        {p.name || k}
                                      </span>
                                      <span className="text-[10.5px] font-mono tabular-nums text-muted-foreground">
                                        {p.accuracy}%
                                      </span>
                                    </div>
                                    {p.verdict && (
                                      <p className="text-[11px] text-muted-foreground/80 leading-snug mt-0.5">
                                        {p.verdict}
                                      </p>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          </>
                        );
                      })()}
                    </div>
                  )}

                  {/* Opening Analysis */}
                  {coachReview?.opening_analysis && (
                    <div className="rounded-xl border border-border p-3">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-bold text-primary/60 uppercase tracking-widest">Opening</span>
                        <span className="text-[10px] text-muted-foreground">
                          {coachReview.opening_analysis.moves_in_theory}/{coachReview.opening_analysis.total_theory_moves} theory
                        </span>
                      </div>
                      <p className="text-sm font-medium text-foreground">{coachReview.opening_analysis.name}</p>
                      {coachReview.opening_analysis.deviation && (
                        <p className="text-xs text-muted-foreground mt-1">
                          Deviated on move {Math.floor(coachReview.opening_analysis.deviation.ply / 2) + 1}:
                          played <span className="font-mono text-red-400">{coachReview.opening_analysis.deviation.played}</span>
                          {" "}instead of <span className="font-mono text-emerald-400">{coachReview.opening_analysis.deviation.expected}</span>
                        </p>
                      )}
                      {coachReview.opening_analysis.traps?.map((t, i) => (
                        <div key={i} className={`mt-2 rounded-lg px-2.5 py-1.5 ${
                          t.sprung && t.victim_color === coachReview.user_color ? "bg-red-500/10 border border-red-500/20" : "bg-amber-500/5 border border-amber-500/15"
                        }`}>
                          <div className="flex items-center gap-1.5">
                            <Zap className="w-3 h-3 text-amber-500" strokeWidth={2.5} />
                            <span className="text-[10px] font-bold text-amber-400">{t.name}</span>
                          </div>
                          <p className="text-[10px] text-muted-foreground mt-0.5">{t.story || t.explanation}</p>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Behavioral Summary */}
                  {coachReview?.behaviors?.length > 0 && (
                    <div>
                      <p className="text-[10px] uppercase tracking-widest font-bold text-red-400/60 mb-2">What went wrong</p>
                      {coachReview.behaviors.map((b, i) => (
                        <div key={i} className="flex items-center justify-between py-1.5">
                          <span className="text-sm text-foreground">{b.label}</span>
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-mono text-muted-foreground">{b.count}x</span>
                            <button
                              onClick={() => navigate(`/training/prescribed?weakness=${b.behavior}`)}
                              className="text-[10px] text-primary hover:text-primary/80 transition-colors"
                            >
                              Practice
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Key Moments — the centerpiece.
                      Each moment is a full-width clickable block with serif
                      commentary, the move comparison in mono, and a severity
                      tag. Tap to jump the board to that ply. */}
                  {coachReview?.key_moments?.length > 0 && (
                    <div>
                      <p className="text-[10.5px] uppercase tracking-[0.22em] font-semibold text-violet-500 dark:text-violet-300 mb-3">
                        Key moments · tap to jump
                      </p>
                      <div className="space-y-3">
                        {coachReview.key_moments.slice(0, 3).map((m, i) => {
                          const isBlunder = m.severity === "blunder";
                          // Card click jumps the board to that ply. The
                          // "Try yourself" button drops the user into
                          // interactive solve mode at the position before
                          // the mistake — that's the highlight-then-quiz
                          // flow the locked spec describes.
                          const canSolve = !!m.fen && !!m.best_move;
                          return (
                            <div
                              key={i}
                              className={`w-full text-left rounded-xl border p-4 transition-colors ${
                                isBlunder
                                  ? "border-rose-400/25 bg-rose-500/[0.03] hover:bg-rose-500/[0.06]"
                                  : "border-amber-400/25 bg-amber-500/[0.03] hover:bg-amber-500/[0.06]"
                              }`}
                            >
                              {/* The clickable region jumps the board on click,
                                  but it's a div (not a button) so it can host
                                  the InlineFlag button child without nesting
                                  interactive controls. */}
                              <div
                                role="button"
                                tabIndex={0}
                                onClick={() => navigateToMoveNumber(m.move_number)}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter" || e.key === " ") {
                                    e.preventDefault();
                                    navigateToMoveNumber(m.move_number);
                                  }
                                }}
                                className="w-full text-left cursor-pointer outline-none group"
                                data-testid={`key-moment-jump-${i}`}
                              >
                                <div className="flex items-baseline gap-2.5 mb-2 flex-wrap">
                                  <span
                                    className={`text-[10.5px] uppercase tracking-[0.22em] font-semibold ${
                                      isBlunder
                                        ? "text-rose-500 dark:text-rose-300"
                                        : "text-amber-600 dark:text-amber-300"
                                    }`}
                                  >
                                    {m.severity} · move {m.move_number}
                                  </span>
                                  <span className="font-mono text-[11.5px] tabular-nums text-muted-foreground">
                                    <span className="text-rose-500/80 dark:text-rose-300/80">
                                      {m.move}
                                    </span>
                                    <span className="text-muted-foreground/40 mx-1.5">→</span>
                                    <span className="text-emerald-600/90 dark:text-emerald-300/80">
                                      {m.best_move || "?"}
                                    </span>
                                  </span>
                                </div>
                                {m.commentary?.summary && (
                                  <p className="font-serif text-[14.5px] leading-snug text-foreground/85">
                                    {m.commentary.summary}
                                    <InlineFlag
                                      section="key_moment_commentary"
                                      flaggedText={m.commentary.summary}
                                      context={{
                                        source: "lab_key_moments",
                                        gameId,
                                        fen: m.fen,
                                        moveSan: m.move,
                                        moveNumber: m.move_number,
                                        side: userColor,
                                        severity: m.severity,
                                        cpLoss: m.cp_loss,
                                        bestMove: m.best_move,
                                        phase: m.phase,
                                        component: "lab_key_moments",
                                        rule_name: "position_intelligence_summary",
                                      }}
                                    />
                                  </p>
                                )}
                              </div>
                              {canSolve && (
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    startInteractiveMoment(m);
                                  }}
                                  className="mt-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-primary hover:text-primary/80 transition-colors"
                                  data-testid={`key-moment-try-${i}`}
                                >
                                  Try yourself →
                                </button>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Fundamentals */}
                  {coachReview?.fundamentals && Object.keys(coachReview.fundamentals).length > 0 && (
                    <div>
                      <p className="text-[10px] uppercase tracking-widest font-bold text-muted-foreground/40 mb-2">Fundamentals</p>
                      {Object.entries(coachReview.fundamentals).map(([phase, funds]) => (
                        funds?.length > 0 && (
                          <div key={phase} className="mb-2">
                            <p className="text-[9px] uppercase tracking-widest text-muted-foreground/30 mb-1 capitalize">{phase}</p>
                            {funds.map((f, i) => (
                              <div key={i} className="flex items-center gap-2 py-0.5">
                                <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                                  <div
                                    className={`h-full rounded-full ${f.progress >= 70 ? "bg-emerald-500" : f.progress >= 40 ? "bg-amber-400" : "bg-red-400"}`}
                                    style={{ width: `${f.progress}%` }}
                                  />
                                </div>
                                <span className="text-[10px] text-muted-foreground w-28 truncate">{f.name}</span>
                              </div>
                            ))}
                          </div>
                        )
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
        )}
        
        {/* Feedback Modal */}
        <FeedbackModal
          isOpen={feedbackOpen}
          onClose={() => setFeedbackOpen(false)}
          context={feedbackContext}
        />
        
        {/* Review Completion Overlay */}
        {reviewComplete && reviewSummary && (
          <ReviewCompleteOverlay 
            summary={reviewSummary.summary}
            nextGame={reviewSummary.next_game}
            navigate={navigate}
          />
        )}
      </div>
    </Layout>
  );
};

export default LabV2;
