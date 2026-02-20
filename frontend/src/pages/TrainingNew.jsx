import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Chess } from "chess.js";
import { API } from "@/App";
import Layout from "@/components/Layout";
import CoachBoard from "@/components/CoachBoard";
import OpeningTrainer from "@/components/OpeningTrainer";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";
import {
  Loader2,
  Target,
  Brain,
  CheckCircle2,
  XCircle,
  Lightbulb,
  Play,
  RotateCcw,
  Trophy,
  Flame,
  BookOpen,
  ChevronRight,
  HelpCircle,
  Zap,
  GraduationCap,
} from "lucide-react";

const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

// Convert centipawns to human-readable evaluation
const formatEvaluation = (cpLoss) => {
  if (!cpLoss || cpLoss < 50) return { text: "Small inaccuracy", color: "text-yellow-400" };
  if (cpLoss < 100) return { text: "Inaccuracy", color: "text-yellow-500" };
  if (cpLoss < 200) return { text: "Mistake (~1 pawn)", color: "text-orange-400" };
  if (cpLoss < 300) return { text: "Serious mistake (~2 pawns)", color: "text-orange-500" };
  if (cpLoss < 500) return { text: "Blunder (~3+ pawns)", color: "text-red-400" };
  if (cpLoss < 900) return { text: "Major blunder (piece lost)", color: "text-red-500" };
  return { text: "Game-losing blunder", color: "text-red-600" };
};

/**
 * Interactive Training Page
 * 
 * Phase 1: Solve puzzles from your own mistakes
 * - Show position from user's game
 * - Let user make a move
 * - Give feedback + teach the principle
 */
