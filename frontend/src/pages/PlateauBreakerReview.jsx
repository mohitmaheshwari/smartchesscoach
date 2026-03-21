/**
 * PlateauBreakerReview.jsx - V1 Simplified Game Review
 * 
 * Shows ONLY:
 * 1. What went wrong (the position + mistake)
 * 2. Pattern recognition ("This is your Xth time")
 * 3. The rule to remember
 * 4. Quick visual demo
 * 5. "Practice This Now" CTA
 * 
 * No tabs. No complexity. One flow.
 */

import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Chess } from "chess.js";
import {
  AlertTriangle,
  Target,
  ArrowRight,
  ArrowLeft,
  Eye,
  Repeat,
  Zap,
  ChevronDown,
  ChevronUp,
  Play,
  SkipBack,
  SkipForward,
  RotateCcw
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import LichessBoard from "@/components/LichessBoard";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

const PlateauBreakerReview = ({ user }) => {
  const { gameId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const blocker = location.state?.blocker;

  const boardRef = useRef(null);
  const chessRef = useRef(new Chess());

  const [loading, setLoading] = useState(true);
  const [gameData, setGameData] = useState(null);
  const [criticalMistake, setCriticalMistake] = useState(null);
  const [mistakeExplanation, setMistakeExplanation] = useState(null); // From explain API
  const [patternCount, setPatternCount] = useState(0);
  const [currentStep, setCurrentStep] = useState(0); // 0: mistake, 1: pattern, 2: rule, 3: demo
  const [showingDemo, setShowingDemo] = useState(false);
  const [demoStep, setDemoStep] = useState(0);
  const [currentFen, setCurrentFen] = useState("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  const [lastMove, setLastMove] = useState(null);
  const [orientation, setOrientation] = useState("white");
  const [arrows, setArrows] = useState([]); // For board visualization
  
  // Line visualization state
  const [showingLine, setShowingLine] = useState(null); // "played" | "best" | null
  const [lineIndex, setLineIndex] = useState(0);
  const [lineMoves, setLineMoves] = useState([]);
  const [linePositions, setLinePositions] = useState([]); // [{fen, lastMove}]

  useEffect(() => {
    if (gameId) {
      fetchGameAnalysis();
    }
  }, [gameId]);

  const fetchGameAnalysis = async () => {
    try {
      setLoading(true);

      // Fetch game data
      const gameRes = await fetch(`${API}/games/${gameId}`, {
        credentials: "include"
      });
      const game = await gameRes.json();
      setGameData(game);

      // Fetch analysis data (separate endpoint)
      let analysisData = null;
      try {
        const analysisRes = await fetch(`${API}/analysis/${gameId}`, {
          credentials: "include"
        });
        if (analysisRes.ok) {
          analysisData = await analysisRes.json();
        }
      } catch (e) {
        console.warn("Could not fetch analysis:", e);
      }

      // Find the most critical mistake from stockfish analysis
      const stockfishAnalysis = analysisData?.stockfish_analysis || {};
      const moveEvaluations = stockfishAnalysis.move_evaluations || [];
      
      // Find biggest mistake by cp_loss
      let biggestMistake = null;
      let maxLoss = 0;
      
      for (const move of moveEvaluations) {
        const loss = Math.abs(move.cp_loss || 0);
        // Only consider significant mistakes (> 100 centipawns)
        if (loss > maxLoss && loss >= 100) {
          maxLoss = loss;
          biggestMistake = {
            move_number: move.move_number,
            move: move.move,  // SAN notation
            move_uci: move.move_uci,
            better_move: move.best_move,  // Best move in SAN
            better_move_uci: move.best_move_uci,
            fen: move.fen_before,
            fen_after_played: move.fen_after,
            eval_loss: loss,
            explanation: move.coaching_focus || move.cognitive_gap || 
              `You played ${move.move}, losing ${(loss / 100).toFixed(1)} pawns worth of advantage.`,
            type: move.critical_reason || "tactical_error",
            is_turning_point: move.is_turning_point,
            // PV lines for showing the continuation
            pv_after_played: move.pv_after_played || [],
            pv_after_best: move.pv_after_best || []
          };
        }
      }

      // Fallback: check interpretation for primary issue
      if (!biggestMistake && analysisData?.interpretation?.primary_issue) {
        // Find the first critical move
        const criticalMove = moveEvaluations.find(m => m.is_critical);
        if (criticalMove) {
          biggestMistake = {
            move_number: criticalMove.move_number,
            move: criticalMove.move,
            better_move: criticalMove.best_move,
            fen: criticalMove.fen_before,
            eval_loss: Math.abs(criticalMove.cp_loss || 0),
            explanation: criticalMove.coaching_focus || `Critical moment at move ${criticalMove.move_number}`,
            type: analysisData.interpretation.primary_issue
          };
        }
      }

      setCriticalMistake(biggestMistake);

      // Now call the explain API to get a proper human explanation
      if (biggestMistake?.fen && biggestMistake?.move_uci && biggestMistake?.better_move_uci) {
        try {
          const explainRes = await fetch(`${API}/coach/explain-mistake`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({
              fen_before: biggestMistake.fen,
              played_move_uci: biggestMistake.move_uci,
              best_move_uci: biggestMistake.better_move_uci,
              eval_before: 0, // We don't have this directly
              eval_after: -(biggestMistake.eval_loss || 0),
              move_number: biggestMistake.move_number,
              pv_after_best: biggestMistake.pv_after_best || []
            })
          });
          
          if (explainRes.ok) {
            const explanation = await explainRes.json();
            setMistakeExplanation(explanation);
            
            // Set arrows for visualization
            if (explanation.arrows && explanation.arrows.length > 0) {
              // Convert to format expected by LichessBoard: [[from, to, color], ...]
              const boardArrows = explanation.arrows.map(arr => [arr[0], arr[1], arr[2]]);
              setArrows(boardArrows);
            }
          }
        } catch (e) {
          console.warn("Could not get mistake explanation:", e);
        }
      }

      // Get pattern count from player identity
      const identityRes = await fetch(`${API}/coach/deep-memory?user_id=${user?.user_id}`, {
        credentials: "include"
      });
      const identity = await identityRes.json();
      
      // Count similar mistakes from blunder taxonomy
      const taxonomy = identity?.identity?.blunder_taxonomy?.by_type || identity?.blunder_taxonomy || {};
      const mistakeType = biggestMistake?.type || blocker?.type || "tactical_error";
      setPatternCount(taxonomy[mistakeType] || 1);

      // Set board to mistake position
      if (biggestMistake?.fen) {
        setCurrentFen(biggestMistake.fen);
        setOrientation(game.user_color || "white");
        setLastMove(null);
      }

    } catch (err) {
      console.error("Error fetching game:", err);
    } finally {
      setLoading(false);
    }
  };

  const showMistakePosition = () => {
    if (criticalMistake?.fen) {
      setCurrentFen(criticalMistake.fen);
      setLastMove(null);
      // Restore arrows when showing mistake position
      if (mistakeExplanation?.arrows?.length > 0) {
        setArrows(mistakeExplanation.arrows.map(arr => [arr[0], arr[1], arr[2]]));
      }
    }
  };

  const showBetterMove = () => {
    if (criticalMistake?.fen && (criticalMistake?.better_move || criticalMistake?.better_move_uci)) {
      chessRef.current.load(criticalMistake.fen);
      // Try SAN first, then UCI
      const moveToPlay = criticalMistake.better_move || criticalMistake.better_move_uci;
      const move = chessRef.current.move(moveToPlay);
      if (move) {
        setCurrentFen(chessRef.current.fen());
        setLastMove([move.from, move.to]);
      }
    }
  };

  // Build the line positions for stepping through
  const buildLinePositions = (startFen, firstMove, pvMoves) => {
    const positions = [];
    const chess = new Chess();
    chess.load(startFen);
    
    // Add starting position
    positions.push({ fen: startFen, lastMove: null, moveLabel: "Start" });
    
    // Play first move
    const first = chess.move(firstMove);
    if (first) {
      positions.push({ 
        fen: chess.fen(), 
        lastMove: [first.from, first.to],
        moveLabel: firstMove
      });
    }
    
    // Play PV continuation
    for (const moveStr of pvMoves) {
      const m = chess.move(moveStr);
      if (m) {
        positions.push({ 
          fen: chess.fen(), 
          lastMove: [m.from, m.to],
          moveLabel: moveStr
        });
      } else {
        break; // Stop if move is invalid
      }
    }
    
    return positions;
  };

  const showPlayedLine = () => {
    if (!criticalMistake) return;
    
    const positions = buildLinePositions(
      criticalMistake.fen,
      criticalMistake.move,
      criticalMistake.pv_after_played || []
    );
    
    setLinePositions(positions);
    setLineMoves([criticalMistake.move, ...(criticalMistake.pv_after_played || [])]);
    setLineIndex(0);
    setShowingLine("played");
    
    // Show starting position
    if (positions.length > 0) {
      setCurrentFen(positions[0].fen);
      setLastMove(positions[0].lastMove);
    }
  };

  const showBestLine = () => {
    if (!criticalMistake) return;
    
    const positions = buildLinePositions(
      criticalMistake.fen,
      criticalMistake.better_move || criticalMistake.better_move_uci,
      criticalMistake.pv_after_best || []
    );
    
    setLinePositions(positions);
    setLineMoves([criticalMistake.better_move, ...(criticalMistake.pv_after_best || [])]);
    setLineIndex(0);
    setShowingLine("best");
    
    // Show starting position
    if (positions.length > 0) {
      setCurrentFen(positions[0].fen);
      setLastMove(positions[0].lastMove);
    }
  };

  const stepForward = () => {
    if (lineIndex < linePositions.length - 1) {
      const newIndex = lineIndex + 1;
      setLineIndex(newIndex);
      setCurrentFen(linePositions[newIndex].fen);
      setLastMove(linePositions[newIndex].lastMove);
    }
  };

  const stepBackward = () => {
    if (lineIndex > 0) {
      const newIndex = lineIndex - 1;
      setLineIndex(newIndex);
      setCurrentFen(linePositions[newIndex].fen);
      setLastMove(linePositions[newIndex].lastMove);
    }
  };

  const resetLine = () => {
    setShowingLine(null);
    setLineIndex(0);
    setLinePositions([]);
    setLineMoves([]);
    showMistakePosition();
  };

  const handlePracticeNow = () => {
    navigate("/plateau-breaker/training", {
      state: { 
        blocker,
        mistakeType: criticalMistake?.type || blocker?.type,
        fromGame: gameId
      }
    });
  };

  const nextStep = () => {
    if (currentStep < 3) {
      setCurrentStep(currentStep + 1);
    } else {
      handlePracticeNow();
    }
  };

  const prevStep = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
          className="w-8 h-8 border-2 border-amber-500 border-t-transparent rounded-full"
        />
      </div>
    );
  }

  const steps = [
    { id: "mistake", label: "The Mistake" },
    { id: "pattern", label: "The Pattern" },
    { id: "rule", label: "Your Rule" },
    { id: "demo", label: "See It" }
  ];

  return (
    <div className="min-h-screen bg-zinc-950 text-white">
      {/* Header */}
      <div className="border-b border-zinc-800 p-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <button 
            onClick={() => navigate("/plateau-breaker")}
            className="flex items-center gap-2 text-zinc-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </button>
          <span className="text-sm text-zinc-500">
            Game vs {gameData?.opponent_username || "Opponent"}
          </span>
        </div>
      </div>

      {/* Progress Steps */}
      <div className="border-b border-zinc-800">
        <div className="max-w-4xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            {steps.map((step, idx) => (
              <div 
                key={step.id}
                className={`flex items-center gap-2 ${
                  idx <= currentStep ? "text-amber-400" : "text-zinc-600"
                }`}
              >
                <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                  idx < currentStep ? "bg-amber-500 text-black" :
                  idx === currentStep ? "border-2 border-amber-500" :
                  "border border-zinc-700"
                }`}>
                  {idx < currentStep ? "✓" : idx + 1}
                </div>
                <span className="text-sm hidden sm:inline">{step.label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-4xl mx-auto p-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          
          {/* Chess Board */}
          <Card className="bg-zinc-900/50 border-zinc-800">
            <CardContent className="p-4">
              <div className="aspect-square">
                <LichessBoard
                  ref={boardRef}
                  fen={currentFen}
                  orientation={orientation}
                  lastMove={lastMove}
                  arrows={showingLine ? [] : arrows}
                  viewOnly={true}
                  interactive={false}
                />
              </div>
              
              {currentStep === 3 && (
                <div className="mt-4 space-y-3">
                  {/* Line indicator when showing a line */}
                  {showingLine && (
                    <div className={`p-2 rounded-lg text-sm ${
                      showingLine === "best" 
                        ? "bg-green-500/10 border border-green-500/30" 
                        : "bg-red-500/10 border border-red-500/30"
                    }`}>
                      <div className="flex items-center justify-between mb-2">
                        <span className={showingLine === "best" ? "text-green-400" : "text-red-400"}>
                          {showingLine === "best" ? "Best Line" : "Played Line"}
                        </span>
                        <span className="text-zinc-500 text-xs">
                          Move {lineIndex}/{linePositions.length - 1}
                        </span>
                      </div>
                      {/* Show moves with current highlighted */}
                      <div className="flex flex-wrap gap-1">
                        {lineMoves.map((move, idx) => (
                          <span 
                            key={idx}
                            className={`font-mono text-xs px-1.5 py-0.5 rounded ${
                              idx === lineIndex - 1
                                ? (showingLine === "best" ? "bg-green-500 text-black" : "bg-red-500 text-white")
                                : idx < lineIndex - 1
                                  ? "bg-zinc-700 text-zinc-300"
                                  : "bg-zinc-800 text-zinc-500"
                            }`}
                          >
                            {move}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  {/* Controls */}
                  {showingLine ? (
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={stepBackward}
                        disabled={lineIndex === 0}
                        className="border-zinc-700"
                      >
                        <SkipBack className="w-4 h-4" />
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={stepForward}
                        disabled={lineIndex >= linePositions.length - 1}
                        className="flex-1 border-zinc-700"
                      >
                        <Play className="w-4 h-4 mr-1" />
                        Next
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={resetLine}
                        className="border-zinc-700"
                      >
                        <RotateCcw className="w-4 h-4" />
                      </Button>
                    </div>
                  ) : (
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={showPlayedLine}
                        className="flex-1 border-red-500/50 text-red-400 hover:bg-red-500/10"
                      >
                        <Eye className="w-4 h-4 mr-1" />
                        Your Line
                      </Button>
                      <Button
                        size="sm"
                        onClick={showBestLine}
                        className="flex-1 bg-green-600 hover:bg-green-700"
                      >
                        <Target className="w-4 h-4 mr-1" />
                        Best Line
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Content Panel */}
          <div className="space-y-4">
            <AnimatePresence mode="wait">
              {/* Step 0: The Mistake */}
              {currentStep === 0 && (
                <motion.div
                  key="mistake"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                >
                  <Card className="bg-red-950/30 border-red-500/50">
                    <CardContent className="p-6">
                      <div className="flex items-center gap-3 mb-4">
                        <AlertTriangle className="w-8 h-8 text-red-400" />
                        <div>
                          <p className="text-red-400 text-sm font-medium">WHAT WENT WRONG</p>
                          <p className="text-lg font-bold">
                            {mistakeExplanation?.headline || 
                             (criticalMistake?.move_number 
                              ? `Move ${criticalMistake.move_number}` 
                              : "No major mistakes found")}
                          </p>
                        </div>
                      </div>

                      {criticalMistake ? (
                        <div className="space-y-4">
                          {/* Main explanation from the API */}
                          <p className="text-lg text-white">
                            {mistakeExplanation?.explanation || 
                             criticalMistake.explanation || 
                             `You played ${criticalMistake.move || "a move"}, losing advantage.`}
                          </p>

                          <div className="grid grid-cols-2 gap-3">
                            <div className="bg-red-500/10 rounded-lg p-3">
                              <p className="text-xs text-red-400 mb-1">You played</p>
                              <p className="font-mono font-bold text-lg">
                                {criticalMistake.move || "—"}
                              </p>
                            </div>
                            <div className="bg-green-500/10 rounded-lg p-3">
                              <p className="text-xs text-green-400 mb-1">Better was</p>
                              <p className="font-mono font-bold text-lg">
                                {criticalMistake.better_move || "—"}
                              </p>
                            </div>
                          </div>
                          
                          {criticalMistake.eval_loss > 0 && (
                            <p className="text-sm text-zinc-500">
                              This cost you ~{(criticalMistake.eval_loss / 100).toFixed(1)} pawns of advantage
                            </p>
                          )}
                          
                          {/* Category badge */}
                          {mistakeExplanation?.category && (
                            <div className="flex gap-2">
                              <span className={`text-xs px-2 py-1 rounded ${
                                mistakeExplanation.category === "opening" 
                                  ? "bg-blue-500/20 text-blue-400" 
                                  : mistakeExplanation.category === "tactical"
                                    ? "bg-red-500/20 text-red-400"
                                    : "bg-yellow-500/20 text-yellow-400"
                              }`}>
                                {mistakeExplanation.category === "opening" ? "Opening Principle" :
                                 mistakeExplanation.category === "tactical" ? "Tactical Error" : 
                                 "Positional Mistake"}
                              </span>
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="space-y-4">
                          <p className="text-zinc-400">
                            This game had no significant mistakes detected. Good job!
                          </p>
                          <p className="text-sm text-zinc-500">
                            Try reviewing a game where you lost or made blunders for more insights.
                          </p>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </motion.div>
              )}

              {/* Step 1: The Pattern */}
              {currentStep === 1 && (
                <motion.div
                  key="pattern"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                >
                  <Card className="bg-amber-950/30 border-amber-500/50">
                    <CardContent className="p-6">
                      <div className="flex items-center gap-3 mb-4">
                        <Repeat className="w-8 h-8 text-amber-400" />
                        <div>
                          <p className="text-amber-400 text-sm font-medium">THE PATTERN</p>
                          <p className="text-lg font-bold">This Keeps Happening</p>
                        </div>
                      </div>

                      <div className="space-y-4">
                        <p className="text-2xl font-bold text-white">
                          This is your <span className="text-amber-400">{patternCount}th</span> time making this mistake.
                        </p>

                        <div className="bg-zinc-900/50 rounded-lg p-4">
                          <p className="text-zinc-300">
                            You are <span className="text-red-400 font-semibold">NOT improving</span> on this.
                          </p>
                          <p className="text-zinc-500 text-sm mt-2">
                            This pattern is costing you games. Let's fix it permanently.
                          </p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              )}

              {/* Step 2: The Rule */}
              {currentStep === 2 && (
                <motion.div
                  key="rule"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                >
                  <Card className="bg-blue-950/30 border-blue-500/50">
                    <CardContent className="p-6">
                      <div className="flex items-center gap-3 mb-4">
                        <Target className="w-8 h-8 text-blue-400" />
                        <div>
                          <p className="text-blue-400 text-sm font-medium">YOUR RULE</p>
                          <p className="text-lg font-bold">Remember This</p>
                        </div>
                      </div>

                      <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-6">
                        <p className="text-xl font-bold text-white leading-relaxed">
                          {mistakeExplanation?.rule || blocker?.rule || "Before EVERY move, ask: What is my opponent threatening?"}
                        </p>
                      </div>

                      <p className="text-zinc-400 text-sm mt-4">
                        Say this to yourself before every move until it becomes automatic.
                      </p>
                    </CardContent>
                  </Card>
                </motion.div>
              )}

              {/* Step 3: Demo */}
              {currentStep === 3 && (
                <motion.div
                  key="demo"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                >
                  <Card className="bg-green-950/30 border-green-500/50">
                    <CardContent className="p-6">
                      <div className="flex items-center gap-3 mb-4">
                        <Eye className="w-8 h-8 text-green-400" />
                        <div>
                          <p className="text-green-400 text-sm font-medium">SEE THE LINES</p>
                          <p className="text-lg font-bold">Step Through the Variations</p>
                        </div>
                      </div>

                      <div className="space-y-4">
                        <p className="text-zinc-300">
                          Step through each line to see why {criticalMistake?.better_move || "the best move"} is better.
                        </p>

                        {/* Line comparison */}
                        <div className="grid grid-cols-2 gap-3">
                          <div className="bg-red-500/10 rounded-lg p-3 border border-red-500/20">
                            <p className="text-xs text-red-400 mb-1">Your line</p>
                            <p className="font-mono text-sm text-white">
                              {criticalMistake?.move} {(criticalMistake?.pv_after_played || []).slice(0, 3).join(" ")}
                              {(criticalMistake?.pv_after_played?.length || 0) > 3 ? "..." : ""}
                            </p>
                          </div>
                          <div className="bg-green-500/10 rounded-lg p-3 border border-green-500/20">
                            <p className="text-xs text-green-400 mb-1">Best line</p>
                            <p className="font-mono text-sm text-white">
                              {criticalMistake?.better_move} {(criticalMistake?.pv_after_best || []).slice(0, 3).join(" ")}
                              {(criticalMistake?.pv_after_best?.length || 0) > 3 ? "..." : ""}
                            </p>
                          </div>
                        </div>

                        <div className="bg-zinc-900/50 rounded-lg p-4 text-sm">
                          <p className="text-zinc-400">
                            Use the controls below the board to step through each move and see how the position evolves.
                          </p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Navigation */}
            <div className="flex gap-3 mt-6">
              {currentStep > 0 && (
                <Button
                  variant="outline"
                  onClick={prevStep}
                  className="border-zinc-700"
                >
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  Back
                </Button>
              )}
              
              <Button
                onClick={nextStep}
                className={`flex-1 ${
                  currentStep === 3 
                    ? "bg-green-600 hover:bg-green-700" 
                    : "bg-amber-600 hover:bg-amber-700"
                }`}
              >
                {currentStep === 3 ? (
                  <>
                    <Zap className="w-4 h-4 mr-2" />
                    Practice This Now
                  </>
                ) : (
                  <>
                    Next
                    <ArrowRight className="w-4 h-4 ml-2" />
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PlateauBreakerReview;
