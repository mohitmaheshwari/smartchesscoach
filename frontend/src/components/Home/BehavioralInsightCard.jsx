/**
 * BehavioralInsightCard
 * 
 * Shows BEHAVIORAL coaching insights, not just "0 blunders, 1 mistake"
 * 
 * Displays:
 * - Headline (one sentence coach insight)
 * - Rich insight (2-3 sentences with history context)
 * - Root cause badge (TIME_TRIGGERED, OVERCONFIDENCE, etc.) [P1]
 * - Scorecard chips (Plan Discipline, Decision Stability, etc.)
 * - Stagnation styling when stuck in same loop [P1]
 * - One mission CTA
 */

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { 
  Brain,
  ChevronRight,
  Target,
  Zap,
  Shield,
  TrendingUp,
  Clock,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Timer,
  Trophy,
  Calculator,
  ShieldAlert,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const API = process.env.REACT_APP_BACKEND_URL || "";

const BehavioralInsightCard = ({ gameId, lastGame }) => {
  const navigate = useNavigate();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchReport = async () => {
      if (!gameId) {
        setLoading(false);
        return;
      }
      
      try {
        const res = await fetch(`${API}/api/behavioral/analyze/${gameId}`, {
          credentials: "include",
        });
        
        if (res.ok) {
          const data = await res.json();
          setReport(data);
        } else {
          setError("Could not load behavioral report");
        }
      } catch (err) {
        setError("Failed to fetch report");
      } finally {
        setLoading(false);
      }
    };

    fetchReport();
  }, [gameId]);

  if (loading) {
    return (
      <div className="rounded-xl border bg-card p-5">
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  if (error || !report || report.error) {
    // Fallback to simple display if behavioral report fails
    return null;
  }

  const { 
    headline, 
    rich_insight, 
    scorecard, 
    next_mission, 
    confidence_label,
    root_cause,
    root_cause_label,
    stagnation,
    stagnation_info,
  } = report;

  // Get label colors
  const getLabelColor = (label) => {
    switch (label) {
      case "Excellent": return "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
      case "Good": return "bg-blue-500/20 text-blue-400 border-blue-500/30";
      case "Mixed": return "bg-amber-500/20 text-amber-400 border-amber-500/30";
      case "Concern": return "bg-red-500/20 text-red-400 border-red-500/30";
      default: return "bg-muted text-muted-foreground";
    }
  };

  // Root cause icon and colors
  const getRootCauseIcon = (cause) => {
    switch (cause) {
      case "TIME_TRIGGERED": return <Timer className="w-3 h-3" />;
      case "OVERCONFIDENCE": return <Trophy className="w-3 h-3" />;
      case "CALCULATION_GAP": return <Calculator className="w-3 h-3" />;
      case "DEFENSIVE_STRESS": return <ShieldAlert className="w-3 h-3" />;
      default: return <AlertTriangle className="w-3 h-3" />;
    }
  };

  const getRootCauseColor = (cause) => {
    switch (cause) {
      case "TIME_TRIGGERED": return "bg-orange-500/20 text-orange-400 border-orange-500/40";
      case "OVERCONFIDENCE": return "bg-yellow-500/20 text-yellow-400 border-yellow-500/40";
      case "CALCULATION_GAP": return "bg-blue-500/20 text-blue-400 border-blue-500/40";
      case "DEFENSIVE_STRESS": return "bg-purple-500/20 text-purple-400 border-purple-500/40";
      default: return "bg-muted text-muted-foreground";
    }
  };

  // Get icon for scorecard dimension
  const getDimensionIcon = (key) => {
    switch (key) {
      case "plan_discipline": return <Target className="w-3 h-3" />;
      case "decision_stability": return <Shield className="w-3 h-3" />;
      case "pattern_persistence": return <TrendingUp className="w-3 h-3" />;
      case "coach_compliance": return <CheckCircle2 className="w-3 h-3" />;
      case "learning_velocity": return <Zap className="w-3 h-3" />;
      default: return null;
    }
  };

  // Format dimension name
  const formatDimensionName = (key) => {
    return key.split("_").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
  };

  // Filter to show only the most relevant scorecard items (non-placeholder)
  const relevantScores = Object.entries(scorecard || {}).filter(
    ([key, item]) => !item.why?.includes("coming soon") && key !== "coach_compliance" && key !== "learning_velocity"
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border bg-card p-5 space-y-4"
      data-testid="behavioral-insight-card"
    >
      {/* Header with brain icon */}
      <div className="flex items-center gap-2">
        <Brain className="w-5 h-5 text-primary" />
        <span className="text-sm font-medium text-muted-foreground">
          Last Game • Coach Analysis
        </span>
        {confidence_label && (
          <Badge variant="outline" className="text-xs ml-auto">
            {confidence_label} confidence
          </Badge>
        )}
      </div>

      {/* Headline - The main insight */}
      <div className="space-y-2">
        <h3 className="text-lg font-semibold leading-tight">
          {headline}
        </h3>
        
        {/* Rich insight - 2-3 sentences */}
        <p className="text-sm text-muted-foreground leading-relaxed">
          {rich_insight}
        </p>
      </div>

      {/* Scorecard chips - horizontal scroll on mobile */}
      <div className="flex flex-wrap gap-2">
        {relevantScores.map(([key, item]) => (
          <div
            key={key}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs ${getLabelColor(item.label)}`}
            title={item.why}
          >
            {getDimensionIcon(key)}
            <span>{formatDimensionName(key)}</span>
            <span className="font-medium">{item.score}</span>
          </div>
        ))}
      </div>

      {/* Mission CTA */}
      {next_mission && (
        <div className="pt-2 border-t border-border/50">
          <div className="flex items-start gap-3">
            <div className="p-2 rounded-lg bg-primary/10">
              <Target className="w-4 h-4 text-primary" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium">{next_mission.title}</p>
              <p className="text-xs text-muted-foreground line-clamp-2">
                {next_mission.instruction}
              </p>
            </div>
          </div>
          
          <Button 
            className="w-full mt-3"
            onClick={() => navigate(`/game/${gameId}`)}
            data-testid="review-game-btn"
          >
            Review This Game
            <ChevronRight className="w-4 h-4 ml-2" />
          </Button>
        </div>
      )}
    </motion.div>
  );
};

export default BehavioralInsightCard;
