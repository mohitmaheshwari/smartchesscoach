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
  History
} from "lucide-react";

// Import new coach-style components
import GameSummary from "@/components/lab/GameSummary";
import CriticalMoments from "@/components/lab/CriticalMoments";
import StrategicThemes from "@/components/lab/StrategicThemes";
import MissedTactics from "@/components/lab/MissedTactics";
import HabitsToImprove from "@/components/lab/HabitsToImprove";
import OpeningFundamentals from "@/components/lab/OpeningFundamentals";
import TrapAnalysis from "@/components/lab/TrapAnalysis";
import DeepMemoryPanel from "@/components/DeepMemoryPanel";

// Feedback modal (reused from Lab.jsx)
import FeedbackModal from "@/components/FeedbackModal";
import GameDecryption from "@/components/GameDecryption";

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
  const [viewMode, setViewMode] = useState("coach"); // "coach" (current) or "decrypt" (step-by-step)
  
  // Derived data
  const userColor = game?.user_color || "white";
  const result = game?.result || "1/2-1/2";
  const accuracy = analysis?.stockfish_analysis?.accuracy || labData?.accuracy;
  const currentFen = allFens[currentMoveIndex + 1] || START_FEN;
  
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
  const goToPrev = () => goToMove(currentMoveIndex - 1);
  const goToNext = () => goToMove(currentMoveIndex + 1);
  
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
        {/* Top Bar - Clean, simple */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate("/lab")}
              className="gap-2"
            >
              <ArrowLeft className="w-4 h-4" />
              Back
            </Button>
            
            <div className="flex items-center gap-3">
              <h1 className="font-semibold">Game Review</h1>
              <span className="text-muted-foreground">
                vs {game?.opponent_name || "Opponent"}
              </span>
              <Badge 
                variant={result.includes("1-0") && userColor === "white" || result.includes("0-1") && userColor === "black" 
                  ? "default" 
                  : result === "1/2-1/2" 
                    ? "secondary" 
                    : "destructive"
                }
              >
                {result.includes("1-0") && userColor === "white" || result.includes("0-1") && userColor === "black"
                  ? "Won"
                  : result === "1/2-1/2"
                    ? "Draw"
                    : "Lost"
                }
              </Badge>
              <span className="text-sm text-muted-foreground">
                {accuracy ? `${accuracy.toFixed(0)}% accuracy` : ""}
              </span>
            </div>
          </div>
          
          {/* View Mode Toggle */}
          <div className="flex items-center gap-2 px-2 py-1 rounded-lg bg-gray-800/50 border border-gray-700">
            <button
              onClick={() => setViewMode("coach")}
              className={`px-2 py-1 text-xs rounded transition-colors ${
                viewMode === "coach" 
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' 
                  : 'text-gray-400 hover:text-gray-300'
              }`}
              data-testid="coach-view-btn"
            >
              <Brain className="w-3 h-3 inline mr-1" />
              Coach
            </button>
            <button
              onClick={() => setViewMode("decrypt")}
              className={`px-2 py-1 text-xs rounded transition-colors ${
                viewMode === "decrypt" 
                  ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' 
                  : 'text-gray-400 hover:text-gray-300'
              }`}
              data-testid="decrypt-view-btn"
            >
              <BookOpen className="w-3 h-3 inline mr-1" />
              Decrypt
            </button>
          </div>
        </div>
        
        {/* MAIN CONTENT - Conditional based on viewMode */}
        {viewMode === "decrypt" ? (
          /* Game Decryption View - Step-by-step explanations */
          <div className="flex-1 overflow-auto">
            <GameDecryption
              gameId={gameId}
              analysis={analysis}
              pgn={game?.pgn}
              userColor={userColor}
              onBack={() => navigate(-1)}
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
            <div className="p-4 border-t border-border flex items-center justify-center gap-2">
              <Button variant="ghost" size="sm" onClick={goToStart}>
                <SkipBack className="w-4 h-4" />
              </Button>
              <Button variant="ghost" size="sm" onClick={goToPrev}>
                <ChevronLeft className="w-4 h-4" />
              </Button>
              <Button 
                variant={isPlaying ? "secondary" : "default"} 
                size="sm"
                onClick={() => setIsPlaying(!isPlaying)}
              >
                {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
              </Button>
              <Button variant="ghost" size="sm" onClick={goToNext}>
                <ChevronRight className="w-4 h-4" />
              </Button>
              <Button variant="ghost" size="sm" onClick={goToEnd}>
                <SkipForward className="w-4 h-4" />
              </Button>
              <Button 
                variant="ghost" 
                size="sm"
                onClick={() => setBoardOrientation(o => o === "white" ? "black" : "white")}
              >
                <RotateCcw className="w-4 h-4" />
              </Button>
              
              <span className="ml-4 text-sm text-muted-foreground">
                Move {currentMoveIndex + 1} / {moves.length}
              </span>
            </div>
            
            {/* Move list (compact) */}
            <div className="h-32 overflow-y-auto p-3 border-t border-border bg-muted/20">
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm font-mono">
                {moves.map((move, idx) => {
                  const isWhite = idx % 2 === 0;
                  const moveNum = Math.floor(idx / 2) + 1;
                  
                  return (
                    <span key={idx} className="inline-flex items-center">
                      {isWhite && <span className="text-muted-foreground mr-1">{moveNum}.</span>}
                      <button
                        onClick={() => goToMove(idx)}
                        className={`px-1 rounded hover:bg-primary/20 ${
                          idx === currentMoveIndex ? "bg-primary/30 text-primary" : ""
                        }`}
                      >
                        {move.san}
                      </button>
                    </span>
                  );
                })}
              </div>
            </div>
          </div>
          
          {/* Right: Coach Analysis */}
          <div className="w-[45%] flex flex-col overflow-hidden">
            {/* Tabs */}
            <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col overflow-hidden">
              <TabsList className="grid w-full grid-cols-5 rounded-none border-b shrink-0">
                <TabsTrigger value="summary" className="gap-1.5 text-xs">
                  <BookOpen className="w-3.5 h-3.5" />
                  Summary
                </TabsTrigger>
                <TabsTrigger value="moments" className="gap-1.5 text-xs">
                  <Target className="w-3.5 h-3.5" />
                  Moments
                </TabsTrigger>
                <TabsTrigger value="ideas" className="gap-1.5 text-xs">
                  <Brain className="w-3.5 h-3.5" />
                  Ideas
                </TabsTrigger>
                <TabsTrigger value="habits" className="gap-1.5 text-xs">
                  <Zap className="w-3.5 h-3.5" />
                  Habits
                </TabsTrigger>
                <TabsTrigger value="memory" className="gap-1.5 text-xs">
                  <History className="w-3.5 h-3.5" />
                  Memory
                </TabsTrigger>
              </TabsList>
              
              {/* Tab content - scrollable */}
              <div className="flex-1 overflow-y-auto">
                {/* Summary Tab */}
                <TabsContent value="summary" className="p-4 m-0">
                  {loadingDeepStrategy ? (
                    <div className="flex items-center justify-center py-12">
                      <Loader2 className="w-6 h-6 animate-spin text-primary" />
                    </div>
                  ) : (
                    <GameSummary
                      game={game}
                      labData={labData}
                      analysis={analysis}
                      userColor={userColor}
                      result={result}
                      accuracy={accuracy}
                      deepStrategy={deepStrategy}
                      patternContext={labData?.pattern_context}
                      onNavigateToMove={navigateToMoveNumber}
                    />
                  )}
                </TabsContent>
                
                {/* Critical Moments Tab */}
                <TabsContent value="moments" className="p-4 m-0">
                  {loadingDeepStrategy ? (
                    <div className="flex items-center justify-center py-12">
                      <Loader2 className="w-6 h-6 animate-spin text-primary" />
                    </div>
                  ) : (
                    <CriticalMoments
                      moments={deepStrategy?.critical_moments || []}
                      userColor={userColor}
                      onNavigateToMove={navigateToMoveNumber}
                      onFeedback={handleFeedback}
                      onPlayBestLine={playBestLine}
                      onStartInteractive={startInteractiveMoment}
                      onClearInteractive={clearInteractiveMoment}
                      onTryAgain={handleTryAgain}
                      userAttemptResult={userAttemptResult}
                      gameId={gameId}
                      playerLevel={deepStrategy?.player_level}
                      playerLevelDisplay={deepStrategy?.player_level_display}
                      playerLevelEmoji={deepStrategy?.player_level_emoji}
                      coachingVoice={deepStrategy?.coaching_voice}
                      chessUnderstanding={deepStrategy?.chess_understanding}
                    />
                  )}
                </TabsContent>
                
                {/* Ideas Tab (Strategic Themes + Missed Tactics + Opening Opportunities) */}
                <TabsContent value="ideas" className="p-4 m-0 space-y-6">
                  {loadingDeepStrategy ? (
                    <div className="flex items-center justify-center py-12">
                      <Loader2 className="w-6 h-6 animate-spin text-primary" />
                    </div>
                  ) : (
                    <>
                      <StrategicThemes
                        deepStrategy={deepStrategy}
                        labData={labData}
                        game={game}
                        playerRating={game?.user_rating || labData?.player_rating}
                        onNavigateToMove={(moveNum, yourMove, bestMove) => {
                          navigateToMoveNumber(moveNum, yourMove, bestMove);
                        }}
                      />
                      
                      <MissedTactics
                        deepStrategy={deepStrategy}
                        labData={labData}
                        onNavigateToMove={(moveNum, yourMove, bestMove) => {
                          // Switch to summary tab to see the board
                          setActiveTab("summary");
                          // Navigate to the position with arrows showing the moves
                          navigateToMoveNumber(moveNum, yourMove, bestMove);
                        }}
                      />
                      
                      {/* Opening Opportunities - TrapAnalysis moved here */}
                      {deepStrategy?.trap_analysis && (
                        <div className="pt-2">
                          <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-3">
                            Opening Opportunities
                          </h3>
                          <TrapAnalysis trapAnalysis={deepStrategy.trap_analysis} />
                        </div>
                      )}
                    </>
                  )}
                </TabsContent>
                
                {/* Habits Tab */}
                <TabsContent value="habits" className="p-4 m-0 space-y-4">
                  {/* Opening Fundamentals Analysis */}
                  <OpeningFundamentals gameId={game?.game_id} />
                  
                  {/* Existing Habits Component */}
                  <HabitsToImprove
                    patternContext={labData?.pattern_context}
                    focusModule={focusModule}
                    labData={labData}
                    deepStrategy={deepStrategy}
                    onStartTraining={() => navigate("/training/prescribed")}
                    onNavigateToMove={navigateToMoveNumber}
                  />
                </TabsContent>
                
                {/* Memory Tab - Deep Coach Memory Profile */}
                <TabsContent value="memory" className="p-4 m-0">
                  <div className="space-y-4">
                    <div className="text-sm text-muted-foreground mb-4">
                      Your coach's memory of your playing patterns, style, and areas for improvement.
                    </div>
                    <DeepMemoryPanel compact={false} />
                  </div>
                </TabsContent>
              </div>
            </Tabs>
          </div>
        </div>
        )}
        
        {/* Feedback Modal */}
        <FeedbackModal
          isOpen={feedbackOpen}
          onClose={() => setFeedbackOpen(false)}
          context={feedbackContext}
        />
      </div>
    </Layout>
  );
};

export default LabV2;
