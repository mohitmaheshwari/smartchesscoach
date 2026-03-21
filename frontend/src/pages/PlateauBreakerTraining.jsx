/**
 * PlateauBreakerTraining.jsx - V1 Forced Training Mode
 * 
 * User CANNOT skip this.
 * 
 * Must complete:
 * - 5 puzzles (from their mistake type)
 * - OR 1 coached game with <1 blunder
 * 
 * Only then is next game analysis unlocked.
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Chess } from "chess.js";
import { Chessground } from "chessground";
import {
  Target,
  CheckCircle,
  XCircle,
  ArrowRight,
  Trophy,
  Lightbulb,
  Lock,
  Unlock,
  RotateCcw,
  Zap
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

import "chessground/assets/chessground.base.css";
import "chessground/assets/chessground.brown.css";
import "chessground/assets/chessground.cburnett.css";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

// Training positions by mistake type (simplified for demo)
const TRAINING_POSITIONS = {
  tactical_error: [
    {
      fen: "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
      solution: "Qxf7#",
      hint: "Look for a checkmate threat",
      explanation: "White can checkmate with Qxf7! The f7 pawn is only defended by the king."
    },
    {
      fen: "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3",
      solution: "Nf6",
      hint: "Defend the f7 square",
      explanation: "Nf6 develops a piece and defends f7 from the bishop attack."
    },
    {
      fen: "r2qkb1r/ppp2ppp/2n1bn2/3pp3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 2 5",
      solution: "exd5",
      hint: "Win a pawn!",
      explanation: "exd5 wins a pawn. After Nxd5, Nxd5 and White is up material."
    },
    {
      fen: "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
      solution: "Bc4",
      hint: "Develop with a threat",
      explanation: "Bc4 develops the bishop to an active square, targeting f7."
    },
    {
      fen: "rnbqk2r/pppp1ppp/5n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
      solution: "d3",
      hint: "Protect e4 and prepare development",
      explanation: "d3 is solid, protecting e4 and preparing to develop the bishop."
    }
  ],
  hanging_piece: [
    {
      fen: "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 2 3",
      solution: "Nc3",
      hint: "Develop without leaving pieces hanging",
      explanation: "Nc3 develops the knight to a safe square where it's defended."
    }
  ],
  missed_tactic: [
    {
      fen: "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
      solution: "Qxf7#",
      hint: "Scholar's mate!",
      explanation: "Qxf7 is checkmate! Always look for checks first."
    }
  ]
};

const PlateauBreakerTraining = ({ user }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const blocker = location.state?.blocker;
  const mistakeType = location.state?.mistakeType || blocker?.type || "tactical_error";

  const boardRef = useRef(null);
  const groundRef = useRef(null);
  const chessRef = useRef(new Chess());

  const [currentPuzzleIndex, setCurrentPuzzleIndex] = useState(0);
  const [puzzlesCompleted, setPuzzlesCompleted] = useState(0);
  const [puzzleState, setPuzzleState] = useState("thinking"); // thinking, correct, incorrect
  const [selectedMove, setSelectedMove] = useState(null);
  const [showHint, setShowHint] = useState(false);
  const [trainingComplete, setTrainingComplete] = useState(false);

  const puzzles = TRAINING_POSITIONS[mistakeType] || TRAINING_POSITIONS.tactical_error;
  const currentPuzzle = puzzles[currentPuzzleIndex % puzzles.length];
  const requiredPuzzles = 5;

  useEffect(() => {
    if (boardRef.current && !groundRef.current) {
      initializeBoard();
    }
    return () => {
      if (groundRef.current) {
        groundRef.current.destroy();
        groundRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (groundRef.current && currentPuzzle) {
      loadPuzzle();
    }
  }, [currentPuzzleIndex, currentPuzzle]);

  const initializeBoard = () => {
    groundRef.current = Chessground(boardRef.current, {
      fen: currentPuzzle.fen,
      orientation: "white",
      movable: {
        free: false,
        color: "white",
        dests: new Map(),
        events: {
          after: onMove
        }
      },
      animation: { duration: 300 }
    });
    loadPuzzle();
  };

  const loadPuzzle = useCallback(() => {
    chessRef.current.load(currentPuzzle.fen);
    const dests = getLegalMoves();
    
    if (groundRef.current) {
      groundRef.current.set({
        fen: currentPuzzle.fen,
        turnColor: chessRef.current.turn() === 'w' ? 'white' : 'black',
        movable: {
          free: false,
          color: chessRef.current.turn() === 'w' ? 'white' : 'black',
          dests: dests
        },
        lastMove: undefined
      });
    }
    
    setPuzzleState("thinking");
    setSelectedMove(null);
    setShowHint(false);
  }, [currentPuzzle]);

  const getLegalMoves = () => {
    const dests = new Map();
    const moves = chessRef.current.moves({ verbose: true });
    
    for (const move of moves) {
      const from = move.from;
      const to = move.to;
      if (!dests.has(from)) {
        dests.set(from, []);
      }
      dests.get(from).push(to);
    }
    
    return dests;
  };

  const onMove = (orig, dest) => {
    const move = chessRef.current.move({ from: orig, to: dest });
    
    if (move) {
      setSelectedMove(move.san);
      
      // Check if correct
      const isCorrect = move.san === currentPuzzle.solution || 
                        move.san.replace(/[+#]/, '') === currentPuzzle.solution.replace(/[+#]/, '');
      
      if (isCorrect) {
        setPuzzleState("correct");
        // Update board to show the move
        if (groundRef.current) {
          groundRef.current.set({
            fen: chessRef.current.fen(),
            lastMove: [orig, dest],
            movable: { dests: new Map() }
          });
        }
      } else {
        setPuzzleState("incorrect");
        // Reset after delay
        setTimeout(() => {
          loadPuzzle();
        }, 1500);
      }
    }
  };

  const handleNextPuzzle = () => {
    const newCompleted = puzzlesCompleted + 1;
    setPuzzlesCompleted(newCompleted);
    
    if (newCompleted >= requiredPuzzles) {
      // Training complete!
      setTrainingComplete(true);
      
      // Save to localStorage (should be backend)
      localStorage.setItem(`training_status_${user?.user_id}`, JSON.stringify({
        puzzlesCompleted: newCompleted,
        puzzlesRequired: requiredPuzzles,
        isUnlocked: true,
        completedAt: new Date().toISOString()
      }));
    } else {
      setCurrentPuzzleIndex(prev => prev + 1);
    }
  };

  const handleRetry = () => {
    loadPuzzle();
  };

  const handleFinish = () => {
    navigate("/plateau-breaker");
  };

  if (trainingComplete) {
    return (
      <div className="min-h-screen bg-zinc-950 text-white flex items-center justify-center p-6">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="max-w-md w-full"
        >
          <Card className="bg-green-950/30 border-green-500/50">
            <CardContent className="p-8 text-center">
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: 0.2, type: "spring" }}
                className="w-20 h-20 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-6"
              >
                <Trophy className="w-10 h-10 text-green-400" />
              </motion.div>

              <h2 className="text-2xl font-bold text-green-400 mb-2">
                Training Complete!
              </h2>
              
              <p className="text-zinc-300 mb-6">
                You completed {requiredPuzzles} puzzles. Your next game analysis is now unlocked.
              </p>

              <div className="flex items-center justify-center gap-2 text-green-400 mb-8">
                <Unlock className="w-5 h-5" />
                <span>Analysis Unlocked</span>
              </div>

              <Button
                onClick={handleFinish}
                className="w-full h-12 text-lg bg-green-600 hover:bg-green-700"
              >
                Continue
                <ArrowRight className="w-5 h-5 ml-2" />
              </Button>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-white">
      {/* Header */}
      <div className="border-b border-zinc-800 p-4">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Lock className="w-5 h-5 text-amber-500" />
              <span className="font-semibold">Training Required</span>
            </div>
            <span className="text-sm text-zinc-500">
              {puzzlesCompleted} / {requiredPuzzles} puzzles
            </span>
          </div>
          <Progress value={(puzzlesCompleted / requiredPuzzles) * 100} className="h-2" />
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-4xl mx-auto p-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          
          {/* Board */}
          <Card className="bg-zinc-900/50 border-zinc-800">
            <CardContent className="p-4">
              <div 
                ref={boardRef} 
                className="w-full aspect-square rounded-lg overflow-hidden"
              />
            </CardContent>
          </Card>

          {/* Puzzle Info */}
          <div className="space-y-4">
            {/* Rule Reminder */}
            <Card className="bg-amber-500/10 border-amber-500/30">
              <CardContent className="p-4">
                <div className="flex items-start gap-3">
                  <Target className="w-5 h-5 text-amber-400 mt-0.5" />
                  <div>
                    <p className="text-amber-400 text-sm font-medium mb-1">Remember Your Rule</p>
                    <p className="text-white font-semibold">
                      {blocker?.rule || "Before EVERY move, ask: What is my opponent threatening?"}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Puzzle State */}
            <AnimatePresence mode="wait">
              {puzzleState === "thinking" && (
                <motion.div
                  key="thinking"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                >
                  <Card className="bg-zinc-900/50 border-zinc-800">
                    <CardContent className="p-6">
                      <h3 className="text-lg font-semibold mb-2">Find the best move</h3>
                      <p className="text-zinc-400">
                        Apply your rule and find the winning move.
                      </p>

                      {showHint && (
                        <motion.div
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          className="mt-4 p-3 bg-amber-500/10 rounded-lg"
                        >
                          <p className="text-amber-400 text-sm">
                            <Lightbulb className="w-4 h-4 inline mr-1" />
                            {currentPuzzle.hint}
                          </p>
                        </motion.div>
                      )}

                      {!showHint && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setShowHint(true)}
                          className="mt-4 text-zinc-500 hover:text-zinc-300"
                        >
                          <Lightbulb className="w-4 h-4 mr-1" />
                          Show Hint
                        </Button>
                      )}
                    </CardContent>
                  </Card>
                </motion.div>
              )}

              {puzzleState === "correct" && (
                <motion.div
                  key="correct"
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0 }}
                >
                  <Card className="bg-green-950/30 border-green-500/50">
                    <CardContent className="p-6">
                      <div className="flex items-center gap-3 mb-4">
                        <CheckCircle className="w-8 h-8 text-green-400" />
                        <div>
                          <h3 className="text-lg font-semibold text-green-400">Correct!</h3>
                          <p className="text-zinc-400 text-sm">{selectedMove}</p>
                        </div>
                      </div>

                      <p className="text-zinc-300 mb-4">
                        {currentPuzzle.explanation}
                      </p>

                      <Button
                        onClick={handleNextPuzzle}
                        className="w-full bg-green-600 hover:bg-green-700"
                      >
                        {puzzlesCompleted + 1 >= requiredPuzzles ? (
                          <>
                            <Trophy className="w-4 h-4 mr-2" />
                            Complete Training
                          </>
                        ) : (
                          <>
                            Next Puzzle
                            <ArrowRight className="w-4 h-4 ml-2" />
                          </>
                        )}
                      </Button>
                    </CardContent>
                  </Card>
                </motion.div>
              )}

              {puzzleState === "incorrect" && (
                <motion.div
                  key="incorrect"
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0 }}
                >
                  <Card className="bg-red-950/30 border-red-500/50">
                    <CardContent className="p-6">
                      <div className="flex items-center gap-3 mb-4">
                        <XCircle className="w-8 h-8 text-red-400" />
                        <div>
                          <h3 className="text-lg font-semibold text-red-400">Not quite</h3>
                          <p className="text-zinc-400 text-sm">Try again</p>
                        </div>
                      </div>

                      <p className="text-zinc-300">
                        That's not the best move. Apply your rule and try again.
                      </p>
                    </CardContent>
                  </Card>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Progress Info */}
            <Card className="bg-zinc-900/50 border-zinc-800">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-zinc-500">Puzzle</p>
                    <p className="text-xl font-bold">{puzzlesCompleted + 1} of {requiredPuzzles}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-zinc-500">Until Unlock</p>
                    <p className="text-xl font-bold text-amber-400">
                      {Math.max(0, requiredPuzzles - puzzlesCompleted - 1)} left
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PlateauBreakerTraining;
