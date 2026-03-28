/**
 * ThinkingScoreCard - Shows player's thinking habits progress
 * 
 * Displays:
 * - Overall thinking score (0-100)
 * - Progress trends for each thinking habit
 * - Personalized recommendations
 * - Score explanations
 * 
 * All data is calculated from REAL game analysis - not random numbers.
 */

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { API } from "@/App";
import { motion } from "framer-motion";
import {
  Brain,
  TrendingUp,
  TrendingDown,
  Minus,
  Target,
  Shield,
  Zap,
  CheckCircle2,
  Clock,
  ChevronDown,
  ChevronUp,
  Loader2,
  AlertCircle,
  Lightbulb,
  Info
} from "lucide-react";

const HABIT_ICONS = {
  threat_awareness: Target,
  tactical_vision: Zap,
  move_verification: CheckCircle2,
  king_safety: Shield,
  patience: Clock
};

const HABIT_LABELS = {
  threat_awareness: "Threat Awareness",
  tactical_vision: "Tactical Vision",
  move_verification: "Move Verification",
  king_safety: "King Safety",
  patience: "Patience"
};

const HABIT_DESCRIPTIONS = {
  threat_awareness: "Checking opponent threats before moving",
  tactical_vision: "Finding checks, captures, and forcing moves",
  move_verification: "Double-checking moves before playing",
  king_safety: "Keeping your king safe",
  patience: "Taking time to calculate properly"
};

const TrendIcon = ({ trend }) => {
  if (trend === "improving") return <TrendingUp className="w-4 h-4 text-green-400" />;
  if (trend === "declining") return <TrendingDown className="w-4 h-4 text-red-400" />;
  return <Minus className="w-4 h-4 text-muted-foreground" />;
};

const getScoreColor = (score) => {
  if (score >= 80) return "text-green-400";
  if (score >= 60) return "text-yellow-400";
  if (score >= 40) return "text-orange-400";
  return "text-red-400";
};

const getProgressColor = (score) => {
  if (score >= 80) return "bg-green-500";
  if (score >= 60) return "bg-yellow-500";
  if (score >= 40) return "bg-orange-500";
  return "bg-red-500";
};

