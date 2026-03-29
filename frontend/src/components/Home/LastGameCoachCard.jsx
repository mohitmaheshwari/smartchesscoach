/**
 * LastGameCoachCard - Renders GameCoachSummary from Single Source of Truth
 * 
 * Shows in order (as per spec):
 * 1. Confidence pill (Low/Medium/High)
 * 2. Root Cause / Primary Issue (human label)
 * 3. Emotion mirror line ("You rushed here.")
 * 4. Coach explain line (positional + contextual)
 * 5. Theme reinforcement line (if ties to active theme)
 * 6. One CTA: "Review Critical Moment" OR "Start 3-min Drill"
 * 
 * Tone: Indian coach - Direct, calm, slightly firm
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  ChevronRight,
  Target,
  AlertCircle,
  Loader2,
  ArrowRight,
  Brain,
  Zap
} from "lucide-react";

// Map confidence to colors
const CONFIDENCE_STYLES = {
  Low: "bg-slate-500/20 text-slate-300 border-slate-500/30",
  Medium: "bg-amber-500/20 text-amber-300 border-amber-500/30",
  High: "bg-red-500/20 text-red-300 border-red-500/30"
};

// Map primary issue to display name
const ISSUE_LABELS = {
  ThreatScanFailure: "Threat Scan Failure",
  RushedWhenAhead: "Rushed When Ahead",
  StoppedCalculationEarly: "Stopped Calculation Early",
  PieceLeftUndefended: "Piece Left Undefended",
  MissedTactic: "Missed Tactic",
  PoorPiecePlacement: "Poor Piece Placement",
  KingSafetyNeglect: "King Safety Neglect",
  TimePressureCollapse: "Time Pressure Collapse",
  OpeningInaccuracy: "Opening Inaccuracy",
  EndgameTechniqueFailure: "Endgame Technique Failure",
  PrematureAttack: "Premature Attack",
  DefensiveLapse: "Defensive Lapse"
};

const LastGameCoachCard = ({ gameId }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchSummary();
  }, [gameId]);

  const fetchSummary = async () => {
    try {
      setLoading(true);
      
      // Try to get existing summary first
      const res = await fetch(`${API}/coach/last-game-summary`, { 
        credentials: "include" 
      });
      
      if (res.ok) {
        const data = await res.json();
        if (data.has_summary) {
          setSummary(data);
        } else if (gameId) {
          // Generate summary for this game
          const genRes = await fetch(`${API}/coach/generate-summary/${gameId}`, {
            method: "POST",
            credentials: "include"
          });
          if (genRes.ok) {
            setSummary(await genRes.json());
          }
        }
      }
    } catch (err) {
      console.error("Error fetching game summary:", err);
      setError("Failed to load coach analysis");
    } finally {
      setLoading(false);
    }
  };

  const handleCTA = () => {
    if (summary?.cta_target) {
      navigate(summary.cta_target);
    }
  };

  if (loading) {
    return (
      <div className="rounded-xl border border-border bg-card p-4">
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span className="text-sm">Analyzing your last game...</span>
        </div>
      </div>
    );
  }

  if (!summary || error) {
    return null; // Don't show card if no summary
  }

  const issueLabel = ISSUE_LABELS[summary.primary_issue] || summary.primary_issue;
  const confidenceStyle = CONFIDENCE_STYLES[summary.confidence] || CONFIDENCE_STYLES.Medium;

  return (
    <div 
      className="rounded-xl border border-border bg-card overflow-hidden"
      data-testid="last-game-coach-card"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <Brain className="w-4 h-4 text-primary" />
          <span className="text-sm font-medium">Last Game • Coach Analysis</span>
        </div>
        <Badge 
          variant="outline" 
          className={`text-xs ${confidenceStyle}`}
        >
          {summary.confidence} confidence
        </Badge>
      </div>

      {/* Content - In exact order from spec */}
      <div className="p-4 space-y-3">
        {/* 1. Root Cause / Primary Issue */}
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded bg-destructive/10">
            <AlertCircle className="w-4 h-4 text-destructive" />
          </div>
          <span className="font-medium text-destructive">
            Root Cause: {issueLabel}
          </span>
        </div>

        {/* 2. Emotion mirror line */}
        <p className="text-sm text-foreground font-medium pl-0.5">
          "{summary.emotion_mirror_line}"
        </p>

        {/* 3. Coach explain line */}
        <p className="text-sm text-muted-foreground pl-0.5">
          {summary.coach_explain_line}
        </p>

        {/* 4. Theme reinforcement line (if ties) */}
        {summary.ties_to_active_theme && summary.theme_reinforcement_line && (
          <div className="flex items-start gap-2 mt-2 p-2 rounded-lg bg-primary/5 border border-primary/20">
            <Target className="w-4 h-4 text-primary mt-0.5" />
            <p className="text-sm text-primary">
              {summary.theme_reinforcement_line}
            </p>
          </div>
        )}

        {/* 5. Move reference */}
        {summary.primary_moment && summary.primary_moment.move_number > 1 && (
          <p className="text-xs text-muted-foreground pl-0.5">
            Critical moment: {summary.primary_moment.label}
          </p>
        )}
      </div>

      {/* 6. Single CTA */}
      <div className="px-4 pb-4">
        <Button 
          onClick={handleCTA}
          className="w-full gap-2"
          variant={summary.cta_type === "start_drill" ? "default" : "outline"}
          data-testid="last-game-cta"
        >
          {summary.cta_type === "start_drill" ? (
            <Zap className="w-4 h-4" />
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
          {summary.cta_text}
        </Button>
      </div>
    </div>
  );
};

export default LastGameCoachCard;
