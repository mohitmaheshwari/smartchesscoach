import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
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
  
  const currentGame = gamesNeedingReflection[currentGameIndex];
  const currentMoment = moments[currentMomentIndex];
  const totalMoments = moments.length;
  
  // Helper to convert SAN move to arrow coordinates
  const sanToArrow = (san, fen, color = "red") => {
    if (!san || !fen) return null;
    try {
      const { Chess } = require("chess.js");
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
  
  // Fetch explanation when moment changes
  useEffect(() => {
    if (currentMoment && !coachExplanation) {
      fetchCoachExplanation(currentMoment);
    }
  }, [currentMoment]);
  
  // Reset explanation when moment changes
  useEffect(() => {
    setCoachExplanation(null);
    setViewMode("your_move");
  }, [currentMomentIndex, currentGameIndex]);
  
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
        setMoments(data.moments || []);
        setCurrentMomentIndex(0);
        setUserThought("");
        setAwarenessGap(null);
        setShowingGap(false);
      }
    } catch (err) {
      console.error("Failed to fetch moments:", err);
    } finally {
      setLoadingMoments(false);
    }
  };
  
  const handlePlanMove = (moveData) => {
    setPlanMoves(prev => [...prev, moveData.san]);
  };
  
  const handleUndoPlanMove = () => {
    setPlanMoves(prev => prev.slice(0, -1));
    if (boardRef.current?.undo) {
      boardRef.current.undo();
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
  
  const finishPlanMode = async () => {
    if (planMoves.length === 0) {
      toast.error("Play at least one move");
      return;
    }
    
    // Convert plan moves to thought text via LLM
    try {
      const res = await fetch(`${API}/training/plan/describe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          fen: currentMoment?.fen,
          moves: planMoves,
          user_playing_color: currentGame?.user_color,
          turn_to_move: currentMoment?.fen?.includes(" b ") ? "black" : "white",
          user_move: currentMoment?.user_move,
          best_move: currentMoment?.best_move,
        }),
      });
      
      const data = await res.json();
      if (data.plan_description) {
        setUserThought(data.plan_description);
      }
    } catch (err) {
      // Fallback: just show moves
      setUserThought(`I was thinking: ${planMoves.join(" ")}`);
    }
    
    setIsPlanMode(false);
    setPlanMoves([]);
    if (boardRef.current?.stopPlanMode) {
      boardRef.current.stopPlanMode();
    }
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
  
  const moveToNextMoment = () => {
    setUserThought("");
    
    if (currentMomentIndex < totalMoments - 1) {
      setCurrentMomentIndex(prev => prev + 1);
    } else {
      // All moments done for this game
      toast.success("Reflection complete!");
      
      if (currentGameIndex < gamesNeedingReflection.length - 1) {
        // Move to next game
        setCurrentGameIndex(prev => prev + 1);
      } else {
        // All games done!
        setGamesNeedingReflection([]);
      }
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
                  
                  {/* Chess Board */}
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
                    />
                  </div>
                  
                  {/* Move Info */}
                  <div className="px-4 pb-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="text-center">
                        <div className="text-xs text-muted-foreground">You played</div>
                        <div className="font-mono font-bold text-red-500">{currentMoment.user_move}</div>
                      </div>
                      <ChevronRight className="w-4 h-4 text-muted-foreground" />
                      <div className="text-center">
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
            </div>

            {/* Reflection Section */}
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
                        <div className="flex items-start gap-3 mb-4">
                          <div className="w-10 h-10 rounded-full bg-amber-500/20 flex items-center justify-center shrink-0">
                            <Eye className="w-5 h-5 text-amber-500" />
                          </div>
                          <div>
                            <h3 className="font-semibold text-amber-400 mb-1">
                              Awareness Gap Detected
                            </h3>
                            <p className="text-sm text-muted-foreground">
                              There's a difference between what you noticed and what happened
                            </p>
                          </div>
                        </div>
                        
                        <div className="space-y-3 mb-6">
                          <div className="p-3 rounded-lg bg-muted/50">
                            <div className="text-xs text-muted-foreground mb-1">You thought:</div>
                            <div className="text-sm">{userThought}</div>
                          </div>
                          
                          <div className="p-3 rounded-lg bg-muted/50">
                            <div className="text-xs text-muted-foreground mb-1">What actually happened:</div>
                            <div className="text-sm">{awarenessGap.engine_insight}</div>
                          </div>
                          
                          {awarenessGap.training_hint && (
                            <div className="p-3 rounded-lg bg-purple-500/10 border border-purple-500/30">
                              <div className="text-xs text-purple-400 mb-1">Training opportunity:</div>
                              <div className="text-sm text-purple-300">{awarenessGap.training_hint}</div>
                            </div>
                          )}
                        </div>
                        
                        <Button onClick={acknowledgeGap} className="w-full">
                          Got it, continue
                          <ChevronRight className="w-4 h-4 ml-2" />
                        </Button>
                      </CardContent>
                    </Card>
                  </motion.div>
                ) : (
                  <motion.div
                    key="reflect"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -20 }}
                  >
                    <Card>
                      <CardContent className="py-6">
                        <div className="flex items-center gap-3 mb-4">
                          <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                            <Brain className="w-5 h-5 text-primary" />
                          </div>
                          <div>
                            <h3 className="font-semibold">What were you thinking?</h3>
                            <p className="text-sm text-muted-foreground">
                              Before you played {currentMoment.user_move}
                            </p>
                          </div>
                        </div>
                        
                        <div className="space-y-4">
                          <div className="relative">
                            <Textarea
                              value={userThought}
                              onChange={(e) => setUserThought(e.target.value)}
                              placeholder="I was trying to... / I didn't see... / I thought my opponent would..."
                              className="min-h-[120px] resize-none"
                              disabled={isPlanMode}
                            />
                            
                            {!isPlanMode && !userThought && (
                              <Button
                                variant="outline"
                                size="sm"
                                className="absolute bottom-3 right-3 gap-1 text-xs"
                                onClick={startPlanMode}
                              >
                                <Play className="w-3 h-3" />
                                Show on board
                              </Button>
                            )}
                          </div>
                          
                          {/* Quick tags */}
                          <div className="flex flex-wrap gap-2">
                            {[
                              "I didn't see the threat",
                              "I was rushing",
                              "I miscalculated",
                              "I forgot about that piece",
                              "I had a different plan",
                            ].map((tag) => (
                              <Button
                                key={tag}
                                variant="outline"
                                size="sm"
                                className="text-xs h-7"
                                onClick={() => setUserThought(tag)}
                                disabled={isPlanMode}
                              >
                                {tag}
                              </Button>
                            ))}
                          </div>
                          
                          <Button 
                            onClick={submitReflection} 
                            className="w-full"
                            disabled={!userThought.trim() || submitting || isPlanMode}
                          >
                            {submitting ? (
                              "Analyzing..."
                            ) : currentMomentIndex < totalMoments - 1 ? (
                              <>Next moment <ChevronRight className="w-4 h-4 ml-1" /></>
                            ) : (
                              <>Complete reflection <Check className="w-4 h-4 ml-1" /></>
                            )}
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                    
                    {/* Tip */}
                    <Card className="mt-4 bg-muted/30">
                      <CardContent className="py-3 px-4">
                        <div className="flex items-start gap-2">
                          <Lightbulb className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
                          <p className="text-xs text-muted-foreground">
                            Be honest about what you were thinking - not what you know now. 
                            This helps identify blind spots in your thinking process.
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
          <div className="text-center py-20 text-muted-foreground">
            No critical moments found in this game
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
