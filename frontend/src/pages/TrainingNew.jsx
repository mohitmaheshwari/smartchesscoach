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
  TrendingUp,
  TrendingDown,
  Award,
  Crown,
  Sparkles,
  ChevronUp,
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
  
  // Puzzle progression state
  const [puzzleProgress, setPuzzleProgress] = useState(null);
  const [showLevelUp, setShowLevelUp] = useState(false);
  const [levelUpData, setLevelUpData] = useState(null);
  const [newAchievements, setNewAchievements] = useState([]);
  
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
        
        // Fetch user's puzzles, community puzzles, progress, weaknesses, and puzzle progression
        const [puzzlesRes, communityRes, progressRes, weaknessRes, puzzleProgressRes] = await Promise.all([
          fetch(`${API}/training/puzzles?limit=10`, { credentials: "include" }),
          fetch(`${API}/community/puzzles?limit=10`, { credentials: "include" }),
          fetch(`${API}/training/progress`, { credentials: "include" }),
          fetch(`${API}/training/weakness-patterns`, { credentials: "include" }),
          fetch(`${API}/training/puzzle-progress`, { credentials: "include" })
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
        
        if (puzzleProgressRes.ok) {
          const data = await puzzleProgressRes.json();
          setPuzzleProgress(data);
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
  
  // Refresh puzzle progress
  const refreshPuzzleProgress = async () => {
    try {
      const res = await fetch(`${API}/training/puzzle-progress`, { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        setPuzzleProgress(data);
      }
    } catch (err) {
      console.error("Error refreshing puzzle progress:", err);
    }
  };
  
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
    if (displayPuzzle && displayPuzzle.fen) {
      setBoardFen(displayPuzzle.fen);
      setBoardOrientation(displayPuzzle.user_color || "white");
      setPuzzleState("thinking");
      setUserAnswer(null);
      setFeedback(null);
    } else {
      // Reset to starting position if no puzzle
      setBoardFen(START_FEN);
      setBoardOrientation("white");
    }
  }, [displayPuzzle]);
  
  // Reset puzzle index when filter changes
  useEffect(() => {
    setCurrentPuzzleIndex(0);
  }, [puzzleSource]);
  
  // Handle user making a move on the board
  const handleMove = useCallback(async (move) => {
    if (puzzleState !== "thinking" || !displayPuzzle) return;
    
    setUserAnswer(move);
    setValidating(true);
    
    try {
      let res;
      
      // Use different endpoint for community puzzles
      if (displayPuzzle.source === "community" && displayPuzzle.community_puzzle_id) {
        res = await fetch(`${API}/community/puzzles/${displayPuzzle.community_puzzle_id}/attempt`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ user_move: move })
        });
      } else {
        // User's own puzzle - use the smart validation
        res = await fetch(`${API}/training/puzzle/validate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            puzzle_id: displayPuzzle.id || displayPuzzle.puzzle_id,
            user_answer: move,
            correct_move: displayPuzzle.correct_move || displayPuzzle.best_move_san,
            fen: displayPuzzle.fen
          })
        });
      }
      
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
  }, [puzzleState, displayPuzzle]);
  
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
    if (hasMoreFilteredPuzzles) {
      setCurrentPuzzleIndex(prev => prev + 1);
    } else {
      toast.success("Training session complete!");
    }
  };
  
  // Reset current puzzle
  const resetPuzzle = () => {
    if (displayPuzzle) {
      setBoardFen(displayPuzzle.fen);
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
          </TabsList>

          {/* Puzzles Tab */}
          <TabsContent value="puzzles" className="mt-0">
            {/* Source Filter */}
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Show:</span>
                <select 
                  value={puzzleSource} 
                  onChange={(e) => setPuzzleSource(e.target.value)}
                  className="text-sm bg-muted/50 border border-muted rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary"
                  data-testid="puzzle-source-filter"
                >
                  <option value="all">All Puzzles</option>
                  <option value="my_games">My Games Only</option>
                  <option value="community">Community Puzzles</option>
                </select>
              </div>
              <p className="text-xs text-muted-foreground">
                Puzzle {currentPuzzleIndex + 1} of {filteredPuzzles.length}
              </p>
            </div>
            
            {/* Progress Bar */}
            <Progress 
              value={filteredPuzzles.length > 0 ? ((currentPuzzleIndex + 1) / filteredPuzzles.length) * 100 : 0} 
              className="h-2 mb-6 bg-gray-800"
            />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Puzzle Area */}
          <div className="lg:col-span-2">
            <Card className="bg-gray-900/50 border-gray-800">
              <CardContent className="p-4">
                {/* No puzzles state */}
                {!loading && filteredPuzzles.length === 0 && (
                  <div className="text-center py-12">
                    <Brain className="w-16 h-16 text-gray-600 mx-auto mb-4" />
                    <h3 className="text-lg font-medium text-gray-400 mb-2">No Puzzles Available</h3>
                    <p className="text-sm text-gray-500 mb-4">
                      {puzzleSource === "my_games" 
                        ? "Import some games to generate puzzles from your mistakes"
                        : puzzleSource === "community"
                        ? "No community puzzles available yet"
                        : "No puzzles available. Import games or check back later!"}
                    </p>
                    {puzzleSource !== "all" && (
                      <Button 
                        variant="outline" 
                        onClick={() => setPuzzleSource("all")}
                        className="border-gray-700"
                      >
                        Show All Puzzles
                      </Button>
                    )}
                  </div>
                )}

                {/* Puzzle Context */}
                {displayPuzzle && (
                  <div className="mb-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Badge className={getDifficultyColor(displayPuzzle.difficulty)}>
                        {displayPuzzle.difficulty}
                      </Badge>
                      {/* Source indicator */}
                      <div className="flex items-center gap-2">
                        {displayPuzzle.source === "my_game" ? (
                          <Badge variant="outline" className="text-green-400 border-green-400/30">
                            <Target className="w-3 h-3 mr-1" />
                            Your Game
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="text-blue-400 border-blue-400/30">
                            <Users className="w-3 h-3 mr-1" />
                            Community
                          </Badge>
                        )}
                        <span className="text-sm text-gray-400">
                          {displayPuzzle.source_label}
                          {displayPuzzle.move_number ? ` • Move ${displayPuzzle.move_number}` : ""}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {displayPuzzle.source_detail && (
                        <span className="text-xs text-gray-500">
                          {displayPuzzle.source_detail}
                        </span>
                      )}
                      <Badge 
                        variant="outline" 
                        className={`${
                          displayPuzzle.user_color === "white" 
                            ? "text-amber-400 border-amber-400/50" 
                            : "text-slate-300 border-slate-400/50"
                        }`}
                      >
                        Playing as {displayPuzzle.user_color === "white" ? "White" : "Black"}
                      </Badge>
                    </div>
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
                      puzzleState !== "thinking" && displayPuzzle
                        ? [(displayPuzzle.correct_move || displayPuzzle.best_move_san || "").slice(-2)]
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
                            disabled={!hasMoreFilteredPuzzles}
                          >
                            {hasMoreFilteredPuzzles ? (
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
                                You played: <span className="text-red-400 font-mono">{feedback.user_move || userAnswer}</span>
                              </p>
                              <p className="text-gray-400">
                                Best move: <span className="text-green-400 font-mono">{feedback.correct_move || feedback.expected_move || displayPuzzle?.correct_move}</span>
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
                            disabled={!hasMoreFilteredPuzzles}
                          >
                            {hasMoreFilteredPuzzles ? "Next Puzzle" : "Complete"}
                            <ChevronRight className="w-4 h-4 ml-1" />
                          </Button>
                        </div>
                      </motion.div>
                    )}

                    {puzzleState === "revealed" && displayPuzzle && (
                      <motion.div
                        key="revealed"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="bg-gray-800/50 border border-gray-700 rounded-lg p-4"
                      >
                        <div className="text-center mb-3">
                          <p className="text-gray-400 mb-2">The best move was:</p>
                          <p className="text-2xl font-mono text-amber-500">{displayPuzzle.correct_move || displayPuzzle.best_move_san}</p>
                        </div>
                        {displayPuzzle.critical_detail && (
                          <p className="text-gray-300 text-sm text-center mb-3">
                            {displayPuzzle.critical_detail}
                          </p>
                        )}
                        {displayPuzzle.principle && (
                          <div className="bg-gray-900/50 rounded p-3 mb-4">
                            <p className="text-xs text-amber-500 font-medium mb-1">
                              <Lightbulb className="w-3 h-3 inline mr-1" />
                              PRINCIPLE: {displayPuzzle.principle.name}
                            </p>
                            <p className="text-sm text-gray-300">{displayPuzzle.principle.quick_tip}</p>
                          </div>
                        )}
                        <div className="flex justify-center">
                          <Button
                            onClick={nextPuzzle}
                            disabled={!hasMoreFilteredPuzzles}
                          >
                            {hasMoreFilteredPuzzles ? "Next Puzzle" : "Complete"}
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
            {displayPuzzle && (
              <Card className="bg-gray-900/50 border-gray-800">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-400">
                    This Position
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {/* Source info */}
                    <div>
                      <p className="text-xs text-gray-500 mb-1">
                        {displayPuzzle.source === "my_game" ? "From your game" : "From"}
                      </p>
                      <p className="text-white font-medium">{displayPuzzle.source_label}</p>
                      {displayPuzzle.source_detail && (
                        <p className="text-xs text-gray-500">{displayPuzzle.source_detail}</p>
                      )}
                    </div>
                    {/* User's original move (only for user's games) */}
                    {displayPuzzle.source === "my_game" && displayPuzzle.user_move && (
                      <div>
                        <p className="text-xs text-gray-500 mb-1">You played</p>
                        <p className="text-red-400 font-mono">{displayPuzzle.user_move}</p>
                      </div>
                    )}
                    {/* Severity */}
                    {displayPuzzle.cp_loss && (
                      <div>
                        <p className="text-xs text-gray-500 mb-1">Severity</p>
                        <p className={formatEvaluation(displayPuzzle.cp_loss).color}>
                          {formatEvaluation(displayPuzzle.cp_loss).text}
                        </p>
                      </div>
                    )}
                    {/* Community stats */}
                    {displayPuzzle.source === "community" && (
                      <div>
                        <p className="text-xs text-gray-500 mb-1">Community Stats</p>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="text-xs">
                            {displayPuzzle.difficulty}
                          </Badge>
                          <span className="text-xs text-gray-400">
                            {displayPuzzle.solve_rate}% solve rate
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Puzzle-Specific Issue */}
            {displayPuzzle?.principle && (
              <Card className="bg-orange-500/10 border-orange-500/30">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-orange-400 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4" />
                    What Went Wrong
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <Badge className="bg-orange-500/20 text-orange-400 border-orange-500/30 mb-3">
                    {displayPuzzle.principle.name || displayPuzzle.issue_type?.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                  </Badge>
                  {displayPuzzle.critical_detail && (
                    <p className="text-sm text-orange-300 mb-2">
                      {displayPuzzle.critical_detail}
                    </p>
                  )}
                  <p className="text-sm text-gray-400">
                    {displayPuzzle.principle.quick_tip || displayPuzzle.principle.principle}
                  </p>
                </CardContent>
              </Card>
            )}

            {/* Issue type for community puzzles */}
            {displayPuzzle?.source === "community" && displayPuzzle?.issue_type && !displayPuzzle?.principle && (
              <Card className="bg-blue-500/10 border-blue-500/30">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-blue-400 flex items-center gap-2">
                    <HelpCircle className="w-4 h-4" />
                    Puzzle Theme
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <Badge className="bg-blue-500/20 text-blue-400 border-blue-500/30">
                    {displayPuzzle.issue_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                  </Badge>
                </CardContent>
              </Card>
            )}

            {/* Weakness Pattern - only show if no puzzle-specific info */}
            {!displayPuzzle?.principle && weaknesses && weaknesses.weakest_phase && (
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
        </Tabs>
      </div>
    </Layout>
  );
};

export default Training;
