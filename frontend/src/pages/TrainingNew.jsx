import { useState, useEffect, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
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

// Validate FEN string
const isValidFen = (fen) => {
  if (!fen || typeof fen !== 'string') return false;
  const parts = fen.split(' ');
  if (parts.length < 1) return false;
  
  // Check the piece placement part
  const ranks = parts[0].split('/');
  if (ranks.length !== 8) return false;
  
  // Valid piece chars and numbers
  const validChars = /^[rnbqkpRNBQKP1-8]+$/;
  
  for (const rank of ranks) {
    if (!validChars.test(rank)) return false;
    
    // Count squares in rank (pieces = 1, numbers = their value)
    let count = 0;
    for (const char of rank) {
      if (char >= '1' && char <= '8') {
        count += parseInt(char);
      } else {
        count += 1;
      }
    }
    if (count !== 8) return false;
  }
  
  return true;
};

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
  const [searchParams] = useSearchParams();
  
  // Get focus override from URL (e.g., /coach?focus=one_move_blunders)
  const focusFromUrl = searchParams.get('focus');
  
  // Tab state
  const [activeTab, setActiveTab] = useState("puzzles");
  
  // Core state
  const [loading, setLoading] = useState(true);
  const [puzzles, setPuzzles] = useState([]);
  const [currentPuzzleIndex, setCurrentPuzzleIndex] = useState(0);
  const [progress, setProgress] = useState(null);
  const [weaknesses, setWeaknesses] = useState(null);
  
  // Training mode: "recommended" | "browse"
  const [trainingMode, setTrainingMode] = useState("recommended");
  
  // Cognitive patterns state
  const [trainingPriority, setTrainingPriority] = useState(null);
  const [cognitivePatterns, setCognitivePatterns] = useState(null);
  const [focusStatus, setFocusStatus] = useState(null);
  const [focusOverride, setFocusOverride] = useState(null); // Override from URL param
  
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
  const [mistakeArrow, setMistakeArrow] = useState([]); // Arrow showing the bad move
  const [boardKey, setBoardKey] = useState(0); // Key to force board re-render on reset
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
        
        // Fetch user's puzzles, community puzzles, progress, weaknesses, puzzle progression, AND training priority
        const [puzzlesRes, communityRes, progressRes, weaknessRes, puzzleProgressRes, priorityRes, patternsRes] = await Promise.all([
          fetch(`${API}/training/puzzles?limit=10`, { credentials: "include" }),
          fetch(`${API}/community/puzzles?limit=10`, { credentials: "include" }),
          fetch(`${API}/training/progress`, { credentials: "include" }),
          fetch(`${API}/training/weakness-patterns`, { credentials: "include" }),
          fetch(`${API}/training/puzzle-progress`, { credentials: "include" }),
          fetch(`${API}/cognitive/training-priority`, { credentials: "include" }),
          fetch(`${API}/cognitive/patterns`, { credentials: "include" })
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
        
        // Filter out puzzles with invalid FENs
        allPuzzles = allPuzzles.filter(p => isValidFen(p.fen));
        
        // Get training priority to reorder puzzles
        let priority = null;
        if (priorityRes.ok) {
          priority = await priorityRes.json();
          setTrainingPriority(priority);
        }
        
        // Get cognitive patterns
        if (patternsRes.ok) {
          const patternsData = await patternsRes.json();
          setCognitivePatterns(patternsData);
        }
        
        // Sort puzzles: Prioritized by weakness, then random
        // This reorders but does NOT remove content
        if (priority && priority.puzzle_priority_order && priority.puzzle_priority_order.length > 0) {
          const priorityOrder = priority.puzzle_priority_order;
          allPuzzles = allPuzzles.sort((a, b) => {
            const aType = a.issue_type || a.mistake_type || "";
            const bType = b.issue_type || b.mistake_type || "";
            
            const aIndex = priorityOrder.findIndex(p => aType.includes(p));
            const bIndex = priorityOrder.findIndex(p => bType.includes(p));
            
            // Prioritized puzzles come first
            if (aIndex !== -1 && bIndex === -1) return -1;
            if (aIndex === -1 && bIndex !== -1) return 1;
            if (aIndex !== -1 && bIndex !== -1) return aIndex - bIndex;
            
            // Then random for non-prioritized
            return Math.random() - 0.5;
          });
        } else {
          // No priority, just shuffle
          allPuzzles = allPuzzles.sort(() => Math.random() - 0.5);
        }
        
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
  
  // Fetch focus override when URL param is present
  useEffect(() => {
    const fetchFocusOverride = async () => {
      if (!focusFromUrl) return;
      
      try {
        const res = await fetch(`${API}/training/data-driven?focus=${encodeURIComponent(focusFromUrl)}`, {
          credentials: "include"
        });
        if (res.ok) {
          const data = await res.json();
          // Override the training priority display with the URL focus
          setFocusOverride({
            display_name: data.active_layer_label || data.micro_habit_label,
            message: data.active_layer_description || data.micro_habit_description,
            focus_key: data.override_focus || focusFromUrl
          });
          
          // If focus is about blunders, fetch user's actual blunders as puzzles
          if (focusFromUrl.toLowerCase().includes('blunder') || 
              focusFromUrl.toLowerCase().includes('one_move') ||
              focusFromUrl.toLowerCase().includes('tactical')) {
            const blundersRes = await fetch(`${API}/games/blunders`, { credentials: "include" });
            if (blundersRes.ok) {
              const blunderData = await blundersRes.json();
              
              const blunderPuzzles = (blunderData.blunders || []).map((b, idx) => {
                // Note: We won't try to parse SAN moves since the FEN position
                // might not match where the move was actually made.
                // The arrow feature will be added when backend provides from/to squares.
                
                // Determine user color from FEN (whose turn it is)
                const userColor = b.fen.includes(' w ') ? 'white' : 'black';
                
                return {
                  puzzle_id: `blunder_${b.game_id}_${b.move_number}`,
                  fen: b.fen,
                  user_move: b.move,
                  user_move_from: null, // TODO: Backend should provide this
                  user_move_to: null,   // TODO: Backend should provide this  
                  correct_move: b.consider || "Find the better move",
                  user_color: userColor,
                  issue_type: b.evaluation,
                  source: "your_blunders",
                  source_label: `Move ${b.move_number}`,
                  source_detail: b.feedback || "Your blunder from a real game",
                  move_number: b.move_number,
                  game_id: b.game_id,
                  principle: {
                    name: b.evaluation === "blunder" ? "Blunder" : "Mistake",
                    description: b.feedback || "Review this critical moment"
                  }
                };
              });
              
              // Add blunder puzzles to the front of the puzzle list
              if (blunderPuzzles.length > 0) {
                setPuzzles(prev => [...blunderPuzzles, ...prev.filter(p => p.source !== "your_blunders")]);
                setCurrentPuzzleIndex(0);
              }
            }
          }
        }
      } catch (err) {
        console.error("Error fetching focus override:", err);
      }
    };
    
    fetchFocusOverride();
  }, [focusFromUrl]);
  
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
  
  // Filter puzzles based on source selection, training mode, AND focus override
  const filteredPuzzles = puzzles.filter(p => {
    // Source filter
    if (puzzleSource === "my_games" && p.source !== "my_game") return false;
    if (puzzleSource === "community" && p.source !== "community") return false;
    
    // Special handling for "your_blunders" source - always include when in blunder focus
    if (p.source === "your_blunders") {
      return true; // Always show user's actual blunders
    }
    
    // Focus override filter - when URL has focus param, prioritize matching puzzles
    const activeFocusKey = focusOverride?.focus_key || focusFromUrl;
    if (activeFocusKey) {
      const focusKey = activeFocusKey.toLowerCase();
      const issueType = (p.issue_type || p.mistake_type || "").toLowerCase();
      const principle = (p.principle?.name || "").toLowerCase();
      
      // Match one_move_blunders with blunder-related puzzles
      if (focusKey.includes("blunder") || focusKey.includes("one_move")) {
        return issueType.includes("blunder") || 
               issueType.includes("mistake") ||  // Include mistakes too!
               issueType.includes("hanging") || 
               issueType.includes("tactical") ||
               principle.includes("blunder") ||
               principle.includes("mistake") ||  // Include mistakes too!
               principle.includes("hanging");
      }
      
      // Match other focus areas
      if (issueType.includes(focusKey) || principle.includes(focusKey)) {
        return true;
      }
      
      // For other focus areas, be more lenient
      return true;
    }
    
    return true;
  });
  
  // Sort filtered puzzles - put focus-matching ones first
  const sortedFilteredPuzzles = [...filteredPuzzles].sort((a, b) => {
    const activeFocusKey = focusOverride?.focus_key || focusFromUrl;
    if (!activeFocusKey) return 0;
    
    // Put "your_blunders" source first
    if (a.source === "your_blunders" && b.source !== "your_blunders") return -1;
    if (a.source !== "your_blunders" && b.source === "your_blunders") return 1;
    
    const aType = (a.issue_type || a.mistake_type || "").toLowerCase();
    const bType = (b.issue_type || b.mistake_type || "").toLowerCase();
    
    const aMatches = aType.includes("blunder") || aType.includes("mistake") || aType.includes("hanging") || aType.includes("tactical");
    const bMatches = bType.includes("blunder") || bType.includes("mistake") || bType.includes("hanging") || bType.includes("tactical");
    
    if (aMatches && !bMatches) return -1;
    if (!aMatches && bMatches) return 1;
    return 0;
  });
  
  // Get current puzzle from filtered list
  const displayPuzzle = sortedFilteredPuzzles[currentPuzzleIndex] || null;
  const hasMoreFilteredPuzzles = currentPuzzleIndex < sortedFilteredPuzzles.length - 1;
  
  // Update board when puzzle changes
  useEffect(() => {
    if (displayPuzzle && displayPuzzle.fen) {
      setBoardFen(displayPuzzle.fen);
      setBoardOrientation(displayPuzzle.user_color || "white");
      setPuzzleState("thinking");
      setUserAnswer(null);
      setFeedback(null);
      
      // Show the user's bad move as a red arrow
      if (displayPuzzle.user_move_from && displayPuzzle.user_move_to) {
        // Use pre-calculated from/to squares
        setMistakeArrow([[displayPuzzle.user_move_from, displayPuzzle.user_move_to, "rgb(239, 68, 68)"]]);
      } else {
        setMistakeArrow([]);
      }
    } else {
      // Reset to starting position if no puzzle
      setBoardFen(START_FEN);
      setBoardOrientation("white");
      setMistakeArrow([]);
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
            fen: displayPuzzle.fen,
            difficulty: displayPuzzle.difficulty || "intermediate"
          })
        });
      }
      
      if (res.ok) {
        const result = await res.json();
        setFeedback(result);
        
        // Handle progression updates
        if (result.progression) {
          const prog = result.progression;
          
          // Update local puzzle progress state
          setPuzzleProgress(prev => prev ? {
            ...prev,
            puzzle_rating: prog.new_rating,
            current_streak: prog.current_streak,
            total_puzzles: (prev.total_puzzles || 0) + 1,
            puzzles_solved: (prev.puzzles_solved || 0) + (result.correct ? 1 : 0)
          } : prev);
          
          // Show level up celebration
          if (prog.leveled_up) {
            setLevelUpData(prog);
            setShowLevelUp(true);
            toast.success(`Level Up! You've reached ${prog.new_level.charAt(0).toUpperCase() + prog.new_level.slice(1)}!`, {
              duration: 5000,
              icon: "🎉"
            });
          }
          
          // Show new achievements
          if (prog.new_achievements && prog.new_achievements.length > 0) {
            setNewAchievements(prog.new_achievements);
            prog.new_achievements.forEach(achievement => {
              toast.success(`Achievement: ${achievement.name}`, {
                description: achievement.desc,
                duration: 4000,
                icon: "🏆"
              });
            });
          }
        }
        
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
      // Force board to re-render by changing key
      setBoardKey(prev => prev + 1);
      setBoardFen(displayPuzzle.fen);
      setPuzzleState("thinking");
      setUserAnswer(null);
      setFeedback(null);
      
      // Re-show the mistake arrow
      if (displayPuzzle.user_move_from && displayPuzzle.user_move_to) {
        setMistakeArrow([[displayPuzzle.user_move_from, displayPuzzle.user_move_to, "rgb(239, 68, 68)"]]);
      }
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
            {/* Training Focus Banner - Shows cognitive priority (or URL override) */}
            {(focusOverride || (trainingPriority && trainingPriority.primary_focus)) && (
              <Card className="bg-gradient-to-r from-amber-900/30 to-gray-900/50 border-amber-500/20 mb-4" data-testid="training-focus-card">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-amber-500/20 rounded-lg">
                        <Target className="w-5 h-5 text-amber-400" />
                      </div>
                      <div>
                        <p className="text-xs text-amber-400/80 font-medium uppercase tracking-wide">Your Focus Area</p>
                        <p className="text-white font-semibold" data-testid="focus-display-name">
                          {focusOverride?.display_name || trainingPriority?.primary_focus?.display_name}
                        </p>
                        <p className="text-xs text-gray-400 mt-0.5">
                          {focusOverride?.message || trainingPriority?.primary_focus?.message}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      {/* TSI Display with Interpretation */}
                      {cognitivePatterns && (
                        <div className="text-right">
                          <div className="flex items-center gap-2">
                            <span className="text-xl font-bold text-white" data-testid="tsi-score">{cognitivePatterns.thinking_stability_index}</span>
                            {cognitivePatterns.tsi_trend === "improving" && (
                              <TrendingUp className="w-4 h-4 text-green-400" />
                            )}
                            {cognitivePatterns.tsi_trend === "worsening" && (
                              <TrendingDown className="w-4 h-4 text-red-400" />
                            )}
                          </div>
                          <p className={`text-xs ${
                            cognitivePatterns.thinking_stability_index >= 80 ? 'text-green-400' :
                            cognitivePatterns.thinking_stability_index >= 65 ? 'text-yellow-400' :
                            cognitivePatterns.thinking_stability_index >= 50 ? 'text-orange-400' :
                            'text-red-400'
                          }`} data-testid="tsi-interpretation">
                            {cognitivePatterns.thinking_stability_index >= 80 ? 'Stable decision process' :
                             cognitivePatterns.thinking_stability_index >= 65 ? 'Moderate instability' :
                             cognitivePatterns.thinking_stability_index >= 50 ? 'Frequent cognitive lapses' :
                             'High volatility'}
                            {cognitivePatterns.tsi_trend === "improving" && " (Improving)"}
                            {cognitivePatterns.tsi_trend === "worsening" && " (Declining)"}
                          </p>
                        </div>
                      )}
                      {/* Mode Toggle */}
                      <div className="flex items-center gap-1 px-2 py-1 rounded-lg bg-gray-800/50 border border-gray-700">
                        <button
                          onClick={() => setTrainingMode("recommended")}
                          className={`px-2 py-1 text-xs rounded transition-colors ${
                            trainingMode === "recommended" 
                              ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' 
                              : 'text-gray-400 hover:text-gray-300'
                          }`}
                          data-testid="recommended-mode-btn"
                        >
                          Recommended
                        </button>
                        <button
                          onClick={() => setTrainingMode("browse")}
                          className={`px-2 py-1 text-xs rounded transition-colors ${
                            trainingMode === "browse" 
                              ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' 
                              : 'text-gray-400 hover:text-gray-300'
                          }`}
                          data-testid="browse-mode-btn"
                        >
                          Browse All
                        </button>
                      </div>
                    </div>
                  </div>
                  {/* Trend indicator - no secondary focus (noise reduction) */}
                  {trainingPriority.primary_focus.trend && (
                    <div className="mt-2 flex items-center gap-2">
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        trainingPriority.primary_focus.trend === "improving" 
                          ? "bg-green-500/20 text-green-400"
                          : trainingPriority.primary_focus.trend === "worsening"
                          ? "bg-red-500/20 text-red-400"
                          : "bg-gray-500/20 text-gray-400"
                      }`}>
                        {trainingPriority.primary_focus.trend === "improving" ? "Improving" :
                         trainingPriority.primary_focus.trend === "worsening" ? "Needs Work" : "Stable"}
                      </span>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
            
            {/* General Drills Banner (when no specific weakness) */}
            {trainingPriority && trainingPriority.general_drills && (
              <Card className="bg-gray-900/50 border-gray-800 mb-4">
                <CardContent className="p-4">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-green-500/20 rounded-lg">
                      <CheckCircle2 className="w-5 h-5 text-green-400" />
                    </div>
                    <div>
                      <p className="text-white font-medium">General Improvement Drills</p>
                      <p className="text-xs text-gray-400">No major weaknesses detected. Keep practicing to maintain your skills!</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

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
                    key={boardKey}
                    position={boardFen}
                    userColor={boardOrientation}
                    onUserMove={puzzleState === "thinking" ? (moveData) => handleMove(moveData.san) : null}
                    interactive={puzzleState === "thinking"}
                    customArrows={puzzleState === "thinking" ? mistakeArrow : []}
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
                        {/* Show what was played (for blunder puzzles) */}
                        {displayPuzzle?.user_move && displayPuzzle?.source === "your_blunders" && (
                          <div className="mb-3 p-3 bg-red-500/10 border border-red-500/30 rounded-lg inline-block">
                            <p className="text-sm text-red-400">
                              <span className="font-medium">You played:</span>{' '}
                              <span className="font-mono text-white">{displayPuzzle.user_move}</span>
                              <span className="text-red-300 ml-2">(shown with red arrow)</span>
                            </p>
                          </div>
                        )}
                        <p className="text-gray-300 mb-4">
                          <Brain className="w-5 h-5 inline mr-2 text-amber-500" />
                          {displayPuzzle?.source === "your_blunders" 
                            ? "What should you have played instead?"
                            : "Find the best move. Take your time."}
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
                          <div className="flex-1">
                            <div className="flex items-center justify-between mb-1">
                              <h3 className="text-green-400 font-semibold">
                                {feedback.message}
                              </h3>
                              {/* Rating Change Badge */}
                              {feedback.progression && (
                                <Badge className="bg-green-500/20 text-green-400 border-green-500/30" data-testid="rating-change-badge">
                                  <TrendingUp className="w-3 h-3 mr-1" />
                                  +{feedback.progression.rating_change}
                                </Badge>
                              )}
                            </div>
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
                            {/* Streak indicator */}
                            {feedback.progression && feedback.progression.current_streak >= 3 && (
                              <div className="flex items-center gap-2 mt-3 text-orange-400 text-sm">
                                <Flame className="w-4 h-4" />
                                <span>{feedback.progression.current_streak} puzzle streak!</span>
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
                            <div className="flex items-center justify-between mb-1">
                              <h3 className="text-red-400 font-semibold">
                                {feedback.message}
                              </h3>
                              {/* Rating Change Badge */}
                              {feedback.progression && feedback.progression.rating_change < 0 && (
                                <Badge className="bg-red-500/20 text-red-400 border-red-500/30">
                                  <TrendingDown className="w-3 h-3 mr-1" />
                                  {feedback.progression.rating_change}
                                </Badge>
                              )}
                            </div>
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

            {/* Puzzle Rating Card - NEW */}
            {puzzleProgress && (
              <Card className="bg-gradient-to-br from-gray-900/80 to-gray-800/50 border-gray-700" data-testid="puzzle-rating-card">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-300 flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      <Crown className="w-4 h-4 text-amber-500" />
                      Puzzle Rating
                    </span>
                    <Badge 
                      className={`text-xs ${
                        puzzleProgress.level_color === 'green' ? 'bg-green-500/20 text-green-400 border-green-500/30' :
                        puzzleProgress.level_color === 'emerald' ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' :
                        puzzleProgress.level_color === 'amber' ? 'bg-amber-500/20 text-amber-400 border-amber-500/30' :
                        puzzleProgress.level_color === 'orange' ? 'bg-orange-500/20 text-orange-400 border-orange-500/30' :
                        puzzleProgress.level_color === 'red' ? 'bg-red-500/20 text-red-400 border-red-500/30' :
                        'bg-purple-500/20 text-purple-400 border-purple-500/30'
                      }`}
                    >
                      {puzzleProgress.level_label}
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Main Rating Display */}
                  <div className="text-center">
                    <p className="text-4xl font-bold text-white" data-testid="puzzle-rating-value">
                      {puzzleProgress.puzzle_rating}
                    </p>
                    {puzzleProgress.highest_rating > puzzleProgress.puzzle_rating && (
                      <p className="text-xs text-gray-500 mt-1">
                        Peak: {puzzleProgress.highest_rating}
                      </p>
                    )}
                  </div>
                  
                  {/* Progress to Next Level */}
                  {puzzleProgress.next_level && (
                    <div>
                      <div className="flex justify-between text-xs text-gray-400 mb-1">
                        <span>{puzzleProgress.level_label}</span>
                        <span>{puzzleProgress.next_level_label}</span>
                      </div>
                      <Progress 
                        value={puzzleProgress.progress_in_level} 
                        className="h-2 bg-gray-700"
                      />
                      <p className="text-xs text-gray-500 mt-1 text-center">
                        {puzzleProgress.points_to_next_level} points to {puzzleProgress.next_level_label}
                      </p>
                    </div>
                  )}
                  
                  {/* Stats Grid */}
                  <div className="grid grid-cols-2 gap-3">
                    <div className="bg-gray-800/50 rounded-lg p-2 text-center">
                      <div className="flex items-center justify-center gap-1">
                        <Flame className={`w-4 h-4 ${puzzleProgress.current_streak > 0 ? 'text-orange-400' : 'text-gray-500'}`} />
                        <span className="text-lg font-bold text-white" data-testid="puzzle-streak">
                          {puzzleProgress.current_streak}
                        </span>
                      </div>
                      <p className="text-xs text-gray-500">Streak</p>
                    </div>
                    <div className="bg-gray-800/50 rounded-lg p-2 text-center">
                      <div className="flex items-center justify-center gap-1">
                        <Target className="w-4 h-4 text-green-400" />
                        <span className="text-lg font-bold text-white">
                          {puzzleProgress.solve_rate}%
                        </span>
                      </div>
                      <p className="text-xs text-gray-500">Solve Rate</p>
                    </div>
                  </div>
                  
                  {/* Best Streak */}
                  {puzzleProgress.best_streak > 0 && (
                    <div className="flex items-center justify-between text-sm bg-gray-800/30 rounded-lg px-3 py-2">
                      <span className="text-gray-400 flex items-center gap-1">
                        <Trophy className="w-3 h-3 text-amber-500" />
                        Best Streak
                      </span>
                      <span className="text-white font-medium">{puzzleProgress.best_streak}</span>
                    </div>
                  )}
                  
                  {/* Recent Accuracy */}
                  {puzzleProgress.recent_accuracy !== undefined && puzzleProgress.total_puzzles > 0 && (
                    <div className="flex items-center justify-between text-sm bg-gray-800/30 rounded-lg px-3 py-2">
                      <span className="text-gray-400 flex items-center gap-1">
                        <TrendingUp className="w-3 h-3 text-emerald-500" />
                        Recent (last 20)
                      </span>
                      <span className="text-white font-medium">{puzzleProgress.recent_accuracy}%</span>
                    </div>
                  )}
                  
                  {/* Total Puzzles */}
                  <div className="text-center text-xs text-gray-500">
                    {puzzleProgress.total_puzzles} puzzles attempted • {puzzleProgress.puzzles_solved} solved
                  </div>
                  
                  {/* Achievements Preview */}
                  {puzzleProgress.achievements && puzzleProgress.achievements.length > 0 && (
                    <div className="pt-2 border-t border-gray-700">
                      <p className="text-xs text-gray-400 mb-2 flex items-center gap-1">
                        <Award className="w-3 h-3" />
                        Achievements ({puzzleProgress.achievements.length})
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {puzzleProgress.achievements.slice(0, 4).map(achievement => (
                          <Badge 
                            key={achievement} 
                            variant="outline" 
                            className="text-[10px] py-0 px-1.5 border-amber-500/30 text-amber-400"
                          >
                            {achievement.replace(/_/g, ' ')}
                          </Badge>
                        ))}
                        {puzzleProgress.achievements.length > 4 && (
                          <Badge 
                            variant="outline" 
                            className="text-[10px] py-0 px-1.5 border-gray-600 text-gray-400"
                          >
                            +{puzzleProgress.achievements.length - 4} more
                          </Badge>
                        )}
                      </div>
                    </div>
                  )}
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
      
      {/* Level Up Celebration Modal */}
      <AnimatePresence>
        {showLevelUp && levelUpData && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/80 flex items-center justify-center z-50"
            onClick={() => setShowLevelUp(false)}
          >
            <motion.div
              initial={{ scale: 0.5, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.5, opacity: 0 }}
              transition={{ type: "spring", damping: 15 }}
              className="bg-gradient-to-br from-amber-900/90 to-gray-900 border border-amber-500/50 rounded-2xl p-8 max-w-md mx-4 text-center"
              onClick={(e) => e.stopPropagation()}
              data-testid="level-up-modal"
            >
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: 0.2, type: "spring" }}
              >
                <Sparkles className="w-16 h-16 text-amber-400 mx-auto mb-4" />
              </motion.div>
              
              <motion.h2
                initial={{ y: 20, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ delay: 0.3 }}
                className="text-3xl font-bold text-amber-400 mb-2"
              >
                Level Up!
              </motion.h2>
              
              <motion.p
                initial={{ y: 20, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ delay: 0.4 }}
                className="text-gray-300 mb-4"
              >
                You've reached a new level!
              </motion.p>
              
              <motion.div
                initial={{ y: 20, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ delay: 0.5 }}
                className="bg-gray-800/50 rounded-xl p-4 mb-6"
              >
                <div className="flex items-center justify-center gap-4">
                  <div className="text-center">
                    <p className="text-gray-500 text-sm">From</p>
                    <p className="text-xl font-bold text-gray-400">
                      {levelUpData.old_level?.charAt(0).toUpperCase() + levelUpData.old_level?.slice(1)}
                    </p>
                  </div>
                  <ChevronRight className="w-6 h-6 text-amber-500" />
                  <div className="text-center">
                    <p className="text-amber-500 text-sm">To</p>
                    <p className="text-xl font-bold text-amber-400">
                      {levelUpData.new_level?.charAt(0).toUpperCase() + levelUpData.new_level?.slice(1)}
                    </p>
                  </div>
                </div>
                
                <div className="mt-4 pt-4 border-t border-gray-700">
                  <p className="text-gray-400">New Rating</p>
                  <p className="text-3xl font-bold text-white">{levelUpData.new_rating}</p>
                  <p className="text-green-400 text-sm flex items-center justify-center gap-1">
                    <ChevronUp className="w-4 h-4" />
                    +{levelUpData.rating_change} from this puzzle
                  </p>
                </div>
              </motion.div>
              
              <motion.div
                initial={{ y: 20, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ delay: 0.6 }}
              >
                <Button 
                  onClick={() => setShowLevelUp(false)}
                  className="bg-amber-600 hover:bg-amber-700 text-white px-8"
                >
                  Continue
                </Button>
              </motion.div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </Layout>
  );
};

export default Training;
