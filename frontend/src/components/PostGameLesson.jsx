/**
 * PostGameLesson.jsx - Post-Game Teaching Summary
 * 
 * Shows a comprehensive analysis after the game ends:
 * - Performance Rating (estimated vs actual)
 * - Mistake breakdown with explanations
 * - Habit check (progress on weaknesses)
 * - Personalized recommendations
 * - Coach summary and encouragement
 */

import { useState, useEffect } from "react";
import { API } from "@/App";
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Trophy,
  Target,
  Lightbulb,
  BookOpen,
  CheckCircle2,
  AlertTriangle,
  ChevronRight,
  Star,
  TrendingUp,
  TrendingDown,
  Award,
  Brain,
  Zap,
  XCircle,
  ArrowUp,
  ArrowDown,
  Minus
} from "lucide-react";

/**
 * Result Banner - Shows win/loss/draw with appropriate styling
 */
const ResultBanner = ({ result }) => {
  const config = {
    win: {
      icon: Trophy,
      text: "Victory!",
      bgColor: "bg-green-500/20",
      borderColor: "border-green-500/30",
      textColor: "text-green-400"
    },
    loss: {
      icon: Target,
      text: "Good effort!",
      bgColor: "bg-orange-500/20",
      borderColor: "border-orange-500/30",
      textColor: "text-orange-400"
    },
    draw: {
      icon: Award,
      text: "Draw!",
      bgColor: "bg-blue-500/20",
      borderColor: "border-blue-500/30",
      textColor: "text-blue-400"
    }
  };

  const { icon: Icon, text, bgColor, borderColor, textColor } = config[result] || config.draw;

  return (
    <div className={`flex items-center gap-3 p-4 rounded-lg ${bgColor} border ${borderColor}`}>
      <Icon className={`w-8 h-8 ${textColor}`} />
      <div>
        <h3 className={`text-xl font-bold ${textColor}`}>{text}</h3>
        <p className="text-sm text-muted-foreground">
          {result === "win" ? "Great game!" : result === "loss" ? "Every game makes you stronger." : "Well fought!"}
        </p>
      </div>
    </div>
  );
};

/**
 * Performance Rating Display
 */
const PerformanceRatingCard = ({ rating, userRating }) => {
  const diff = rating.estimated - userRating;
  const isAbove = diff > 50;
  const isBelow = diff < -50;
  
  return (
    <div className="p-4 rounded-lg bg-card border border-border">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-medium flex items-center gap-2">
          <Brain className="w-4 h-4 text-primary" />
          Performance Rating
        </h4>
        <Badge variant={rating.confidence === "high" ? "default" : "outline"}>
          {rating.confidence} confidence
        </Badge>
      </div>
      
      <div className="flex items-center gap-4">
        <div className="text-3xl font-bold">{rating.estimated}</div>
        <div className="flex items-center gap-1 text-sm">
          {isAbove ? (
            <>
              <ArrowUp className="w-4 h-4 text-green-400" />
              <span className="text-green-400">+{diff} from your {userRating}</span>
            </>
          ) : isBelow ? (
            <>
              <ArrowDown className="w-4 h-4 text-orange-400" />
              <span className="text-orange-400">{diff} from your {userRating}</span>
            </>
          ) : (
            <>
              <Minus className="w-4 h-4 text-muted-foreground" />
              <span className="text-muted-foreground">At your level ({userRating})</span>
            </>
          )}
        </div>
      </div>
      
      {rating.factors?.length > 0 && (
        <div className="mt-3 text-xs text-muted-foreground">
          {rating.factors.map((f, i) => (
            <p key={i} className="flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" /> {f}
            </p>
          ))}
        </div>
      )}
    </div>
  );
};

/**
 * Mistake Breakdown Component
 */
