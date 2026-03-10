/**
 * DeepMemoryPanel.jsx - Enhanced Coach Memory Display
 * 
 * Shows the coach's deep understanding of the player:
 * - Blunder taxonomy (what kind of mistakes they make)
 * - Playing style profile
 * - Behavioral patterns (tilt, time management)
 * - Pattern history for "remember when..."
 * 
 * This is the 9/10 memory system visualization.
 */

import { useState, useEffect } from "react";
import { API } from "@/App";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  Brain,
  Target,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Clock,
  Zap,
  Shield,
  Swords,
  Crown,
  ChevronDown,
  ChevronUp,
  Loader2,
  History,
  BarChart3,
  User,
  Flame,
} from "lucide-react";

const DeepMemoryPanel = ({ compact = false }) => {
  const [memory, setMemory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchMemory = async () => {
      try {
        setLoading(true);
        const response = await fetch(`${API}/coach/deep-memory`, {
          credentials: "include"
        });
        if (!response.ok) throw new Error("Failed to load memory");
        const data = await response.json();
        setMemory(data);
      } catch (err) {
        console.error("Failed to fetch deep memory:", err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchMemory();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground py-2">
        <Loader2 className="w-3 h-3 animate-spin" />
        <span>Loading coach memory...</span>
      </div>
    );
  }

  if (error || !memory) {
    return null;
  }

  const { summary, identity, games_analyzed, has_data } = memory;

  // New user - minimal display
  if (!has_data || games_analyzed < 2) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground py-2 px-1" data-testid="deep-memory-panel">
        <Brain className="w-3 h-3 text-primary" />
        <span>Building your profile... Play more games with coach!</span>
      </div>
    );
  }

  // Style icon mapping
  const styleIcons = {
    aggressive: <Swords className="w-4 h-4 text-red-400" />,
    positional: <Shield className="w-4 h-4 text-blue-400" />,
    tactical: <Zap className="w-4 h-4 text-yellow-400" />,
    defensive: <Shield className="w-4 h-4 text-green-400" />,
    universal: <Crown className="w-4 h-4 text-purple-400" />,
    developing: <User className="w-4 h-4 text-gray-400" />,
  };

  // Trend indicator
  const TrendIndicator = ({ trend }) => {
    if (trend === "improving") {
      return <TrendingUp className="w-3 h-3 text-green-400" />;
    } else if (trend === "worsening") {
      return <TrendingDown className="w-3 h-3 text-red-400" />;
    }
    return <span className="w-3 h-3" />;
  };

  // Compact view for inline display
  if (compact) {
    return (
      <div className="py-2 px-1" data-testid="deep-memory-panel-compact">
        <button 
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center justify-between text-xs hover:bg-muted/30 rounded px-1 py-1 transition-colors"
        >
          <div className="flex items-center gap-2">
            <Brain className="w-3 h-3 text-primary" />
            <span className="font-medium">{games_analyzed} games analyzed</span>
            {summary.primary_style && summary.primary_style !== "developing" && (
              <Badge variant="outline" className="text-[10px] px-1 py-0 capitalize">
                {summary.primary_style}
              </Badge>
            )}
            {summary.most_common_blunder && (
              <span className="text-muted-foreground">
                • Focus: {summary.most_common_blunder.replace(/_/g, " ")}
              </span>
            )}
            {summary.is_tilted && (
              <Badge variant="destructive" className="text-[10px] px-1 py-0">
                <Flame className="w-2 h-2 mr-1" /> Tilt
              </Badge>
            )}
          </div>
          {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </button>

        {expanded && (
          <div className="mt-3 space-y-3 pl-2">
            {/* Blunder Profile */}
            {summary.most_common_blunder && (
              <div className="flex items-center gap-2 text-xs">
                <AlertTriangle className="w-3 h-3 text-orange-400" />
                <span>Primary weakness: {summary.most_common_blunder.replace(/_/g, " ")}</span>
                <TrendIndicator trend={summary.blunder_trend} />
              </div>
            )}
            
            {/* Worst Phase */}
            {summary.worst_phase && (
              <div className="flex items-center gap-2 text-xs">
                <Target className="w-3 h-3 text-amber-400" />
                <span>Struggles in: {summary.worst_phase}</span>
              </div>
            )}

            {/* Coach Notes */}
            {summary.coach_notes?.length > 0 && (
              <div className="space-y-1">
                {summary.coach_notes.map((note, i) => (
                  <div key={i} className="text-[10px] text-muted-foreground pl-5">
                    • {note}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  // Full panel view
  const blunder = identity.blunder_taxonomy;
  const style = identity.style_profile;
  const behavior = identity.behavioral_profile;

  return (
    <Card className="bg-card/50 border-border/50" data-testid="deep-memory-panel-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <Brain className="w-4 h-4 text-primary" />
          Coach Memory
          <Badge variant="secondary" className="ml-auto text-[10px]">
            {games_analyzed} games
          </Badge>
        </CardTitle>
      </CardHeader>
      
      <CardContent className="space-y-4 text-xs">
        {/* Playing Style */}
        <div className="flex items-center gap-3">
          {styleIcons[style.primary_style] || styleIcons.developing}
          <div>
            <div className="font-medium capitalize">{style.primary_style} Player</div>
            <div className="text-muted-foreground text-[10px]">
              {style.confidence > 0.5 ? "Confident classification" : "Still learning your style"}
            </div>
          </div>
        </div>

        {/* Blunder Profile */}
        {blunder.total_blunders > 0 && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Blunder Profile</span>
              <TrendIndicator trend={blunder.trend} />
            </div>
            
            {/* By Phase */}
            {blunder.worst_phase && (
              <div className="flex items-center gap-2">
                <Target className="w-3 h-3 text-amber-400" />
                <span>Worst phase: <span className="text-amber-400 capitalize">{blunder.worst_phase}</span></span>
              </div>
            )}
            
            {/* Most Common Type */}
            {blunder.most_common_type && (
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-3 h-3 text-orange-400" />
                <span>Most common: <span className="text-orange-400">{blunder.most_common_type.replace(/_/g, " ")}</span></span>
              </div>
            )}

            {/* Time-related stats */}
            {blunder.impulse_moves > 0 && (
              <div className="flex items-center gap-2 text-muted-foreground">
                <Zap className="w-3 h-3" />
                <span>{blunder.impulse_moves} impulse moves (&lt;2s)</span>
              </div>
            )}
            {blunder.under_time_pressure > 0 && (
              <div className="flex items-center gap-2 text-muted-foreground">
                <Clock className="w-3 h-3" />
                <span>{blunder.under_time_pressure} time trouble blunders</span>
              </div>
            )}
          </div>
        )}

        {/* Behavioral Alerts */}
        {identity.consecutive_losses >= 2 && (
          <div className="flex items-center gap-2 p-2 bg-destructive/10 rounded text-destructive">
            <Flame className="w-4 h-4" />
            <span>On a {identity.consecutive_losses}-game losing streak</span>
          </div>
        )}
        
        {identity.consecutive_wins >= 3 && (
          <div className="flex items-center gap-2 p-2 bg-green-500/10 rounded text-green-400">
            <Crown className="w-4 h-4" />
            <span>{identity.consecutive_wins}-game winning streak!</span>
          </div>
        )}

        {/* Priority Focus */}
        {summary.priority_focus && (
          <div className="flex items-center gap-2 p-2 bg-primary/10 rounded">
            <Target className="w-4 h-4 text-primary" />
            <span>Current focus: <span className="font-medium">{summary.priority_focus.replace(/_/g, " ")}</span></span>
          </div>
        )}

        {/* Pattern History Preview */}
        {identity.pattern_history?.length > 0 && (
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-muted-foreground">
              <History className="w-3 h-3" />
              <span>Recent patterns</span>
            </div>
            <div className="flex flex-wrap gap-1">
              {[...new Set(identity.pattern_history.slice(-5).map(p => p.pattern_type))].map((type, i) => (
                <Badge key={i} variant="outline" className="text-[10px]">
                  {type.replace(/_/g, " ")}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default DeepMemoryPanel;
