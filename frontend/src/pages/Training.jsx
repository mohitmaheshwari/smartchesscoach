import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import CoachBoard from "@/components/CoachBoard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
  MessageSquare,
  Zap,
  Eye,
  History,
  BarChart3,
  ArrowRight,
} from "lucide-react";

const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

// Layer icons
const LAYER_ICONS = {
  stability: Shield,
  conversion: TrendingUp,
  structure: Layers,
  precision: Crosshair,
};

// Layer colors
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

// Constants
const CLEAN_GAMES_FOR_GRADUATION = 3;

/**
 * Training Page - Adaptive Behavioral Correction System
 * 
 * Step-by-step flow:
 * 1. Phase Context - Show which layer is their biggest leak
 * 2. Micro Habit - The specific pattern within the phase
 * 3. Your Rules - 2 actionable rules for the week
 * 4. Reflection - Tag what happened in last game
 * 5. Training Drill - Practice position
 */
const Training = ({ user }) => {
  const navigate = useNavigate();
  const boardRef = useRef(null);

  // Data states
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState(null);
  const [regenerating, setRegenerating] = useState(false);

  // Step navigation
  const [currentStep, setCurrentStep] = useState(0);
  const TOTAL_STEPS = 5;
  
  // View mode: "training" or "history"
  const [viewMode, setViewMode] = useState("training");
  
  // History & AI Insights state
  const [reflectionHistory, setReflectionHistory] = useState(null);
  const [aiInsights, setAiInsights] = useState(null);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [loadingInsights, setLoadingInsights] = useState(false);
  
  // Phase Progress state
  const [phaseProgress, setPhaseProgress] = useState(null);
  const [loadingProgress, setLoadingProgress] = useState(false);
  const [graduationMessage, setGraduationMessage] = useState(null);

  // Board state
  const [currentFen, setCurrentFen] = useState(START_FEN);
  const [currentDrillIndex, setCurrentDrillIndex] = useState(0);
  const [currentExampleIndex, setCurrentExampleIndex] = useState(0);

  // Reflection state - Enhanced
  const [reflectionOptions, setReflectionOptions] = useState([]);
  const [selectedTags, setSelectedTags] = useState([]);
  const [reflectionText, setReflectionText] = useState("");
  const [savingReflection, setSavingReflection] = useState(false);
  
  // Enhanced reflection state
  const [gameMilestones, setGameMilestones] = useState([]);
  const [currentMilestoneIndex, setCurrentMilestoneIndex] = useState(0);
  const [loadingMilestones, setLoadingMilestones] = useState(false);
  const [milestoneExplanation, setMilestoneExplanation] = useState(null);
  const [loadingExplanation, setLoadingExplanation] = useState(false);
  const [userPlan, setUserPlan] = useState("");
  const [milestoneSelectedTags, setMilestoneSelectedTags] = useState({});
  const [milestoneUserPlans, setMilestoneUserPlans] = useState({});
  const [showBetterLine, setShowBetterLine] = useState(false);
  const [variationIndex, setVariationIndex] = useState(0);
  const [boardMode, setBoardMode] = useState("position"); // "position" | "my_move" | "threat" | "better_line"
  const [betterLineIndex, setBetterLineIndex] = useState(0);

  // Drills state
  const [drills, setDrills] = useState([]);
  const [loadingDrills, setLoadingDrills] = useState(false);

  // Fetch training profile
  useEffect(() => {
    const fetchProfile = async () => {
      try {
        setLoading(true);
        const res = await fetch(`${API}/training/profile`, { credentials: "include" });
        if (!res.ok) throw new Error("Failed to fetch training profile");
        const data = await res.json();
        setProfile(data);

        // Set initial board position if example positions exist
        if (data.example_positions && data.example_positions.length > 0) {
          setCurrentFen(data.example_positions[0].fen || START_FEN);
        }
      } catch (err) {
        console.error("Error fetching profile:", err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchProfile();
  }, []);

  // Fetch phase progress when profile is loaded (auto-graduation happens here)
  useEffect(() => {
    const fetchPhaseProgress = async () => {
      if (!profile) return;
      
      try {
        setLoadingProgress(true);
        const res = await fetch(`${API}/training/phase-progress`, { credentials: "include" });
        if (res.ok) {
          const data = await res.json();
          setPhaseProgress(data);
          
          // Check if auto-graduated
          if (data.graduated) {
            setGraduationMessage(data.graduated.message);
            toast.success(data.graduated.message);
            // Refresh profile after graduation
            const newProfileRes = await fetch(`${API}/training/profile`, { credentials: "include" });
            if (newProfileRes.ok) {
              setProfile(await newProfileRes.json());
            }
          }
        }
      } catch (err) {
        console.error("Error fetching phase progress:", err);
      } finally {
        setLoadingProgress(false);
      }
    };

    fetchPhaseProgress();
  }, [profile?.active_phase]);

  // Fetch reflection options
  useEffect(() => {
    const fetchReflectionOptions = async () => {
      try {
        const res = await fetch(`${API}/training/reflection-options`, { credentials: "include" });
        if (res.ok) {
          const data = await res.json();
          setReflectionOptions(data.options || []);
        }
      } catch (err) {
        console.error("Error fetching reflection options:", err);
      }
    };

    fetchReflectionOptions();
  }, []);

  // Fetch game milestones when reaching reflection step (step 4)
  useEffect(() => {
    const fetchMilestones = async () => {
      if (currentStep !== 3 || gameMilestones.length > 0) return;
      
      try {
        setLoadingMilestones(true);
        
        // First get the last game ID
        const lastGameRes = await fetch(`${API}/training/last-game-for-reflection`, { credentials: "include" });
        if (!lastGameRes.ok) return;
        const { game_id } = await lastGameRes.json();
        if (!game_id) return;
        
        // Then fetch milestones for that game
        const res = await fetch(`${API}/training/game/${game_id}/milestones`, { credentials: "include" });
        if (res.ok) {
          const data = await res.json();
          setGameMilestones(data.milestones || []);
          // Reset state for new milestones
          setCurrentMilestoneIndex(0);
          setMilestoneSelectedTags({});
          setMilestoneUserPlans({});
          setMilestoneExplanation(null);
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
      if (currentStep !== 3 || gameMilestones.length === 0) return;
      
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

  // Fetch reflection history when switching to history view
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
        console.error("Error fetching reflection history:", err);
      } finally {
        setLoadingHistory(false);
      }
    };

    fetchHistory();
  }, [viewMode, reflectionHistory]);

  // Fetch AI insights when on history view and history is loaded
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
        console.error("Error fetching AI insights:", err);
      } finally {
        setLoadingInsights(false);
      }
    };

    fetchInsights();
  }, [viewMode, reflectionHistory, aiInsights]);

  // Fetch drills when reaching step 5
  useEffect(() => {
    const fetchDrills = async () => {
      if (currentStep !== 4 || drills.length > 0) return;
      
      try {
        setLoadingDrills(true);
        const res = await fetch(`${API}/training/drills?limit=5`, { credentials: "include" });
        if (res.ok) {
          const data = await res.json();
          setDrills(data.drills || []);
          if (data.drills?.length > 0) {
            setCurrentFen(data.drills[0].fen || START_FEN);
          }
        }
      } catch (err) {
        console.error("Error fetching drills:", err);
      } finally {
        setLoadingDrills(false);
      }
    };

    fetchDrills();
  }, [currentStep, drills.length]);

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

  // Save reflection
  const handleSaveReflection = async () => {
    if (selectedTags.length === 0 && !reflectionText.trim()) {
      toast.error("Please select at least one tag or write a reflection");
      return;
    }

    try {
      setSavingReflection(true);
      // Get the last game ID from the profile
      const gameId = profile?.example_positions?.[0]?.game_id || "unknown";
      
      const res = await fetch(`${API}/training/reflection?game_id=${gameId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          selected_tags: selectedTags,
          free_text: reflectionText,
        }),
      });

      if (!res.ok) throw new Error("Failed to save reflection");
      
      toast.success("Reflection saved! Your training will adapt.");
      setCurrentStep(4); // Move to drills
    } catch (err) {
      toast.error("Failed to save reflection");
    } finally {
      setSavingReflection(false);
    }
  };

  // Navigation
  const nextStep = () => setCurrentStep((s) => Math.min(s + 1, TOTAL_STEPS - 1));
  const prevStep = () => setCurrentStep((s) => Math.max(s - 1, 0));

  // Toggle reflection tag
  const toggleTag = (tag) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
  };

  // Render loading state
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

  // Render insufficient data state
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

  // Step renderers
  const renderStepIndicator = () => (
    <div className="flex items-center justify-center gap-2 mb-8">
      {[0, 1, 2, 3, 4].map((step) => (
        <button
          key={step}
          onClick={() => setCurrentStep(step)}
          className={`w-3 h-3 rounded-full transition-all ${
            step === currentStep
              ? "bg-primary w-8"
              : step < currentStep
              ? "bg-primary/50"
              : "bg-muted"
          }`}
        />
      ))}
    </div>
  );

  // Step 1: Phase Context (Tier + Phase Progress) - Auto-graduating
  const renderPhaseStep = () => {
    const activePhase = profile?.active_phase;
    const LayerIcon = LAYER_ICONS[activePhase] || Target;
    const examplePositions = profile?.example_positions || [];
    const currentExample = examplePositions[currentExampleIndex];
    
    // New tier-based progress data
    const progress = phaseProgress || {};
    const tier = progress.tier_label || "Training";
    const tierRating = progress.tier_rating_range || [0, 0];
    const phase = progress.phase || {};
    const phaseIndex = progress.phase_index || 0;
    const totalPhases = progress.total_phases || 1;
    const stats = progress.stats || {};
    const progressPercent = progress.progress_percent || 0;
    const rating = progress.rating || 1200;
    
    return (
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: -20 }}
        className="space-y-5"
      >
        {/* Graduation Message */}
        {graduationMessage && (
          <Card className="bg-gradient-to-r from-green-500/20 to-emerald-500/20 border-green-500/50">
            <CardContent className="py-4">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-full bg-green-500/20">
                  <CheckCircle2 className="w-6 h-6 text-green-500" />
                </div>
                <div>
                  <p className="font-medium text-green-400">{graduationMessage}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Tier Header */}
        <div className="text-center mb-2">
          <Badge variant="outline" className="mb-2 text-amber-500 border-amber-500/50">
            {tier} Tier ({tierRating[0]}-{tierRating[1]} Rating)
          </Badge>
          <h1 className="text-2xl font-bold mb-1">Your Training Journey</h1>
          <p className="text-sm text-muted-foreground">
            Rating: {rating} • Phase {phaseIndex + 1} of {totalPhases}
          </p>
        </div>

        {/* Current Phase Card */}
        <Card className={`${LAYER_BG_COLORS[activePhase] || "bg-blue-500/10 border-blue-500/30"} border-2`}>
          <CardContent className="pt-5 space-y-4">
            <div className="flex items-start gap-3">
              <div className={`p-2 rounded-xl ${LAYER_BG_COLORS[activePhase] || "bg-blue-500/20"}`}>
                <LayerIcon className={`w-6 h-6 ${LAYER_COLORS[activePhase] || "text-blue-500"}`} />
              </div>
              <div className="flex-1">
                <h2 className="text-xl font-bold">{phase.label || "Training"}</h2>
                <p className="text-sm text-muted-foreground">{phase.description}</p>
                {phase.focus && (
                  <p className="text-xs mt-1 text-primary">Focus: {phase.focus}</p>
                )}
              </div>
            </div>
            
            {/* Progress Section */}
            {!loadingProgress && progress.games_played >= 0 && (
              <div className="pt-3 border-t border-border/50 space-y-3">
                {/* Progress Bar */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Progress</span>
                    <span className="font-medium">{progressPercent}%</span>
                  </div>
                  <Progress value={progressPercent} className="h-2" />
                </div>
                
                {/* Phase-Specific Stats */}
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="bg-background/50 rounded-lg p-2">
                    <p className="text-lg font-bold">{progress.games_played}/{progress.games_needed}</p>
                    <p className="text-xs text-muted-foreground">Games</p>
                  </div>
                  <div className="bg-background/50 rounded-lg p-2">
                    <p className="text-lg font-bold">{stats.clean_games || 0}/{CLEAN_GAMES_FOR_GRADUATION || 3}</p>
                    <p className="text-xs text-muted-foreground">Clean Games</p>
                  </div>
                  <div className={`bg-background/50 rounded-lg p-2 ${
                    stats.trend === "improving" ? "text-green-400" : 
                    stats.trend === "regressing" ? "text-red-400" : ""
                  }`}>
                    <p className="text-lg font-bold">{stats.trend_icon || "→"} {Math.abs(stats.improvement_percent || 0)}%</p>
                    <p className="text-xs text-muted-foreground capitalize">{stats.trend || "Stable"}</p>
                  </div>
                </div>
                
                {/* Phase-Specific Metric */}
                {stats.stat_description && (
                  <div className="bg-background/50 rounded-lg p-2 text-center">
                    <p className="text-sm">
                      <span className={stats.metric_value <= (phase.target || 1) ? "text-green-400" : "text-amber-400"}>
                        {stats.stat_description}
                      </span>
                    </p>
                  </div>
                )}
                
                {/* Phase Roadmap */}
                <div className="pt-2">
                  <p className="text-xs text-muted-foreground mb-2">Your {tier} Journey:</p>
                  <div className="flex gap-1">
                    {Array.from({ length: totalPhases }).map((_, idx) => (
                      <div 
                        key={idx}
                        className={`flex-1 h-2 rounded-full ${
                          idx < phaseIndex ? "bg-green-500" :
                          idx === phaseIndex ? "bg-primary" :
                          "bg-muted"
                        }`}
                        title={`Phase ${idx + 1}`}
                      />
                    ))}
                  </div>
                </div>
              </div>
            )}
            
            {loadingProgress && (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
              </div>
            )}
          </CardContent>
        </Card>

        {/* Example Positions from Mistakes */}
        {examplePositions.length > 0 && (
          <div className="space-y-3">
            <h3 className="text-sm font-medium text-muted-foreground">
              Example Position (Move {currentExample?.move_number})
            </h3>
            <div className="flex justify-center">
              <div className="w-full max-w-sm">
                <CoachBoard
                  ref={boardRef}
                  position={currentExample?.fen || START_FEN}
                  onMove={() => {}}
                  interactive={false}
                  showControls={false}
                />
              </div>
            </div>
            <Card className="bg-red-500/10 border-red-500/30">
              <CardContent className="py-3">
                <div className="flex items-center justify-between text-sm">
                  <span>
                    <span className="text-red-400 font-medium">Played:</span>{" "}
                    <span className="font-mono">{currentExample?.move}</span>
                  </span>
                  <span>
                    <span className="text-green-400 font-medium">Better:</span>{" "}
                    <span className="font-mono">{currentExample?.best_move}</span>
                  </span>
                </div>
              </CardContent>
            </Card>
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

        {/* Layer Breakdown */}
        <div className="grid grid-cols-2 gap-3">
          {Object.entries(profile?.layer_breakdown || {}).map(([phase, data]) => {
            const Icon = LAYER_ICONS[phase] || Target;
            const isActive = data.is_active;
            return (
              <div
                key={phase}
                className={`p-4 rounded-lg border transition-all ${
                  isActive
                    ? LAYER_BG_COLORS[phase]
                    : "bg-muted/30 border-border/50 opacity-60"
                }`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <Icon className={`w-4 h-4 ${isActive ? LAYER_COLORS[phase] : "text-muted-foreground"}`} />
                  <span className={`font-medium ${isActive ? "" : "text-muted-foreground"}`}>
                    {data.label}
                  </span>
                </div>
                <div className="text-xs text-muted-foreground">
                  Cost: {Math.round(data.cost).toLocaleString()}
                </div>
              </div>
            );
          })}
        </div>

        <div className="flex justify-end">
          <Button onClick={nextStep} className="gap-2">
            See Your Pattern <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      </motion.div>
    );
  };

  // Step 2: Micro Habit
  const renderHabitStep = () => {
    const patternWeights = profile?.pattern_weights || {};
    const microHabit = profile?.micro_habit;
    
    return (
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: -20 }}
        className="space-y-6"
      >
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold mb-2">Your Pattern</h1>
          <p className="text-muted-foreground">
            Within {profile?.active_phase_label}, this is your dominant pattern
          </p>
        </div>

        {/* Main Pattern */}
        <Card className="bg-gradient-to-br from-violet-500/10 to-purple-500/10 border-violet-500/30 border-2">
          <CardContent className="pt-6">
            <div className="flex items-start gap-4">
              <div className="p-3 rounded-xl bg-violet-500/20">
                <Brain className="w-8 h-8 text-violet-500" />
              </div>
              <div className="flex-1">
                <h2 className="text-2xl font-bold mb-1">{profile?.micro_habit_label}</h2>
                <p className="text-muted-foreground">{profile?.micro_habit_description}</p>
                <div className="mt-4">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm text-muted-foreground">Pattern strength</span>
                    <span className="text-sm font-medium">
                      {Math.round((patternWeights[microHabit] || 0) * 100)}%
                    </span>
                  </div>
                  <Progress 
                    value={(patternWeights[microHabit] || 0) * 100} 
                    className="h-2"
                  />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* All Patterns */}
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-muted-foreground mb-3">All patterns in this phase</h3>
          {Object.entries(patternWeights)
            .sort(([, a], [, b]) => b - a)
            .map(([pattern, weight]) => (
              <div
                key={pattern}
                className={`flex items-center justify-between p-3 rounded-lg ${
                  pattern === microHabit
                    ? "bg-violet-500/10 border border-violet-500/30"
                    : "bg-muted/30"
                }`}
              >
                <span className={pattern === microHabit ? "font-medium" : "text-muted-foreground"}>
                  {pattern.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())}
                </span>
                <span className="text-sm">{Math.round(weight * 100)}%</span>
              </div>
            ))}
        </div>

        <div className="flex justify-between">
          <Button variant="ghost" onClick={prevStep} className="gap-2">
            <ChevronLeft className="w-4 h-4" /> Back
          </Button>
          <Button onClick={nextStep} className="gap-2">
            See Your Rules <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      </motion.div>
    );
  };

  // Step 3: Rules
  const renderRulesStep = () => {
    const rules = profile?.rules || [];
    
    return (
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: -20 }}
        className="space-y-6"
      >
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold mb-2">Your 2 Rules</h1>
          <p className="text-muted-foreground">
            Focus on these in every game this week
          </p>
        </div>

        <div className="space-y-4">
          {rules.map((rule, idx) => (
            <Card key={idx} className="bg-gradient-to-r from-amber-500/10 to-orange-500/10 border-amber-500/30">
              <CardContent className="py-5">
                <div className="flex items-start gap-4">
                  <div className="flex items-center justify-center w-10 h-10 rounded-full bg-amber-500/20 text-amber-500 font-bold text-lg shrink-0">
                    {idx + 1}
                  </div>
                  <p className="text-lg leading-relaxed">{rule}</p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        <Card className="bg-muted/30">
          <CardContent className="py-4">
            <div className="flex items-start gap-3">
              <Lightbulb className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
              <p className="text-sm text-muted-foreground">
                <strong>Tip:</strong> Write these rules on a sticky note and put it next to your screen.
                One focus at a time builds lasting improvement.
              </p>
            </div>
          </CardContent>
        </Card>

        <div className="flex justify-between">
          <Button variant="ghost" onClick={prevStep} className="gap-2">
            <ChevronLeft className="w-4 h-4" /> Back
          </Button>
          <Button onClick={nextStep} className="gap-2">
            Reflect on Last Game <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      </motion.div>
    );
  };

  // Step 4: Enhanced Reflection - Per Position with Context
  const renderReflectionStep = () => {
    const currentMilestone = gameMilestones[currentMilestoneIndex];
    const totalMilestones = gameMilestones.length;
    
    // Get current milestone's selected tags
    const currentTags = milestoneSelectedTags[currentMilestoneIndex] || [];
    const currentPlan = milestoneUserPlans[currentMilestoneIndex] || "";
    
    // Toggle tag for current milestone
    const toggleMilestoneTag = (tag) => {
      setMilestoneSelectedTags(prev => {
        const current = prev[currentMilestoneIndex] || [];
        const newTags = current.includes(tag) 
          ? current.filter(t => t !== tag)
          : [...current, tag];
        return { ...prev, [currentMilestoneIndex]: newTags };
      });
    };
    
    // Update plan for current milestone
    const updateMilestonePlan = (plan) => {
      setMilestoneUserPlans(prev => ({
        ...prev,
        [currentMilestoneIndex]: plan
      }));
    };
    
    // Save current milestone reflection and move to next
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
        
        // Move to next milestone or finish
        if (currentMilestoneIndex < totalMilestones - 1) {
          setCurrentMilestoneIndex(i => i + 1);
          setBoardMode("position");
          setBetterLineIndex(0);
          toast.success(`Reflection saved! (${currentMilestoneIndex + 1}/${totalMilestones})`);
        } else {
          toast.success("All reflections saved!");
          setCurrentStep(4); // Move to drills
        }
      } catch (err) {
        toast.error("Failed to save reflection");
      } finally {
        setSavingReflection(false);
      }
    };
    
    // Board interaction handlers
    const showMyMove = () => {
      if (!boardRef.current || !currentMilestone) return;
      boardRef.current.reset();
      boardRef.current.clearArrows();
      setBoardMode("my_move");
      // Play the user's move
      setTimeout(() => {
        boardRef.current.playSingleMove(currentMilestone.user_move);
      }, 100);
    };
    
    const showThreat = () => {
      if (!boardRef.current || !currentMilestone?.threat) return;
      boardRef.current.reset();
      setBoardMode("threat");
      // Show threat arrow
      setTimeout(() => {
        boardRef.current.showThreat(currentMilestone.threat);
      }, 100);
    };
    
    const startBetterLine = () => {
      if (!boardRef.current) return;
      boardRef.current.reset();
      boardRef.current.clearArrows();
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
      if (!boardRef.current) return;
      boardRef.current.reset();
      boardRef.current.clearArrows();
      setBoardMode("position");
      setBetterLineIndex(0);
    };
    
    // Loading state
    if (loadingMilestones) {
      return (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex items-center justify-center py-20"
        >
          <div className="text-center">
            <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4 text-primary" />
            <p className="text-muted-foreground">Loading your game for reflection...</p>
          </div>
        </motion.div>
      );
    }
    
    // No milestones state
    if (gameMilestones.length === 0) {
      return (
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          className="space-y-6"
        >
          <div className="text-center py-12">
            <CheckCircle2 className="w-12 h-12 mx-auto mb-4 text-green-500" />
            <h2 className="text-2xl font-bold mb-2">Great Game!</h2>
            <p className="text-muted-foreground mb-6">
              No significant mistakes found in your last game at your level.
            </p>
            <Button onClick={() => setCurrentStep(4)} className="gap-2">
              Continue to Drills <ChevronRight className="w-4 h-4" />
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
        {/* Header with progress */}
        <div className="text-center mb-4">
          <Badge variant="outline" className="mb-2">
            Position {currentMilestoneIndex + 1} of {totalMilestones}
          </Badge>
          <h1 className="text-2xl font-bold mb-1">Reflect on Your Moves</h1>
          <p className="text-sm text-muted-foreground">
            Let's understand what happened at each critical moment
          </p>
        </div>

        {/* Board with Position */}
        {currentMilestone && (
          <div className="space-y-3">
            <div className="flex items-center justify-between px-2">
              <span className="text-sm text-muted-foreground">
                Move {currentMilestone.move_number}
              </span>
              <Badge variant={currentMilestone.evaluation_type === "blunder" ? "destructive" : "secondary"}>
                {currentMilestone.evaluation_type} (-{(currentMilestone.cp_loss / 100).toFixed(1)})
              </Badge>
            </div>
            
            <div className="flex justify-center">
              <div className="w-full max-w-sm">
                <CoachBoard
                  ref={boardRef}
                  position={currentMilestone.fen || START_FEN}
                  onMove={() => {}}
                  interactive={false}
                  showControls={true}
                />
              </div>
            </div>
            
            {/* Board Mode Indicator */}
            {boardMode !== "position" && (
              <div className="flex justify-center">
                <Badge variant="outline" className={`
                  ${boardMode === "my_move" ? "bg-red-500/10 text-red-400 border-red-500/30" : ""}
                  ${boardMode === "threat" ? "bg-amber-500/10 text-amber-400 border-amber-500/30" : ""}
                  ${boardMode === "better_line" ? "bg-green-500/10 text-green-400 border-green-500/30" : ""}
                `}>
                  {boardMode === "my_move" && "Showing: Your Move"}
                  {boardMode === "threat" && "Showing: Opponent's Threat"}
                  {boardMode === "better_line" && `Better Line: ${betterLineIndex}/${currentMilestone.pv_after_best?.length || 0}`}
                </Badge>
              </div>
            )}
            
            {/* Move Info */}
            <div className="grid grid-cols-2 gap-2 max-w-sm mx-auto">
              <Card 
                className={`bg-red-500/10 border-red-500/30 cursor-pointer hover:bg-red-500/20 transition-colors ${boardMode === "my_move" ? "ring-2 ring-red-500" : ""}`}
                onClick={showMyMove}
              >
                <CardContent className="py-2 px-3">
                  <p className="text-xs text-red-400">You played (click to see)</p>
                  <p className="font-mono font-bold">{currentMilestone.user_move}</p>
                </CardContent>
              </Card>
              <Card 
                className={`bg-green-500/10 border-green-500/30 cursor-pointer hover:bg-green-500/20 transition-colors ${boardMode === "better_line" ? "ring-2 ring-green-500" : ""}`}
                onClick={startBetterLine}
              >
                <CardContent className="py-2 px-3">
                  <p className="text-xs text-green-400">Better was (click to play)</p>
                  <p className="font-mono font-bold">{currentMilestone.best_move}</p>
                </CardContent>
              </Card>
            </div>
            
            {/* Interactive Board Controls */}
            <div className="flex flex-wrap justify-center gap-2 max-w-sm mx-auto">
              {/* Show Threat Button */}
              {currentMilestone.threat && (
                <Button 
                  variant={boardMode === "threat" ? "default" : "outline"} 
                  size="sm" 
                  onClick={showThreat}
                  className="gap-1"
                >
                  <AlertTriangle className="w-3 h-3" />
                  Show Threat
                </Button>
              )}
              
              {/* Better Line Controls */}
              {boardMode === "better_line" && currentMilestone.pv_after_best?.length > 0 && (
                <>
                  <Button 
                    variant="outline" 
                    size="sm" 
                    onClick={prevBetterMove}
                    disabled={betterLineIndex === 0}
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </Button>
                  <Button 
                    variant="default" 
                    size="sm" 
                    onClick={nextBetterMove}
                    disabled={betterLineIndex >= currentMilestone.pv_after_best.length}
                    className="gap-1"
                  >
                    <Play className="w-3 h-3" />
                    Next
                  </Button>
                </>
              )}
              
              {/* Reset Button */}
              {boardMode !== "position" && (
                <Button 
                  variant="ghost" 
                  size="sm" 
                  onClick={resetBoard}
                >
                  <RotateCcw className="w-3 h-3 mr-1" />
                  Reset
                </Button>
              )}
            </div>
            
            {/* Threat Info Card */}
            {currentMilestone.threat && (
              <Card className={`bg-amber-500/10 border-amber-500/30 max-w-sm mx-auto cursor-pointer hover:bg-amber-500/20 transition-colors ${boardMode === "threat" ? "ring-2 ring-amber-500" : ""}`}
                onClick={showThreat}
              >
                <CardContent className="py-2 px-3">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-amber-500" />
                    <div>
                      <p className="text-xs text-amber-400">Opponent's threat (click to see)</p>
                      <p className="text-sm font-mono">{currentMilestone.threat}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {/* Why Better? - GPT Explanation */}
        <Card className="bg-gradient-to-r from-violet-500/10 to-purple-500/10 border-violet-500/30">
          <CardContent className="py-3">
            <div className="flex items-start gap-2">
              <Lightbulb className="w-5 h-5 text-violet-400 shrink-0 mt-0.5" />
              <div>
                <p className="text-xs text-violet-400 font-medium mb-1">Why is {currentMilestone?.best_move} better?</p>
                {loadingExplanation ? (
                  <div className="flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span className="text-sm text-muted-foreground">Analyzing...</span>
                  </div>
                ) : (
                  <p className="text-sm leading-relaxed">
                    {milestoneExplanation?.human_explanation || milestoneExplanation?.stockfish_analysis?.better_line || "Loading explanation..."}
                  </p>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* What was your plan? */}
        <div className="space-y-2">
          <h3 className="font-medium flex items-center gap-2">
            <Brain className="w-4 h-4" />
            What was your plan?
          </h3>
          <Textarea
            value={currentPlan}
            onChange={(e) => updateMilestonePlan(e.target.value)}
            placeholder="What were you thinking when you played this move?"
            rows={2}
            className="text-sm"
          />
        </div>

        {/* Contextual Tags */}
        <div className="space-y-2">
          <h3 className="font-medium">What happened?</h3>
          <div className="grid grid-cols-2 gap-2">
            {(currentMilestone?.reflection_options || []).map((option) => (
              <button
                key={option.tag}
                onClick={() => toggleMilestoneTag(option.tag)}
                className={`p-2 rounded-lg text-left transition-all border text-sm ${
                  currentTags.includes(option.tag)
                    ? "bg-primary/10 border-primary"
                    : "bg-muted/30 border-border hover:bg-muted/50"
                } ${option.contextual ? "border-l-2 border-l-amber-500" : ""}`}
              >
                <div className="flex items-center gap-2">
                  {currentTags.includes(option.tag) && (
                    <CheckCircle2 className="w-3 h-3 text-primary shrink-0" />
                  )}
                  <span className={currentTags.includes(option.tag) ? "font-medium" : ""}>
                    {option.label}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Navigation */}
        <div className="flex justify-between pt-2">
          <Button 
            variant="ghost" 
            onClick={() => {
              if (currentMilestoneIndex > 0) {
                setCurrentMilestoneIndex(i => i - 1);
                setShowBetterLine(false);
                setVariationIndex(0);
              } else {
                prevStep();
              }
            }} 
            className="gap-2"
          >
            <ChevronLeft className="w-4 h-4" /> 
            {currentMilestoneIndex > 0 ? "Previous" : "Back"}
          </Button>
          <Button
            onClick={handleSaveMilestoneReflection}
            disabled={savingReflection}
            className="gap-2"
          >
            {savingReflection ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : currentMilestoneIndex < totalMilestones - 1 ? (
              <>
                Save & Next
                <ChevronRight className="w-4 h-4" />
              </>
            ) : (
              <>
                <CheckCircle2 className="w-4 h-4" />
                Finish Reflection
              </>
            )}
          </Button>
        </div>

        <Button
          variant="link"
          onClick={() => setCurrentStep(4)}
          className="w-full text-muted-foreground text-sm"
        >
          Skip remaining reflections
        </Button>
      </motion.div>
    );
  };

  // Step 5: Training Drill
  const renderDrillStep = () => {
    const currentDrill = drills[currentDrillIndex];
    
    return (
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: -20 }}
        className="space-y-6"
      >
        <div className="text-center mb-6">
          <h1 className="text-3xl font-bold mb-2">Training Position</h1>
          <p className="text-muted-foreground">
            Practice recognizing {profile?.micro_habit_label?.toLowerCase()}
          </p>
        </div>

        {loadingDrills ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
          </div>
        ) : drills.length === 0 ? (
          <Card className="bg-muted/30">
            <CardContent className="py-8 text-center">
              <AlertTriangle className="w-8 h-8 mx-auto mb-3 text-amber-500" />
              <p className="text-muted-foreground">No drill positions available yet.</p>
              <p className="text-sm text-muted-foreground mt-1">Play more games to build your drill library!</p>
            </CardContent>
          </Card>
        ) : (
          <>
            {/* Board */}
            <div className="flex justify-center">
              <div className="w-full max-w-md">
                <CoachBoard
                  ref={boardRef}
                  position={currentDrill?.fen || START_FEN}
                  onMove={() => {}}
                  interactive={false}
                />
              </div>
            </div>

            {/* Drill Info */}
            <Card>
              <CardContent className="py-4">
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Position {currentDrillIndex + 1} of {drills.length}</span>
                    <Badge variant={currentDrill?.source === "own_game" ? "default" : "secondary"}>
                      {currentDrill?.source === "own_game" ? "Your Game" : "Similar Player"}
                    </Badge>
                  </div>
                  
                  <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30">
                    <p className="text-sm">
                      <span className="text-red-500 font-medium">Played:</span>{" "}
                      <span className="font-mono">{currentDrill?.user_move}</span>
                      <span className="text-muted-foreground"> (lost {currentDrill?.cp_loss} centipawns)</span>
                    </p>
                  </div>
                  
                  <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/30">
                    <p className="text-sm">
                      <span className="text-green-500 font-medium">Better:</span>{" "}
                      <span className="font-mono">{currentDrill?.correct_move}</span>
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Navigation */}
            <div className="flex items-center justify-between">
              <Button
                variant="ghost"
                onClick={() => {
                  const newIdx = Math.max(0, currentDrillIndex - 1);
                  setCurrentDrillIndex(newIdx);
                  if (drills[newIdx]) setCurrentFen(drills[newIdx].fen);
                }}
                disabled={currentDrillIndex === 0}
              >
                <ChevronLeft className="w-4 h-4" /> Previous
              </Button>
              <Button
                variant="ghost"
                onClick={() => {
                  const newIdx = Math.min(drills.length - 1, currentDrillIndex + 1);
                  setCurrentDrillIndex(newIdx);
                  if (drills[newIdx]) setCurrentFen(drills[newIdx].fen);
                }}
                disabled={currentDrillIndex >= drills.length - 1}
              >
                Next <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          </>
        )}

        <div className="flex justify-between pt-4 border-t">
          <Button variant="ghost" onClick={prevStep} className="gap-2">
            <ChevronLeft className="w-4 h-4" /> Back
          </Button>
          <Button onClick={() => navigate("/")} className="gap-2">
            Done <CheckCircle2 className="w-4 h-4" />
          </Button>
        </div>
      </motion.div>
    );
  };

  // Reflection History View
  const renderHistoryView = () => {
    const tagLabels = {
      missed_threat: "Missed Threat",
      piece_safety: "Piece Safety",
      lost_advantage: "Lost Advantage",
      time_pressure: "Time Pressure",
      saw_but_miscalculated: "Miscalculated",
      didnt_consider: "Didn't Consider",
      tunnel_vision: "Tunnel Vision",
      opening_unfamiliar: "Opening Unfamiliar",
      endgame_technique: "Endgame Technique",
    };

    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="space-y-6"
      >
        <div className="text-center mb-6">
          <h1 className="text-3xl font-bold mb-2">Your Reflection History</h1>
          <p className="text-muted-foreground">
            How your patterns have evolved over time
          </p>
        </div>

        {loadingHistory ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
          </div>
        ) : !reflectionHistory || reflectionHistory.total_reflections === 0 ? (
          <Card className="bg-muted/30">
            <CardContent className="py-8 text-center">
              <Brain className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
              <h3 className="font-medium mb-2">No Reflections Yet</h3>
              <p className="text-sm text-muted-foreground">
                Complete some reflections to see your thinking patterns evolve.
              </p>
              <Button 
                className="mt-4" 
                onClick={() => setViewMode("training")}
              >
                Start Reflecting
              </Button>
            </CardContent>
          </Card>
        ) : (
          <>
            {/* Stats Overview */}
            <div className="grid grid-cols-2 gap-3">
              <Card>
                <CardContent className="py-4 text-center">
                  <p className="text-3xl font-bold">{reflectionHistory.total_reflections}</p>
                  <p className="text-sm text-muted-foreground">Total Reflections</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="py-4 text-center">
                  <p className="text-3xl font-bold">{Object.keys(reflectionHistory.tag_counts || {}).length}</p>
                  <p className="text-sm text-muted-foreground">Patterns Identified</p>
                </CardContent>
              </Card>
            </div>

            {/* AI Insights Section */}
            <Card className="bg-gradient-to-r from-violet-500/10 to-purple-500/10 border-violet-500/30">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Lightbulb className="w-5 h-5 text-violet-400" />
                  AI Analysis of Your Patterns
                </CardTitle>
              </CardHeader>
              <CardContent>
                {loadingInsights ? (
                  <div className="flex items-center gap-2 py-4">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span className="text-sm text-muted-foreground">Analyzing your thinking patterns...</span>
                  </div>
                ) : aiInsights?.has_insights ? (
                  <div className="prose prose-sm prose-invert max-w-none">
                    <p className="text-sm leading-relaxed whitespace-pre-wrap">
                      {aiInsights.ai_analysis}
                    </p>
                  </div>
                ) : reflectionHistory.total_reflections < 3 ? (
                  <p className="text-sm text-muted-foreground">
                    Complete at least 3 reflections to unlock AI analysis of your thinking patterns.
                  </p>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    AI analysis unavailable. Try again later.
                  </p>
                )}
              </CardContent>
            </Card>

            {/* Top Patterns */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-lg">Your Most Common Patterns</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {(reflectionHistory.top_patterns || []).map(([tag, count], idx) => {
                    const percentage = reflectionHistory.tag_percentages?.[tag] || 0;
                    return (
                      <div key={tag} className="space-y-1">
                        <div className="flex items-center justify-between text-sm">
                          <span className="flex items-center gap-2">
                            {idx === 0 && <Badge variant="destructive" className="text-xs">Top</Badge>}
                            {tagLabels[tag] || tag}
                          </span>
                          <span className="text-muted-foreground">{count}x ({percentage}%)</span>
                        </div>
                        <Progress value={percentage} className="h-2" />
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>

            {/* Recent Reflections */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-lg">Recent Reflections</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4 max-h-80 overflow-y-auto">
                  {(reflectionHistory.reflections || []).slice(0, 10).map((r, idx) => (
                    <div key={idx} className="border-b border-border/50 pb-3 last:border-0">
                      <div className="flex items-center justify-between mb-2">
                        <Badge variant="outline">Move {r.move_number}</Badge>
                        <span className="text-xs text-muted-foreground">
                          {r.created_at ? new Date(r.created_at).toLocaleDateString() : ""}
                        </span>
                      </div>
                      {r.user_plan && (
                        <p className="text-sm italic text-muted-foreground mb-2">
                          "{r.user_plan}"
                        </p>
                      )}
                      <div className="flex flex-wrap gap-1">
                        {(r.selected_tags || []).map(tag => (
                          <Badge key={tag} variant="secondary" className="text-xs">
                            {tagLabels[tag] || tag}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Back to Training */}
            <Button 
              className="w-full" 
              variant="outline"
              onClick={() => setViewMode("training")}
            >
              <ChevronLeft className="w-4 h-4 mr-2" />
              Back to Training
            </Button>
          </>
        )}
      </motion.div>
    );
  };

  // Main render
  const STEP_RENDERERS = [
    renderPhaseStep,
    renderHabitStep,
    renderRulesStep,
    renderReflectionStep,
    renderDrillStep,
  ];

  return (
    <Layout user={user}>
      <div className="min-h-screen py-8 px-4">
        <div className="max-w-2xl mx-auto">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-sm font-medium text-muted-foreground">Training Engine</h2>
            </div>
            <div className="flex items-center gap-2">
              {/* View Toggle */}
              <Button
                variant={viewMode === "history" ? "default" : "ghost"}
                size="sm"
                onClick={() => setViewMode(viewMode === "history" ? "training" : "history")}
                className="gap-2"
              >
                {viewMode === "history" ? (
                  <>
                    <Target className="w-4 h-4" />
                    Training
                  </>
                ) : (
                  <>
                    <History className="w-4 h-4" />
                    History
                  </>
                )}
              </Button>
              {viewMode === "training" && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleRegenerate}
                  disabled={regenerating}
                  className="gap-2"
                >
                  {regenerating ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <RefreshCw className="w-4 h-4" />
                  )}
                  Refresh
                </Button>
              )}
            </div>
          </div>

          {/* Conditional Rendering: Training vs History */}
          {viewMode === "history" ? (
            renderHistoryView()
          ) : (
            <>
              {/* Step Indicator */}
              {renderStepIndicator()}

              {/* Step Content */}
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