const MistakeBreakdown = ({ mistakes }) => {
  const { blunders, mistakes: mistakeCount, inaccuracies, details } = mistakes;
  const total = blunders + mistakeCount + inaccuracies;
  
  return (
    <div className="space-y-3">
      <h4 className="text-sm font-medium flex items-center gap-2">
        <AlertTriangle className="w-4 h-4 text-orange-400" />
        Mistakes Analysis
      </h4>
      
      <div className="grid grid-cols-3 gap-2">
        <div className={`p-3 rounded-lg text-center ${blunders > 0 ? "bg-red-500/10 border border-red-500/20" : "bg-muted/30"}`}>
          <div className={`text-xl font-bold ${blunders > 0 ? "text-red-400" : "text-muted-foreground"}`}>{blunders}</div>
          <div className="text-xs text-muted-foreground">Blunders</div>
        </div>
        <div className={`p-3 rounded-lg text-center ${mistakeCount > 0 ? "bg-orange-500/10 border border-orange-500/20" : "bg-muted/30"}`}>
          <div className={`text-xl font-bold ${mistakeCount > 0 ? "text-orange-400" : "text-muted-foreground"}`}>{mistakeCount}</div>
          <div className="text-xs text-muted-foreground">Mistakes</div>
        </div>
        <div className={`p-3 rounded-lg text-center ${inaccuracies > 0 ? "bg-yellow-500/10 border border-yellow-500/20" : "bg-muted/30"}`}>
          <div className={`text-xl font-bold ${inaccuracies > 0 ? "text-yellow-400" : "text-muted-foreground"}`}>{inaccuracies}</div>
          <div className="text-xs text-muted-foreground">Inaccuracies</div>
        </div>
      </div>
      
      {details?.length > 0 && (
        <div className="mt-3 space-y-2">
          <p className="text-xs text-muted-foreground font-medium">Key errors:</p>
          {details.slice(0, 3).map((d, i) => (
            <div key={i} className="p-2 rounded bg-muted/20 text-xs">
              <span className="font-mono text-primary">Move {d.move_number}. {d.move}</span>
              <span className={`ml-2 ${d.type === "blunder" ? "text-red-400" : "text-orange-400"}`}>
                ({d.type})
              </span>
              <p className="text-muted-foreground mt-1">{d.explanation}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

/**
 * Habit Progress Component
 */
const HabitProgress = ({ habits }) => {
  const { violations, improved, still_weak } = habits;
  
  const habitLabels = {
    early_queen: "Early queen moves",
    one_move_blunder: "One-move blunders",
    impatience: "Rushing moves",
    time_management: "Time management",
    calculation_errors: "Calculation errors"
  };
  
  return (
    <div className="space-y-3">
      <h4 className="text-sm font-medium flex items-center gap-2">
        <TrendingUp className="w-4 h-4 text-primary" />
        Habit Check
      </h4>
      
      {improved?.length > 0 && (
        <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/20">
          <p className="text-xs font-medium text-green-400 mb-1">Improvements!</p>
          <ul className="text-xs text-muted-foreground">
            {improved.map((h, i) => (
              <li key={i} className="flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3 text-green-400" />
                {habitLabels[h] || h} - avoided this game!
              </li>
            ))}
          </ul>
        </div>
      )}
      
      {violations?.length > 0 && (
        <div className="p-3 rounded-lg bg-orange-500/10 border border-orange-500/20">
          <p className="text-xs font-medium text-orange-400 mb-1">Areas to work on:</p>
          <ul className="text-xs text-muted-foreground space-y-1">
            {violations.map((v, i) => (
              <li key={i} className="flex items-start gap-1">
                <XCircle className="w-3 h-3 text-orange-400 mt-0.5 flex-shrink-0" />
                <span>{v.description}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      
      {!improved?.length && !violations?.length && (
        <p className="text-xs text-muted-foreground">No habit data for this game yet.</p>
      )}
    </div>
  );
};

/**
 * Recommendations Component
 */
const Recommendations = ({ recommendations }) => {
  const { priority, suggestions, opening_to_learn } = recommendations;
  
  return (
    <div className="space-y-3">
      <h4 className="text-sm font-medium flex items-center gap-2">
        <Lightbulb className="w-4 h-4 text-amber-400" />
        What to Practice
      </h4>
      
      {opening_to_learn && (
        <div className="p-3 rounded-lg bg-primary/10 border border-primary/20">
          <div className="flex items-center gap-2 text-sm">
            <BookOpen className="w-4 h-4 text-primary" />
            <span>{opening_to_learn}</span>
          </div>
        </div>
      )}
      
      {suggestions?.length > 0 && (
        <ul className="space-y-2">
          {suggestions.map((s, i) => (
            <li key={i} className="flex items-start gap-2 text-sm p-2 rounded bg-muted/20">
              <Zap className="w-4 h-4 text-amber-400 mt-0.5 flex-shrink-0" />
              <span>{s}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

/**
 * Coach Memory Insights - Shows personalized insights based on history
 * This is what makes the coach feel HUMAN - it remembers patterns
 */
const CoachMemoryInsights = ({ memory }) => {
  if (!memory || !memory.insights?.length) return null;
  
  const getInsightStyle = (type) => {
    switch (type) {
      case "recurring_pattern":
        return { 
          bg: "bg-orange-500/10", 
          border: "border-orange-500/20", 
          icon: AlertTriangle,
          iconColor: "text-orange-400"
        };
      case "improvement":
        return { 
          bg: "bg-green-500/10", 
          border: "border-green-500/20", 
          icon: TrendingUp,
          iconColor: "text-green-400"
        };
      case "performance_comparison":
        return { 
          bg: "bg-blue-500/10", 
          border: "border-blue-500/20", 
          icon: Brain,
          iconColor: "text-blue-400"
        };
      case "milestone":
        return { 
          bg: "bg-purple-500/10", 
          border: "border-purple-500/20", 
          icon: Star,
          iconColor: "text-purple-400"
        };
      default:
        return { 
          bg: "bg-muted/20", 
          border: "border-border", 
          icon: Lightbulb,
          iconColor: "text-muted-foreground"
        };
    }
  };
  
  return (
    <div className="space-y-3" data-testid="coach-memory-insights">
      <h4 className="text-sm font-medium flex items-center gap-2">
        <Brain className="w-4 h-4 text-primary" />
        Coach Memory
        {memory.games_together > 0 && (
          <span className="text-xs text-muted-foreground ml-auto">
            Game #{memory.games_together}
          </span>
        )}
      </h4>
      
      {memory.coach_knows_you && (
        <p className="text-xs text-muted-foreground italic">
          I&apos;m starting to understand your style...
        </p>
      )}
      
      <div className="space-y-2">
        {memory.insights.map((insight, i) => {
          const style = getInsightStyle(insight.type);
          const Icon = style.icon;
          
          return (
            <div 
              key={i} 
              className={`p-3 rounded-lg ${style.bg} border ${style.border}`}
              data-testid={`memory-insight-${insight.type}`}
            >
              <div className="flex items-start gap-2">
                <Icon className={`w-4 h-4 ${style.iconColor} mt-0.5 flex-shrink-0`} />
                <div className="flex-1">
                  <p className="text-sm">{insight.message}</p>
                  {insight.pattern && insight.count > 1 && (
                    <p className="text-xs text-muted-foreground mt-1">
                      Pattern: {insight.pattern} ({insight.count} times)
                    </p>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

/**
 * Main PostGameLesson Component - Enhanced with full analysis
 */
const PostGameLesson = ({ 
  sessionId,
  result,
  studentColor,
  moves,
  onPlayAgain,
  onClose,
  userRating = 1200
}) => {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchAnalysis();
  }, [sessionId]);

  const fetchAnalysis = async () => {
    setLoading(true);
    setError(null);

    try {
      // Fetch comprehensive analysis
      const response = await fetch(`${API}/coach/play/analysis`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ session_id: sessionId })
      });

      if (response.ok) {
        const data = await response.json();
        setAnalysis(data);
      } else {
        // Fallback to basic summary
        setError("Analysis not available");
      }
    } catch (err) {
      console.error("Analysis fetch error:", err);
      setError("Failed to load analysis");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Card className="w-full">
        <CardContent className="p-6 text-center">
          <div className="animate-spin w-8 h-8 border-2 border-primary border-t-transparent rounded-full mx-auto mb-4" />
          <p className="text-muted-foreground">Analyzing your game...</p>
          <p className="text-xs text-muted-foreground mt-1">Checking habits, calculating performance...</p>
        </CardContent>
      </Card>
    );
  }

  if (error || !analysis) {
    return (
      <Card className="w-full">
        <CardContent className="p-6">
          <ResultBanner result={result} />
          <div className="mt-4 text-center">
            <p className="text-muted-foreground">{error || "Analysis not available"}</p>
            <Button onClick={onPlayAgain} className="mt-4">
              Play Again
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="w-full border-primary/20" data-testid="post-game-analysis">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-lg">
          <Brain className="w-5 h-5 text-primary" />
          Game Analysis
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-5">
        {/* Result Banner */}
        <ResultBanner result={analysis.game_result} />

        {/* Coach Summary */}
        <div className="p-4 rounded-lg bg-primary/5 border border-primary/10">
          <p className="text-sm">{analysis.coach_summary}</p>
          <p className="text-sm text-primary mt-2 font-medium">{analysis.encouragement}</p>
        </div>

        {/* COACH MEMORY INSIGHTS - The key personalization */}
        {analysis.memory && (
          <CoachMemoryInsights memory={analysis.memory} />
        )}

        {/* Accuracy Bar */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">Accuracy</span>
            <span className="text-sm font-bold">{analysis.accuracy}%</span>
          </div>
          <Progress value={analysis.accuracy} className="h-2" />
        </div>

        {/* Performance Rating */}
        {analysis.performance_rating && (
          <PerformanceRatingCard 
            rating={analysis.performance_rating} 
            userRating={userRating}
          />
        )}

        {/* Mistakes */}
        {analysis.mistakes && (
          <MistakeBreakdown mistakes={analysis.mistakes} />
        )}

        {/* Habits */}
        {analysis.habits && (
          <HabitProgress habits={analysis.habits} />
        )}

        {/* Recommendations */}
        {analysis.recommendations && (
          <Recommendations recommendations={analysis.recommendations} />
        )}
      </CardContent>

      <CardFooter className="flex gap-2 pt-4">
        <Button onClick={onPlayAgain} className="flex-1" data-testid="play-again-btn">
          Play Again
          <ChevronRight className="w-4 h-4 ml-1" />
        </Button>
        {onClose && (
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        )}
      </CardFooter>
    </Card>
  );
};

export default PostGameLesson;
