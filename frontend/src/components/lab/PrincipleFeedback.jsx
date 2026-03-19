/**
 * PrincipleFeedback - Connects mistakes to fundamental principles
 * 
 * Shows:
 * - The violated principle
 * - Why it matters
 * - A thinking habit to build
 * - What to do instead
 */

import { useState, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { API } from "@/App";
import {
  BookOpen,
  Lightbulb,
  Brain,
  ChevronDown,
  ChevronUp,
  Loader2,
  AlertTriangle,
  CheckCircle2
} from "lucide-react";
import { motion } from "framer-motion";

const PrincipleFeedback = ({
  mistakeType,
  fen,
  movePlayed,
  bestMove,
  autoFetch = true,
  compact = true
}) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(!compact);

  useEffect(() => {
    if (autoFetch && mistakeType && fen && movePlayed && bestMove) {
      fetchFeedback();
    }
  }, [mistakeType, fen, movePlayed, bestMove, autoFetch]);

  const fetchFeedback = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/thinking-coach/principle-feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          mistake_type: mistakeType,
          fen,
          move_played: movePlayed,
          best_move: bestMove
        })
      });
      if (res.ok) {
        const result = await res.json();
        setData(result);
      }
    } catch (e) {
      console.error("Failed to fetch principle feedback:", e);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="p-3 text-center text-muted-foreground">
        <Loader2 className="w-4 h-4 animate-spin mx-auto" />
      </div>
    );
  }

  if (!data) return null;

  // Compact view
  if (compact && !expanded) {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={() => setExpanded(true)}
        className="w-full justify-between bg-amber-500/10 border-amber-500/30 hover:bg-amber-500/20 text-amber-300"
        data-testid="principle-feedback-expand"
      >
        <div className="flex items-center gap-2">
          <BookOpen className="w-4 h-4" />
          <span className="text-xs">Principle: {data.principle}</span>
        </div>
        <ChevronDown className="w-4 h-4" />
      </Button>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      exit={{ opacity: 0, height: 0 }}
    >
      <Card className="border-amber-500/30 bg-amber-500/5" data-testid="principle-feedback">
        <CardContent className="p-4">
          {/* Header */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-amber-400" />
              <span className="text-sm font-medium text-amber-300">Fundamental Principle</span>
            </div>
            {compact && (
              <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0"
                onClick={() => setExpanded(false)}
              >
                <ChevronUp className="w-3 h-3" />
              </Button>
            )}
          </div>

          {/* Principle Name */}
          <div className="mb-4">
            <Badge className="bg-amber-500/20 text-amber-300 border-amber-500/50 text-sm px-3 py-1">
              {data.principle}
            </Badge>
          </div>

          {/* Explanation */}
          <div className="p-3 rounded-lg bg-background/50 border border-border/50 mb-3">
            <p className="text-sm text-foreground">{data.explanation}</p>
          </div>

          {/* Applied to Position */}
          {data.applied_to_position && (
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 mb-3">
              <div className="flex items-center gap-2 mb-1">
                <AlertTriangle className="w-4 h-4 text-red-400" />
                <span className="text-xs font-medium text-red-400">In This Position</span>
              </div>
              <p className="text-sm text-red-200">{data.applied_to_position}</p>
            </div>
          )}

          {/* Thinking Habit */}
          <div className="p-3 rounded-lg bg-purple-500/10 border border-purple-500/30 mb-3">
            <div className="flex items-center gap-2 mb-1">
              <Brain className="w-4 h-4 text-purple-400" />
              <span className="text-xs font-medium text-purple-400">Thinking Habit to Build</span>
            </div>
            <p className="text-sm text-purple-200 italic">"{data.thinking_habit}"</p>
          </div>

          {/* What to Do Instead */}
          {data.what_to_do_instead && (
            <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/30">
              <div className="flex items-center gap-2 mb-1">
                <CheckCircle2 className="w-4 h-4 text-green-400" />
                <span className="text-xs font-medium text-green-400">What to Do Instead</span>
              </div>
              <p className="text-sm text-green-200">{data.what_to_do_instead}</p>
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
};

export default PrincipleFeedback;