const Training = ({ user }) => {
  const navigate = useNavigate();
  
  // Core state
  const [loading, setLoading] = useState(true);
  const [puzzles, setPuzzles] = useState([]);
  const [currentPuzzleIndex, setCurrentPuzzleIndex] = useState(0);
  const [progress, setProgress] = useState(null);
  const [weaknesses, setWeaknesses] = useState(null);
  
  // Puzzle solving state
  const [puzzleState, setPuzzleState] = useState("thinking"); // thinking | correct | incorrect | revealed
  const [userAnswer, setUserAnswer] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const [validating, setValidating] = useState(false);
  
  // Board state
  const [boardFen, setBoardFen] = useState(START_FEN);
  const [boardOrientation, setBoardOrientation] = useState("white");
  
  // Stats
  const [sessionStats, setSessionStats] = useState({
    attempted: 0,
    correct: 0,
    streak: 0
  });

  // Current puzzle
  const currentPuzzle = puzzles[currentPuzzleIndex] || null;
  const hasMorePuzzles = currentPuzzleIndex < puzzles.length - 1;
  
  // Fetch puzzles and progress on mount
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        
        const [puzzlesRes, progressRes, weaknessRes] = await Promise.all([
          fetch(`${API}/training/puzzles?limit=10`, { credentials: "include" }),
          fetch(`${API}/training/progress`, { credentials: "include" }),
          fetch(`${API}/training/weakness-patterns`, { credentials: "include" })
        ]);
        
        if (puzzlesRes.ok) {
          const data = await puzzlesRes.json();
          setPuzzles(data.puzzles || []);
        }
        
        if (progressRes.ok) {
          const data = await progressRes.json();
          setProgress(data);
        }
        
        if (weaknessRes.ok) {
          const data = await weaknessRes.json();
          setWeaknesses(data);
        }
      } catch (err) {
        console.error("Error fetching training data:", err);
        toast.error("Failed to load training data");
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
  }, []);
  
  // Update board when puzzle changes
  useEffect(() => {
    if (currentPuzzle) {
      setBoardFen(currentPuzzle.fen);
      setBoardOrientation(currentPuzzle.user_color || "white");
      setPuzzleState("thinking");
      setUserAnswer(null);
      setFeedback(null);
    }
  }, [currentPuzzle]);
  
  // Handle user making a move on the board
  const handleMove = useCallback(async (move) => {
    if (puzzleState !== "thinking" || !currentPuzzle) return;
    
    setUserAnswer(move);
    setValidating(true);
    
    try {
      const res = await fetch(`${API}/training/puzzle/validate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          puzzle_id: currentPuzzle.id,
          user_answer: move,
          correct_move: currentPuzzle.correct_move,
          fen: currentPuzzle.fen
        })
      });
      
      if (res.ok) {
        const result = await res.json();
        setFeedback(result);
        
        if (result.correct) {
          setPuzzleState("correct");
          setSessionStats(prev => ({
            attempted: prev.attempted + 1,
            correct: prev.correct + 1,
            streak: prev.streak + 1
          }));
          toast.success("Correct! Well done!");
        } else {
          setPuzzleState("incorrect");
          setSessionStats(prev => ({
            attempted: prev.attempted + 1,
            correct: prev.correct,
            streak: 0
          }));
        }
      }
    } catch (err) {
      console.error("Error validating answer:", err);
      toast.error("Failed to check answer");
    } finally {
      setValidating(false);
    }
  }, [puzzleState, currentPuzzle]);
  
  // Show the solution
  const revealSolution = () => {
    setPuzzleState("revealed");
    setSessionStats(prev => ({
      ...prev,
      attempted: prev.attempted + (puzzleState === "thinking" ? 1 : 0),
      streak: 0
    }));
  };
  
  // Move to next puzzle
  const nextPuzzle = () => {
    if (hasMorePuzzles) {
      setCurrentPuzzleIndex(prev => prev + 1);
    } else {
      toast.success("Training session complete!");
    }
  };
  
  // Reset current puzzle
  const resetPuzzle = () => {
    if (currentPuzzle) {
      setBoardFen(currentPuzzle.fen);
      setPuzzleState("thinking");
      setUserAnswer(null);
      setFeedback(null);
    }
  };
  
  // Get difficulty badge color
  const getDifficultyColor = (difficulty) => {
    switch (difficulty) {
      case "easy": return "bg-green-500/20 text-green-400";
      case "medium": return "bg-yellow-500/20 text-yellow-400";
      case "hard": return "bg-red-500/20 text-red-400";
      default: return "bg-gray-500/20 text-gray-400";
    }
  };

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <div className="text-center">
            <Loader2 className="w-8 h-8 animate-spin text-amber-500 mx-auto mb-4" />
            <p className="text-gray-400">Loading your training session...</p>
          </div>
        </div>
      </Layout>
    );
  }

  if (puzzles.length === 0) {
    return (
      <Layout user={user}>
        <div className="max-w-2xl mx-auto px-4 py-8">
          <Card className="bg-gray-900/50 border-gray-800">
            <CardContent className="p-8 text-center">
              <BookOpen className="w-16 h-16 text-gray-600 mx-auto mb-4" />
              <h2 className="text-xl font-semibold text-white mb-2">No Training Puzzles Yet</h2>
              <p className="text-gray-400 mb-6">
                We need to analyze some of your games first to create personalized training puzzles.
              </p>
              <Button 
                onClick={() => navigate("/games")}
                className="bg-amber-600 hover:bg-amber-700"
              >
                Import Games
              </Button>
            </CardContent>
          </Card>
        </div>
      </Layout>
    );
  }

  return (
    <Layout user={user}>
      <div className="max-w-6xl mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <Target className="w-6 h-6 text-amber-500" />
              Training
            </h1>
            <p className="text-gray-400 text-sm mt-1">
              Learn from your mistakes • Puzzle {currentPuzzleIndex + 1} of {puzzles.length}
            </p>
          </div>
          
          {/* Session Stats */}
          <div className="flex items-center gap-4">
            {sessionStats.streak >= 3 && (
              <Badge className="bg-orange-500/20 text-orange-400 border-orange-500/30">
                <Flame className="w-3 h-3 mr-1" />
                {sessionStats.streak} streak!
              </Badge>
            )}
            <div className="text-right">
              <div className="text-white font-medium">
                {sessionStats.correct}/{sessionStats.attempted}
              </div>
              <div className="text-xs text-gray-500">correct</div>
            </div>
          </div>
        </div>

        {/* Progress Bar */}
        <Progress 
          value={(currentPuzzleIndex / puzzles.length) * 100} 
          className="h-2 mb-6 bg-gray-800"
        />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Puzzle Area */}
          <div className="lg:col-span-2">
            <Card className="bg-gray-900/50 border-gray-800">
              <CardContent className="p-4">
                {/* Puzzle Context */}
                {currentPuzzle && (
                  <div className="mb-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Badge className={getDifficultyColor(currentPuzzle.difficulty)}>
                        {currentPuzzle.difficulty}
                      </Badge>
                      <span className="text-sm text-gray-400">
                        vs {currentPuzzle.opponent} • Move {currentPuzzle.move_number}
                      </span>
                    </div>
                    <Badge variant="outline" className="text-gray-400 border-gray-700">
                      {currentPuzzle.user_color === "white" ? "White" : "Black"} to move
                    </Badge>
                  </div>
                )}

                {/* Chess Board */}
                <div className="aspect-square max-w-lg mx-auto">
                  <CoachBoard
                    fen={boardFen}
                    orientation={boardOrientation}
                    onMove={puzzleState === "thinking" ? handleMove : null}
                    interactive={puzzleState === "thinking"}
                    highlightSquares={
                      puzzleState !== "thinking" && currentPuzzle
                        ? [currentPuzzle.correct_move.slice(-2)]
                        : []
                    }
                  />
                </div>

                {/* Puzzle Status */}
                <div className="mt-4">
                  <AnimatePresence mode="wait">
                    {puzzleState === "thinking" && (
                      <motion.div
                        key="thinking"
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                        className="text-center"
                      >
                        <p className="text-gray-300 mb-4">
                          <Brain className="w-5 h-5 inline mr-2 text-amber-500" />
                          Find the best move. Take your time.
                        </p>
                        <div className="flex justify-center gap-3">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={revealSolution}
                            className="border-gray-700 text-gray-400 hover:text-white"
                          >
                            <HelpCircle className="w-4 h-4 mr-1" />
                            Show Solution
                          </Button>
                        </div>
                      </motion.div>
                    )}

                    {puzzleState === "correct" && feedback && (
                      <motion.div
                        key="correct"
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0 }}
                        className="bg-green-500/10 border border-green-500/30 rounded-lg p-4"
                      >
                        <div className="flex items-start gap-3">
                          <CheckCircle2 className="w-6 h-6 text-green-500 flex-shrink-0 mt-0.5" />
                          <div>
                            <h3 className="text-green-400 font-semibold mb-1">
                              {feedback.message}
                            </h3>
                            {feedback.explanation && (
                              <p className="text-gray-300 text-sm mb-3">
                                {feedback.explanation}
                              </p>
                            )}
                            {feedback.principle && (
                              <div className="bg-gray-800/50 rounded p-3 mt-2">
                                <p className="text-xs text-amber-500 font-medium mb-1">
                                  <Lightbulb className="w-3 h-3 inline mr-1" />
                                  PRINCIPLE
                                </p>
                                <p className="text-sm text-gray-300">{feedback.principle}</p>
                              </div>
                            )}
                          </div>
                        </div>
                        <div className="flex justify-end mt-4">
                          <Button
                            onClick={nextPuzzle}
                            className="bg-green-600 hover:bg-green-700"
                            disabled={!hasMorePuzzles}
                          >
                            {hasMorePuzzles ? (
                              <>
                                Next Puzzle
                                <ChevronRight className="w-4 h-4 ml-1" />
                              </>
                            ) : (
                              <>
                                <Trophy className="w-4 h-4 mr-1" />
                                Complete!
                              </>
                            )}
                          </Button>
                        </div>
                      </motion.div>
                    )}

                    {puzzleState === "incorrect" && feedback && (
                      <motion.div
                        key="incorrect"
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0 }}
                        className="bg-red-500/10 border border-red-500/30 rounded-lg p-4"
                      >
                        <div className="flex items-start gap-3">
                          <XCircle className="w-6 h-6 text-red-500 flex-shrink-0 mt-0.5" />
                          <div className="flex-1">
                            <h3 className="text-red-400 font-semibold mb-1">
                              {feedback.message}
                            </h3>
                            <div className="text-sm space-y-2 mb-3">
                              <p className="text-gray-400">
                                You played: <span className="text-red-400 font-mono">{feedback.user_move}</span>
                              </p>
                              <p className="text-gray-400">
                                Best move: <span className="text-green-400 font-mono">{feedback.correct_move}</span>
                              </p>
                              {feedback.why_correct && (
                                <p className="text-gray-300">{feedback.why_correct}</p>
                              )}
                            </div>
                            {feedback.principle && (
                              <div className="bg-gray-800/50 rounded p-3">
                                <p className="text-xs text-amber-500 font-medium mb-1">
                                  <Lightbulb className="w-3 h-3 inline mr-1" />
                                  REMEMBER THIS
                                </p>
                                <p className="text-sm text-gray-300">{feedback.principle}</p>
                              </div>
                            )}
                          </div>
                        </div>
                        <div className="flex justify-between mt-4">
                          <Button
                            variant="outline"
                            onClick={resetPuzzle}
                            className="border-gray-700"
                          >
                            <RotateCcw className="w-4 h-4 mr-1" />
                            Try Again
                          </Button>
                          <Button
                            onClick={nextPuzzle}
                            disabled={!hasMorePuzzles}
                          >
                            {hasMorePuzzles ? "Next Puzzle" : "Complete"}
                            <ChevronRight className="w-4 h-4 ml-1" />
                          </Button>
                        </div>
                      </motion.div>
                    )}

                    {puzzleState === "revealed" && currentPuzzle && (
                      <motion.div
                        key="revealed"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="bg-gray-800/50 border border-gray-700 rounded-lg p-4"
                      >
                        <div className="text-center mb-3">
                          <p className="text-gray-400 mb-2">The best move was:</p>
                          <p className="text-2xl font-mono text-amber-500">{currentPuzzle.correct_move}</p>
                        </div>
                        {currentPuzzle.critical_detail && (
                          <p className="text-gray-300 text-sm text-center mb-3">
                            {currentPuzzle.critical_detail}
                          </p>
                        )}
                        {currentPuzzle.principle && (
                          <div className="bg-gray-900/50 rounded p-3 mb-4">
                            <p className="text-xs text-amber-500 font-medium mb-1">
                              <Lightbulb className="w-3 h-3 inline mr-1" />
                              PRINCIPLE: {currentPuzzle.principle.name}
                            </p>
                            <p className="text-sm text-gray-300">{currentPuzzle.principle.quick_tip}</p>
                          </div>
                        )}
                        <div className="flex justify-center">
                          <Button
                            onClick={nextPuzzle}
                            disabled={!hasMorePuzzles}
                          >
                            {hasMorePuzzles ? "Next Puzzle" : "Complete"}
                            <ChevronRight className="w-4 h-4 ml-1" />
                          </Button>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>

                  {validating && (
                    <div className="flex items-center justify-center py-4">
                      <Loader2 className="w-5 h-5 animate-spin text-amber-500 mr-2" />
                      <span className="text-gray-400">Checking...</span>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Side Panel */}
          <div className="space-y-4">
            {/* Current Puzzle Info */}
            {currentPuzzle && (
              <Card className="bg-gray-900/50 border-gray-800">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-400">
                    This Position
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div>
                      <p className="text-xs text-gray-500 mb-1">From your game against</p>
                      <p className="text-white font-medium">{currentPuzzle.opponent}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 mb-1">You played</p>
                      <p className="text-red-400 font-mono">{currentPuzzle.user_move}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 mb-1">Severity</p>
                      <p className={formatEvaluation(currentPuzzle.cp_loss).color}>
                        {formatEvaluation(currentPuzzle.cp_loss).text}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Weakness Pattern */}
            {weaknesses && weaknesses.weakest_phase && (
              <Card className="bg-gray-900/50 border-gray-800">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-400 flex items-center gap-2">
                    <Zap className="w-4 h-4 text-amber-500" />
                    Your Focus Area
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <Badge className="bg-amber-500/20 text-amber-400 border-amber-500/30 mb-3">
                    {weaknesses.weakest_phase.charAt(0).toUpperCase() + weaknesses.weakest_phase.slice(1)}
                  </Badge>
                  <p className="text-sm text-gray-400">
                    {weaknesses.recommendation}
                  </p>
                </CardContent>
              </Card>
            )}

            {/* Progress */}
            {progress && (
              <Card className="bg-gray-900/50 border-gray-800">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-400">
                    Training Progress
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-4 text-center">
                    <div>
                      <p className="text-2xl font-bold text-white">{progress.puzzles_solved}</p>
                      <p className="text-xs text-gray-500">Solved</p>
                    </div>
                    <div>
                      <p className="text-2xl font-bold text-amber-500">{progress.accuracy}%</p>
                      <p className="text-xs text-gray-500">Accuracy</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Quick Actions */}
            <Card className="bg-gray-900/50 border-gray-800">
              <CardContent className="p-4">
                <Button
                  variant="outline"
                  className="w-full border-gray-700 text-gray-400 hover:text-white"
                  onClick={() => navigate("/reflect")}
                >
                  <BookOpen className="w-4 h-4 mr-2" />
                  Go to Reflections
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default Training;
