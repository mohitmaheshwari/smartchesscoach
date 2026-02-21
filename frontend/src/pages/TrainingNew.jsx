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
  AlertTriangle,
  Users,
  Share2,
  Star,
  Clock,
  Filter,
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
  
  // Tab state
  const [activeTab, setActiveTab] = useState("puzzles");
  
  // Core state
  const [loading, setLoading] = useState(true);
  const [puzzles, setPuzzles] = useState([]);
  const [currentPuzzleIndex, setCurrentPuzzleIndex] = useState(0);
  const [progress, setProgress] = useState(null);
  const [weaknesses, setWeaknesses] = useState(null);
  
  // Puzzle source filter: "my_games" | "community" | "all"
  const [puzzleSource, setPuzzleSource] = useState("all");
  
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
        
        // Fetch user's puzzles, community puzzles, progress, and weaknesses
        const [puzzlesRes, communityRes, progressRes, weaknessRes] = await Promise.all([
          fetch(`${API}/training/puzzles?limit=10`, { credentials: "include" }),
          fetch(`${API}/community/puzzles?limit=10`, { credentials: "include" }),
          fetch(`${API}/training/progress`, { credentials: "include" }),
          fetch(`${API}/training/weakness-patterns`, { credentials: "include" })
        ]);
        
        let allPuzzles = [];
        
        // User's own puzzles (from their games)
        if (puzzlesRes.ok) {
          const data = await puzzlesRes.json();
          const userPuzzles = (data.puzzles || []).map(p => ({
            ...p,
            source: "my_game",
            source_label: `vs ${p.opponent_name || "Unknown"}`,
            source_detail: p.game_date ? new Date(p.game_date).toLocaleDateString() : null
          }));
          allPuzzles = [...allPuzzles, ...userPuzzles];
        }
        
        // Community puzzles
        if (communityRes.ok) {
          const data = await communityRes.json();
          const communityPuzzles = (data.puzzles || []).map(p => ({
            puzzle_id: p.puzzle_id,
            fen: p.fen,
            correct_move: p.best_move_san,
            best_move_san: p.best_move_san,
            user_color: p.user_color || "white",
            issue_type: p.issue_type,
            difficulty: p.difficulty,
            move_number: p.move_number,
            source: "community",
            source_label: p.opening_name || "Community Puzzle",
            source_detail: `${p.attempts} attempts • ${p.solve_rate}% solved`,
            community_puzzle_id: p.puzzle_id
          }));
          allPuzzles = [...allPuzzles, ...communityPuzzles];
        }
        
        // Shuffle to mix user and community puzzles
        allPuzzles = allPuzzles.sort(() => Math.random() - 0.5);
        
        setPuzzles(allPuzzles);
        
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
  
  // Filter puzzles based on source selection
  const filteredPuzzles = puzzles.filter(p => {
    if (puzzleSource === "all") return true;
    if (puzzleSource === "my_games") return p.source === "my_game";
    if (puzzleSource === "community") return p.source === "community";
    return true;
  });
  
  // Get current puzzle from filtered list
  const displayPuzzle = filteredPuzzles[currentPuzzleIndex] || null;
  const hasMoreFilteredPuzzles = currentPuzzleIndex < filteredPuzzles.length - 1;
  
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
              Improve your chess with personalized training
            </p>
          </div>
          
          {/* Session Stats - only show for puzzles */}
          {activeTab === "puzzles" && (
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
          )}
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="bg-gray-900/50 border border-gray-800">
            <TabsTrigger 
              value="puzzles" 
              className="data-[state=active]:bg-primary/20 gap-2"
              data-testid="tab-puzzles"
            >
              <Brain className="w-4 h-4" />
              Puzzles
            </TabsTrigger>
            <TabsTrigger 
              value="openings" 
              className="data-[state=active]:bg-primary/20 gap-2"
              data-testid="tab-openings"
            >
              <GraduationCap className="w-4 h-4" />
              Opening Trainer
            </TabsTrigger>
            <TabsTrigger 
              value="community" 
              className="data-[state=active]:bg-primary/20 gap-2"
              data-testid="tab-community"
            >
              <Users className="w-4 h-4" />
              Community
            </TabsTrigger>
          </TabsList>

          {/* Puzzles Tab */}
          <TabsContent value="puzzles" className="mt-0">
            {/* Progress Bar */}
            <Progress 
              value={(currentPuzzleIndex / puzzles.length) * 100} 
              className="h-2 mb-6 bg-gray-800"
            />
            <p className="text-xs text-muted-foreground mb-4">
              Puzzle {currentPuzzleIndex + 1} of {puzzles.length}
            </p>

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
                    <Badge 
                      variant="outline" 
                      className={`${
                        currentPuzzle.user_color === "white" 
                          ? "text-amber-400 border-amber-400/50" 
                          : "text-slate-300 border-slate-400/50"
                      }`}
                    >
                      Playing as {currentPuzzle.user_color === "white" ? "White" : "Black"}
                    </Badge>
                  </div>
                )}

                {/* Chess Board */}
                <div className="aspect-square max-w-lg mx-auto">
                  <CoachBoard
                    position={boardFen}
                    userColor={boardOrientation}
                    onUserMove={puzzleState === "thinking" ? (moveData) => handleMove(moveData.san) : null}
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

            {/* Puzzle-Specific Issue */}
            {currentPuzzle?.principle && (
              <Card className="bg-orange-500/10 border-orange-500/30">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-orange-400 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4" />
                    What Went Wrong
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <Badge className="bg-orange-500/20 text-orange-400 border-orange-500/30 mb-3">
                    {currentPuzzle.principle.name || currentPuzzle.issue_type?.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                  </Badge>
                  {currentPuzzle.critical_detail && (
                    <p className="text-sm text-orange-300 mb-2">
                      {currentPuzzle.critical_detail}
                    </p>
                  )}
                  <p className="text-sm text-gray-400">
                    {currentPuzzle.principle.quick_tip || currentPuzzle.principle.principle}
                  </p>
                </CardContent>
              </Card>
            )}

            {/* Weakness Pattern - only show if no puzzle-specific info */}
            {!currentPuzzle?.principle && weaknesses && weaknesses.weakest_phase && (
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
          </TabsContent>

          {/* Openings Tab */}
          <TabsContent value="openings" className="mt-0">
            <OpeningTrainer />
          </TabsContent>

          {/* Community Tab */}
          <TabsContent value="community" className="mt-0">
            <CommunityPuzzles />
          </TabsContent>
        </Tabs>
      </div>
    </Layout>
  );
};

// Community Puzzles Component
const CommunityPuzzles = () => {
  const [puzzles, setPuzzles] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedPuzzle, setSelectedPuzzle] = useState(null);
  const [puzzleState, setPuzzleState] = useState("idle"); // idle | thinking | correct | incorrect
  const [sortBy, setSortBy] = useState("newest");
  const [difficulty, setDifficulty] = useState(null);

  useEffect(() => {
    fetchCommunityData();
  }, [sortBy, difficulty]);

  const fetchCommunityData = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("sort_by", sortBy);
      if (difficulty) params.set("difficulty", difficulty);

      const [puzzlesRes, statsRes] = await Promise.all([
        fetch(`${API}/community/puzzles?${params}`, { credentials: "include" }),
        fetch(`${API}/community/stats`, { credentials: "include" })
      ]);

      if (puzzlesRes.ok) {
        const data = await puzzlesRes.json();
        setPuzzles(data.puzzles || []);
      }

      if (statsRes.ok) {
        const data = await statsRes.json();
        setStats(data);
      }
    } catch (err) {
      console.error("Error fetching community data:", err);
      toast.error("Failed to load community puzzles");
    } finally {
      setLoading(false);
    }
  };

  const handleSelectPuzzle = (puzzle) => {
    setSelectedPuzzle(puzzle);
    setPuzzleState("thinking");
  };

  const handleMove = async (moveData) => {
    if (!selectedPuzzle || puzzleState !== "thinking") return;

    const moveSan = moveData.san || moveData;

    try {
      const res = await fetch(`${API}/community/puzzles/${selectedPuzzle.puzzle_id}/attempt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ user_move: moveSan })
      });

      if (res.ok) {
        const result = await res.json();
        if (result.correct) {
          setPuzzleState("correct");
          toast.success("Correct!");
          // Refresh puzzles to update solve status
          fetchCommunityData();
        } else {
          setPuzzleState("incorrect");
          toast.error(result.message);
        }
      }
    } catch (err) {
      console.error("Error submitting answer:", err);
      toast.error("Failed to submit answer");
    }
  };

  const handleNextPuzzle = () => {
    const currentIndex = puzzles.findIndex(p => p.puzzle_id === selectedPuzzle?.puzzle_id);
    const nextPuzzle = puzzles[currentIndex + 1] || puzzles[0];
    handleSelectPuzzle(nextPuzzle);
  };

  const handleRatePuzzle = async (rating) => {
    if (!selectedPuzzle) return;

    try {
      const res = await fetch(`${API}/community/puzzles/${selectedPuzzle.puzzle_id}/rate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ rating })
      });

      if (res.ok) {
        toast.success("Thanks for rating!");
        fetchCommunityData();
      }
    } catch (err) {
      console.error("Error rating puzzle:", err);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Left: Puzzle List */}
      <div className="lg:col-span-1 space-y-4">
        {/* Stats Card */}
        {stats && (
          <Card className="bg-gradient-to-br from-primary/20 to-primary/5 border-primary/30">
            <CardContent className="py-4">
              <div className="flex items-center gap-2 mb-3">
                <Users className="w-5 h-5 text-primary" />
                <span className="font-medium">Community Stats</span>
              </div>
              <div className="grid grid-cols-2 gap-3 text-center">
                <div>
                  <p className="text-2xl font-bold text-primary">{stats.total_puzzles}</p>
                  <p className="text-xs text-muted-foreground">Puzzles</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-green-500">{stats.overall_solve_rate}%</p>
                  <p className="text-xs text-muted-foreground">Solve Rate</p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Filters */}
        <Card className="bg-muted/30">
          <CardContent className="py-3">
            <div className="flex items-center gap-2 mb-2">
              <Filter className="w-4 h-4 text-muted-foreground" />
              <span className="text-sm font-medium">Filters</span>
            </div>
            <div className="flex flex-wrap gap-2">
              <select 
                value={sortBy} 
                onChange={(e) => setSortBy(e.target.value)}
                className="text-sm bg-muted/50 border border-muted rounded px-2 py-1"
              >
                <option value="newest">Newest</option>
                <option value="most_solved">Most Solved</option>
                <option value="hardest">Hardest</option>
                <option value="easiest">Easiest</option>
                <option value="highest_rated">Highest Rated</option>
              </select>
              <select 
                value={difficulty || ""} 
                onChange={(e) => setDifficulty(e.target.value || null)}
                className="text-sm bg-muted/50 border border-muted rounded px-2 py-1"
              >
                <option value="">All Difficulties</option>
                <option value="beginner">Beginner</option>
                <option value="intermediate">Intermediate</option>
                <option value="advanced">Advanced</option>
              </select>
            </div>
          </CardContent>
        </Card>

        {/* Puzzle List */}
        <div className="space-y-2 max-h-[500px] overflow-y-auto">
          {puzzles.length === 0 ? (
            <Card className="bg-muted/30">
              <CardContent className="py-8 text-center">
                <Users className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                <h4 className="font-medium mb-2">No Community Puzzles Yet</h4>
                <p className="text-sm text-muted-foreground">
                  Be the first to share a puzzle from your games!
                </p>
              </CardContent>
            </Card>
          ) : (
            puzzles.map((puzzle) => (
              <Card 
                key={puzzle.puzzle_id}
                className={`cursor-pointer transition-all hover:bg-muted/50 ${
                  selectedPuzzle?.puzzle_id === puzzle.puzzle_id ? "bg-primary/20 border-primary/50" : "bg-muted/30"
                }`}
                onClick={() => handleSelectPuzzle(puzzle)}
                data-testid={`community-puzzle-${puzzle.puzzle_id}`}
              >
                <CardContent className="py-3">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className={`text-xs ${
                        puzzle.difficulty === "beginner" ? "text-green-400 border-green-400/30" :
                        puzzle.difficulty === "intermediate" ? "text-amber-400 border-amber-400/30" :
                        "text-red-400 border-red-400/30"
                      }`}>
                        {puzzle.difficulty}
                      </Badge>
                      <Badge variant="outline" className="text-xs">
                        {puzzle.issue_type?.replace(/_/g, " ")}
                      </Badge>
                    </div>
                    {puzzle.user_solved && (
                      <CheckCircle2 className="w-4 h-4 text-green-500" />
                    )}
                  </div>
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>{puzzle.attempts} attempts • {puzzle.solve_rate}% solved</span>
                    {puzzle.avg_rating > 0 && (
                      <span className="flex items-center gap-1">
                        <Star className="w-3 h-3 text-amber-400 fill-amber-400" />
                        {puzzle.avg_rating}
                      </span>
                    )}
                  </div>
                  {puzzle.opening_name && (
                    <p className="text-xs text-muted-foreground mt-1 truncate">
                      {puzzle.opening_name}
                    </p>
                  )}
                </CardContent>
              </Card>
            ))
          )}
        </div>
      </div>

      {/* Center: Board */}
      <div className="lg:col-span-1">
        <Card className="bg-muted/30 border-muted">
          <CardContent className="py-4">
            {selectedPuzzle ? (
              <>
                <div className="flex items-center justify-between mb-3">
                  <Badge className={`${
                    puzzleState === "thinking" ? "bg-amber-500/20 text-amber-400" :
                    puzzleState === "correct" ? "bg-green-500/20 text-green-400" :
                    puzzleState === "incorrect" ? "bg-red-500/20 text-red-400" :
                    "bg-primary/20 text-primary"
                  }`}>
                    {puzzleState === "thinking" ? "Your Turn" :
                     puzzleState === "correct" ? "Correct!" :
                     puzzleState === "incorrect" ? "Incorrect" :
                     "Ready"}
                  </Badge>
                  <Badge variant="outline" className="text-xs">
                    Playing as {selectedPuzzle.user_color}
                  </Badge>
                </div>
                <div className="aspect-square">
                  <CoachBoard
                    position={selectedPuzzle.fen}
                    userColor={selectedPuzzle.user_color}
                    onUserMove={puzzleState === "thinking" ? (moveData) => handleMove(moveData.san) : null}
                    interactive={puzzleState === "thinking"}
                    highlightSquares={
                      puzzleState !== "thinking" && selectedPuzzle
                        ? [selectedPuzzle.best_move_san.slice(-2)]
                        : []
                    }
                  />
                </div>
                <p className="text-center text-sm text-muted-foreground mt-3">
                  Find the best move for {selectedPuzzle.user_color}
                </p>
              </>
            ) : (
              <div className="aspect-square flex items-center justify-center">
                <div className="text-center">
                  <Target className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                  <p className="text-muted-foreground">Select a puzzle to start</p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Right: Result Panel */}
      <div className="lg:col-span-1 space-y-4">
        {selectedPuzzle && (puzzleState === "correct" || puzzleState === "incorrect") && (
          <Card className={`${
            puzzleState === "correct" ? "bg-green-500/10 border-green-500/30" : "bg-red-500/10 border-red-500/30"
          }`}>
            <CardContent className="py-4">
              <div className="flex items-center gap-2 mb-3">
                {puzzleState === "correct" ? (
                  <CheckCircle2 className="w-6 h-6 text-green-500" />
                ) : (
                  <XCircle className="w-6 h-6 text-red-500" />
                )}
                <span className={`font-medium ${
                  puzzleState === "correct" ? "text-green-400" : "text-red-400"
                }`}>
                  {puzzleState === "correct" ? "Correct!" : "Incorrect"}
                </span>
              </div>
              
              <p className="text-sm text-muted-foreground mb-4">
                {puzzleState === "correct" 
                  ? "Great job! You found the best move."
                  : `The best move was ${selectedPuzzle.best_move_san}`}
              </p>

              <div className="flex gap-2">
                <Button 
                  variant="outline" 
                  size="sm"
                  className="flex-1"
                  onClick={() => handleSelectPuzzle(selectedPuzzle)}
                >
                  <RotateCcw className="w-4 h-4 mr-1" />
                  Retry
                </Button>
                <Button 
                  variant="default" 
                  size="sm"
                  className="flex-1"
                  onClick={handleNextPuzzle}
                >
                  Next
                  <ChevronRight className="w-4 h-4 ml-1" />
                </Button>
              </div>

              {/* Rating */}
              <div className="mt-4 pt-4 border-t border-muted">
                <p className="text-xs text-muted-foreground mb-2">Rate this puzzle:</p>
                <div className="flex gap-1">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <button
                      key={star}
                      onClick={() => handleRatePuzzle(star)}
                      className="p-1 hover:scale-110 transition-transform"
                      data-testid={`rate-${star}`}
                    >
                      <Star className="w-5 h-5 text-amber-400 hover:fill-amber-400" />
                    </button>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Puzzle Info */}
        {selectedPuzzle && (
          <Card className="bg-muted/30">
            <CardContent className="py-4">
              <h4 className="font-medium mb-3">Puzzle Info</h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Difficulty:</span>
                  <span className="capitalize">{selectedPuzzle.difficulty}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Theme:</span>
                  <span className="capitalize">{selectedPuzzle.issue_type?.replace(/_/g, " ")}</span>
                </div>
                {selectedPuzzle.opening_name && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Opening:</span>
                    <span>{selectedPuzzle.opening_name}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Solve Rate:</span>
                  <span>{selectedPuzzle.solve_rate}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Attempts:</span>
                  <span>{selectedPuzzle.attempts}</span>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default Training;
