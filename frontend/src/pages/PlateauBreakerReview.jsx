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
  ChevronUp
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
  const [patternCount, setPatternCount] = useState(0);
  const [currentStep, setCurrentStep] = useState(0); // 0: mistake, 1: pattern, 2: rule, 3: demo
  const [showingDemo, setShowingDemo] = useState(false);
  const [demoStep, setDemoStep] = useState(0);
  const [currentFen, setCurrentFen] = useState("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  const [lastMove, setLastMove] = useState(null);
  const [orientation, setOrientation] = useState("white");

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

      // Find the most critical mistake
      const analysis = game.analysis || {};
      const mistakes = analysis.mistakes || [];
      
      // Get biggest mistake (by eval loss)
      let biggestMistake = null;
      let maxLoss = 0;
      
      for (const mistake of mistakes) {
        const loss = Math.abs(mistake.eval_loss || mistake.evaluation_change || 0);
        if (loss > maxLoss) {
          maxLoss = loss;
          biggestMistake = mistake;
        }
      }

      // If no mistakes found, use turning point
      if (!biggestMistake && analysis.turning_point) {
        biggestMistake = {
          move_number: analysis.turning_point.move_number,
          move: analysis.turning_point.played_move,
          better_move: analysis.turning_point.best_move,
          fen: analysis.turning_point.fen,
          explanation: analysis.turning_point.explanation,
          type: "turning_point"
        };
      }

      setCriticalMistake(biggestMistake);

      // Get pattern count from player identity
      const identityRes = await fetch(`${API}/coach/deep-memory?user_id=${user?.user_id}`, {
        credentials: "include"
      });
      const identity = await identityRes.json();
      
      // Count similar mistakes
      const taxonomy = identity.blunder_taxonomy || {};
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
    }
  };

  const showBetterMove = () => {
    if (criticalMistake?.fen && criticalMistake?.better_move) {
      chessRef.current.load(criticalMistake.fen);
      const move = chessRef.current.move(criticalMistake.better_move);
      if (move) {
        setCurrentFen(chessRef.current.fen());
        setLastMove([move.from, move.to]);
      }
    }
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
                  viewOnly={true}
                  interactive={false}
                />
              </div>
              
              {currentStep === 3 && (
                <div className="mt-4 flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={showMistakePosition}
                    className="flex-1 border-zinc-700"
                  >
                    <Eye className="w-4 h-4 mr-1" />
                    Your Move
                  </Button>
                  <Button
                    size="sm"
                    onClick={showBetterMove}
                    className="flex-1 bg-green-600 hover:bg-green-700"
                  >
                    <Target className="w-4 h-4 mr-1" />
                    Better Move
                  </Button>
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
                          <p className="text-lg font-bold">Move {criticalMistake?.move_number}</p>
                        </div>
                      </div>

                      <div className="space-y-4">
                        <p className="text-lg text-white">
                          {criticalMistake?.explanation || 
                           `You played ${criticalMistake?.move}, but this was a mistake.`}
                        </p>

                        <div className="grid grid-cols-2 gap-3">
                          <div className="bg-red-500/10 rounded-lg p-3">
                            <p className="text-xs text-red-400 mb-1">You played</p>
                            <p className="font-mono font-bold text-lg">{criticalMistake?.move}</p>
                          </div>
                          <div className="bg-green-500/10 rounded-lg p-3">
                            <p className="text-xs text-green-400 mb-1">Better was</p>
                            <p className="font-mono font-bold text-lg">{criticalMistake?.better_move || "..."}</p>
                          </div>
                        </div>
                      </div>
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
                          {blocker?.rule || "Before EVERY move, ask: What is my opponent threatening?"}
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
                          <p className="text-green-400 text-sm font-medium">SEE IT</p>
                          <p className="text-lg font-bold">The Difference</p>
                        </div>
                      </div>

                      <div className="space-y-4">
                        <p className="text-zinc-300">
                          Click the buttons below to see your move vs the better move.
                        </p>

                        <div className="bg-zinc-900/50 rounded-lg p-4">
                          <p className="text-sm text-zinc-400 mb-2">What you should have seen:</p>
                          <p className="text-white">
                            If you had followed the rule, you would have noticed the threat and played {criticalMistake?.better_move || "the better move"}.
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
