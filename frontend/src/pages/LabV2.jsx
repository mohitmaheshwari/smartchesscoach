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
  
  // Update position when move index changes
  useEffect(() => {
    const fen = allFens[currentMoveIndex + 1] || START_FEN;
    setPositionObject(fenToPositionObject(fen));
    
    // Update last move squares
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
    const evalData = findEvalForMove(idx);
    if (!evalData) return false;
    const c = (evalData.classification || evalData.evaluation || "").toLowerCase();
    return c.includes("blunder") || c.includes("mistake") || c.includes("inaccuracy") || c.includes("brilliant");
  };

  const goToPrev = () => {
    if (viewMode === "decrypt") {
      goToMove(currentMoveIndex - 1);
      return;
    }
    // Coach/Habits: jump to previous important move
    let i = currentMoveIndex - 1;
    while (i >= 0 && !isImportantMove(i)) i--;
    goToMove(Math.max(-1, i));
  };

  const goToNext = () => {
    if (viewMode === "decrypt") {
      goToMove(currentMoveIndex + 1);
      return;
    }
    // Coach/Habits: jump to next important move
    let i = currentMoveIndex + 1;
    while (i < moves.length - 1 && !isImportantMove(i)) i++;
    if (i < moves.length) goToMove(i);
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
        lineMoves.push({ san: moment.best_move, from: bestMove.from, to: bestMove.to });
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
            lineMoves.push({ san: moveStr, from: move.from, to: move.to });
            lineFens.push(chess.fen());
          } else {
            break;
          }
        } catch {
          break;
        }
      }
      
      if (lineMoves.length > 0) {
        setCurrentBestLine({
          startFen: moment.fen,
          moves: lineMoves,
          fens: lineFens
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
          original_move: interactiveMoment.your_move || null
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
          
          // For bad moves, show Try Again after punishment
          if (!isOkay) {
            setTimeout(() => {
              setUserAttemptResult(prev => prev ? ({
                ...prev,
                showTryAgain: true
              }) : null);
            }, 2500);
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
    }
    
    return isCorrect;
  };
  
  // Clear interactive mode
  const clearInteractiveMoment = () => {
    setInteractiveMoment(null);
    setUserAttemptResult(null);
    setInteractiveFen(null);
  };
  
  // Reset for try again - go back to original position
  const handleTryAgain = () => {
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
              
              <div className="flex items-center gap-4">
                {/* Accuracy ring */}
                {accuracy != null && (
                  <div className="relative w-11 h-11" data-testid="accuracy-ring">
                    <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
                      <circle cx="18" cy="18" r="15.5" fill="none" stroke="currentColor" strokeWidth="2" className="text-gray-200 dark:text-gray-700" />
                      <circle 
                        cx="18" cy="18" r="15.5" fill="none" strokeWidth="2.5" strokeLinecap="round"
                        stroke={accuracy >= 80 ? '#10B981' : accuracy >= 60 ? '#F59E0B' : '#EF4444'}
                        strokeDasharray={`${accuracy * 0.975} 97.5`}
                      />
                    </svg>
                    <span className="absolute inset-0 flex items-center justify-center text-xs font-bold font-mono">
                      {accuracy.toFixed(0)}
                    </span>
                  </div>
                )}
                
                <div>
                  <div className="flex items-center gap-2.5">
                    <h1 className="text-base font-semibold tracking-tight">
                      vs {game?.opponent_name || "Opponent"}
                    </h1>
                    <ResultBadge result={result} userColor={userColor} />
                    {game?.termination && game.termination !== "unknown" && (
                      <TerminationTag termination={game.termination} result={result} userColor={userColor} />
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {game?.opening_name || game?.opening || ""}
                    {game?.time_control && <span className="ml-2 opacity-60">{game.time_control}s</span>}
                  </p>
                </div>
              </div>
            </div>
            
            {/* View Mode Toggle + Done Button */}
            <div className="flex items-center gap-3">
              <div className="flex items-center bg-muted/60 rounded-lg p-0.5" data-testid="view-mode-tabs">
                {[
                  { key: "coach", label: "Coach", icon: Brain },
                  { key: "habits", label: "Habits", icon: Target },
                  { key: "decrypt", label: "Decrypt", icon: BookOpen },
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
          
          {/* Coach narrative strip — only on coach/habits tabs */}
          {viewMode !== "decrypt" && coachSummary?.key_observation && (
            <div className="px-5 pb-2.5">
              <p className="text-xs text-muted-foreground italic leading-relaxed pl-14" data-testid="coach-narrative-strip">
                {coachSummary.key_observation}
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
                  viewOnly={!interactiveMoment}
                  interactive={!!interactiveMoment}
                  planMode={false}
                  movableColor={interactiveMoment ? userColor : undefined}
                  lastMove={displayLastMove}
                  arrows={boardArrows}
                  onMove={interactiveMoment ? (moveData) => {
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
              {viewMode === "coach" ? (
                <CoachMovePanel
                  gameId={gameId}
                  currentMoveIndex={currentMoveIndex}
                  moves={moves}
                  analysis={analysis}
                  userColor={userColor}
                  currentFen={currentMoveIndex >= 0 ? allFens[currentMoveIndex + 1] : allFens[0]}
                />
              ) : (
                <div className="p-6">
                  <CoachInsightPanel
                    gameId={gameId}
                    onMoveClick={(moveNum) => navigateToMoveNumber(moveNum)}
                  />
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