const ThinkingScoreCard = ({ compact = false }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(!compact);
  const [showAllHabits, setShowAllHabits] = useState(false);

  useEffect(() => {
    fetchThinkingScore();
  }, []);

  const fetchThinkingScore = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/thinking-score`, { credentials: "include" });
      if (res.ok) {
        const result = await res.json();
        setData(result);
      }
    } catch (e) {
      console.error("Failed to fetch thinking score:", e);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Card className="border-purple-500/30 bg-purple-500/5">
        <CardContent className="p-6 text-center">
          <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-purple-400" />
          <p className="text-sm text-muted-foreground">Calculating your thinking score...</p>
        </CardContent>
      </Card>
    );
  }

  if (!data?.has_data) {
    return (
      <Card className="border-slate-500/30 bg-slate-500/5">
        <CardContent className="p-6 text-center">
          <Brain className="w-8 h-8 mx-auto mb-3 text-muted-foreground" />
          <p className="text-sm font-medium mb-2">No Thinking Score Yet</p>
          <p className="text-xs text-muted-foreground">
            Play and analyze games to see how well you're applying thinking habits.
          </p>
        </CardContent>
      </Card>
    );
  }

  const { overall_score, overall_trend, overall_change, habit_progress, recommendations, explanation, games_analyzed } = data;

  // Compact view
  if (compact && !expanded) {
    return (
      <Card 
        className="border-purple-500/30 bg-purple-500/5 cursor-pointer hover:bg-purple-500/10 transition-colors"
        onClick={() => setExpanded(true)}
        data-testid="thinking-score-card-compact"
      >
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-full bg-purple-500/20 flex items-center justify-center">
                <Brain className="w-6 h-6 text-purple-400" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Thinking Score</p>
                <p className={`text-2xl font-bold ${getScoreColor(overall_score)}`}>
                  {Math.round(overall_score)}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <TrendIcon trend={overall_trend} />
              {overall_change !== null && (
                <span className={`text-sm ${overall_change > 0 ? 'text-green-400' : overall_change < 0 ? 'text-red-400' : 'text-muted-foreground'}`}>
                  {overall_change > 0 ? '+' : ''}{Math.round(overall_change)}
                </span>
              )}
              <ChevronDown className="w-4 h-4 text-muted-foreground" />
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Sort habits by score (lowest first for recommendations focus)
  const sortedHabits = Object.entries(habit_progress || {}).sort(
    (a, b) => (a[1]?.current_score || 0) - (b[1]?.current_score || 0)
  );

  const habitsToShow = showAllHabits ? sortedHabits : sortedHabits.slice(0, 3);

  return (
    <Card className="border-purple-500/30 bg-purple-500/5" data-testid="thinking-score-card">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Brain className="w-5 h-5 text-purple-400" />
            <CardTitle className="text-base">Thinking Score</CardTitle>
            <Badge variant="outline" className="text-[10px] border-purple-500/50 text-purple-400">
              {games_analyzed} games
            </Badge>
          </div>
          {compact && (
            <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={() => setExpanded(false)}>
              <ChevronUp className="w-4 h-4" />
            </Button>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Overall Score */}
        <div className="flex items-center gap-4">
          <div className="relative w-20 h-20">
            <svg className="w-full h-full -rotate-90">
              <circle
                cx="40"
                cy="40"
                r="36"
                fill="none"
                stroke="currentColor"
                strokeWidth="6"
                className="text-slate-700"
              />
              <circle
                cx="40"
                cy="40"
                r="36"
                fill="none"
                stroke="currentColor"
                strokeWidth="6"
                strokeDasharray={`${(overall_score / 100) * 226} 226`}
                className={getScoreColor(overall_score).replace('text-', 'text-')}
                style={{ stroke: overall_score >= 80 ? '#4ade80' : overall_score >= 60 ? '#facc15' : overall_score >= 40 ? '#fb923c' : '#f87171' }}
              />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className={`text-2xl font-bold ${getScoreColor(overall_score)}`}>
                {Math.round(overall_score)}
              </span>
            </div>
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <TrendIcon trend={overall_trend} />
              <span className="text-sm font-medium">
                {overall_trend === "improving" ? "Improving" : overall_trend === "declining" ? "Needs Work" : "Stable"}
              </span>
              {overall_change !== null && (
                <span className={`text-xs ${overall_change > 0 ? 'text-green-400' : overall_change < 0 ? 'text-red-400' : 'text-muted-foreground'}`}>
                  ({overall_change > 0 ? '+' : ''}{Math.round(overall_change)} from last {games_analyzed > 5 ? '5' : games_analyzed} games)
                </span>
              )}
            </div>
            <p className="text-xs text-muted-foreground">{explanation}</p>
          </div>
        </div>

        {/* How Score is Calculated */}
        <div className="p-2 rounded bg-slate-800/50 border border-slate-700/50">
          <div className="flex items-start gap-2">
            <Info className="w-3.5 h-3.5 text-muted-foreground mt-0.5 flex-shrink-0" />
            <p className="text-[10px] text-muted-foreground">
              Score is calculated from your actual game mistakes. Each thinking habit is measured by how often you avoid related errors.
            </p>
          </div>
        </div>

        {/* Habit Breakdown */}
        <div className="space-y-3">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Habit Breakdown</p>
          
          {habitsToShow.map(([habitKey, habitData]) => {
            const HabitIcon = HABIT_ICONS[habitKey] || Brain;
            const score = habitData?.current_score || 0;
            const change = habitData?.change;
            const trend = habitData?.trend;
            
            return (
              <motion.div
                key={habitKey}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-1.5"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <HabitIcon className="w-3.5 h-3.5 text-muted-foreground" />
                    <span className="text-xs font-medium">{HABIT_LABELS[habitKey]}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-medium ${getScoreColor(score)}`}>
                      {Math.round(score)}
                    </span>
                    {change !== null && (
                      <span className={`text-[10px] ${change > 0 ? 'text-green-400' : change < 0 ? 'text-red-400' : 'text-muted-foreground'}`}>
                        {change > 0 ? '+' : ''}{Math.round(change)}
                      </span>
                    )}
                    <TrendIcon trend={trend} />
                  </div>
                </div>
                <div className="h-1.5 rounded-full bg-slate-700 overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${score}%` }}
                    transition={{ duration: 0.5, delay: 0.1 }}
                    className={`h-full rounded-full ${getProgressColor(score)}`}
                  />
                </div>
                <p className="text-[10px] text-muted-foreground">
                  {HABIT_DESCRIPTIONS[habitKey]}
                </p>
              </motion.div>
            );
          })}
          
          {sortedHabits.length > 3 && !showAllHabits && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowAllHabits(true)}
              className="w-full text-xs text-muted-foreground"
            >
              Show all {sortedHabits.length} habits
              <ChevronDown className="w-3 h-3 ml-1" />
            </Button>
          )}
        </div>

        {/* Recommendations */}
        {recommendations && recommendations.length > 0 && (
          <div className="space-y-2 pt-2 border-t border-border/30">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-1">
              <Lightbulb className="w-3 h-3" />
              Focus Areas
            </p>
            
            {recommendations.slice(0, 2).map((rec, idx) => (
              <div 
                key={idx}
                className={`p-2.5 rounded-lg border ${
                  rec.priority === 'high' 
                    ? 'bg-red-500/10 border-red-500/30' 
                    : 'bg-amber-500/10 border-amber-500/30'
                }`}
              >
                <div className="flex items-start gap-2">
                  <span className="text-base">{rec.icon}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium mb-0.5">{rec.habit_label}</p>
                    <p className="text-[10px] text-muted-foreground">{rec.recommendation}</p>
                    <p className="text-[10px] text-purple-300 mt-1 italic">
                      Checklist: "{rec.checklist_item}"
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default ThinkingScoreCard;
