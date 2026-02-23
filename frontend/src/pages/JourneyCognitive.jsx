/**
 * JOURNEY PAGE - Stat-Light Cognitive Evolution
 * 
 * Purpose: Behavioral truth, not arithmetic.
 * 
 * Default mode = meaning.
 * Advanced toggle = numbers.
 * 
 * Users think in identity:
 * "I relax when ahead."
 * "I rush critical moments."
 * "I lose structure in middlegames."
 */

import { useState, useEffect } from "react";
import { API } from "@/App";
import { Card, CardContent } from "@/components/ui/card";
import Layout from "@/components/Layout";
import { Loader2, ChevronDown, ChevronUp } from "lucide-react";

// Pattern name mapping
const PATTERN_NAMES = {
  "random_move_critical": "Critical Moment Drift",
  "missed_forcing_move": "Missed Forcing Move",
  "ignored_opponent_forcing": "Ignored Opponent Forcing",
  "phantom_threat_reaction": "Phantom Threat Reaction",
  "advantage_mismanagement": "Advantage Mismanagement",
  "structural_misjudgment": "Structural Misjudgment",
  "time_pressure_collapse": "Time Pressure Collapse"
};

const getPatternName = (key) => PATTERN_NAMES[key] || key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

// Behavioral explanations - no numbers, pure meaning
const getPatternBehavior = (category, status) => {
  const behaviors = {
    "random_move_critical": {
      "Improving": "Reduced instability in high-pressure positions.",
      "Worsening": "Increased drift in critical decision moments."
    },
    "missed_forcing_move": {
      "Improving": "Better recognition of decisive opportunities.",
      "Worsening": "More forcing moves being overlooked."
    },
    "structural_misjudgment": {
      "Improving": "Clearer evaluation of positional factors.",
      "Worsening": "More frequent positional miscalculations."
    },
    "advantage_mismanagement": {
      "Improving": "Stronger technique when converting advantages.",
      "Worsening": "More carelessness after gaining an edge."
    },
    "time_pressure_collapse": {
      "Improving": "Better composure under time pressure.",
      "Worsening": "Decision quality drops more under clock pressure."
    }
  };
  return behaviors[category]?.[status] || (status === "Improving" 
    ? "This pattern is becoming less frequent."
    : "This pattern is becoming more frequent.");
};

