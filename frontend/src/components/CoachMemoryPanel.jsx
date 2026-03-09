/**
 * CoachMemoryPanel.jsx - Shows what the coach KNOWS about you
 * 
 * This replaces TeachingInsights with real, personalized data:
 * - Games played together
 * - Your known weaknesses (watch_for)
 * - Today's focus
 * - Recent form and patterns
 * - Openings you've learned
 * 
 * This makes the coach feel like a REAL human who remembers you.
 */

import { useState, useEffect, useCallback } from "react";
import { API } from "@/App";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Brain,
  Target,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle2,
  BookOpen,
  Flame,
  Loader2,
  Eye,
  Sparkles,
} from "lucide-react";

const CoachMemoryPanel = ({ sessionId }) => {
  const [memory, setMemory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch coach memory on mount
  useEffect(() => {
    const fetchMemory = async () => {
      try {
        setLoading(true);
        const response = await fetch(`${API}/coach/memory`, {
          credentials: "include"
        });
        
        if (!response.ok) throw new Error("Failed to load");
        
        const data = await response.json();
        setMemory(data);
      } catch (err) {
        console.error("Failed to fetch coach memory:", err);
        setError("Could not load coach memory");
      } finally {
        setLoading(false);
      }
    };
    
    fetchMemory();
  }, [sessionId]);

  if (loading) {
    return (
      <Card className="bg-gradient-to-br from-primary/5 to-transparent border-primary/20">
        <CardContent className="py-4 flex items-center justify-center">
          <Loader2 className="w-5 h-5 animate-spin text-primary" />
        </CardContent>
      </Card>
    );
  }

  if (error || !memory?.context) {
    return null; // Silently fail - don't show broken UI
  }

  const ctx = memory.context;
  const gamesPlayed = ctx.games_played || 0;
  const avgAccuracy = ctx.avg_accuracy || 0;
  const watchFor = ctx.watch_for || [];
  const focusSuggestion = ctx.focus_suggestion;
  const openingsKnown = ctx.openings_known || [];
  const recurringPatterns = ctx.recurring_patterns || [];
  const lastInsights = ctx.last_game_insights || [];
  const improving = ctx.improving;

  // Don't show if no meaningful data
  if (gamesPlayed < 2 && watchFor.length === 0) {
    return (
      <Card className="bg-gradient-to-br from-primary/5 to-transparent border-primary/20">
        <CardContent className="py-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Brain className="w-4 h-4 text-primary" />
            <span>Play a few games and I'll start learning your patterns...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-gradient-to-br from-primary/5 to-transparent border-primary/20" data-testid="coach-memory-panel">
      <CardContent className="py-4 space-y-4">
        {/* Header with games count */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Brain className="w-5 h-5 text-primary" />
            <span className="font-medium">Coach Memory</span>
          </div>
          <Badge variant="outline" className="text-xs">
            Game #{gamesPlayed + 1}
          </Badge>
        </div>

        {/* Today's Focus - Most Important */}
        {focusSuggestion && (
          <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20" data-testid="focus-today">
            <div className="flex items-start gap-2">
              <Target className="w-4 h-4 text-amber-400 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-xs font-medium text-amber-400 uppercase tracking-wide">Today's Focus</p>
                <p className="text-sm mt-1">{focusSuggestion}</p>
              </div>
            </div>
          </div>
        )}

        {/* Watch For - Your Patterns */}
        {watchFor.length > 0 && (
          <div className="space-y-2" data-testid="watch-for-patterns">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide flex items-center gap-1">
              <Eye className="w-3 h-3" />
              I'm Watching For
            </p>
            <div className="space-y-1.5">
              {watchFor.slice(0, 3).map((pattern, i) => (
                <div 
                  key={i} 
                  className={`flex items-center justify-between p-2 rounded-lg text-sm ${
                    pattern.improving 
                      ? "bg-green-500/10 border border-green-500/20" 
                      : "bg-orange-500/10 border border-orange-500/20"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    {pattern.improving ? (
                      <CheckCircle2 className="w-4 h-4 text-green-400" />
                    ) : (
                      <AlertTriangle className="w-4 h-4 text-orange-400" />
                    )}
                    <span>{pattern.name}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">{pattern.count}x</span>
                    {pattern.improving && (
                      <TrendingUp className="w-3 h-3 text-green-400" />
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Last Game Insight - Quick Win */}
        {lastInsights.length > 0 && (
          <div className="p-2 rounded-lg bg-primary/5 border border-primary/10" data-testid="last-insight">
            <div className="flex items-start gap-2">
              <Sparkles className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" />
              <p className="text-xs">{lastInsights[0]}</p>
            </div>
          </div>
        )}

        {/* Stats Row */}
        <div className="flex items-center justify-between text-xs text-muted-foreground pt-2 border-t border-border/50">
          <div className="flex items-center gap-1">
            <span>{gamesPlayed} games together</span>
          </div>
          <div className="flex items-center gap-3">
            {avgAccuracy > 0 && (
              <span className="flex items-center gap-1">
                <span className={avgAccuracy >= 80 ? "text-green-400" : avgAccuracy >= 60 ? "text-amber-400" : "text-red-400"}>
                  {avgAccuracy.toFixed(0)}%
                </span>
                avg
              </span>
            )}
            {openingsKnown.length > 0 && (
              <span className="flex items-center gap-1">
                <BookOpen className="w-3 h-3" />
                {openingsKnown.length} openings
              </span>
            )}
          </div>
        </div>

        {/* Recurring Pattern Warning */}
        {recurringPatterns.length > 0 && recurringPatterns[0].includes("loss") && (
          <div className="p-2 rounded-lg bg-red-500/10 border border-red-500/20 text-xs flex items-center gap-2" data-testid="streak-warning">
            <Flame className="w-4 h-4 text-red-400" />
            <span>{recurringPatterns[0]}</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default CoachMemoryPanel;
