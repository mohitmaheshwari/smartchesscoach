import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Chess } from "chess.js";
import Layout from "@/components/Layout";
import CoachBoard from "@/components/CoachBoard";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Progress } from "@/components/ui/progress";
import { API } from "@/App";
import { toast } from "sonner";
import {
  Brain,
  Clock,
  ChevronRight,
  ChevronLeft,
  AlertTriangle,
  Lightbulb,
  Target,
  Play,
  Check,
  Sparkles,
  Flame,
  MessageSquare,
  Undo2,
  X,
  Trophy,
  TrendingDown,
  Eye,
  HelpCircle,
  CheckCircle2,
  RotateCcw,
} from "lucide-react";

const Reflect = ({ user }) => {
  const navigate = useNavigate();
  const boardRef = useRef(null);
  
  // State
  const [loading, setLoading] = useState(true);
  const [gamesNeedingReflection, setGamesNeedingReflection] = useState([]);
  const [currentGameIndex, setCurrentGameIndex] = useState(0);
  const [currentMomentIndex, setCurrentMomentIndex] = useState(0);
  const [moments, setMoments] = useState([]);
  const [loadingMoments, setLoadingMoments] = useState(false);
  
  // Reflection state
  const [userThought, setUserThought] = useState("");
  const [isPlanMode, setIsPlanMode] = useState(false);
  const [planMoves, setPlanMoves] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [awarenessGap, setAwarenessGap] = useState(null);
  const [showingGap, setShowingGap] = useState(false);
  
  // View mode for arrows: "position" | "your_move" | "better_move"
  const [viewMode, setViewMode] = useState("your_move");
  const [coachExplanation, setCoachExplanation] = useState(null);
  const [loadingExplanation, setLoadingExplanation] = useState(false);
  
  // Contextual tags state
  const [contextualTags, setContextualTags] = useState([]);
  const [loadingTags, setLoadingTags] = useState(false);
  const [couldNotInferIntent, setCouldNotInferIntent] = useState(false);
  
  // V1 REFLECTION ENGINE STATE (Progressive 2-tap flow)
  const [reflectProfile, setReflectProfile] = useState(null);
  const [reflectStep, setReflectStep] = useState(0); // 0=intent/plan, 1=confidence, 2=tags, 3=done
  const [selectedIntent, setSelectedIntent] = useState(null);
  const [selectedConfidence, setSelectedConfidence] = useState(null);
  const [selectedTags, setSelectedTags] = useState([]);
  const [v1QuickTags, setV1QuickTags] = useState([]);
  const [coachReward, setCoachReward] = useState(null);
  const [reflectionStartTime, setReflectionStartTime] = useState(null);
  
  // Time context state
  const [timeContext, setTimeContext] = useState(null);
  const [loadingTimeContext, setLoadingTimeContext] = useState(false);
  
  // Move intent hypotheses - position-specific options
  const [intentHypotheses, setIntentHypotheses] = useState([]);
  const [loadingHypotheses, setLoadingHypotheses] = useState(false);
  const [selectedHypothesis, setSelectedHypothesis] = useState(null);
  
  const currentGame = gamesNeedingReflection[currentGameIndex];
  const currentMoment = moments[currentMomentIndex];
  const totalMoments = moments.length;
  
  // V1 Engine: Fetch adaptive profile on mount
  useEffect(() => {
    fetchReflectProfile();
  }, []);
  
  const fetchReflectProfile = async () => {
    try {
      const res = await fetch(`${API}/reflect/v1/profile`, { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        setReflectProfile(data);
      }
    } catch (err) {
      console.error("Failed to fetch reflect profile:", err);
    }
  };
  
  // V1 Engine: Fetch quick tags when moment changes
  const fetchV1QuickTags = async (moment) => {
    if (!moment) return;
    setLoadingTags(true);
    setV1QuickTags([]);
    
    try {
      const res = await fetch(`${API}/reflect/v1/quick-tags`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          fen: moment.fen,
          user_move: moment.user_move,
          best_move: moment.best_move,
          mistake_category: moment.mistake_category || "critical_moment_drift",
          cp_loss: Math.abs(moment.eval_change || 0) * 100,
          move_number: moment.move_number || 0,
        })
      });
      if (res.ok) {
        const data = await res.json();
        setV1QuickTags(data.tags || []);
        // Also update profile if returned
        if (data.intent_options && reflectProfile) {
          setReflectProfile(prev => ({
            ...prev,
            intent_options: data.intent_options,
            confidence_options: data.confidence_options,
          }));
        }
      }
    } catch (err) {
      console.error("Error fetching V1 quick tags:", err);
    } finally {
      setLoadingTags(false);
    }
  };
  
  // Fetch time context for the current move
  const fetchTimeContext = async (gameId, moveNumber) => {
    if (!gameId || !moveNumber) return;
    setLoadingTimeContext(true);
    
    try {
      const res = await fetch(`${API}/games/${gameId}/move/${moveNumber}/time-context`, {
        credentials: "include"
      });
      if (res.ok) {
        const data = await res.json();
        setTimeContext(data);
      }
    } catch (err) {
      console.error("Error fetching time context:", err);
    } finally {
      setLoadingTimeContext(false);
    }
  };
  
  // Fetch position-specific intent hypotheses
  const fetchIntentHypotheses = async (gameId, moveNumber) => {
    if (!gameId || !moveNumber) return;
    setLoadingHypotheses(true);
    setIntentHypotheses([]);
    
    try {
      const res = await fetch(`${API}/games/${gameId}/move/${moveNumber}/intent-hypotheses`, {
        credentials: "include"
      });
      if (res.ok) {
        const data = await res.json();
        setIntentHypotheses(data.hypotheses || []);
      }
    } catch (err) {
      console.error("Error fetching intent hypotheses:", err);
    } finally {
      setLoadingHypotheses(false);
    }
  };
  
  // V1 Engine: Submit reflection
  const submitReflectionV1 = async () => {
    if (!selectedIntent || !selectedConfidence) {
      toast.error("Please select your intent and confidence");
      return;
    }
    
    // Calculate completion time
    const completionTimeMs = reflectionStartTime ? Date.now() - reflectionStartTime : 0;
    const completionTimeSec = Math.round(completionTimeMs / 1000);
    
    setSubmitting(true);
    try {
      const res = await fetch(`${API}/reflect/v1/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          game_id: currentGame.game_id,
          move_index: currentMomentIndex,
          fen: currentMoment.fen,
          user_move: currentMoment.user_move,
          best_move: currentMoment.best_move,
          mistake_category: currentMoment.mistake_category || "critical_moment_drift",
          intent: selectedIntent,
          intent_confidence: selectedConfidence,
          selected_quick_tags: selectedTags,
          auto_tag_candidates_shown: v1QuickTags.map(t => t.id),
          free_text: userThought || "",
          cp_loss: Math.abs(currentMoment.eval_change || 0) * 100,
          move_number: currentMoment.move_number || 0,
          completed_in_seconds: completionTimeSec,
          game_ended_at: currentGame.played_at || currentGame.created_at,
        })
      });
      
      const data = await res.json();
      
      if (data.awareness_result) {
        setAwarenessGap(data.awareness_result);
        setCoachReward(data.coach_message);
        setShowingGap(true);
      } else {
        // Move to next moment
        moveToNextMoment();
      }
    } catch (err) {
      toast.error("Failed to save reflection");
    } finally {
      setSubmitting(false);
    }
  };
  
  // Reset V1 state when moment changes
  const resetV1State = () => {
    setReflectStep(0);
    setSelectedIntent(null);
    setSelectedConfidence(null);
    setSelectedTags([]);
    setV1QuickTags([]);
    setCoachReward(null);
    setReflectionStartTime(Date.now());
  };
  
  // Helper to convert SAN move to arrow coordinates
  const sanToArrow = (san, fen, color = "red") => {
    if (!san || !fen) return null;
    try {
      const chess = new Chess(fen);
      const move = chess.move(san);
      if (move) {
        return [move.from, move.to, color];
      }
    } catch (e) {
      console.error("Error converting SAN to arrow:", e);
    }
    return null;
  };
  
  // Calculate arrows based on view mode
  const getArrows = () => {
    if (!currentMoment) return [];
    const arrows = [];
    
    if (viewMode === "your_move" || viewMode === "both") {
      const userArrow = sanToArrow(currentMoment.user_move, currentMoment.fen, "red");
      if (userArrow) arrows.push(userArrow);
    }
    
    if (viewMode === "better_move" || viewMode === "both") {
      const betterArrow = sanToArrow(currentMoment.best_move, currentMoment.fen, "green");
      if (betterArrow) arrows.push(betterArrow);
    }
    
    return arrows;
  };
  
  // Fetch coach explanation for the moment
  const fetchCoachExplanation = async (moment) => {
    if (!moment) return;
    setLoadingExplanation(true);
    try {
      const res = await fetch(`${API}/reflect/explain-moment`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          fen: moment.fen,
          user_move: moment.user_move,
          best_move: moment.best_move,
          eval_change: moment.eval_change,
          type: moment.type
        })
      });
      if (res.ok) {
        const data = await res.json();
        setCoachExplanation(data);
      }
    } catch (err) {
      console.error("Error fetching explanation:", err);
    } finally {
      setLoadingExplanation(false);
    }
  };
  
  // Fetch contextual tags for the moment
  const fetchContextualTags = async (moment) => {
    if (!moment) return;
    setLoadingTags(true);
    setContextualTags([]);
    setCouldNotInferIntent(false);
    
    try {
      const res = await fetch(`${API}/reflect/moment/contextual-tags`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          fen: moment.fen,
          user_move: moment.user_move,
          best_move: moment.best_move,
          eval_change: moment.eval_change
        })
      });
      if (res.ok) {
        const data = await res.json();
        setContextualTags(data.tags || []);
        setCouldNotInferIntent(data.could_not_infer || false);
      }
    } catch (err) {
      console.error("Error fetching contextual tags:", err);
    } finally {
      setLoadingTags(false);
    }
  };
  
  // Fetch explanation and tags when moment changes
  useEffect(() => {
    if (currentMoment && !coachExplanation) {
      fetchCoachExplanation(currentMoment);
    }
    if (currentMoment) {
      fetchContextualTags(currentMoment);
    }
    // Fetch time context for this move
    if (currentGame && currentMoment?.move_number) {
      fetchTimeContext(currentGame.game_id, currentMoment.move_number);
      // Fetch position-specific intent hypotheses
      fetchIntentHypotheses(currentGame.game_id, currentMoment.move_number);
    }
    // Reset hypothesis selection when moment changes
    setSelectedHypothesis(null);
  }, [currentMoment, currentGame]);
  
  // Reset explanation and tags when moment changes
  useEffect(() => {
    setCoachExplanation(null);
    setContextualTags([]);
    setCouldNotInferIntent(false);
    setViewMode("your_move");
    // V1: Reset progressive flow state
    resetV1State();
  }, [currentMomentIndex, currentGameIndex]);
  
  // V1: Fetch tags when moment is available
  useEffect(() => {
    if (currentMoment) {
      fetchV1QuickTags(currentMoment);
    }
  }, [currentMoment?.fen]);
  
  // Fetch games needing reflection
  useEffect(() => {
    fetchGamesNeedingReflection();
  }, []);
  
  // Fetch moments when game changes
  useEffect(() => {
    if (currentGame) {
      fetchGameMoments(currentGame.game_id);
    }
  }, [currentGame?.game_id]);
  
  const fetchGamesNeedingReflection = async () => {
    try {
      const res = await fetch(`${API}/reflect/pending`, { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        setGamesNeedingReflection(data.games || []);
      }
    } catch (err) {
      console.error("Failed to fetch games:", err);
    } finally {
      setLoading(false);
    }
  };
  
  const fetchGameMoments = async (gameId) => {
    setLoadingMoments(true);
    try {
      const res = await fetch(`${API}/reflect/game/${gameId}/moments`, { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        const newMoments = data.moments || [];
        setMoments(newMoments);
        setCurrentMomentIndex(0);
        setUserThought("");
        setAwarenessGap(null);
        setShowingGap(false);
        return newMoments;  // Return for immediate use
      }
      return [];
    } catch (err) {
      console.error("Failed to fetch moments:", err);
      return [];
    } finally {
      setLoadingMoments(false);
    }
  };
  
  const handlePlanMove = (moveData) => {
    // CoachBoard passes move data with 'move' key containing SAN notation
    const san = moveData.move || moveData.san;
    if (san) {
      setPlanMoves(prev => [...prev, san]);
    }
  };
  
  const handleUndoPlanMove = () => {
    setPlanMoves(prev => prev.slice(0, -1));
    if (boardRef.current?.undo) {
      boardRef.current.undo();
    }
  };
  
  const resetBoardToPosition = () => {
    // Reset board back to original moment position
    setPlanMoves([]);
    if (boardRef.current?.reset) {
      boardRef.current.reset();
    }
    if (boardRef.current?.setPosition && currentMoment?.fen) {
      boardRef.current.setPosition(currentMoment.fen);
    }
  };
  
  const startPlanMode = () => {
    setIsPlanMode(true);
    setPlanMoves([]);
  };
  
  const cancelPlanMode = () => {
    setIsPlanMode(false);
    setPlanMoves([]);
    if (boardRef.current?.reset) {
      boardRef.current.reset();
    }
  };
  
  const finishPlanMode = () => {
    // NO LLM TRANSLATION - just capture the moves and let user describe
    if (planMoves.length === 0) {
      toast.error("Play at least one move");
      return;
    }
    
    // Store the moves played for reference, but don't auto-fill text
    const movesPlayed = planMoves.join(" ");
    
    // Exit plan mode
    setIsPlanMode(false);
    
    // Reset board to original position
    if (boardRef.current?.reset) {
      boardRef.current.reset();
    }
    
    // Keep moves for display, but let user write their own description
    // Don't clear planMoves - we'll show them as a reference
    toast.success(`Moves recorded: ${movesPlayed}. Now describe what you were thinking.`);
  };
  
  const usePlanMovesAsThought = () => {
    // Option to directly use moves as the thought text
    if (planMoves.length > 0) {
      setUserThought(`My plan was: ${planMoves.join(" ")}`);
    }
  };
  
  const clearPlanMoves = () => {
    setPlanMoves([]);
  };
  
  const submitReflection = async () => {
    if (!userThought.trim()) {
      toast.error("Share what you were thinking");
      return;
    }
    
    setSubmitting(true);
    try {
      const res = await fetch(`${API}/reflect/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          game_id: currentGame.game_id,
          moment_index: currentMomentIndex,
          moment_fen: currentMoment?.fen,
          user_thought: userThought,
          user_move: currentMoment?.user_move,
          best_move: currentMoment?.best_move,
          eval_change: currentMoment?.eval_change,
          move_number: currentMoment?.move_number,  // Track which move was reflected
        }),
      });
      
      const data = await res.json();
      
      if (data.awareness_gap) {
        setAwarenessGap(data.awareness_gap);
        setShowingGap(true);
      } else {
        // Move to next moment
        moveToNextMoment();
      }
    } catch (err) {
      toast.error("Failed to save reflection");
    } finally {
      setSubmitting(false);
    }
  };
  
  const acknowledgeGap = () => {
    setShowingGap(false);
    setAwarenessGap(null);
    moveToNextMoment();
  };
  
  const moveToNextMoment = async () => {
    setUserThought("");
    setPlanMoves([]);
    
    if (currentMomentIndex < totalMoments - 1) {
      // More moments in this game
      setCurrentMomentIndex(prev => prev + 1);
    } else {
      // All moments done for this game - refetch to confirm
      // (the backend now filters out already-reflected moments)
      const remainingMoments = await fetchGameMoments(currentGame.game_id);
      
      // If no more moments after refetch, move to next game
      if (remainingMoments.length === 0) {
        toast.success("Game reflection complete!");
        
        if (currentGameIndex < gamesNeedingReflection.length - 1) {
          setCurrentGameIndex(prev => prev + 1);
          setCurrentMomentIndex(0);
        } else {
          // All games done!
          toast.success("All reflections done!");
          // Refetch games list to update badge
          fetchGamesNeedingReflection();
        }
      }
      // If there are remaining moments, fetchGameMoments already set them
    }
  };
  
  const getUrgencyColor = (hoursAgo) => {
    if (hoursAgo < 6) return "text-green-500";
    if (hoursAgo < 12) return "text-amber-500";
    return "text-red-500";
  };
  
  const getUrgencyText = (hoursAgo) => {
    if (hoursAgo < 1) return "Just played";
    if (hoursAgo < 6) return `${Math.floor(hoursAgo)}h ago - Memory fresh`;
    if (hoursAgo < 12) return `${Math.floor(hoursAgo)}h ago - Reflect soon`;
    if (hoursAgo < 24) return `${Math.floor(hoursAgo)}h ago - Don't lose this`;
    return `${Math.floor(hoursAgo / 24)}d ago - Memory fading`;
  };

  if (loading) {
    return (
      <Layout user={user}>
        <div className="max-w-4xl mx-auto py-12 px-4 flex items-center justify-center">
          <div className="animate-pulse text-muted-foreground">Loading...</div>
        </div>
      </Layout>
    );
  }

  // No games to reflect on
  if (gamesNeedingReflection.length === 0) {
    return (
      <Layout user={user}>
        <div className="max-w-2xl mx-auto py-16 px-4 text-center">
          <div className="w-16 h-16 rounded-full bg-green-500/10 flex items-center justify-center mx-auto mb-6">
            <Check className="w-8 h-8 text-green-500" />
          </div>
          <h1 className="text-2xl font-bold mb-3">All caught up!</h1>
          <p className="text-muted-foreground mb-8">
            No games need reflection right now. Play some games and come back!
          </p>
          <Button onClick={() => navigate("/dashboard")} variant="outline">
            Go to Dashboard
          </Button>
        </div>
      </Layout>
    );
  }

  return (
    <Layout user={user}>
      <div className="max-w-5xl mx-auto py-6 px-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h1 className="text-xl font-bold">Reflect</h1>
              <Badge variant="destructive" className="animate-pulse">
                {gamesNeedingReflection.length} game{gamesNeedingReflection.length > 1 ? 's' : ''}
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground">
              Capture your thoughts while they're fresh
            </p>
          </div>
          
          {currentGame && (
            <div className={`text-sm ${getUrgencyColor(currentGame.hours_ago)}`}>
              <Clock className="w-4 h-4 inline mr-1" />
              {getUrgencyText(currentGame.hours_ago)}
            </div>
          )}
        </div>

        {/* Game Info Bar */}
        {currentGame && (
          <Card className="mb-4 bg-muted/30">
            <CardContent className="py-3 px-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    {currentGame.result === "win" ? (
                      <Trophy className="w-4 h-4 text-green-500" />
                    ) : (
                      <TrendingDown className="w-4 h-4 text-red-500" />
                    )}
                    <span className="font-medium">
                      vs {currentGame.opponent_name}
                    </span>
                  </div>
                  <Badge variant="outline" className="text-xs">
                    {currentGame.time_control}
                  </Badge>
                  {currentGame.accuracy && (
                    <span className="text-sm text-muted-foreground">
                      {currentGame.accuracy.toFixed(0)}% accuracy
                    </span>
                  )}
                </div>
                
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">
                    Moment {currentMomentIndex + 1} of {totalMoments}
                  </span>
                  <Progress 
                    value={((currentMomentIndex + 1) / Math.max(totalMoments, 1)) * 100} 
                    className="w-20 h-2"
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {loadingMoments ? (
          <div className="flex items-center justify-center py-20">
            <div className="animate-pulse text-muted-foreground">Loading moments...</div>
          </div>
        ) : currentMoment ? (
          <div className="grid lg:grid-cols-2 gap-6">
            {/* Board Section */}
            <div>
              <Card className="overflow-hidden">
                <CardContent className="p-0">
                  {/* Moment Type Badge */}
                  <div className="px-4 py-2 bg-muted/50 border-b flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Badge 
                        variant={currentMoment.type === "blunder" ? "destructive" : "secondary"}
                        className="text-xs"
                      >
                        {currentMoment.type === "blunder" ? (
                          <><AlertTriangle className="w-3 h-3 mr-1" /> Blunder</>
                        ) : currentMoment.type === "mistake" ? (
                          <><Target className="w-3 h-3 mr-1" /> Mistake</>
                        ) : (
                          <><HelpCircle className="w-3 h-3 mr-1" /> Critical</>
                        )}
                      </Badge>
                      <span className="text-sm text-muted-foreground">
                        Move {currentMoment.move_number}
                      </span>
                    </div>
                    {currentMoment.eval_change && (
                      <span className="text-sm font-mono text-red-500">
                        {currentMoment.eval_change > 0 ? "+" : ""}{currentMoment.eval_change.toFixed(1)}
                      </span>
                    )}
                  </div>
                  
                  {/* View Mode Toggle */}
                  <div className="px-4 pb-2">
                    <div className="flex items-center justify-center gap-1 bg-muted/50 rounded-lg p-1">
                      <Button
                        variant={viewMode === "your_move" ? "default" : "ghost"}
                        size="sm"
                        onClick={() => setViewMode("your_move")}
                        className={`flex-1 gap-1 ${viewMode === "your_move" ? "bg-red-500/20 text-red-400 hover:bg-red-500/30" : ""}`}
                      >
                        <span className="w-2 h-2 rounded-full bg-red-500" />
                        Your Move
                      </Button>
                      <Button
                        variant={viewMode === "better_move" ? "default" : "ghost"}
                        size="sm"
                        onClick={() => setViewMode("better_move")}
                        className={`flex-1 gap-1 ${viewMode === "better_move" ? "bg-green-500/20 text-green-400 hover:bg-green-500/30" : ""}`}
                      >
                        <span className="w-2 h-2 rounded-full bg-green-500" />
                        Better Move
                      </Button>
                      <Button
                        variant={viewMode === "both" ? "default" : "ghost"}
                        size="sm"
                        onClick={() => setViewMode("both")}
                        className={`flex-1 ${viewMode === "both" ? "bg-primary/20" : ""}`}
                      >
                        Both
                      </Button>
                    </div>
                  </div>
                  
                  {/* Chess Board with Arrows */}
                  <div className="p-4">
                    <CoachBoard
                      ref={boardRef}
                      position={currentMoment.fen}
                      orientation={currentGame?.user_color || "white"}
                      interactive={isPlanMode}
                      planMode={isPlanMode}
                      onPlanMove={handlePlanMove}
                      showDests={isPlanMode}
                      viewOnly={!isPlanMode}
                      customArrows={getArrows()}
                    />
                  </div>
                  
                  {/* Coach Explanation */}
                  {(loadingExplanation || coachExplanation) && (
                    <div className="px-4 pb-3">
                      <Card className="bg-gradient-to-r from-amber-500/10 to-orange-500/10 border-amber-500/30">
                        <CardContent className="py-3 px-4">
                          {loadingExplanation ? (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                              <div className="w-4 h-4 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
                              Getting coach insights...
                            </div>
                          ) : coachExplanation && (
                            <div className="space-y-2">
                              <div className="flex items-start gap-2">
                                <Lightbulb className="w-4 h-4 text-amber-500 mt-0.5 shrink-0" />
                                <div className="space-y-1">
                                  <p className="text-sm font-medium text-amber-400">What happened</p>
                                  <p className="text-sm text-foreground/90">{coachExplanation.impact}</p>
                                </div>
                              </div>
                              {coachExplanation.better_plan && (
                                <div className="flex items-start gap-2 pt-2 border-t border-amber-500/20">
                                  <Target className="w-4 h-4 text-green-500 mt-0.5 shrink-0" />
                                  <div className="space-y-1">
                                    <p className="text-sm font-medium text-green-400">Better plan</p>
                                    <p className="text-sm text-foreground/90">{coachExplanation.better_plan}</p>
                                  </div>
                                </div>
                              )}
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    </div>
                  )}
                  
                  {/* Move Info */}
                  <div className="px-4 pb-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`text-center p-2 rounded-lg transition-colors ${viewMode === "your_move" || viewMode === "both" ? "bg-red-500/10 ring-1 ring-red-500/30" : ""}`}>
                        <div className="text-xs text-muted-foreground">You played</div>
                        <div className="font-mono font-bold text-red-500">{currentMoment.user_move}</div>
                      </div>
                      <ChevronRight className="w-4 h-4 text-muted-foreground" />
                      <div className={`text-center p-2 rounded-lg transition-colors ${viewMode === "better_move" || viewMode === "both" ? "bg-green-500/10 ring-1 ring-green-500/30" : ""}`}>
                        <div className="text-xs text-muted-foreground">Better was</div>
                        <div className="font-mono font-bold text-green-500">{currentMoment.best_move}</div>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
              
              {/* Plan Mode Controls */}
              {isPlanMode && (
                <Card className="mt-3 bg-purple-500/10 border-purple-500/30">
                  <CardContent className="py-3 px-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="text-sm font-medium text-purple-400 mb-1">
                          Show your thinking
                        </div>
                        {planMoves.length > 0 && (
                          <div className="text-sm font-mono">
                            {planMoves.map((m, i) => (
                              <span key={i} className="mr-1">
                                {i % 2 === 0 && <span className="text-muted-foreground mr-1">{Math.floor(i/2) + 1}.</span>}
                                {m}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <Button size="sm" variant="ghost" onClick={resetBoardToPosition} title="Reset to position">
                          <RotateCcw className="w-4 h-4" />
                        </Button>
                        <Button size="sm" variant="ghost" onClick={handleUndoPlanMove} disabled={planMoves.length === 0}>
                          <Undo2 className="w-4 h-4" />
                        </Button>
                        <Button size="sm" variant="ghost" onClick={cancelPlanMode}>
                          Cancel
                        </Button>
                        <Button size="sm" onClick={finishPlanMode} disabled={planMoves.length === 0}>
                          Done
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
              
              {/* Show recorded moves after plan mode (not in plan mode, but moves exist) */}
              {!isPlanMode && planMoves.length > 0 && (
                <Card className="mt-3 bg-blue-500/10 border-blue-500/30">
                  <CardContent className="py-3 px-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="text-xs text-blue-400 mb-1">Your moves on the board:</div>
                        <div className="text-sm font-mono">{planMoves.join(" ")}</div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button 
                          size="sm" 
                          variant="outline"
                          onClick={usePlanMovesAsThought}
                          className="text-xs"
                        >
                          Use as description
                        </Button>
                        <Button 
                          size="sm" 
                          variant="ghost"
                          onClick={clearPlanMoves}
                          className="text-xs"
                        >
                          <X className="w-3 h-3" />
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>

            {/* Reflection Section - V1 Progressive Flow */}
            <div>
              <AnimatePresence mode="wait">
                {showingGap && awarenessGap ? (
                  <motion.div
                    key="gap"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -20 }}
                  >
                    <Card className="border-amber-500/50 bg-amber-500/5">
                      <CardContent className="py-6">
                        {/* Coach Reward Message */}
                        {coachReward && (
                          <div className="mb-4 p-3 rounded-lg bg-green-500/10 border border-green-500/30">
                            <div className="flex items-center gap-2 text-green-400">
                              <Check className="w-4 h-4" />
                              <span className="text-sm">{coachReward}</span>
                            </div>
                          </div>
                        )}
                        
                        <div className="flex items-start gap-3 mb-4">
                          <div className="w-10 h-10 rounded-full bg-amber-500/20 flex items-center justify-center shrink-0">
                            <Eye className="w-5 h-5 text-amber-500" />
                          </div>
                          <div>
                            <h3 className="font-semibold text-amber-400 mb-1">
                              {awarenessGap.type === "aligned" ? "Good Self-Awareness" : 
                               awarenessGap.type === "confidence_gap" ? "Confidence Gap" :
                               awarenessGap.type === "panic_pattern" ? "Time Pressure Pattern" :
                               "Awareness Insight"}
                            </h3>
                            <p className="text-sm text-muted-foreground">
                              {awarenessGap.headline}
                            </p>
                          </div>
                        </div>
                        
                        {awarenessGap.focus_recommendation && (
                          <div className="p-3 rounded-lg bg-purple-500/10 border border-purple-500/30 mb-4">
                            <div className="text-xs text-purple-400 mb-1">Recommended focus:</div>
                            <div className="text-sm text-purple-300">{awarenessGap.focus_recommendation}</div>
                          </div>
                        )}
                        
                        <Button onClick={acknowledgeGap} className="w-full">
                          {currentMomentIndex < totalMoments - 1 ? (
                            <>Next moment <ChevronRight className="w-4 h-4 ml-1" /></>
                          ) : (
                            <>Complete <Check className="w-4 h-4 ml-1" /></>
                          )}
                        </Button>
                      </CardContent>
                    </Card>
                  </motion.div>
                ) : (
                  <motion.div
                    key="reflect-v1"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -20 }}
                  >
                    <Card>
                      <CardContent className="py-6">
                        {/* Ego-safe framing */}
                        <div className="text-xs text-muted-foreground mb-4 p-2 bg-muted/30 rounded">
                          No judgment — we're capturing what you saw, so training becomes personal.
                        </div>
                        
                        {/* Progress indicator */}
                        <div className="flex items-center gap-2 mb-6">
                          {[0, 1, 2].map(step => (
                            <div 
                              key={step}
                              className={`h-1 flex-1 rounded-full transition-colors ${
                                step < reflectStep ? "bg-green-500" :
                                step === reflectStep ? "bg-primary" : "bg-muted"
                              }`}
                            />
                          ))}
                        </div>
                        
                        {/* Step 0: Intent/Plan Selection */}
                        {reflectStep === 0 && (
                          <div className="space-y-4">
                            <div className="flex items-center gap-3 mb-4">
                              <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                                <Target className="w-4 h-4 text-primary" />
                              </div>
                              <div>
                                <h3 className="font-semibold">
                                  {reflectProfile?.show_plan_input 
                                    ? "What was your plan here?" 
                                    : "What were you trying to do?"}
                                </h3>
                                <p className="text-xs text-muted-foreground">
                                  Before you played {currentMoment?.user_move}
                                </p>
                              </div>
                            </div>
                            
                            {/* Time Context Badge - Show if available */}
                            {timeContext?.has_data && (
                              <div className={`mb-3 p-2 rounded text-xs flex items-center gap-2 ${
                                timeContext.time_category === 'time_pressure' 
                                  ? 'bg-red-500/10 text-red-400 border border-red-500/30' 
                                  : timeContext.time_category === 'rushed'
                                    ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                                    : timeContext.time_category === 'long_think'
                                      ? 'bg-blue-500/10 text-blue-400 border border-blue-500/30'
                                      : 'bg-muted/30 text-muted-foreground'
                              }`}>
                                <Clock className="w-3 h-3" />
                                <span>
                                  {timeContext.time_category === 'time_pressure' && `Only ${Math.round(timeContext.clock_after)}s left`}
                                  {timeContext.time_category === 'rushed' && `Spent ${timeContext.time_spent.toFixed(1)}s on this move`}
                                  {timeContext.time_category === 'long_think' && `Thought for ${Math.round(timeContext.time_spent)}s`}
                                  {timeContext.time_category === 'normal' && `${timeContext.time_spent.toFixed(1)}s spent`}
                                </span>
                              </div>
                            )}
                            
                            {/* Plan Input for 1000+ players */}
                            {reflectProfile?.show_plan_input && (
                              <div className="mb-4 space-y-3">
                                {/* Plan questions */}
                                <div className="text-sm text-muted-foreground space-y-1">
                                  {(reflectProfile?.plan_questions || []).map((q, idx) => (
                                    <p key={idx} className="flex items-start gap-2">
                                      <span className="text-primary">•</span> {q}
                                    </p>
                                  ))}
                                </div>
                                
                                {/* Board input for 1300+ */}
                                {reflectProfile?.allow_board_moves && (
                                  <div className="flex items-center gap-2">
                                    <Button
                                      size="sm"
                                      variant={isPlanMode ? "default" : "outline"}
                                      onClick={() => setIsPlanMode(true)}
                                      className="text-xs"
                                    >
                                      <Play className="w-3 h-3 mr-1" />
                                      Show on board
                                    </Button>
                                    <span className="text-xs text-muted-foreground">or type below</span>
                                  </div>
                                )}
                                
                                {/* Show recorded moves */}
                                {planMoves.length > 0 && (
                                  <div className="p-2 rounded bg-blue-500/10 border border-blue-500/30">
                                    <div className="text-xs text-blue-400 mb-1">Your plan:</div>
                                    <div className="text-sm font-mono">{planMoves.join(" → ")}</div>
                                  </div>
                                )}
                                
                                {/* Text input */}
                                <Textarea
                                  placeholder="Describe what you were planning..."
                                  value={userThought}
                                  onChange={(e) => setUserThought(e.target.value)}
                                  className="min-h-[60px] text-sm"
                                />
                                
                                <Button 
                                  size="sm" 
                                  onClick={() => setReflectStep(1)}
                                  disabled={!userThought && planMoves.length === 0}
                                  className="w-full"
                                >
                                  Continue
                                  <ChevronRight className="w-4 h-4 ml-1" />
                                </Button>
                              </div>
                            )}
                            
                            {/* Simple tap options for lower-rated players */}
                            {!reflectProfile?.show_plan_input && (
                              <div className="grid grid-cols-2 gap-2">
                                {(reflectProfile?.intent_options || [
                                  { value: "attack", label: "Attack" },
                                  { value: "defend", label: "Defend" },
                                  { value: "improve_pieces", label: "Develop / Improve piece" },
                                  { value: "trade_simplify", label: "Simplify / Trade" },
                                  { value: "win_material", label: "Win material" },
                                  { value: "avoid_threat", label: "Avoid a threat" },
                                  { value: "time_panic", label: "Time pressure move" },
                                  { value: "not_sure", label: "Not sure" },
                                ]).map(option => (
                                  <Button
                                    key={option.value || option.id}
                                    variant={selectedIntent === (option.value || option.id) ? "default" : "outline"}
                                    size="sm"
                                    className="h-auto py-2 px-3 text-left justify-start"
                                    onClick={() => {
                                      setSelectedIntent(option.value || option.id);
                                      // Auto-advance after selection
                                      setTimeout(() => setReflectStep(1), 150);
                                    }}
                                  >
                                    {option.label}
                                  </Button>
                                ))}
                              </div>
                            )}
                            
                            {/* For plan mode users, also show intent after plan */}
                            {reflectProfile?.show_plan_input && (userThought || planMoves.length > 0) && (
                              <div className="mt-4 pt-4 border-t border-border/30">
                                <p className="text-xs text-muted-foreground mb-2">Your main intent:</p>
                                <div className="flex flex-wrap gap-2">
                                  {(reflectProfile?.intent_options || []).slice(0, 6).map(option => (
                                    <Button
                                      key={option.value || option.id}
                                      variant={selectedIntent === (option.value || option.id) ? "default" : "outline"}
                                      size="sm"
                                      className="text-xs py-1 px-2"
                                      onClick={() => setSelectedIntent(option.value || option.id)}
                                    >
                                      {option.label}
                                    </Button>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                        
                        {/* Step 1: Confidence Selection (1 tap) */}
                        {reflectStep === 1 && (
                          <div className="space-y-4">
                            <div className="flex items-center gap-3 mb-4">
                              <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                                <Brain className="w-4 h-4 text-primary" />
                              </div>
                              <div>
                                <h3 className="font-semibold">How sure were you?</h3>
                                <p className="text-xs text-muted-foreground">
                                  When you played {currentMoment?.user_move}
                                </p>
                              </div>
                            </div>
                            
                            {/* Show selected intent as context */}
                            <div className="text-xs text-muted-foreground mb-2">
                              Intent: <span className="text-foreground">{selectedIntent?.replace(/_/g, " ")}</span>
                              <button 
                                className="ml-2 text-primary hover:underline"
                                onClick={() => setReflectStep(0)}
                              >
                                change
                              </button>
                            </div>
                            
                            <div className="grid grid-cols-1 gap-2">
                              {(reflectProfile?.confidence_options || [
                                { id: "very_sure", label: "Very sure" },
                                { id: "somewhat_sure", label: "Somewhat sure" },
                                { id: "guessing", label: "Guessing / fast move" },
                              ]).map(option => (
                                <Button
                                  key={option.id}
                                  variant={selectedConfidence === option.id ? "default" : "outline"}
                                  className="h-auto py-3 text-left justify-start"
                                  onClick={() => {
                                    setSelectedConfidence(option.id);
                                    // Auto-advance after selection
                                    setTimeout(() => setReflectStep(2), 150);
                                  }}
                                >
                                  {option.label}
                                </Button>
                              ))}
                            </div>
                          </div>
                        )}
                        
                        {/* Step 2: Quick Tags (optional, multi-select) */}
                        {reflectStep === 2 && (
                          <div className="space-y-4">
                            <div className="flex items-center gap-3 mb-4">
                              <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                                <Lightbulb className="w-4 h-4 text-primary" />
                              </div>
                              <div>
                                <h3 className="font-semibold">What fits your thinking?</h3>
                                <p className="text-xs text-muted-foreground">
                                  Select any that apply (optional)
                                </p>
                              </div>
                            </div>
                            
                            {/* Context */}
                            <div className="text-xs text-muted-foreground mb-2 flex items-center gap-2 flex-wrap">
                              <span>Intent: <span className="text-foreground">{selectedIntent?.replace(/_/g, " ")}</span></span>
                              <span>•</span>
                              <span>Confidence: <span className="text-foreground">{selectedConfidence?.replace(/_/g, " ")}</span></span>
                              <button 
                                className="text-primary hover:underline"
                                onClick={() => setReflectStep(0)}
                              >
                                restart
                              </button>
                            </div>
                            
                            {loadingTags ? (
                              <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
                                <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                                Analyzing position...
                              </div>
                            ) : (
                              <div className="flex flex-wrap gap-2">
                                {v1QuickTags.map(tag => (
                                  <Button
                                    key={tag.id}
                                    variant={selectedTags.includes(tag.id) ? "default" : "outline"}
                                    size="sm"
                                    className="h-auto py-1.5 px-3 text-xs"
                                    onClick={() => {
                                      setSelectedTags(prev => 
                                        prev.includes(tag.id)
                                          ? prev.filter(t => t !== tag.id)
                                          : [...prev, tag.id]
                                      );
                                    }}
                                  >
                                    {selectedTags.includes(tag.id) && (
                                      <Check className="w-3 h-3 mr-1" />
                                    )}
                                    {tag.label}
                                  </Button>
                                ))}
                              </div>
                            )}
                            
                            {/* Optional free text */}
                            <div className="pt-2">
                              <button 
                                className="text-xs text-muted-foreground hover:text-foreground"
                                onClick={() => {
                                  const text = prompt("Add your exact thought (optional):");
                                  if (text) setUserThought(text);
                                }}
                              >
                                + Add your own description
                              </button>
                              {userThought && (
                                <div className="mt-2 text-xs text-muted-foreground p-2 bg-muted/30 rounded">
                                  "{userThought}"
                                </div>
                              )}
                            </div>
                            
                            <Button 
                              onClick={submitReflectionV1}
                              className="w-full mt-4"
                              disabled={submitting}
                            >
                              {submitting ? (
                                "Analyzing..."
                              ) : (
                                <>Submit Reflection <Check className="w-4 h-4 ml-1" /></>
                              )}
                            </Button>
                          </div>
                        )}
                      </CardContent>
                    </Card>
                    
                    {/* Tip */}
                    <Card className="mt-4 bg-muted/30">
                      <CardContent className="py-3 px-4">
                        <div className="flex items-start gap-2">
                          <Lightbulb className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
                          <p className="text-xs text-muted-foreground">
                            {reflectStep === 0 && "Pick your main intention before the move."}
                            {reflectStep === 1 && "How confident were you? Honest answers help training."}
                            {reflectStep === 2 && "Select tags that match your thinking. This takes under 20 seconds."}
                          </p>
                        </div>
                      </CardContent>
                    </Card>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        ) : (
          <div className="text-center py-12">
            <div className="w-16 h-16 rounded-full bg-green-500/10 flex items-center justify-center mx-auto mb-4">
              <CheckCircle2 className="w-8 h-8 text-green-500" />
            </div>
            <h3 className="text-lg font-semibold mb-2">Great Game!</h3>
            <p className="text-muted-foreground max-w-md mx-auto">
              No significant mistakes found in this game. Your play was solid!
            </p>
            {gamesNeedingReflection.length > 1 && currentGameIndex < gamesNeedingReflection.length - 1 && (
              <Button 
                variant="outline" 
                className="mt-4 gap-2"
                onClick={() => setCurrentGameIndex(currentGameIndex + 1)}
              >
                Check Next Game <ChevronRight className="w-4 h-4" />
              </Button>
            )}
          </div>
        )}
        
        {/* Navigation between games */}
        {gamesNeedingReflection.length > 1 && (
          <div className="flex items-center justify-center gap-2 mt-8">
            {gamesNeedingReflection.map((_, i) => (
              <button
                key={i}
                onClick={() => setCurrentGameIndex(i)}
                className={`w-2 h-2 rounded-full transition-colors ${
                  i === currentGameIndex ? "bg-primary" : "bg-muted-foreground/30"
                }`}
              />
            ))}
          </div>
        )}
      </div>
    </Layout>
  );
};

export default Reflect;
