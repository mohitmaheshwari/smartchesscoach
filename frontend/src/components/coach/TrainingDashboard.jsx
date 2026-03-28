/**
 * Training Dashboard - Human Coach Style
 * 
 * Visualizes:
 * - Weekly curriculum with exercises
 * - Coach's memory of you
 * - Emotional state awareness
 * - Progress tracking
 * 
 * Makes training feel personal and purposeful.
 */

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { API } from "@/App";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Brain,
  Target,
  Calendar,
  Zap,
  TrendingUp,
  TrendingDown,
  CheckCircle2,
  Circle,
  Flame,
  Trophy,
  Heart,
  Loader2,
  ChevronDown,
  ChevronUp,
  Sparkles,
  BookOpen,
  Swords,
  RefreshCw,
  Clock,
  Star
} from "lucide-react";

// Emotional state icons and colors
const EMOTIONAL_STATE_CONFIG = {
  confident: { icon: Flame, color: "text-orange-500", bg: "bg-orange-500/10", label: "On Fire!" },
  frustrated: { icon: Heart, color: "text-red-400", bg: "bg-red-500/10", label: "Tough Stretch" },
  tilted: { icon: RefreshCw, color: "text-amber-500", bg: "bg-amber-500/10", label: "Take a Break?" },
  rushed: { icon: Clock, color: "text-blue-400", bg: "bg-blue-500/10", label: "Slow Down" },
  uncertain: { icon: Brain, color: "text-purple-400", bg: "bg-purple-500/10", label: "Thinking..." },
  focused: { icon: Target, color: "text-emerald-500", bg: "bg-emerald-500/10", label: "In the Zone" },
  neutral: { icon: Sparkles, color: "text-primary", bg: "bg-primary/10", label: "Ready to Learn" }
};

// Exercise type icons
const EXERCISE_ICONS = {
  puzzle: Zap,
  game: Swords,
  drill: Target,
  study: BookOpen
};

