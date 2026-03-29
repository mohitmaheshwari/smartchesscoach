/**
 * CoachMemoryPanel.jsx - Compact view of what coach KNOWS about you
 * 
 * COMPACT DESIGN - Single line with expandable details
 * Shows: games together, today's focus, key pattern (if any)
 */

import { useState, useEffect } from "react";
import { API } from "@/App";
import { Badge } from "@/components/ui/badge";
import {
  Brain,
  Target,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Loader2,
  TrendingUp,
} from "lucide-react";

const CoachMemoryPanel = ({ sessionId }) => {
  const [memory, setMemory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);

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
      } finally {
        setLoading(false);
      }
    };
    fetchMemory();
  }, [sessionId]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground py-2">
        <Loader2 className="w-3 h-3 animate-spin" />
        <span>Loading memory...</span>
      </div>
    );
  }

  if (!memory?.context) return null;

  const ctx = memory.context;
  const gamesPlayed = ctx.games_played || 0;
  const watchFor = ctx.watch_for || [];
  const focusSuggestion = ctx.focus_suggestion;
  const topPattern = watchFor[0];

  // Minimal view for new users
  if (gamesPlayed < 2 && watchFor.length === 0) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground py-2 px-1" data-testid="coach-memory-panel">
        <Brain className="w-3 h-3 text-primary" />
        <span>Game #{gamesPlayed + 1} together</span>
      </div>
    );
  }

  return (
    <div className="py-2 px-1" data-testid="coach-memory-panel">
      {/* Compact Header - Always Visible */}
      <button 
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between text-xs hover:bg-muted/30 rounded px-1 py-1 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Brain className="w-3 h-3 text-primary" />
          <span className="font-medium">Game #{gamesPlayed + 1}</span>
          {topPattern && (
            <span className="text-muted-foreground">
              • Watch: {topPattern.name.split(" ")[0]}
              {topPattern.improving && <TrendingUp className="w-3 h-3 inline ml-1 text-green-400" />}
            </span>
          )}
        </div>
        {(focusSuggestion || watchFor.length > 0) && (
          expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />
        )}
      </button>

      {/* Expandable Details */}
      {expanded && (
        <div className="mt-2 space-y-2 text-xs pl-5">
          {/* Focus */}
          {focusSuggestion && (
            <div className="flex items-center gap-2 text-amber-400">
              <Target className="w-3 h-3" />
              <span>{focusSuggestion}</span>
            </div>
          )}
          
          {/* Patterns */}
          {watchFor.length > 0 && (
            <div className="space-y-1">
              {watchFor.slice(0, 2).map((p, i) => (
                <div key={i} className="flex items-center gap-2">
                  <AlertTriangle className={`w-3 h-3 ${p.improving ? "text-green-400" : "text-orange-400"}`} />
                  <span>{p.name}</span>
                  <Badge variant="outline" className="text-[10px] px-1 py-0">{p.count}x</Badge>
                  {p.improving && <span className="text-green-400 text-[10px]">improving</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default CoachMemoryPanel;
