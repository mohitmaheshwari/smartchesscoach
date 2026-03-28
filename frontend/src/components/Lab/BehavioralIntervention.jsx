/**
 * BehavioralIntervention - Assigns thinking habits based on diagnosed patterns
 * 
 * Shows:
 * - The diagnosed behavioral pattern
 * - What it means
 * - A specific intervention/thinking habit
 * - A practice rule to follow
 */

import { useState, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { API } from "@/App";
import {
  Brain,
  Target,
  ChevronDown,
  ChevronUp,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Sparkles
} from "lucide-react";
import { motion } from "framer-motion";

const PATTERN_ICONS = {
  hope_chess: "🎲",
  impulsive_play: "⚡",
  tunnel_vision: "🔭",
  passive_play: "🐢",
  overextension: "🚀",
  material_obsession: "💰"
};

const PATTERN_LABELS = {
  hope_chess: "Hope Chess",
  impulsive_play: "Impulsive Play",
  tunnel_vision: "Tunnel Vision",
  passive_play: "Passive Play",
  overextension: "Overextension",
  material_obsession: "Material Obsession"
};

const BehavioralIntervention = ({
  pattern,
  examples = [],
  autoFetch = true,
  compact = true,
  onDismiss
}) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(!compact);
  const [committed, setCommitted] = useState(false);

  useEffect(() => {
    if (autoFetch && pattern) {
      fetchIntervention();
    }
  }, [pattern, autoFetch]);

  const fetchIntervention = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/thinking-coach/behavioral-intervention`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          behavioral_pattern: pattern,
          examples
        })
      });
      if (res.ok) {
        const result = await res.json();
        setData(result);
      }
    } catch (e) {
      console.error("Failed to fetch behavioral intervention:", e);
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

  const icon = PATTERN_ICONS[pattern] || "🧠";
  const label = PATTERN_LABELS[pattern] || pattern;

  // Compact view
  if (compact && !expanded) {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={() => setExpanded(true)}
        className="w-full justify-between bg-rose-500/10 border-rose-500/30 hover:bg-rose-500/20 text-rose-300"
        data-testid="behavioral-intervention-expand"
      >
        <div className="flex items-center gap-2">
          <span>{icon}</span>
          <span className="text-xs">Pattern: {label}</span>
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
      <Card className="border-rose-500/30 bg-rose-500/5" data-testid="behavioral-intervention">
        <CardContent className="p-4">
          {/* Header */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="text-lg">{icon}</span>
              <span className="text-sm font-medium text-rose-300">Behavioral Pattern Detected</span>
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

          {/* Pattern Badge */}
          <div className="mb-4">
            <Badge className="bg-rose-500/20 text-rose-300 border-rose-500/50 text-sm px-3 py-1">
              {label}
            </Badge>
          </div>

          {/* Diagnosis */}
          <div className="p-3 rounded-lg bg-background/50 border border-border/50 mb-3">
            <div className="flex items-center gap-2 mb-1">
              <AlertCircle className="w-4 h-4 text-rose-400" />
              <span className="text-xs font-medium text-rose-400">What This Means</span>
            </div>
            <p className="text-sm text-foreground">{data.diagnosis}</p>
          </div>

          {/* Intervention */}
          <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/30 mb-3">
            <div className="flex items-center gap-2 mb-1">
              <Brain className="w-4 h-4 text-blue-400" />
              <span className="text-xs font-medium text-blue-400">Your New Thinking Habit</span>
            </div>
            <p className="text-sm text-blue-200 font-medium">{data.intervention}</p>
          </div>

          {/* Practice Rule */}
          <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/30 mb-4">
            <div className="flex items-center gap-2 mb-1">
              <Target className="w-4 h-4 text-green-400" />
              <span className="text-xs font-medium text-green-400">Practice Rule</span>
            </div>
            <p className="text-sm text-green-200">{data.practice_rule}</p>
          </div>

          {/* Commitment Button */}
          {!committed ? (
            <Button
              onClick={() => setCommitted(true)}
              className="w-full gap-2 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600"
              data-testid="commit-to-habit-btn"
            >
              <Sparkles className="w-4 h-4" />
              I'll Practice This
            </Button>
          ) : (
            <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/30 text-center">
              <div className="flex items-center justify-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-green-400" />
                <span className="text-sm text-green-400 font-medium">Committed! Apply this in your next game.</span>
              </div>
            </div>
          )}

          {/* Examples (if provided) */}
          {data.examples && data.examples.length > 0 && (
            <div className="mt-4 pt-4 border-t border-border/30">
              <p className="text-xs text-muted-foreground mb-2">Examples from your games:</p>
              <div className="space-y-2">
                {data.examples.map((ex, i) => (
                  <div key={i} className="text-xs text-muted-foreground bg-background/30 p-2 rounded">
                    Move {ex.move_number}: {ex.description}
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
};

export default BehavioralIntervention;