const TrainingDashboard = ({ onStartTraining }) => {
  const [loading, setLoading] = useState(true);
  const [curriculum, setCurriculum] = useState(null);
  const [memory, setMemory] = useState(null);
  const [emotionalState, setEmotionalState] = useState(null);
  const [expanded, setExpanded] = useState(false);
  const [completedExercises, setCompletedExercises] = useState([]);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    setLoading(true);
    try {
      const [curriculumRes, memoryRes] = await Promise.all([
        fetch(`${API}/coach/human-coach/curriculum`, { credentials: "include" }),
        fetch(`${API}/coach/human-coach/memory`, { credentials: "include" })
      ]);

      if (curriculumRes.ok) {
        const data = await curriculumRes.json();
        setCurriculum(data);
      }

      if (memoryRes.ok) {
        const data = await memoryRes.json();
        setMemory(data);
        
        // Detect emotional state based on recent results
        if (data.recent_results?.length > 0) {
          detectEmotionalState(data.recent_results);
        }
      }
    } catch (error) {
      console.error("Error fetching dashboard data:", error);
    } finally {
      setLoading(false);
    }
  };

  const detectEmotionalState = async (recentResults) => {
    try {
      const response = await fetch(`${API}/coach/human-coach/emotional-state`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ recent_results: recentResults })
      });
      
      if (response.ok) {
        const data = await response.json();
        setEmotionalState(data);
      }
    } catch (error) {
      console.error("Error detecting emotional state:", error);
    }
  };

  const toggleExerciseComplete = (exerciseIndex) => {
    setCompletedExercises(prev => {
      if (prev.includes(exerciseIndex)) {
        return prev.filter(i => i !== exerciseIndex);
      }
      return [...prev, exerciseIndex];
    });
  };

  if (loading) {
    return (
      <Card className="overflow-hidden">
        <CardContent className="p-6 flex items-center justify-center min-h-[200px]">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  const stateConfig = EMOTIONAL_STATE_CONFIG[emotionalState?.emotional_state] || EMOTIONAL_STATE_CONFIG.neutral;
  const StateIcon = stateConfig.icon;

  // Calculate progress
  const totalExercises = curriculum?.exercises?.length || 0;
  const completedCount = completedExercises.length;
  const progressPercent = totalExercises > 0 ? (completedCount / totalExercises) * 100 : 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-4"
    >
      {/* Coach Memory Card */}
      {memory && memory.total_sessions > 0 && (
        <Card className="overflow-hidden border-primary/20 bg-gradient-to-br from-primary/5 to-transparent">
          <CardContent className="p-5">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-xl bg-primary/20 flex items-center justify-center flex-shrink-0">
                <Brain className="w-6 h-6 text-primary" />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <h3 className="font-semibold">Coach Remembers</h3>
                  <Badge variant="secondary" className="text-xs">
                    {memory.total_sessions} sessions
                  </Badge>
                </div>
                
                {/* Streak indicator */}
                {memory.streak && memory.streak.count >= 2 && (
                  <div className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs mb-2 ${
                    memory.streak.type === 'winning' 
                      ? 'bg-emerald-500/20 text-emerald-400' 
                      : 'bg-red-500/20 text-red-400'
                  }`}>
                    {memory.streak.type === 'winning' ? (
                      <><TrendingUp className="w-3 h-3" /> {memory.streak.count} wins in a row!</>
                    ) : (
                      <><TrendingDown className="w-3 h-3" /> Let's break this streak</>
                    )}
                  </div>
                )}
                
                {/* Concepts practiced */}
                {memory.concepts_practiced?.length > 0 && (
                  <div className="text-sm text-muted-foreground">
                    <span className="font-medium">Recently practiced: </span>
                    {memory.concepts_practiced.slice(0, 3).join(", ")}
                  </div>
                )}
                
                {/* Top weaknesses */}
                {memory.top_weaknesses?.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {memory.top_weaknesses.slice(0, 3).map((weakness, i) => (
                      <Badge key={i} variant="outline" className="text-xs border-amber-500/30 text-amber-400">
                        {weakness.replace(/_/g, " ")}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Emotional State Card */}
      {emotionalState && (
        <Card className={`overflow-hidden border-transparent ${stateConfig.bg}`}>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded-full ${stateConfig.bg} flex items-center justify-center`}>
                <StateIcon className={`w-5 h-5 ${stateConfig.color}`} />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className={`font-medium ${stateConfig.color}`}>{stateConfig.label}</span>
                </div>
                {emotionalState.sample_prefix && (
                  <p className="text-sm text-muted-foreground">{emotionalState.sample_prefix}</p>
                )}
              </div>
              {emotionalState.should_offer_break && (
                <Button variant="outline" size="sm" className="border-amber-500/30 text-amber-400 hover:bg-amber-500/10">
                  Take Break
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Weekly Curriculum Card */}
      {curriculum && (
        <Card className="overflow-hidden">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Calendar className="w-5 h-5 text-primary" />
                <CardTitle className="text-lg">This Week's Focus</CardTitle>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setExpanded(!expanded)}
                className="text-muted-foreground"
              >
                {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </Button>
            </div>
          </CardHeader>
          <CardContent className="pt-0">
            {/* Focus area header */}
            <div className="mb-4">
              <div className="flex items-center gap-2 mb-2">
                <Target className="w-5 h-5 text-amber-500" />
                <span className="font-semibold text-lg capitalize">
                  {curriculum.focus_area?.replace(/_/g, " ")}
                </span>
              </div>
              <p className="text-sm text-muted-foreground">{curriculum.reason}</p>
            </div>

            {/* Progress bar */}
            <div className="mb-4">
              <div className="flex items-center justify-between text-sm mb-2">
                <span className="text-muted-foreground">Weekly Progress</span>
                <span className="font-medium">{completedCount}/{totalExercises}</span>
              </div>
              <Progress value={progressPercent} className="h-2" />
            </div>

            {/* Weekly targets */}
            <div className="grid grid-cols-3 gap-3 mb-4">
              <div className="text-center p-3 rounded-lg bg-muted/50">
                <div className="text-2xl font-bold text-primary">{curriculum.targets?.games || 0}</div>
                <div className="text-xs text-muted-foreground">Games</div>
              </div>
              <div className="text-center p-3 rounded-lg bg-muted/50">
                <div className="text-2xl font-bold text-amber-500">{curriculum.targets?.puzzles || 0}</div>
                <div className="text-xs text-muted-foreground">Puzzles</div>
              </div>
              <div className="text-center p-3 rounded-lg bg-muted/50">
                <div className="text-2xl font-bold text-emerald-500">{curriculum.targets?.sessions || 0}</div>
                <div className="text-xs text-muted-foreground">Sessions</div>
              </div>
            </div>

            {/* Exercises list (expandable) */}
            <AnimatePresence>
              {expanded && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="space-y-2 overflow-hidden"
                >
                  <h4 className="font-medium text-sm mb-3">Exercises</h4>
                  {curriculum.exercises?.map((exercise, index) => {
                    const ExerciseIcon = EXERCISE_ICONS[exercise.type] || Target;
                    const isCompleted = completedExercises.includes(index);
                    
                    return (
                      <motion.div
                        key={index}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: index * 0.05 }}
                        className={`flex items-center gap-3 p-3 rounded-lg border transition-colors cursor-pointer ${
                          isCompleted 
                            ? 'bg-emerald-500/10 border-emerald-500/30' 
                            : 'bg-muted/30 border-transparent hover:border-primary/30'
                        }`}
                        onClick={() => toggleExerciseComplete(index)}
                        data-testid={`exercise-${index}`}
                      >
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                          isCompleted ? 'bg-emerald-500/20' : 'bg-muted'
                        }`}>
                          {isCompleted ? (
                            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                          ) : (
                            <ExerciseIcon className="w-4 h-4 text-muted-foreground" />
                          )}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span className={`text-sm font-medium ${isCompleted ? 'line-through text-muted-foreground' : ''}`}>
                              {exercise.description}
                            </span>
                            {exercise.count && (
                              <Badge variant="outline" className="text-xs">
                                {exercise.count}x
                              </Badge>
                            )}
                          </div>
                          <span className="text-xs text-muted-foreground capitalize">
                            {exercise.type} {exercise.theme ? `• ${exercise.theme}` : ''}
                          </span>
                        </div>
                      </motion.div>
                    );
                  })}
                </motion.div>
              )}
            </AnimatePresence>

            {/* Concepts to practice */}
            {curriculum.concepts_to_practice?.length > 0 && (
              <div className="mt-4 pt-4 border-t border-border">
                <h4 className="text-xs font-medium text-muted-foreground mb-2">KEY CONCEPTS</h4>
                <div className="flex flex-wrap gap-2">
                  {curriculum.concepts_to_practice.map((concept, i) => (
                    <Badge key={i} variant="secondary" className="text-xs">
                      {concept}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Motivation message */}
            {curriculum.motivation && (
              <div className="mt-4 p-3 rounded-lg bg-primary/5 border border-primary/10">
                <div className="flex items-start gap-2">
                  <Star className="w-4 h-4 text-primary flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-muted-foreground italic">{curriculum.motivation}</p>
                </div>
              </div>
            )}

            {/* Start training button */}
            {onStartTraining && (
              <Button 
                onClick={onStartTraining} 
                className="w-full mt-4"
                data-testid="start-training-btn"
              >
                <Zap className="w-4 h-4 mr-2" />
                Start Training
              </Button>
            )}
          </CardContent>
        </Card>
      )}
    </motion.div>
  );
};

export default TrainingDashboard;
