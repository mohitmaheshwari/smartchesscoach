/**
 * CoachFocusCard - Shows active theme from CoachState
 * 
 * For Progress page top block:
 * - Theme name
 * - 1-2 micro rules
 * - "Are you improving?" mini-trend
 * - Simple delta: "Mistakes from this theme: 12 → 7 (last 10 games)"
 */

import { useState, useEffect } from "react";
import { API } from "@/App";
import { Badge } from "@/components/ui/badge";
import {
  Target,
  TrendingUp,
  TrendingDown,
  Minus,
  Loader2,
  ChevronRight,
  CheckCircle2
} from "lucide-react";

// Trend icons and colors
const TREND_CONFIG = {
  improving: { 
    icon: TrendingUp, 
    color: "text-green-400", 
    bg: "bg-green-500/10",
    label: "Improving" 
  },
  declining: { 
    icon: TrendingDown, 
    color: "text-red-400", 
    bg: "bg-red-500/10",
    label: "Needs attention" 
  },
  stable: { 
    icon: Minus, 
    color: "text-amber-400", 
    bg: "bg-amber-500/10",
    label: "Stable" 
  },
  insufficient_data: { 
    icon: Minus, 
    color: "text-slate-400", 
    bg: "bg-slate-500/10",
    label: "Building data" 
  }
};

const CoachFocusCard = () => {
  const [loading, setLoading] = useState(true);
  const [themeStats, setThemeStats] = useState(null);

  useEffect(() => {
    fetchThemeStats();
  }, []);

  const fetchThemeStats = async () => {
    try {
      const res = await fetch(`${API}/coach/theme-stats`, { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        if (data.has_theme) {
          setThemeStats(data);
        }
      }
    } catch (err) {
      console.error("Error fetching theme stats:", err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="rounded-xl border border-border bg-card p-4">
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span className="text-sm">Loading focus area...</span>
        </div>
      </div>
    );
  }

  if (!themeStats) {
    return null;
  }

  const trend = themeStats.improvement_stats?.trend || "insufficient_data";
  const trendConfig = TREND_CONFIG[trend] || TREND_CONFIG.stable;
  const TrendIcon = trendConfig.icon;

  const mistakesBefore = themeStats.improvement_stats?.mistakes_before || 0;
  const mistakesAfter = themeStats.improvement_stats?.mistakes_after || 0;
  const gamesAnalyzed = themeStats.improvement_stats?.games_analyzed || 0;

  return (
    <div 
      className="rounded-xl border border-primary/30 bg-gradient-to-br from-primary/5 to-transparent overflow-hidden"
      data-testid="coach-focus-card"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border/50">
        <div className="flex items-center gap-2">
          <Target className="w-4 h-4 text-primary" />
          <span className="text-sm font-medium">Coach Focus This Week</span>
        </div>
        <Badge 
          variant="outline" 
          className="text-xs border-primary/30 text-primary"
        >
          {themeStats.days_on_theme} days
        </Badge>
      </div>

      {/* Content */}
      <div className="p-4 space-y-4">
        {/* Theme Name */}
        <div>
          <h3 className="text-lg font-semibold text-foreground">
            {themeStats.theme_display}
          </h3>
          <p className="text-sm text-muted-foreground mt-0.5">
            {themeStats.theme_reason}
          </p>
        </div>

        {/* Micro Rules */}
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground uppercase tracking-wider">
            Your Rules
          </p>
          {themeStats.micro_rules?.slice(0, 2).map((rule, idx) => (
            <div 
              key={idx}
              className="flex items-start gap-2 p-2 rounded-lg bg-background/50"
            >
              <CheckCircle2 className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" />
              <span className="text-sm">{rule}</span>
            </div>
          ))}
        </div>

        {/* Improvement Trend */}
        {gamesAnalyzed >= 4 && (
          <div className={`flex items-center justify-between p-3 rounded-lg ${trendConfig.bg}`}>
            <div className="flex items-center gap-2">
              <TrendIcon className={`w-4 h-4 ${trendConfig.color}`} />
              <span className={`text-sm font-medium ${trendConfig.color}`}>
                {trendConfig.label}
              </span>
            </div>
            <span className="text-sm text-muted-foreground">
              {mistakesBefore} → {mistakesAfter} 
              <span className="text-xs ml-1">
                (last {gamesAnalyzed} games)
              </span>
            </span>
          </div>
        )}

        {/* Games on theme */}
        <p className="text-xs text-muted-foreground text-center">
          {themeStats.games_on_theme} games played on this focus
        </p>
      </div>
    </div>
  );
};

export default CoachFocusCard;
