/**
 * DeepMemoryPanel.jsx - Enhanced Coach Memory Display
 * 
 * Shows the coach's deep understanding of the player:
 * - Blunder taxonomy (what kind of mistakes they make)
 * - Playing style profile
 * - Behavioral patterns (tilt, time management)
 * - Pattern history with CLICKABLE LINKS to exact games/moves
 * 
 * This is the 9/10 memory system visualization.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { API } from "@/App";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
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
  User,
  Flame,
  ExternalLink,
  ArrowRight,
} from "lucide-react";

const DeepMemoryPanel = ({ compact = false }) => {
  const navigate = useNavigate();
  const [memory, setMemory] = useState(null);
  const [patternHistory, setPatternHistory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [showAllPatterns, setShowAllPatterns] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        
        // Fetch main memory
        const memoryRes = await fetch(`${API}/coach/deep-memory`, {
          credentials: "include"
        });
        if (!memoryRes.ok) throw new Error("Failed to load memory");
        const memoryData = await memoryRes.json();
        setMemory(memoryData);
        
        // Fetch detailed pattern history
        const historyRes = await fetch(`${API}/coach/deep-memory/pattern-history?limit=30`, {
          credentials: "include"
        });
        if (historyRes.ok) {
          const historyData = await historyRes.json();
          setPatternHistory(historyData);
        }
      } catch (err) {
        console.error("Failed to fetch deep memory:", err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  // Navigate to specific game and move
  const goToGameMove = (gameId, moveNumber) => {
    if (gameId && gameId !== "unknown") {
      // Navigate to game review with move parameter
      navigate(`/game/${gameId}?move=${moveNumber || 0}`);
    }
  };

  // Format relative time
  const formatTimeAgo = (dateStr) => {
    try {
      const date = new Date(dateStr);
      const now = new Date();
      const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));
      
      if (diffDays === 0) return "today";
      if (diffDays === 1) return "yesterday";
      if (diffDays < 7) return `${diffDays} days ago`;
      if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
      return date.toLocaleDateString();
    } catch {
      return "recently";
    }
  };

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

  // Pattern Entry Component - Shows clickable link to game
  const PatternEntry = ({ pattern, showDate = true }) => (
    <div 
      className="flex items-center justify-between p-2 bg-muted/30 rounded hover:bg-muted/50 transition-colors cursor-pointer group"
      onClick={() => goToGameMove(pattern.game_id, pattern.move_number)}
    >
      <div className="flex items-center gap-2 flex-1 min-w-0">
        <AlertTriangle className="w-3 h-3 text-orange-400 shrink-0" />
        <div className="truncate">
          <span className="text-xs font-medium capitalize">
            {pattern.pattern_type?.replace(/_/g, " ")}
          </span>
          <span className="text-[10px] text-muted-foreground ml-2">
            Move {pattern.move_number}
            {pattern.opponent && pattern.opponent !== "unknown" && ` vs ${pattern.opponent}`}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {showDate && (
          <span className="text-[10px] text-muted-foreground">
            {formatTimeAgo(pattern.date)}
          </span>
        )}
        <ExternalLink className="w-3 h-3 text-muted-foreground group-hover:text-primary transition-colors" />
      </div>
    </div>
  );

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

            {/* Recent Pattern History - Clickable */}
            {patternHistory?.recent_patterns?.length > 0 && (
              <div className="space-y-1">
                <div className="text-[10px] text-muted-foreground font-medium">
                  Recent mistakes (click to review):
                </div>
                {patternHistory.recent_patterns.slice(0, 3).map((p, i) => (
                  <PatternEntry key={i} pattern={p} />
                ))}
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
              <span className="text-muted-foreground font-medium">Blunder Profile</span>
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

        {/* Pattern History - CLICKABLE LINKS TO GAMES */}
        {patternHistory?.recent_patterns?.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-muted-foreground font-medium">
                <History className="w-3 h-3" />
                <span>Your Mistake History</span>
              </div>
              <span className="text-[10px] text-muted-foreground">
                {patternHistory.total_patterns} total
              </span>
            </div>
            
            <div className="text-[10px] text-muted-foreground mb-2">
              Click any mistake to review in that game:
            </div>
            
            <div className="space-y-1 max-h-48 overflow-y-auto">
              {patternHistory.recent_patterns
                .slice(0, showAllPatterns ? 20 : 5)
                .map((pattern, i) => (
                  <PatternEntry key={i} pattern={pattern} />
                ))}
            </div>
            
            {patternHistory.recent_patterns.length > 5 && (
              <Button
                variant="ghost"
                size="sm"
                className="w-full text-xs h-7"
                onClick={() => setShowAllPatterns(!showAllPatterns)}
              >
                {showAllPatterns ? "Show Less" : `Show ${patternHistory.recent_patterns.length - 5} More`}
                <ArrowRight className={`w-3 h-3 ml-1 transition-transform ${showAllPatterns ? "rotate-90" : ""}`} />
              </Button>
            )}
          </div>
        )}

        {/* Grouped by Type */}
        {patternHistory?.grouped_by_type && Object.keys(patternHistory.grouped_by_type).length > 0 && (
          <div className="space-y-2 pt-2 border-t border-border/50">
            <div className="text-muted-foreground font-medium text-[10px]">
              Mistakes by Type:
            </div>
            <div className="flex flex-wrap gap-1">
              {Object.entries(patternHistory.grouped_by_type).map(([type, patterns]) => (
                <Badge 
                  key={type} 
                  variant="outline" 
                  className="text-[10px] cursor-pointer hover:bg-muted transition-colors"
                  onClick={() => {
                    // Navigate to most recent game with this pattern
                    const recent = patterns[0];
                    if (recent) goToGameMove(recent.game_id, recent.move_number);
                  }}
                >
                  {type.replace(/_/g, " ")} ({patterns.length})
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
