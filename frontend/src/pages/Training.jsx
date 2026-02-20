import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Chess } from "chess.js";
import { API } from "@/App";
import Layout from "@/components/Layout";
import CoachBoard from "@/components/CoachBoard";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import {
  Loader2,
  Target,
  Brain,
  Shield,
  TrendingUp,
  Layers,
  Crosshair,
  ChevronRight,
  ChevronLeft,
  CheckCircle2,
  AlertTriangle,
  Lightbulb,
  Play,
  RefreshCw,
  RotateCcw,
  History,
  Dumbbell,
} from "lucide-react";

const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

/**
 * Convert centipawn loss to user-friendly evaluation text
 * @param {number} cpLoss - Centipawn loss value
 * @param {string} evalType - Optional evaluation type from backend
 * @returns {string} User-friendly description
 */
const getEvaluationText = (cpLoss, evalType) => {
  // If we have a backend classification, use it directly
  if (evalType) {
    const typeMap = {
      "blunder": "Blunder",
      "mistake": "Mistake", 
      "inaccuracy": "Inaccuracy",
      "good": "Good Move",
      "excellent": "Excellent",
      "best": "Best Move",
    };
    return typeMap[evalType.toLowerCase()] || evalType;
  }
  
  // Fallback to centipawn-based classification
  const loss = Math.abs(cpLoss || 0);
  if (loss >= 300) return "Blunder";
  if (loss >= 100) return "Mistake";
  if (loss >= 50) return "Inaccuracy";
  if (loss >= 20) return "Minor Slip";
  return "Slight Imprecision";
};

/**
 * Get badge variant based on evaluation severity
 */
const getEvalBadgeVariant = (cpLoss, evalType) => {
  const type = evalType?.toLowerCase() || "";
  if (type === "blunder" || cpLoss >= 300) return "destructive";
  if (type === "mistake" || cpLoss >= 100) return "warning";
  return "secondary";
};

// Layer icons and colors
const LAYER_ICONS = {
  stability: Shield,
  conversion: TrendingUp,
  structure: Layers,
  precision: Crosshair,
};

const LAYER_COLORS = {
  stability: "text-blue-500",
  conversion: "text-green-500",
  structure: "text-purple-500",
  precision: "text-orange-500",
};

const LAYER_BG_COLORS = {
  stability: "bg-blue-500/10 border-blue-500/30",
  conversion: "bg-green-500/10 border-green-500/30",
  structure: "bg-purple-500/10 border-purple-500/30",
  precision: "bg-orange-500/10 border-orange-500/30",
};

// Step labels for the 3-step wizard
const STEP_LABELS = ["Focus", "Reflect", "Practice"];

/**
 * Training Page - Streamlined 3-Step Wizard
 * 
 * 1. Focus - Your weakness + pattern + rules (combined view)
 * 2. Reflect - Review critical moments from last game
 * 3. Practice - Training drills
 */
