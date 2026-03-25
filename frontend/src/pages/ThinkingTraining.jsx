/**
 * TRAINING PAGE → Rewire Your Thinking
 * 
 * Not a puzzle app. A thinking simulator.
 * 
 * The Flow:
 * 1. CONFRONT - Show user's actual mistake from their game
 * 2. DIAGNOSE - "What were you thinking?" + cognitive gap
 * 3. PATTERN LOCK - Show this is a recurring pattern
 * 4. TEST - Similar position to practice recognition
 * 
 * One pattern. Deep understanding. Lasting change.
 */

import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Chess } from "chess.js";
import { API } from "@/App";
import Layout from "@/components/Layout";
import LichessBoard from "@/components/LichessBoard";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";
import {
  Loader2,
  Brain,
  CheckCircle2,
  XCircle,
  Lightbulb,
  ChevronRight,
  AlertTriangle,
  Eye,
  Target,
  Zap,
  RotateCcw,
  Trophy,
} from "lucide-react";

// Steps in the training flow
const STEPS = {
  CONFRONT: "confront",
  PATTERN: "pattern",
  TEST: "test",
  COMPLETE: "complete"
};

const ThinkingTraining = ({ user }) => {
  const navigate = useNavigate();
  
  // Core state
  const [loading, setLoading] = useState(true);
  const [step, setStep] = useState(STEPS.CONFRONT);
  const [puzzle, setPuzzle] = useState(null);
  const [pattern, setPattern] = useState(null);
  const [similarPositions, setSimilarPositions] = useState([]);
  
  // Board state
  const [boardFen, setBoardFen] = useState("start");
  const [boardOrientation, setBoardOrientation] = useState("white");
  const [lastMove, setLastMove] = useState(null);
  const [arrows, setArrows] = useState([]);
  
  // Test step state
  const [testPuzzle, setTestPuzzle] = useState(null);
  const [testState, setTestState] = useState("thinking"); // thinking, correct, incorrect
  const [testAttempts, setTestAttempts] = useState(0);
  
  // Session state
  const [sessionStats, setSessionStats] = useState({ completed: 0, patterns: [] });

  // Fetch initial data
  useEffect(() => {
    fetchTrainingData();
  }, []);

  const fetchTrainingData = async () => {
    setLoading(true);
    try {
      // Get user's cognitive patterns (their recurring weaknesses)
      const [patternsRes, puzzlesRes] = await Promise.all([
        fetch(`${API}/cognitive/patterns`, { credentials: "include" }),
        fetch(`${API}/training/puzzles?limit=5`, { credentials: "include" })
      ]);
      
      if (patternsRes.ok) {
        const patternData = await patternsRes.json();
        // Find the worst pattern (highest weighted score)
        const patterns = patternData.patterns || {};
        const sorted = Object.entries(patterns)
          .map(([key, val]) => ({ key, ...val }))
          .sort((a, b) => b.weighted_score - a.weighted_score);
        
        if (sorted.length > 0) {
          setPattern(sorted[0]);
        }
      }
      
      if (puzzlesRes.ok) {
        const puzzleData = await puzzlesRes.json();
        const puzzles = puzzleData.puzzles || [];
        
        if (puzzles.length > 0) {
          // Pick the first puzzle (highest priority)
          const firstPuzzle = puzzles[0];
          setPuzzle(firstPuzzle);
          setBoardFen(firstPuzzle.fen);
          setBoardOrientation(firstPuzzle.user_color || "white");
          
          // Set up similar positions for testing
          if (puzzles.length > 1) {
            setSimilarPositions(puzzles.slice(1, 3));
            setTestPuzzle(puzzles[1]);
          }
        }
      }
    } catch (e) {
      console.error("Failed to load training data:", e);
      toast.error("Could not load training");
    } finally {
      setLoading(false);
    }
  };

  // Handle test move
  const handleTestMove = useCallback((from, to, promotion) => {
    if (!testPuzzle || testState !== "thinking") return false;
    
    const chess = new Chess(testPuzzle.fen);
    
    try {
      const move = chess.move({ from, to, promotion: promotion || 'q' });
      if (!move) return false;
      
      const isCorrect = move.san === testPuzzle.correct_move || 
                        `${from}${to}` === testPuzzle.best_move_uci;
      
      setTestAttempts(prev => prev + 1);
      
      if (isCorrect) {
        setTestState("correct");
        setBoardFen(chess.fen());
        setLastMove([from, to]);
        
        // Show the winning arrow
        setArrows([{ 
          orig: from, 
          dest: to, 
          brush: 'green' 
        }]);
        
        // Update session stats
        setSessionStats(prev => ({
          ...prev,
          completed: prev.completed + 1,
          patterns: [...prev.patterns, pattern?.key]
        }));
        
        return true;
      } else {
        setTestState("incorrect");
        
        // Show what they played vs what was correct
        const correctFrom = testPuzzle.best_move_uci?.slice(0, 2);
        const correctTo = testPuzzle.best_move_uci?.slice(2, 4);
        
        setArrows([
          { orig: from, dest: to, brush: 'red' },
          { orig: correctFrom, dest: correctTo, brush: 'green' }
        ]);
        
        return true;
      }
    } catch (e) {
      return false;
    }
  }, [testPuzzle, testState, pattern]);

  // Move to next step
  const nextStep = () => {
    switch (step) {
      case STEPS.CONFRONT:
        setStep(STEPS.PATTERN);
        break;
      case STEPS.PATTERN:
        if (testPuzzle) {
          setStep(STEPS.TEST);
          setBoardFen(testPuzzle.fen);
          setBoardOrientation(testPuzzle.user_color || "white");
          setArrows([]);
          setLastMove(null);
        } else {
          setStep(STEPS.COMPLETE);
        }
        break;
      case STEPS.TEST:
        setStep(STEPS.COMPLETE);
        break;
      default:
        break;
    }
  };

  // Reset for another round
  const startAgain = () => {
    setStep(STEPS.CONFRONT);
    setTestState("thinking");
    setTestAttempts(0);
    setArrows([]);
    fetchTrainingData();
  };

  // Format pattern name for display
  const formatPatternName = (key) => {
    if (!key) return "Unknown Pattern";
    return key.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  };

  // Loading state
  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
          <p className="text-zinc-400">Finding your patterns...</p>
        </div>
      </Layout>
    );
  }

  // No puzzles available
  if (!puzzle) {
    return (
      <Layout user={user}>
        <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
          <Brain className="w-12 h-12 text-zinc-600" />
          <h2 className="text-xl font-semibold">No Training Available</h2>
          <p className="text-zinc-400 text-center max-w-md">
            Play some games and analyze them first. We'll find your patterns and create personalized training.
          </p>
          <Button onClick={() => navigate("/play-with-coach")}>
            Play a Game
          </Button>
        </div>
      </Layout>
    );
  }

  return (
    <Layout user={user}>
      <div className="max-w-5xl mx-auto py-6 px-4" data-testid="thinking-training">
        
        {/* Progress indicator */}
        <div className="mb-6">
          <div className="flex items-center justify-between text-xs text-zinc-500 mb-2">
            <span>Training Progress</span>
            <span>{step === STEPS.COMPLETE ? "Complete!" : `Step ${Object.values(STEPS).indexOf(step) + 1} of 3`}</span>
          </div>
          <Progress 
            value={(Object.values(STEPS).indexOf(step) + 1) * 33.33} 
            className="h-1"
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          
          {/* LEFT: Board */}
          <div className="space-y-4">
            <div className="aspect-square max-w-[500px] mx-auto">
              <LichessBoard
                fen={boardFen}
                orientation={boardOrientation}
                viewOnly={step !== STEPS.TEST || testState !== "thinking"}
                onMove={step === STEPS.TEST ? handleTestMove : undefined}
                lastMove={lastMove}
                arrows={arrows}
              />
            </div>
            
            {/* Context below board */}
            {puzzle && step !== STEPS.TEST && step !== STEPS.COMPLETE && (
              <div className="text-center text-sm text-zinc-500">
                <p>vs {puzzle.opponent} · Move {puzzle.move_number}</p>
                <p className="text-xs">You played <span className="font-mono text-red-400">{puzzle.user_move}</span></p>
              </div>
            )}
            
            {testPuzzle && step === STEPS.TEST && (
              <div className="text-center text-sm text-zinc-500">
                <p>Similar position · Find the best move</p>
              </div>
            )}
          </div>

          {/* RIGHT: Training Content */}
          <div className="space-y-4">
            <AnimatePresence mode="wait">
              
              {/* ═══════════════════════════════════════════════════════════
                  STEP 1: CONFRONT
              ═══════════════════════════════════════════════════════════ */}
              {step === STEPS.CONFRONT && (
                <motion.div
                  key="confront"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                >
                  <Card className="bg-zinc-900/50 border-zinc-800">
                    <CardContent className="p-6 space-y-4">
                      <div className="flex items-center gap-2">
                        <AlertTriangle className="w-5 h-5 text-amber-500" />
                        <h2 className="text-lg font-semibold">Confront</h2>
                      </div>
                      
                      <p className="text-zinc-300">
                        This is a position from your recent game. You played{" "}
                        <span className="font-mono text-red-400">{puzzle.user_move}</span>, 
                        but the best move was{" "}
                        <span className="font-mono text-emerald-400">{puzzle.correct_move}</span>.
                      </p>
                      
                      {puzzle.cp_loss && (
                        <div className="p-3 rounded bg-red-500/10 border border-red-500/20">
                          <p className="text-sm text-red-300">
                            This cost you{" "}
                            <span className="font-bold">{(puzzle.cp_loss / 100).toFixed(1)} pawns</span>{" "}
                            worth of advantage.
                          </p>
                        </div>
                      )}
                      
                      {pattern && (
                        <div className="p-3 rounded bg-amber-500/10 border border-amber-500/20">
                          <p className="text-xs text-amber-400 mb-1">Your recurring pattern</p>
                          <p className="text-sm font-medium text-amber-200">
                            {formatPatternName(pattern.key)}
                          </p>
                          <p className="text-xs text-zinc-500 mt-1">
                            {pattern.frequency} occurrences · {pattern.trend}
                          </p>
                        </div>
                      )}
                      
                      <Button onClick={nextStep} className="w-full">
                        Understand Why
                        <ChevronRight className="w-4 h-4 ml-2" />
                      </Button>
                    </CardContent>
                  </Card>
                </motion.div>
              )}

              {/* ═══════════════════════════════════════════════════════════
                  STEP 2: PATTERN LOCK
              ═══════════════════════════════════════════════════════════ */}
              {step === STEPS.PATTERN && (
                <motion.div
                  key="pattern"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                >
                  <Card className="bg-zinc-900/50 border-zinc-800">
                    <CardContent className="p-6 space-y-4">
                      <div className="flex items-center gap-2">
                        <Target className="w-5 h-5 text-cyan-500" />
                        <h2 className="text-lg font-semibold">Pattern Lock</h2>
                      </div>
                      
                      <p className="text-zinc-300">
                        This isn't a one-time mistake. It's a{" "}
                        <span className="text-cyan-400 font-medium">pattern</span>{" "}
                        in how you think.
                      </p>
                      
                      {pattern && (
                        <div className="p-4 rounded bg-cyan-500/10 border border-cyan-500/20">
                          <div className="flex items-center justify-between mb-2">
                            <p className="font-medium text-cyan-300">
                              {formatPatternName(pattern.key)}
                            </p>
                            <Badge variant="outline" className="text-xs border-cyan-500/50 text-cyan-400">
                              {pattern.frequency}x
                            </Badge>
                          </div>
                          <p className="text-xs text-zinc-400">
                            You've made this type of error {pattern.frequency} times.
                            {pattern.trend === "worsening" && " It's getting worse."}
                            {pattern.trend === "improving" && " You're improving!"}
                          </p>
                        </div>
                      )}
                      
                      <div className="p-4 rounded bg-amber-500/5 border border-amber-500/20">
                        <div className="flex items-start gap-2">
                          <Lightbulb className="w-4 h-4 text-amber-400 mt-0.5 flex-shrink-0" />
                          <div>
                            <p className="text-xs text-amber-400 mb-1">The Cure</p>
                            <p className="text-sm text-amber-200">
                              {diagnosisResult?.lesson || puzzle.thinking_habit || 
                               "Before every move, pause and ask: What is my opponent's threat?"}
                            </p>
                          </div>
                        </div>
                      </div>
                      
                      {testPuzzle ? (
                        <Button onClick={nextStep} className="w-full bg-cyan-600 hover:bg-cyan-700">
                          <Zap className="w-4 h-4 mr-2" />
                          Test My Understanding
                        </Button>
                      ) : (
                        <Button onClick={() => setStep(STEPS.COMPLETE)} className="w-full">
                          Complete Training
                        </Button>
                      )}
                    </CardContent>
                  </Card>
                </motion.div>
              )}

              {/* ═══════════════════════════════════════════════════════════
                  STEP 4: TEST
              ═══════════════════════════════════════════════════════════ */}
              {step === STEPS.TEST && (
                <motion.div
                  key="test"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                >
                  <Card className="bg-zinc-900/50 border-zinc-800">
                    <CardContent className="p-6 space-y-4">
                      <div className="flex items-center gap-2">
                        <Zap className="w-5 h-5 text-yellow-500" />
                        <h2 className="text-lg font-semibold">Test</h2>
                      </div>
                      
                      {testState === "thinking" && (
                        <>
                          <p className="text-zinc-300">
                            Here's a similar position. Apply what you just learned.
                          </p>
                          <p className="text-sm text-zinc-500">
                            Find the best move. Make it on the board.
                          </p>
                          
                          <div className="p-3 rounded bg-zinc-800/50 text-sm">
                            <p className="text-zinc-400">
                              Remember: {diagnosisResult?.principle?.quick_tip || puzzle.thinking_habit}
                            </p>
                          </div>
                        </>
                      )}
                      
                      {testState === "correct" && (
                        <>
                          <div className="p-4 rounded bg-emerald-500/10 border border-emerald-500/20 text-center">
                            <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
                            <p className="font-medium text-emerald-300">You got it!</p>
                            <p className="text-sm text-zinc-400 mt-1">
                              The pattern is locking in.
                            </p>
                          </div>
                          
                          <Button onClick={nextStep} className="w-full">
                            Complete Training
                            <ChevronRight className="w-4 h-4 ml-2" />
                          </Button>
                        </>
                      )}
                      
                      {testState === "incorrect" && (
                        <>
                          <div className="p-4 rounded bg-red-500/10 border border-red-500/20 text-center">
                            <XCircle className="w-8 h-8 text-red-500 mx-auto mb-2" />
                            <p className="font-medium text-red-300">Not quite</p>
                            <p className="text-sm text-zinc-400 mt-1">
                              The best move was{" "}
                              <span className="font-mono text-emerald-400">{testPuzzle.correct_move}</span>
                            </p>
                          </div>
                          
                          <Button 
                            onClick={() => {
                              setTestState("thinking");
                              setBoardFen(testPuzzle.fen);
                              setArrows([]);
                            }} 
                            variant="outline"
                            className="w-full"
                          >
                            <RotateCcw className="w-4 h-4 mr-2" />
                            Try Again
                          </Button>
                          
                          <Button onClick={nextStep} variant="ghost" className="w-full text-zinc-500">
                            Continue anyway
                          </Button>
                        </>
                      )}
                    </CardContent>
                  </Card>
                </motion.div>
              )}

              {/* ═══════════════════════════════════════════════════════════
                  COMPLETE
              ═══════════════════════════════════════════════════════════ */}
              {step === STEPS.COMPLETE && (
                <motion.div
                  key="complete"
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                >
                  <Card className="bg-gradient-to-b from-emerald-500/10 to-transparent border-emerald-500/30">
                    <CardContent className="p-6 space-y-4 text-center">
                      <Trophy className="w-12 h-12 text-emerald-500 mx-auto" />
                      
                      <h2 className="text-xl font-semibold">Training Complete</h2>
                      
                      <p className="text-zinc-300">
                        You've worked on your{" "}
                        <span className="text-cyan-400">{formatPatternName(pattern?.key)}</span>{" "}
                        pattern.
                      </p>
                      
                      <div className="p-4 rounded bg-zinc-800/50 text-left">
                        <p className="text-xs text-zinc-500 mb-2">Key takeaway</p>
                        <p className="text-sm text-zinc-200">
                          {diagnosisResult?.lesson || puzzle.thinking_habit}
                        </p>
                      </div>
                      
                      <div className="flex gap-2 pt-2">
                        <Button onClick={startAgain} className="flex-1">
                          <Zap className="w-4 h-4 mr-2" />
                          Train Again
                        </Button>
                        <Button onClick={() => navigate("/home")} variant="outline" className="flex-1">
                          Done
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              )}
              
            </AnimatePresence>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default ThinkingTraining;
