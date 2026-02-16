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
  MessageSquare,
  Zap,
  Eye,
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

  // Board state
  const [currentFen, setCurrentFen] = useState(START_FEN);
  const [currentDrillIndex, setCurrentDrillIndex] = useState(0);
  const [currentExampleIndex, setCurrentExampleIndex] = useState(0);

  // Reflection state
  const [reflectionOptions, setReflectionOptions] = useState([]);
  const [selectedTags, setSelectedTags] = useState([]);
  const [reflectionText, setReflectionText] = useState("");
  const [savingReflection, setSavingReflection] = useState(false);

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

  // Step 1: Phase Context (Weekly Focus)
  const renderPhaseStep = () => {
    const activePhase = profile?.active_phase;
    const LayerIcon = LAYER_ICONS[activePhase] || Target;
    const examplePositions = profile?.example_positions || [];
    const currentExample = examplePositions[currentExampleIndex];
    
    return (
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: -20 }}
        className="space-y-6"
      >
        <div className="text-center mb-8">
          <Badge variant="outline" className="mb-3 text-amber-500 border-amber-500/50">
            This Week's Focus
          </Badge>
          <h1 className="text-3xl font-bold mb-2">Your Training Phase</h1>
          <p className="text-muted-foreground">
            Based on your last {profile?.games_analyzed} games, focus on this for the week
          </p>
        </div>

        {/* Active Phase Card */}
        <Card className={`${LAYER_BG_COLORS[activePhase]} border-2`}>
          <CardContent className="pt-6">
            <div className="flex items-start gap-4">
              <div className={`p-3 rounded-xl ${LAYER_BG_COLORS[activePhase]}`}>
                <LayerIcon className={`w-8 h-8 ${LAYER_COLORS[activePhase]}`} />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <h2 className="text-2xl font-bold">{profile?.active_phase_label}</h2>
                  <Badge variant="secondary">Weekly Focus</Badge>
                </div>
                <p className="text-muted-foreground">{profile?.active_phase_description}</p>
              </div>
            </div>
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

  // Step 4: Reflection
  const renderReflectionStep = () => (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="space-y-6"
    >
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold mb-2">Quick Reflection</h1>
        <p className="text-muted-foreground">
          {profile?.reflection_question}
        </p>
      </div>

      {/* Tag Selection */}
      <div className="space-y-3">
        <h3 className="font-medium">What happened? (select all that apply)</h3>
        <div className="grid grid-cols-2 gap-2">
          {reflectionOptions.map((option) => (
            <button
              key={option.tag}
              onClick={() => toggleTag(option.tag)}
              className={`p-3 rounded-lg text-left transition-all border ${
                selectedTags.includes(option.tag)
                  ? "bg-primary/10 border-primary"
                  : "bg-muted/30 border-border hover:bg-muted/50"
              }`}
            >
              <div className="flex items-center gap-2">
                {selectedTags.includes(option.tag) && (
                  <CheckCircle2 className="w-4 h-4 text-primary shrink-0" />
                )}
                <span className={selectedTags.includes(option.tag) ? "font-medium" : ""}>
                  {option.label}
                </span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Free text */}
      <div className="space-y-2">
        <h3 className="font-medium">Anything else? (optional)</h3>
        <Textarea
          value={reflectionText}
          onChange={(e) => setReflectionText(e.target.value)}
          placeholder="What were you thinking? What will you try differently?"
          rows={3}
        />
      </div>

      <div className="flex justify-between">
        <Button variant="ghost" onClick={prevStep} className="gap-2">
          <ChevronLeft className="w-4 h-4" /> Back
        </Button>
        <Button
          onClick={handleSaveReflection}
          disabled={savingReflection || (selectedTags.length === 0 && !reflectionText.trim())}
          className="gap-2"
        >
          {savingReflection ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <MessageSquare className="w-4 h-4" />
          )}
          Save & Continue
        </Button>
      </div>

      <Button
        variant="link"
        onClick={() => setCurrentStep(4)}
        className="w-full text-muted-foreground"
      >
        Skip reflection for now
      </Button>
    </motion.div>
  );

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
          </div>

          {/* Step Indicator */}
          {renderStepIndicator()}

          {/* Step Content */}
          <AnimatePresence mode="wait">
            {STEP_RENDERERS[currentStep]()}
          </AnimatePresence>
        </div>
      </div>
    </Layout>
  );
};

export default Training;