const Training = ({ user }) => {
  const navigate = useNavigate();
  const boardRef = useRef(null);

  // Core data states
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState(null);
  const [dataDrivenFocus, setDataDrivenFocus] = useState(null);
  const [regenerating, setRegenerating] = useState(false);

  // Step navigation (3 steps now)
  const [currentStep, setCurrentStep] = useState(0);
  const TOTAL_STEPS = 3;
  
  // View mode: "training" or "history"
  const [viewMode, setViewMode] = useState("training");
  
  // History & AI Insights state
  const [reflectionHistory, setReflectionHistory] = useState(null);
  const [aiInsights, setAiInsights] = useState(null);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [loadingInsights, setLoadingInsights] = useState(false);

  // Board state
  const [currentExampleIndex, setCurrentExampleIndex] = useState(0);
  const [exampleExplanation, setExampleExplanation] = useState(null);
  const [loadingExampleExplanation, setLoadingExampleExplanation] = useState(false);

  // Reflection state
  const [gameMilestones, setGameMilestones] = useState([]);
  const [currentMilestoneIndex, setCurrentMilestoneIndex] = useState(0);
  const [loadingMilestones, setLoadingMilestones] = useState(false);
  const [milestoneExplanation, setMilestoneExplanation] = useState(null);
  const [loadingExplanation, setLoadingExplanation] = useState(false);
  const [milestoneSelectedTags, setMilestoneSelectedTags] = useState({});
  const [milestoneUserPlans, setMilestoneUserPlans] = useState({});
  const [savingReflection, setSavingReflection] = useState(false);
  const [userPlayingColor, setUserPlayingColor] = useState("white");
  
  // Plan mode state
  const [isPlanMode, setIsPlanMode] = useState(false);
  const [planMoves, setPlanMoves] = useState([]);
  const [generatingPlanText, setGeneratingPlanText] = useState(false);
  const [boardMode, setBoardMode] = useState("position");
  const [betterLineIndex, setBetterLineIndex] = useState(0);

  // Drills state
  const [drills, setDrills] = useState([]);
  const [loadingDrills, setLoadingDrills] = useState(false);
  const [currentDrillIndex, setCurrentDrillIndex] = useState(0);

  // Derived state
  const examplePositions = profile?.example_positions || [];
  const currentExample = examplePositions[currentExampleIndex] || null;

  // Fetch training profile and data-driven focus
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [profileRes, focusRes] = await Promise.all([
          fetch(`${API}/training/profile`, { credentials: "include" }),
          fetch(`${API}/training/data-driven`, { credentials: "include" })
        ]);
        
        if (profileRes.ok) {
          const profileData = await profileRes.json();
          setProfile(profileData);
        }
        
        if (focusRes.ok) {
          const focusData = await focusRes.json();
          setDataDrivenFocus(focusData);
        }
      } catch (err) {
        console.error("Error fetching training data:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  // Fetch milestones when on Reflect step
  useEffect(() => {
    const fetchMilestones = async () => {
      if (currentStep !== 1 || gameMilestones.length > 0) return;
      
      try {
        setLoadingMilestones(true);
        const lastGameRes = await fetch(`${API}/training/last-game-for-reflection`, { credentials: "include" });
        if (!lastGameRes.ok) return;
        const { game_id } = await lastGameRes.json();
        if (!game_id) return;
        
        const res = await fetch(`${API}/training/game/${game_id}/milestones`, { credentials: "include" });
        if (res.ok) {
          const data = await res.json();
          setGameMilestones(data.milestones || []);
          if (data.user_color) setUserPlayingColor(data.user_color);
        }
      } catch (err) {
        console.error("Error fetching milestones:", err);
      } finally {
        setLoadingMilestones(false);
      }
    };

    fetchMilestones();
  }, [currentStep, gameMilestones.length]);

  // Fetch explanation when milestone changes
  useEffect(() => {
    const fetchExplanation = async () => {
      if (currentStep !== 1 || gameMilestones.length === 0) return;
      
      const milestone = gameMilestones[currentMilestoneIndex];
      if (!milestone) return;
      
      try {
        setLoadingExplanation(true);
        setMilestoneExplanation(null);
        
        const res = await fetch(`${API}/training/milestone/explain`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            context_for_explanation: milestone.context_for_explanation,
            fen: milestone.fen,
            move_played: milestone.user_move,
            best_move: milestone.best_move,
          }),
        });
        
        if (res.ok) {
          const data = await res.json();
          setMilestoneExplanation(data);
        }
      } catch (err) {
        console.error("Error fetching explanation:", err);
      } finally {
        setLoadingExplanation(false);
      }
    };

    fetchExplanation();
  }, [currentStep, currentMilestoneIndex, gameMilestones]);

  // Fetch drills when on Practice step
  useEffect(() => {
    const fetchDrills = async () => {
      if (currentStep !== 2 || drills.length > 0) return;
      
      try {
        setLoadingDrills(true);
        const res = await fetch(`${API}/training/drills?limit=5`, { credentials: "include" });
        if (res.ok) {
          const data = await res.json();
          setDrills(data.drills || []);
        }
      } catch (err) {
        console.error("Error fetching drills:", err);
      } finally {
        setLoadingDrills(false);
      }
    };

    fetchDrills();
  }, [currentStep, drills.length]);

  // Fetch reflection history
  useEffect(() => {
    const fetchHistory = async () => {
      if (viewMode !== "history" || reflectionHistory) return;
      
      try {
        setLoadingHistory(true);
        const res = await fetch(`${API}/training/reflection-history`, { credentials: "include" });
        if (res.ok) {
          const data = await res.json();
          setReflectionHistory(data);
        }
      } catch (err) {
        console.error("Error fetching history:", err);
      } finally {
        setLoadingHistory(false);
      }
    };

    fetchHistory();
  }, [viewMode, reflectionHistory]);

  // Fetch AI insights
  useEffect(() => {
    const fetchInsights = async () => {
      if (viewMode !== "history" || !reflectionHistory || aiInsights) return;
      if (reflectionHistory.total_reflections < 3) return;
      
      try {
        setLoadingInsights(true);
        const res = await fetch(`${API}/training/ai-insights`, { credentials: "include" });
        if (res.ok) {
          const data = await res.json();
          setAiInsights(data);
        }
      } catch (err) {
        console.error("Error fetching insights:", err);
      } finally {
        setLoadingInsights(false);
      }
    };

    fetchInsights();
  }, [viewMode, reflectionHistory, aiInsights]);

  // Draw arrows for example positions
  useEffect(() => {
    if (boardRef.current && currentExample?.best_move && currentExample?.move && currentExample?.fen) {
      try {
        const chess = new Chess(currentExample.fen);
        const arrows = [];
        
        // User's move (red)
        try {
          const userMove = chess.move(currentExample.move, { sloppy: true });
          if (userMove) {
            arrows.push([userMove.from, userMove.to, "rgba(239, 68, 68, 0.85)"]);
            chess.undo();
          }
        } catch (e) {}
        
        // Better move (blue)
        try {
          const bestMove = chess.move(currentExample.best_move, { sloppy: true });
          if (bestMove) {
            arrows.push([bestMove.from, bestMove.to, "rgba(59, 130, 246, 0.85)"]);
          }
        } catch (e) {}
        
        if (arrows.length > 0) {
          boardRef.current.drawArrows(arrows);
        }
      } catch (e) {
        boardRef.current.clearArrows?.();
      }
    }
  }, [currentExample, currentExampleIndex]);

  // Clear explanation when example changes
  useEffect(() => {
    setExampleExplanation(null);
  }, [currentExampleIndex]);

  // Regenerate profile
  const handleRegenerate = async () => {
    try {
      setRegenerating(true);
      const res = await fetch(`${API}/training/profile/regenerate`, {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) throw new Error("Failed to regenerate");
      const data = await res.json();
      setProfile(data);
      toast.success("Training profile updated!");
    } catch (err) {
      toast.error("Failed to regenerate profile");
    } finally {
      setRegenerating(false);
    }
  };

  // Navigation
  const nextStep = () => setCurrentStep((s) => Math.min(s + 1, TOTAL_STEPS - 1));
  const prevStep = () => setCurrentStep((s) => Math.max(s - 1, 0));

  // Fetch example explanation
  const fetchExampleExplanation = async (example) => {
    if (!example) return;
    setLoadingExampleExplanation(true);
    setExampleExplanation(null);
    
    try {
      const res = await fetch(`${API}/training/milestone/explain`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fen: example.fen,
          move_played: example.move,
          best_move: example.best_move,
          cp_loss: example.cp_loss,
        }),
      });
      
      if (res.ok) {
        const data = await res.json();
        setExampleExplanation(data.human_explanation || data.explanation || "This move was a mistake.");
      }
    } catch (err) {
      setExampleExplanation("Unable to generate explanation.");
    } finally {
      setLoadingExampleExplanation(false);
    }
  };

  // Loading state
  if (loading) {
    return (
      <Layout user={user}>
        <div className="min-h-screen flex items-center justify-center">
          <div className="text-center">
            <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4 text-primary" />
            <p className="text-muted-foreground">Analyzing your games...</p>
          </div>
        </div>
      </Layout>
    );
  }

  // Insufficient data state
  if (profile?.status === "insufficient_data") {
    return (
      <Layout user={user}>
        <div className="min-h-screen flex items-center justify-center p-4">
          <Card className="max-w-md w-full">
            <CardContent className="pt-6 text-center">
              <AlertTriangle className="w-12 h-12 mx-auto mb-4 text-amber-500" />
              <h2 className="text-xl font-semibold mb-2">More Games Needed</h2>
              <p className="text-muted-foreground mb-4">
                We need at least {profile.games_required} analyzed games to build your personalized training.
                You have {profile.games_analyzed} so far.
              </p>
              <Button onClick={() => navigate("/import")} className="gap-2">
                <Play className="w-4 h-4" />
                Import Games
              </Button>
            </CardContent>
          </Card>
        </div>
      </Layout>
    );
  }

  // Step indicator
  const renderStepIndicator = () => (
    <div className="flex items-center justify-center gap-1 mb-6">
      {STEP_LABELS.map((label, idx) => (
        <button
          key={idx}
          onClick={() => setCurrentStep(idx)}
          className={`flex items-center gap-2 px-4 py-2 rounded-full transition-all text-sm ${
            idx === currentStep
              ? "bg-primary text-primary-foreground"
              : idx < currentStep
              ? "bg-primary/20 text-primary"
              : "bg-muted text-muted-foreground"
          }`}
        >
          {idx < currentStep && <CheckCircle2 className="w-4 h-4" />}
          {label}
        </button>
      ))}
    </div>
  );

  // ============== STEP 1: FOCUS ==============
  const renderFocusStep = () => {
    const focus = dataDrivenFocus || profile;
    const activePhase = focus?.active_layer || focus?.active_phase;
    const LayerIcon = LAYER_ICONS[activePhase] || Target;
    const patternWeights = profile?.pattern_weights || {};
    const microHabit = profile?.micro_habit;
    const rules = focus?.rules || profile?.rules || [];
    
    return (
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: -20 }}
        className="space-y-6"
      >
        {/* Reflection Impact Banner */}
        {dataDrivenFocus?.reflection_adjusted && dataDrivenFocus?.reflection_count > 0 && (
          <Card className="bg-gradient-to-r from-amber-500/20 to-orange-500/20 border-amber-500/50">
            <CardContent className="py-3">
              <div className="flex items-center gap-3">
                <Brain className="w-5 h-5 text-amber-500" />
                <p className="text-sm">
                  <span className="font-medium text-amber-400">Training shaped by {dataDrivenFocus.reflection_count} reflections</span>
                </p>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Main Focus Card */}
        <Card className={`${LAYER_BG_COLORS[activePhase] || "bg-blue-500/10 border-blue-500/30"} border-2`}>
          <CardContent className="pt-5 space-y-4">
            {/* Layer Header */}
            <div className="flex items-start gap-3">
              <div className={`p-2 rounded-xl ${LAYER_BG_COLORS[activePhase] || "bg-blue-500/20"}`}>
                <LayerIcon className={`w-6 h-6 ${LAYER_COLORS[activePhase] || "text-blue-500"}`} />
              </div>
              <div className="flex-1">
                <Badge variant="outline" className="mb-1 text-xs">This Week's Focus</Badge>
                <h2 className="text-xl font-bold">{focus?.active_layer_label || profile?.active_phase_label}</h2>
                <p className="text-sm text-muted-foreground">{focus?.active_layer_description}</p>
              </div>
            </div>

            {/* Your Pattern */}
            <div className="bg-background/50 rounded-lg p-4 space-y-3">
              <div className="flex items-center gap-2">
                <Brain className="w-4 h-4 text-violet-500" />
                <span className="text-sm font-medium">Your Main Pattern</span>
              </div>
              <div>
                <p className="font-semibold text-lg text-violet-400">
                  {focus?.micro_habit_label || profile?.micro_habit_label}
                </p>
                <p className="text-sm text-muted-foreground mt-1">
                  {focus?.micro_habit_description || profile?.micro_habit_description}
                </p>
              </div>
              
              {/* Pattern strength */}
              {patternWeights[microHabit] && (
                <div className="pt-2">
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="text-muted-foreground">Pattern strength</span>
                    <span>{Math.round((patternWeights[microHabit] || 0) * 100)}%</span>
                  </div>
                  <Progress value={(patternWeights[microHabit] || 0) * 100} className="h-1.5" />
                </div>
              )}
            </div>

            {/* Your Rules */}
            {rules.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Your Rules</p>
                {rules.slice(0, 2).map((rule, idx) => (
                  <div key={idx} className="flex items-start gap-3 bg-amber-500/10 rounded-lg p-3">
                    <div className="flex items-center justify-center w-6 h-6 rounded-full bg-amber-500/20 text-amber-500 font-bold text-xs shrink-0">
                      {idx + 1}
                    </div>
                    <p className="text-sm leading-relaxed">{rule}</p>
                  </div>
                ))}
              </div>
            )}
            
            {/* Weakness Breakdown */}
            {dataDrivenFocus?.layer_breakdown && (
              <div className="pt-3 border-t border-border/50">
                <p className="text-xs text-muted-foreground mb-2">Where your mistakes happen:</p>
                <div className="grid grid-cols-4 gap-2">
                  {Object.entries(dataDrivenFocus.layer_breakdown).map(([layerId, layer]) => {
                    const LayerIconSmall = LAYER_ICONS[layerId] || Target;
                    const isActive = layerId === activePhase;
                    return (
                      <div 
                        key={layerId}
                        className={`p-2 rounded-lg text-center ${isActive ? LAYER_BG_COLORS[layerId] : 'bg-background/30'} ${isActive ? 'ring-1 ring-primary' : ''}`}
                      >
                        <LayerIconSmall className={`w-4 h-4 mx-auto mb-1 ${LAYER_COLORS[layerId]}`} />
                        <p className="text-xs text-muted-foreground">{layer.label?.split(' ')[0]}</p>
                        <p className="text-sm font-bold">{Math.round(layer.cost / 1000)}k</p>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Example Position */}
        {examplePositions.length > 0 && (
          <div className="space-y-3">
            <h3 className="text-sm font-medium text-muted-foreground">
              Example from Your Games (Move {currentExample?.move_number})
            </h3>
            <div className="flex justify-center">
              <div className="w-full max-w-sm">
                <CoachBoard
                  ref={boardRef}
                  position={currentExample?.fen || START_FEN}
                  userColor={currentExample?.fen?.includes(" b ") ? "black" : "white"}
                  interactive={false}
                  showControls={false}
                />
              </div>
            </div>
            
            {/* Arrow Legend */}
            <div className="text-center text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1 mr-4">
                <span className="w-3 h-0.5 bg-red-500 rounded"></span> Your move
              </span>
              <span className="inline-flex items-center gap-1">
                <span className="w-3 h-0.5 bg-blue-500 rounded"></span> Better move
              </span>
            </div>
            
            {/* Move Info */}
            <Card className="bg-red-500/10 border-red-500/30">
              <CardContent className="py-3 space-y-3">
                <div className="flex items-center justify-between text-sm">
                  <span>
                    <span className="text-red-400 font-medium">Played:</span>{" "}
                    <span className="font-mono">{currentExample?.move}</span>
                  </span>
                  <span>
                    <span className="text-blue-400 font-medium">Better:</span>{" "}
                    <span className="font-mono">{currentExample?.best_move}</span>
                  </span>
                </div>
                
                {!exampleExplanation && !loadingExampleExplanation && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full gap-2"
                    onClick={() => fetchExampleExplanation(currentExample)}
                  >
                    <Lightbulb className="w-4 h-4" />
                    Why is {currentExample?.best_move} better?
                  </Button>
                )}
                
                {loadingExampleExplanation && (
                  <div className="flex items-center justify-center py-2 text-sm text-muted-foreground">
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    Analyzing...
                  </div>
                )}
                
                {exampleExplanation && (
                  <div className="bg-background/50 rounded-lg p-3 text-sm">
                    <div className="flex items-start gap-2">
                      <Lightbulb className="w-4 h-4 text-yellow-500 mt-0.5 shrink-0" />
                      <p className="text-muted-foreground leading-relaxed">{exampleExplanation}</p>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
            
            {/* Example Navigation */}
            {examplePositions.length > 1 && (
              <div className="flex items-center justify-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setCurrentExampleIndex(i => Math.max(0, i - 1))}
                  disabled={currentExampleIndex === 0}
                >
                  <ChevronLeft className="w-4 h-4" />
                </Button>
                <span className="text-sm text-muted-foreground">
                  {currentExampleIndex + 1} / {examplePositions.length}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setCurrentExampleIndex(i => Math.min(examplePositions.length - 1, i + 1))}
                  disabled={currentExampleIndex >= examplePositions.length - 1}
                >
                  <ChevronRight className="w-4 h-4" />
                </Button>
              </div>
            )}
          </div>
        )}

        <div className="flex justify-end pt-4">
          <Button onClick={nextStep} className="gap-2" data-testid="focus-next-btn">
            Reflect on Last Game <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      </motion.div>
    );
  };

  // ============== STEP 2: REFLECT ==============
  const renderReflectStep = () => {
    const currentMilestone = gameMilestones[currentMilestoneIndex];
    const totalMilestones = gameMilestones.length;
    const currentTags = milestoneSelectedTags[currentMilestoneIndex] || [];
    const currentPlan = milestoneUserPlans[currentMilestoneIndex] || "";
    
    const toggleMilestoneTag = (tag) => {
      setMilestoneSelectedTags(prev => {
        const current = prev[currentMilestoneIndex] || [];
        const newTags = current.includes(tag) 
          ? current.filter(t => t !== tag)
          : [...current, tag];
        return { ...prev, [currentMilestoneIndex]: newTags };
      });
    };
    
    const updateMilestonePlan = (plan) => {
      setMilestoneUserPlans(prev => ({
        ...prev,
        [currentMilestoneIndex]: plan
      }));
    };
    
    // Plan mode handlers
    const startPlanMode = () => {
      setIsPlanMode(true);
      setPlanMoves([]);
      boardRef.current?.reset();
      boardRef.current?.startPlanMode();
    };
    
    const cancelPlanMode = () => {
      setIsPlanMode(false);
      setPlanMoves([]);
      boardRef.current?.stopPlanMode();
      boardRef.current?.reset();
    };
    
    const undoPlanMove = () => {
      const newMoves = boardRef.current?.undoPlanMove();
      if (newMoves) setPlanMoves(newMoves);
    };
    
    const finishPlan = async () => {
      if (planMoves.length === 0) {
        toast.error("Play at least one move to show your plan");
        return;
      }
      
      setGeneratingPlanText(true);
      try {
        const startFen = currentMilestone?.fen || START_FEN;
        const turnToMove = startFen.includes(" b ") ? "black" : "white";
        
        const res = await fetch(`${API}/training/plan/describe`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            fen: startFen,
            moves: planMoves,
            user_playing_color: userPlayingColor,
            turn_to_move: turnToMove,
            user_move: currentMilestone?.user_move,
            best_move: currentMilestone?.best_move,
          }),
        });
        
        const data = await res.json();
        if (data.plan_description) {
          updateMilestonePlan(data.plan_description);
          toast.success("Plan captured!");
        }
      } catch (err) {
        updateMilestonePlan(`My plan: ${planMoves.join(" ")}`);
      } finally {
        setGeneratingPlanText(false);
        setIsPlanMode(false);
        setPlanMoves([]);
        boardRef.current?.stopPlanMode();
        boardRef.current?.reset();
      }
    };
    
    const handlePlanMove = (moveData) => {
      setPlanMoves(moveData.allMoves);
    };
    
    // Save reflection
    const handleSaveMilestoneReflection = async () => {
      if (!currentMilestone) return;
      
      try {
        setSavingReflection(true);
        const gameIdRes = await fetch(`${API}/training/last-game-for-reflection`, { credentials: "include" });
        const { game_id } = await gameIdRes.json();
        
        await fetch(`${API}/training/milestone/reflect?game_id=${game_id}&move_number=${currentMilestone.move_number}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            selected_tags: currentTags,
            user_plan: currentPlan,
            understood: true,
            fen: currentMilestone.fen,
          }),
        });
        
        if (currentMilestoneIndex < totalMilestones - 1) {
          setCurrentMilestoneIndex(i => i + 1);
          setBoardMode("position");
          setBetterLineIndex(0);
          toast.success(`Saved! (${currentMilestoneIndex + 1}/${totalMilestones})`);
        } else {
          toast.success("All reflections saved!");
          setCurrentStep(2);
        }
      } catch (err) {
        toast.error("Failed to save reflection");
      } finally {
        setSavingReflection(false);
      }
    };
    
    // Board interaction
    const showMyMove = () => {
      boardRef.current?.reset();
      boardRef.current?.clearArrows();
      setBoardMode("my_move");
      setTimeout(() => {
        boardRef.current?.playSingleMove(currentMilestone.user_move);
      }, 100);
    };
    
    const startBetterLine = () => {
      boardRef.current?.reset();
      boardRef.current?.clearArrows();
      setBoardMode("better_line");
      setBetterLineIndex(0);
    };
    
    const nextBetterMove = () => {
      const pvBest = currentMilestone?.pv_after_best || [];
      if (betterLineIndex < pvBest.length && boardRef.current) {
        boardRef.current.playSingleMove(pvBest[betterLineIndex]);
        setBetterLineIndex(i => i + 1);
      }
    };
    
    const prevBetterMove = () => {
      if (betterLineIndex > 0 && boardRef.current) {
        boardRef.current.undoMove();
        setBetterLineIndex(i => i - 1);
      }
    };
    
    const resetBoard = () => {
      boardRef.current?.reset();
      boardRef.current?.clearArrows();
      setBoardMode("position");
      setBetterLineIndex(0);
    };
    
    // Loading state
    if (loadingMilestones) {
      return (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center justify-center py-20">
          <div className="text-center">
            <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4 text-primary" />
            <p className="text-muted-foreground">Loading your last game...</p>
          </div>
        </motion.div>
      );
    }
    
    // No milestones
    if (gameMilestones.length === 0) {
      return (
        <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} className="space-y-6">
          <div className="text-center py-12">
            <CheckCircle2 className="w-12 h-12 mx-auto mb-4 text-green-500" />
            <h2 className="text-2xl font-bold mb-2">Great Game!</h2>
            <p className="text-muted-foreground mb-6">No significant mistakes found in your last game.</p>
            <Button onClick={() => setCurrentStep(2)} className="gap-2">
              Continue to Practice <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        </motion.div>
      );
    }
    
    return (
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: -20 }}
        className="space-y-4"
      >
        {/* Header */}
        <div className="text-center mb-2">
          <Badge variant="outline" className="mb-2">
            Position {currentMilestoneIndex + 1} of {totalMilestones}
          </Badge>
          <h1 className="text-xl font-bold">Reflect on Your Moves</h1>
        </div>

        {/* Board */}
        {currentMilestone && (
          <div className="space-y-3">
            <div className="flex items-center justify-between px-2">
              <span className="text-sm text-muted-foreground">Move {currentMilestone.move_number}</span>
              <Badge variant={currentMilestone.evaluation_type === "blunder" ? "destructive" : "secondary"}>
                {currentMilestone.evaluation_type} (-{(currentMilestone.cp_loss / 100).toFixed(1)})
              </Badge>
            </div>
            
            <div className="flex justify-center">
              <div className="w-full max-w-sm">
                <CoachBoard
                  ref={boardRef}
                  position={currentMilestone.fen || START_FEN}
                  interactive={false}
                  showControls={true}
                  planMode={isPlanMode}
                  onPlanMove={handlePlanMove}
                />
              </div>
            </div>
            
            {/* Mode indicators */}
            {isPlanMode && (
              <div className="flex justify-center">
                <Badge variant="outline" className="bg-purple-500/10 text-purple-400 border-purple-500/30">
                  Plan Mode - Play your intended moves
                </Badge>
              </div>
            )}
            
            {boardMode !== "position" && !isPlanMode && (
              <div className="flex justify-center">
                <Badge variant="outline" className={`
                  ${boardMode === "my_move" ? "bg-red-500/10 text-red-400 border-red-500/30" : ""}
                  ${boardMode === "better_line" ? "bg-green-500/10 text-green-400 border-green-500/30" : ""}
                `}>
                  {boardMode === "my_move" && "Showing: Your Move"}
                  {boardMode === "better_line" && `Better Line: ${betterLineIndex}/${currentMilestone.pv_after_best?.length || 0}`}
                </Badge>
              </div>
            )}
            
            {/* Move cards */}
            <div className="grid grid-cols-2 gap-2 max-w-sm mx-auto">
              <Card 
                className={`bg-red-500/10 border-red-500/30 cursor-pointer hover:bg-red-500/20 ${boardMode === "my_move" ? "ring-2 ring-red-500" : ""}`}
                onClick={showMyMove}
              >
                <CardContent className="py-2 px-3">
                  <p className="text-xs text-red-400">You played</p>
                  <p className="font-mono font-bold">{currentMilestone.user_move}</p>
                </CardContent>
              </Card>
              <Card 
                className={`bg-green-500/10 border-green-500/30 cursor-pointer hover:bg-green-500/20 ${boardMode === "better_line" ? "ring-2 ring-green-500" : ""}`}
                onClick={startBetterLine}
              >
                <CardContent className="py-2 px-3">
                  <p className="text-xs text-green-400">Better was</p>
                  <p className="font-mono font-bold">{currentMilestone.best_move}</p>
                </CardContent>
              </Card>
            </div>
            
            {/* Board controls */}
            <div className="flex flex-wrap justify-center gap-2 max-w-sm mx-auto">
              {boardMode === "better_line" && currentMilestone.pv_after_best?.length > 0 && (
                <>
                  <Button variant="outline" size="sm" onClick={prevBetterMove} disabled={betterLineIndex === 0}>
                    <ChevronLeft className="w-4 h-4" />
                  </Button>
                  <Button variant="default" size="sm" onClick={nextBetterMove} 
                    disabled={betterLineIndex >= currentMilestone.pv_after_best.length} className="gap-1">
                    <Play className="w-3 h-3" /> Next
                  </Button>
                </>
              )}
              {boardMode !== "position" && (
                <Button variant="ghost" size="sm" onClick={resetBoard}>
                  <RotateCcw className="w-3 h-3 mr-1" /> Reset
                </Button>
              )}
            </div>
          </div>
        )}

        {/* Explanation */}
        <Card className="bg-gradient-to-r from-violet-500/10 to-purple-500/10 border-violet-500/30">
          <CardContent className="py-3">
            <div className="flex items-start gap-2">
              <Lightbulb className="w-5 h-5 text-violet-400 shrink-0 mt-0.5" />
              <div>
                <p className="text-xs text-violet-400 font-medium mb-1">Why is {currentMilestone?.best_move} better?</p>
                {loadingExplanation ? (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="w-4 h-4 animate-spin" /> Analyzing...
                  </div>
                ) : (
                  <p className="text-sm leading-relaxed">
                    {milestoneExplanation?.human_explanation || "Loading..."}
                  </p>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* User input */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="font-medium flex items-center gap-2 text-sm">
              <Brain className="w-4 h-4" />
              What were you thinking?
            </h3>
            {!isPlanMode && (
              <Button variant="outline" size="sm" onClick={startPlanMode} className="gap-1 text-xs h-7">
                <Play className="w-3 h-3" /> Show on board
              </Button>
            )}
          </div>
          
          {isPlanMode ? (
            <Card className="bg-purple-500/10 border-purple-500/30">
              <CardContent className="py-3 space-y-3">
                <p className="text-sm text-purple-300">Play moves to show your thinking</p>
                {planMoves.length > 0 && (
                  <div className="bg-background/50 rounded p-2">
                    <p className="text-xs text-muted-foreground mb-1">Your plan:</p>
                    <div className="flex flex-wrap gap-1">
                      {planMoves.map((move, i) => (
                        <span key={i} className="text-sm font-mono px-1.5 py-0.5 rounded bg-white/10">
                          {i % 2 === 0 && <span className="text-muted-foreground mr-1">{Math.floor(i/2) + 1}.</span>}
                          {move}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                <div className="flex gap-2">
                  <Button variant="ghost" size="sm" onClick={cancelPlanMode}>Cancel</Button>
                  <Button variant="ghost" size="sm" onClick={undoPlanMove} disabled={planMoves.length === 0}>
                    <RotateCcw className="w-3 h-3 mr-1" /> Undo
                  </Button>
                  <Button size="sm" onClick={finishPlan} disabled={generatingPlanText || planMoves.length === 0} className="gap-1">
                    {generatingPlanText ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle2 className="w-3 h-3" />}
                    Done
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : (
            <Textarea
              value={currentPlan}
              onChange={(e) => updateMilestonePlan(e.target.value)}
              placeholder="I was trying to..."
              className="min-h-[80px] resize-none"
            />
          )}
          
          {/* Quick tags */}
          {currentMilestone?.contextual_options?.length > 0 && (
            <div className="flex flex-wrap gap-2 pt-2">
              {currentMilestone.contextual_options.map((opt) => (
                <Button
                  key={opt.tag}
                  variant={currentTags.includes(opt.tag) ? "default" : "outline"}
                  size="sm"
                  className="text-xs h-auto py-1.5"
                  onClick={() => toggleMilestoneTag(opt.tag)}
                >
                  {opt.label}
                </Button>
              ))}
            </div>
          )}
        </div>

        {/* Navigation */}
        <div className="flex justify-between pt-4">
          <Button variant="ghost" onClick={prevStep} className="gap-2">
            <ChevronLeft className="w-4 h-4" /> Back
          </Button>
          <Button onClick={handleSaveMilestoneReflection} disabled={savingReflection} className="gap-2">
            {savingReflection ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            {currentMilestoneIndex < totalMilestones - 1 ? "Next Position" : "Continue to Practice"}
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      </motion.div>
    );
  };

  // ============== STEP 3: PRACTICE ==============
  const renderPracticeStep = () => {
    const currentDrill = drills[currentDrillIndex];
    
    if (loadingDrills) {
      return (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center justify-center py-20">
          <div className="text-center">
            <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4 text-primary" />
            <p className="text-muted-foreground">Loading drills...</p>
          </div>
        </motion.div>
      );
    }
    
    if (drills.length === 0) {
      return (
        <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} className="space-y-6">
          <div className="text-center py-12">
            <Dumbbell className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
            <h2 className="text-2xl font-bold mb-2">No Drills Available</h2>
            <p className="text-muted-foreground mb-6">Play more games and come back for targeted practice.</p>
            <Button onClick={() => navigate("/journey")} className="gap-2">
              <Play className="w-4 h-4" /> Back to Journey
            </Button>
          </div>
        </motion.div>
      );
    }
    
    return (
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: -20 }}
        className="space-y-6"
      >
        <div className="text-center mb-4">
          <Badge variant="outline" className="mb-2">
            Drill {currentDrillIndex + 1} of {drills.length}
          </Badge>
          <h1 className="text-xl font-bold">Practice Position</h1>
          <p className="text-sm text-muted-foreground">Find the best move</p>
        </div>

        {currentDrill && (
          <div className="space-y-4">
            <div className="flex justify-center">
              <div className="w-full max-w-sm">
                <CoachBoard
                  ref={boardRef}
                  position={currentDrill.fen || START_FEN}
                  userColor={currentDrill.fen?.includes(" b ") ? "black" : "white"}
                  interactive={true}
                  showControls={true}
                />
              </div>
            </div>
            
            {currentDrill.hint && (
              <Card className="bg-amber-500/10 border-amber-500/30">
                <CardContent className="py-3">
                  <div className="flex items-start gap-2">
                    <Lightbulb className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
                    <p className="text-sm">{currentDrill.hint}</p>
                  </div>
                </CardContent>
              </Card>
            )}
            
            {/* Drill navigation */}
            <div className="flex items-center justify-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setCurrentDrillIndex(i => Math.max(0, i - 1))}
                disabled={currentDrillIndex === 0}
              >
                <ChevronLeft className="w-4 h-4" />
              </Button>
              <span className="text-sm text-muted-foreground">
                {currentDrillIndex + 1} / {drills.length}
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setCurrentDrillIndex(i => Math.min(drills.length - 1, i + 1))}
                disabled={currentDrillIndex >= drills.length - 1}
              >
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
        )}

        <div className="flex justify-between pt-4">
          <Button variant="ghost" onClick={prevStep} className="gap-2">
            <ChevronLeft className="w-4 h-4" /> Back
          </Button>
          <Button onClick={() => navigate("/journey")} className="gap-2">
            <CheckCircle2 className="w-4 h-4" /> Done Training
          </Button>
        </div>
      </motion.div>
    );
  };

  // ============== HISTORY VIEW ==============
  const renderHistoryView = () => {
    if (loadingHistory) {
      return (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      );
    }
    
    if (!reflectionHistory || reflectionHistory.total_reflections === 0) {
      return (
        <div className="text-center py-12">
          <History className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
          <h2 className="text-xl font-bold mb-2">No Reflections Yet</h2>
          <p className="text-muted-foreground">Complete your first training session to see your history here.</p>
        </div>
      );
    }
    
    return (
      <div className="space-y-6">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-2">Your Reflection History</h1>
          <p className="text-muted-foreground">
            {reflectionHistory.total_reflections} reflections across {reflectionHistory.unique_games || 0} games
          </p>
        </div>
        
        {/* AI Insights */}
        {aiInsights && (
          <Card className="bg-gradient-to-r from-violet-500/10 to-purple-500/10 border-violet-500/30">
            <CardContent className="py-4">
              <div className="flex items-start gap-3">
                <Brain className="w-5 h-5 text-violet-400 mt-0.5" />
                <div>
                  <h3 className="font-medium text-violet-300 mb-2">AI Analysis of Your Patterns</h3>
                  <p className="text-sm text-muted-foreground">{aiInsights.analysis}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
        
        {loadingInsights && reflectionHistory.total_reflections >= 3 && (
          <div className="flex items-center justify-center py-4 text-sm text-muted-foreground">
            <Loader2 className="w-4 h-4 animate-spin mr-2" />
            Generating AI insights...
          </div>
        )}
        
        {/* Pattern breakdown */}
        {reflectionHistory.patterns && Object.keys(reflectionHistory.patterns).length > 0 && (
          <Card>
            <CardContent className="pt-4">
              <h3 className="font-medium mb-3">Your Patterns</h3>
              <div className="space-y-3">
                {Object.entries(reflectionHistory.patterns)
                  .sort(([, a], [, b]) => b - a)
                  .slice(0, 5)
                  .map(([pattern, count]) => (
                    <div key={pattern} className="space-y-1">
                      <div className="flex items-center justify-between text-sm">
                        <span>{pattern.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}</span>
                        <span className="text-muted-foreground">{count}x</span>
                      </div>
                      <Progress value={(count / reflectionHistory.total_reflections) * 100} className="h-1.5" />
                    </div>
                  ))}
              </div>
            </CardContent>
          </Card>
        )}
        
        {/* Recent reflections */}
        {reflectionHistory.recent && reflectionHistory.recent.length > 0 && (
          <Card>
            <CardContent className="pt-4">
              <h3 className="font-medium mb-3">Recent Reflections</h3>
              <div className="space-y-3">
                {reflectionHistory.recent.slice(0, 5).map((ref, idx) => (
                  <div key={idx} className="p-3 bg-muted/30 rounded-lg">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-muted-foreground">Move {ref.move_number}</span>
                      <Badge variant="outline" className="text-xs">{ref.evaluation_type}</Badge>
                    </div>
                    {ref.user_plan && (
                      <p className="text-sm italic">"{ref.user_plan}"</p>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    );
  };

  // Step renderers array
  const STEP_RENDERERS = [renderFocusStep, renderReflectStep, renderPracticeStep];

  // Main render
  return (
    <Layout user={user}>
      <div className="min-h-screen py-8 px-4">
        <div className="max-w-2xl mx-auto">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-sm font-medium text-muted-foreground">Training</h2>
            <div className="flex items-center gap-2">
              <Button
                variant={viewMode === "history" ? "default" : "ghost"}
                size="sm"
                onClick={() => setViewMode(viewMode === "history" ? "training" : "history")}
                className="gap-2"
              >
                {viewMode === "history" ? (
                  <><Target className="w-4 h-4" /> Training</>
                ) : (
                  <><History className="w-4 h-4" /> History</>
                )}
              </Button>
              {viewMode === "training" && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleRegenerate}
                  disabled={regenerating}
                >
                  {regenerating ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                </Button>
              )}
            </div>
          </div>

          {/* Content */}
          {viewMode === "history" ? (
            renderHistoryView()
          ) : (
            <>
              {renderStepIndicator()}
              <AnimatePresence mode="wait">
                {STEP_RENDERERS[currentStep]()}
              </AnimatePresence>
            </>
          )}
        </div>
      </div>
    </Layout>
  );
};

export default Training;