const Journey = ({ user }) => {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [showMetrics, setShowMetrics] = useState(false);

  useEffect(() => {
    fetchJourneyData();
  }, []);

  const fetchJourneyData = async () => {
    try {
      const response = await fetch(`${API}/cognitive/journey`, { credentials: "include" });
      if (response.ok) {
        const result = await response.json();
        setData(result);
      } else {
        setError("Failed to load journey data");
      }
    } catch (e) {
      console.error("Failed to fetch journey data:", e);
      setError("Failed to load journey data");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      </Layout>
    );
  }

  if (error) {
    return (
      <Layout user={user}>
        <div className="max-w-4xl mx-auto px-4 py-8">
          <p className="text-red-400">{error}</p>
        </div>
      </Layout>
    );
  }

  // Not activated yet
  if (!data.activated) {
    return (
      <Layout user={user}>
        <div className="max-w-4xl mx-auto px-4 py-8 space-y-8" data-testid="journey-page">
          <div>
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-1">
              Cognitive Evolution
            </p>
            <h1 className="text-2xl font-semibold text-white">Journey</h1>
          </div>

          <Card className="border-slate-700 bg-slate-900/50">
            <CardContent className="p-8 text-center">
              <p className="text-lg text-white mb-2">
                Journey will activate after {data.games_required} analyzed games.
              </p>
              <p className="text-sm text-muted-foreground">
                We need at least 10 games to detect meaningful cognitive shifts.
              </p>
              <p className="text-sm text-slate-500 mt-4">
                Games analyzed: {data.games_analyzed} / {data.games_required}
              </p>
            </CardContent>
          </Card>
        </div>
      </Layout>
    );
  }

  const { stability_momentum, pattern_shifts, context_shift, phase_shift } = data;

  // Generate behavioral stability text
  const getStabilityBehavior = () => {
    if (!stability_momentum.valid) {
      return "Not enough data to assess stability trends yet.";
    }
    if (stability_momentum.delta >= 5) {
      return "Your recent games show more consistent decision-making compared to earlier games.";
    }
    if (stability_momentum.delta <= -5) {
      return "Your recent games show less consistent decision-making compared to earlier games.";
    }
    return "Your decision-making consistency has remained steady.";
  };

  // Generate advantage discipline behavior
  const getAdvantageBehavior = () => {
    if (data.context_unchanged) {
      return "Your discipline when ahead has remained consistent.";
    }
    if (context_shift.direction === "Increased") {
      return "You are losing focus after gaining an advantage more often than before.";
    }
    return "You are maintaining focus better after gaining an advantage.";
  };

  return (
    <Layout user={user}>
      <div className="max-w-4xl mx-auto px-4 py-8 space-y-6" data-testid="journey-page">
        {/* Page Header */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-1">
              Cognitive Evolution
            </p>
            <h1 className="text-2xl font-semibold text-white">Journey</h1>
          </div>
          
          {/* Metrics Toggle */}
          <button
            onClick={() => setShowMetrics(!showMetrics)}
            className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors"
            data-testid="metrics-toggle"
          >
            {showMetrics ? "Hide Metrics" : "View Metrics"}
            {showMetrics ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>
        </div>

        {/* SECTION 1: Cognitive Momentum - The headline story */}
        <Card className="border-slate-700 bg-slate-900/50">
          <CardContent className="p-6">
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-3">
              Cognitive Momentum
            </p>
            <p className="text-base text-white leading-relaxed">
              {data.cognitive_summary}
            </p>
          </CardContent>
        </Card>

        {/* SECTION 2: Stability Trend */}
        <Card className="border-slate-700 bg-slate-900/50">
          <CardContent className="p-6">
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-3">
              Stability Trend
            </p>
            <p className="text-sm text-slate-300">
              {getStabilityBehavior()}
            </p>
            
            {/* Optional metrics */}
            {showMetrics && stability_momentum.valid && (
              <div className="mt-3 pt-3 border-t border-slate-700/50 text-xs text-slate-500">
                Previous 5: {stability_momentum.previous_tsi} | Recent 5: {stability_momentum.recent_tsi} | Change: {stability_momentum.delta >= 0 ? "+" : ""}{stability_momentum.delta}
              </div>
            )}
          </CardContent>
        </Card>

        {/* SECTION 3: Pattern Evolution */}
        <Card className="border-slate-700 bg-slate-900/50">
          <CardContent className="p-6">
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-4">
              Pattern Evolution
            </p>
            
            {data.no_pattern_shifts ? (
              <p className="text-sm text-slate-400">
                Your cognitive patterns have remained stable.
              </p>
            ) : (
              <div className="space-y-4">
                {pattern_shifts.map((shift, idx) => (
                  <div key={shift.category} data-testid={`pattern-shift-${idx}`}>
                    <p className="text-sm font-medium text-white mb-1">
                      {getPatternName(shift.category)}
                    </p>
                    <p className="text-sm text-slate-400">
                      {getPatternBehavior(shift.category, shift.status)}
                    </p>
                    
                    {/* Optional metrics */}
                    {showMetrics && (
                      <p className="text-xs text-slate-600 mt-1">
                        {shift.previous_band} → {shift.recent_band} ({shift.status})
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* SECTION 4: Advantage Discipline */}
        <Card className="border-slate-700 bg-slate-900/50">
          <CardContent className="p-6">
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-3">
              Advantage Discipline
            </p>
            <p className="text-sm text-slate-300">
              {getAdvantageBehavior()}
            </p>
            
            {/* Optional metrics */}
            {showMetrics && !data.context_unchanged && (
              <div className="mt-3 pt-3 border-t border-slate-700/50 text-xs text-slate-500">
                Blunders when ahead: {context_shift.previous}% → {context_shift.recent}% ({context_shift.change > 0 ? "+" : ""}{context_shift.change}%)
              </div>
            )}
          </CardContent>
        </Card>

        {/* SECTION 5: Phase Stability */}
        <Card className="border-slate-700 bg-slate-900/50">
          <CardContent className="p-6">
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-3">
              Phase Stability
            </p>
            
            {phase_shift.changed ? (
              <p className="text-sm text-slate-300">
                Your instability has shifted from <span className="text-white">{phase_shift.previous}</span> to <span className="text-white">{phase_shift.recent}</span>.
              </p>
            ) : (
              <p className="text-sm text-slate-300">
                <span className="text-white">{phase_shift.recent}</span> remains your most unstable phase.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </Layout>
  );
};

export default Journey;
