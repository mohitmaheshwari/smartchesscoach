/**
 * PlateauBreakerTraining.jsx - V1 Forced Training Mode
 * 
 * User CANNOT skip this. User CANNOT escape.
 * 
 * RULES:
 * - Must complete 5 puzzles CORRECTLY
 * - If 2 wrong answers → RESTART from 0
 * - After puzzles → 1 MINI-GAME applying the rule
 * - Only then is next game analysis unlocked
 * 
 * PSYCHOLOGY:
 * - "You are a player who ignores threats. That's why you're stuck."
 * - Track mistakes across games, show real progress
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
  Zap,
  AlertTriangle,
  Skull,
  TrendingUp
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

import "chessground/assets/chessground.base.css";
import "chessground/assets/chessground.brown.css";
import "chessground/assets/chessground.cburnett.css";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

// Training positions by mistake type - MORE PUZZLES
const TRAINING_POSITIONS = {
  tactical_error: [
    {
      fen: "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
      solution: "Qxf7#",
      hint: "The f7 pawn is weak. Only the king defends it.",
      explanation: "Qxf7 is CHECKMATE. The f7 square is only defended by the king - this is the Scholar's Mate pattern."
    },
    {
      fen: "rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq - 0 2",
      solution: "Qh4#",
      hint: "White's king is exposed. Find the checkmate.",
      explanation: "Qh4 is CHECKMATE. White's f3 and g4 pawns created fatal weaknesses around the king."
    },
    {
      fen: "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3",
      solution: "Nf6",
      hint: "Defend the f7 square while developing.",
      explanation: "Nf6 develops a piece AND defends f7. Always develop with purpose."
    },
    {
      fen: "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 0 5",
      solution: "O-O",
      hint: "Get your king to safety.",
      explanation: "Castling gets the king safe and connects the rooks. Don't delay king safety."
    },
    {
      fen: "r2qkbnr/ppp2ppp/2np4/4p3/2B1P1b1/5N2/PPPP1PPP/RNBQ1RK1 w kq - 0 5",
      solution: "Bxf7+",
      hint: "The f7 pawn is weak again. Check the consequences.",
      explanation: "Bxf7+ wins a pawn and exposes the king. Always look for weak f7/f2 squares."
    },
    {
      fen: "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
      solution: "Ng5",
      hint: "Attack f7 with multiple pieces.",
      explanation: "Ng5 adds a second attacker to f7. Two attackers vs one defender = winning."
    },
    {
      fen: "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2",
      solution: "Nc6",
      hint: "Develop and defend.",
      explanation: "Nc6 develops a piece and defends e5. Never leave pieces undefended."
    }
  ],
  hanging_piece: [
    {
      fen: "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
      solution: "Bb5",
      hint: "Develop with a threat.",
      explanation: "Bb5 develops AND pins the knight. Always look for moves that do two things."
    },
    {
      fen: "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
      solution: "d3",
      hint: "Protect your bishop before it gets attacked.",
      explanation: "d3 protects the c4 bishop. Before making any move, check: is my piece safe?"
    }
  ],
  missed_tactic: [
    {
      fen: "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
      solution: "Qxf7#",
      hint: "Scholar's mate!",
      explanation: "Qxf7 is checkmate! Always look for CHECKS first."
    }
  ],
  positional_mistake: [
    {
      fen: "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
      solution: "Bc4",
      hint: "Develop to an active square.",
      explanation: "Bc4 points at the weak f7 square. Bishops belong on active diagonals."
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
  const [wrongAnswers, setWrongAnswers] = useState(0);
  const [puzzleState, setPuzzleState] = useState("thinking"); // thinking, correct, incorrect, failed
  const [selectedMove, setSelectedMove] = useState(null);
  const [showHint, setShowHint] = useState(false);
  const [trainingComplete, setTrainingComplete] = useState(false);
  const [showFailure, setShowFailure] = useState(false);
  const [attempts, setAttempts] = useState(1);

  const puzzles = TRAINING_POSITIONS[mistakeType] || TRAINING_POSITIONS.tactical_error;
  const currentPuzzle = puzzles[currentPuzzleIndex % puzzles.length];
  const requiredPuzzles = 5;
  const maxWrongAnswers = 2; // Fail after 2 wrong

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
    if (groundRef.current && currentPuzzle && puzzleState === "thinking") {
      loadPuzzle();
    }
  }, [currentPuzzleIndex, currentPuzzle, puzzleState]);

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
      if (!dests.has(move.from)) {
        dests.set(move.from, []);
      }
      dests.get(move.from).push(move.to);
    }
    
    return dests;
  };

  const onMove = (orig, dest) => {
    const move = chessRef.current.move({ from: orig, to: dest });
    
    if (move) {
      setSelectedMove(move.san);
      
      // Check if correct (normalize move notation)
      const isCorrect = move.san.replace(/[+#]/g, '') === currentPuzzle.solution.replace(/[+#]/g, '');
      
      if (isCorrect) {
        setPuzzleState("correct");
        if (groundRef.current) {
          groundRef.current.set({
            fen: chessRef.current.fen(),
            lastMove: [orig, dest],
            movable: { dests: new Map() }
          });
        }
      } else {
        // WRONG ANSWER
        const newWrongCount = wrongAnswers + 1;
        setWrongAnswers(newWrongCount);
        
        if (newWrongCount >= maxWrongAnswers) {
          // FAILED - Must restart
          setPuzzleState("failed");
          setShowFailure(true);
        } else {
          setPuzzleState("incorrect");
          setTimeout(() => {
            loadPuzzle();
          }, 2000);
        }
      }
    }
  };

  const handleNextPuzzle = () => {
    const newCompleted = puzzlesCompleted + 1;
    setPuzzlesCompleted(newCompleted);
    
    if (newCompleted >= requiredPuzzles) {
      // Puzzles complete - now go to Apply Mode
      navigate("/plateau-breaker/apply", {
        state: { blocker, fromTraining: true }
      });
    } else {
      setCurrentPuzzleIndex(prev => prev + 1);
      setPuzzleState("thinking");
    }
  };

  const handleRestart = () => {
    setAttempts(prev => prev + 1);
    setPuzzlesCompleted(0);
    setWrongAnswers(0);
    setCurrentPuzzleIndex(0);
    setShowFailure(false);
    setPuzzleState("thinking");
  };

  const saveTrainingProgress = async (completed) => {
    try {
      localStorage.setItem(`training_status_${user?.user_id}`, JSON.stringify({
        puzzlesCompleted: requiredPuzzles,
        puzzlesRequired: requiredPuzzles,
        isUnlocked: completed,
        completedAt: new Date().toISOString(),
        attempts: attempts,
        blockerType: mistakeType
      }));
    } catch (err) {
      console.error("Error saving training progress:", err);
    }
  };

  const handleFinish = () => {
    navigate("/plateau-breaker");
  };

  // FAILURE SCREEN - Harsh messaging
  if (showFailure) {
    return (
      <div className="min-h-screen bg-zinc-950 text-white flex items-center justify-center p-6">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="max-w-md w-full"
        >
          <Card className="bg-red-950/50 border-red-500/50">
            <CardContent className="p-8 text-center">
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: 0.2, type: "spring" }}
                className="w-20 h-20 bg-red-500/20 rounded-full flex items-center justify-center mx-auto mb-6"
              >
                <Skull className="w-10 h-10 text-red-400" />
              </motion.div>

              <h2 className="text-2xl font-bold text-red-400 mb-4">
                Training Failed
              </h2>
              
              {/* IDENTITY ATTACK */}
              <div className="bg-red-900/30 rounded-lg p-4 mb-6 text-left">
                <p className="text-white font-semibold mb-2">
                  You are a player who {blocker?.title?.toLowerCase() || "makes the same mistakes repeatedly"}.
                </p>
                <p className="text-zinc-400 text-sm">
                  This is why you're stuck at your rating. You got {wrongAnswers} wrong. 
                  You cannot escape this training until you actually learn.
                </p>
              </div>

              <div className="flex items-center justify-center gap-2 text-amber-400 mb-6">
                <AlertTriangle className="w-5 h-5" />
                <span className="text-sm">Attempt #{attempts} failed</span>
              </div>

              <p className="text-zinc-500 text-sm mb-6">
                Progress reset to 0. Complete {requiredPuzzles} puzzles with max {maxWrongAnswers - 1} mistakes.
              </p>

              <Button
                onClick={handleRestart}
                className="w-full h-12 text-lg bg-red-600 hover:bg-red-700"
              >
                <RotateCcw className="w-5 h-5 mr-2" />
                Start Over (Attempt #{attempts + 1})
              </Button>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    );
  }

  // COMPLETION SCREEN
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
                Training Complete
              </h2>
              
              <p className="text-zinc-300 mb-4">
                {requiredPuzzles} puzzles in {attempts} attempt{attempts > 1 ? 's' : ''}.
              </p>

              <div className="bg-zinc-900/50 rounded-lg p-4 mb-6 text-left">
                <div className="flex items-center gap-2 text-green-400 mb-2">
                  <TrendingUp className="w-4 h-4" />
                  <span className="font-semibold">This is how you break plateau.</span>
                </div>
                <p className="text-zinc-400 text-sm">
                  Now apply this rule in your next game. We'll be watching.
                </p>
              </div>

              <div className="flex items-center justify-center gap-2 text-green-400 mb-6">
                <Unlock className="w-5 h-5" />
                <span>Next analysis unlocked</span>
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
      {/* Header with STRICT messaging */}
      <div className="border-b border-zinc-800 p-4">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Lock className="w-5 h-5 text-red-500" />
              <span className="font-semibold text-red-400">Training Required</span>
              <span className="text-xs text-zinc-500 ml-2">Cannot skip</span>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm text-zinc-500">
                {puzzlesCompleted} / {requiredPuzzles} correct
              </span>
              {wrongAnswers > 0 && (
                <span className="text-sm text-red-400">
                  {wrongAnswers} / {maxWrongAnswers} wrong
                </span>
              )}
            </div>
          </div>
          <Progress value={(puzzlesCompleted / requiredPuzzles) * 100} className="h-2" />
          
          {wrongAnswers > 0 && (
            <p className="text-xs text-red-400 mt-2">
              ⚠️ {maxWrongAnswers - wrongAnswers} more wrong and you restart from 0
            </p>
          )}
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
            {/* Rule Reminder - RED and PROMINENT */}
            <Card className="bg-red-500/10 border-red-500/30">
              <CardContent className="p-4">
                <div className="flex items-start gap-3">
                  <Target className="w-5 h-5 text-red-400 mt-0.5" />
                  <div>
                    <p className="text-red-400 text-xs font-medium mb-1">YOUR RULE (say it before every move)</p>
                    <p className="text-white font-bold">
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
                      <p className="text-zinc-400 mb-4">
                        Apply your rule. Think before you click.
                      </p>

                      {showHint && (
                        <motion.div
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          className="mb-4 p-3 bg-amber-500/10 rounded-lg border border-amber-500/30"
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
                          className="text-zinc-500 hover:text-zinc-300"
                        >
                          <Lightbulb className="w-4 h-4 mr-1" />
                          I need a hint
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
                          <p className="text-zinc-400 text-sm font-mono">{selectedMove}</p>
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
                            Next Puzzle ({puzzlesCompleted + 1}/{requiredPuzzles})
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
                          <h3 className="text-lg font-semibold text-red-400">Wrong</h3>
                          <p className="text-zinc-400 text-sm">{selectedMove} is not the best move</p>
                        </div>
                      </div>

                      <p className="text-zinc-300 mb-4">
                        You didn't apply your rule. Think again: <span className="text-amber-400 font-semibold">What is threatening?</span>
                      </p>
                      
                      <p className="text-red-400 text-sm">
                        {maxWrongAnswers - wrongAnswers} wrong left before restart
                      </p>
                    </CardContent>
                  </Card>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Progress Stats */}
            <Card className="bg-zinc-900/50 border-zinc-800">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-zinc-500">Puzzle</p>
                    <p className="text-xl font-bold">{puzzlesCompleted + 1} of {requiredPuzzles}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-sm text-zinc-500">Mistakes</p>
                    <p className={`text-xl font-bold ${wrongAnswers > 0 ? 'text-red-400' : 'text-green-400'}`}>
                      {wrongAnswers} / {maxWrongAnswers}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-zinc-500">Attempt</p>
                    <p className="text-xl font-bold text-amber-400">#{attempts}</p>
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
