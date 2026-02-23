/**
 * JOURNEY PAGE - Cognitive Evolution System
 * 
 * Architecture:
 * 1. SHORT-TERM MOMENTUM (5 vs 5)
 * 2. LONG-TERM GROWTH ARC (Early vs Recent)
 * 
 * Core Principle: Never "invent insight" - all commentary derived from measured deltas.
 * 
 * Page Structure (LOCKED):
 * - Cognitive Momentum (5 vs 5): Stability, Pattern, Advantage, Phase
 * - Divider
 * - Growth Arc (Early vs Recent): Stability Growth, Driver Evolution, Peer Comparison, Phase Evolution
 */

import { useState, useEffect } from "react";
import { API } from "@/App";
import { Card, CardContent } from "@/components/ui/card";
import Layout from "@/components/Layout";
import { Loader2, ChevronDown, ChevronUp } from "lucide-react";

// Pattern name mapping
const PATTERN_NAMES = {
  "structural_misjudgment": "Structural Misjudgment",
  "critical_moment_drift": "Critical Moment Drift",
  "missed_forcing_move": "Missed Forcing Move",
  "random_critical_move": "Critical Moment Drift",
  "advantage_mismanagement": "Advantage Mismanagement",
  "time_pressure_collapse": "Time Pressure Collapse"
};

const getPatternName = (key) => PATTERN_NAMES[key] || key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

// Behavioral explanations derived from measured deltas
const getPatternBehavior = (category, status) => {
  const behaviors = {
    "structural_misjudgment": {
      "improving": "Positional evaluation has improved.",
      "worsening": "Positional misjudgments have increased."
    },
    "critical_moment_drift": {
      "improving": "Reduced instability in high-pressure positions.",
      "worsening": "Increased drift in critical decision moments."
    },
    "random_critical_move": {
      "improving": "Reduced instability in high-pressure positions.",
      "worsening": "Increased drift in critical decision moments."
    },
    "missed_forcing_move": {
      "improving": "Better recognition of forcing opportunities.",
      "worsening": "More forcing moves being overlooked."
    },
    "advantage_mismanagement": {
      "improving": "Better technique when converting advantages.",
      "worsening": "More carelessness after gaining an edge."
    }
  };
  return behaviors[category]?.[status] || (status === "improving" 
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

  // Not activated - Safety Guard
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
              <p className="text-sm text-slate-400">
                {data.message}
              </p>
              {data.games_required && (
                <p className="text-xs text-slate-600 mt-4">
                  Games analyzed: {data.games_analyzed} / {data.games_required}
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </Layout>
    );
  }

  const { momentum, growth_arc } = data;

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

        {/* Cognitive Summary */}
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

        {/* ============================================ */}
        {/* SHORT-TERM MOMENTUM (5 vs 5) */}
        {/* ============================================ */}

        {/* Stability Delta */}
        <Card className="border-slate-700 bg-slate-900/50">
          <CardContent className="p-6">
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-3">
              Stability Trend
            </p>
            <p className="text-sm text-slate-300">
              {momentum.stability.text}
            </p>
            
            {showMetrics && (
              <div className="mt-3 pt-3 border-t border-slate-700/50 text-xs text-slate-500">
                Previous 5: {momentum.stability.previous_avg} | Recent 5: {momentum.stability.recent_avg} | Delta: {momentum.stability.delta >= 0 ? "+" : ""}{momentum.stability.delta}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Pattern Shifts */}
        <Card className="border-slate-700 bg-slate-900/50">
          <CardContent className="p-6">
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-4">
              Pattern Evolution
            </p>
            
            {momentum.no_pattern_shifts ? (
              <p className="text-sm text-slate-400">
                No significant pattern shifts detected.
              </p>
            ) : (
              <div className="space-y-4">
                {momentum.pattern_shifts.map((shift, idx) => (
                  <div key={shift.category} data-testid={`pattern-shift-${idx}`}>
                    <p className="text-sm font-medium text-white mb-1">
                      {getPatternName(shift.category)}
                    </p>
                    <p className="text-sm text-slate-400">
                      {getPatternBehavior(shift.category, shift.status)}
                    </p>
                    
                    {showMetrics && (
                      <p className="text-xs text-slate-600 mt-1">
                        {shift.previous_band} → {shift.recent_band}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Advantage Discipline */}
        <Card className="border-slate-700 bg-slate-900/50">
          <CardContent className="p-6">
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-3">
              Advantage Discipline
            </p>
            
            {momentum.context_unchanged ? (
              <p className="text-sm text-slate-400">
                No meaningful context shift.
              </p>
            ) : (
              <>
                <p className="text-sm text-slate-300">
                  {momentum.context_shift.status === "worsening"
                    ? "You are losing focus after gaining an advantage more often."
                    : "You are maintaining focus better after gaining an advantage."}
                </p>
                
                {showMetrics && (
                  <div className="mt-3 pt-3 border-t border-slate-700/50 text-xs text-slate-500">
                    Blunders when ahead: {momentum.context_shift.previous_rate}% → {momentum.context_shift.recent_rate}% ({momentum.context_shift.delta > 0 ? "+" : ""}{momentum.context_shift.delta}%)
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>

        {/* Phase Stability */}
        <Card className="border-slate-700 bg-slate-900/50">
          <CardContent className="p-6">
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-3">
              Phase Stability
            </p>
            
            {momentum.phase.changed ? (
              <p className="text-sm text-slate-300">
                Primary instability shifted from <span className="text-white">{momentum.phase.previous}</span> to <span className="text-white">{momentum.phase.recent}</span>.
              </p>
            ) : (
              <p className="text-sm text-slate-300">
                <span className="text-white">{momentum.phase.recent}</span> remains your most unstable phase.
              </p>
            )}
          </CardContent>
        </Card>

        {/* ============================================ */}
        {/* DIVIDER */}
        {/* ============================================ */}
        
        {growth_arc && (
          <>
            <div className="border-t border-slate-700 my-8" />

            {/* ============================================ */}
            {/* LONG-TERM GROWTH ARC */}
            {/* ============================================ */}

            <p className="text-xs uppercase tracking-wider text-muted-foreground">
              Growth Arc
            </p>

            {/* Stability Growth */}
            <Card className="border-slate-700 bg-slate-900/50">
              <CardContent className="p-6">
                <p className="text-xs uppercase tracking-wider text-muted-foreground mb-3">
                  Long-Term Stability
                </p>
                <p className="text-sm text-slate-300">
                  {growth_arc.stability_growth.text}
                </p>
              </CardContent>
            </Card>

            {/* Driver Evolution */}
            {growth_arc.driver_evolution && (
              <Card className="border-slate-700 bg-slate-900/50">
                <CardContent className="p-6">
                  <p className="text-xs uppercase tracking-wider text-muted-foreground mb-3">
                    Primary Weakness Evolution
                  </p>
                  <p className="text-sm text-slate-300">
                    {growth_arc.driver_evolution.text}
                  </p>
                  
                  {showMetrics && (
                    <div className="mt-3 pt-3 border-t border-slate-700/50 text-xs text-slate-500">
                      {getPatternName(growth_arc.driver_evolution.driver)}: {growth_arc.driver_evolution.early_band} → {growth_arc.driver_evolution.recent_band}
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Peer Comparison */}
            <Card className="border-slate-700 bg-slate-900/50">
              <CardContent className="p-6">
                <p className="text-xs uppercase tracking-wider text-muted-foreground mb-3">
                  Peer Comparison
                </p>
                <p className="text-sm text-slate-300">
                  {growth_arc.peer_comparison.text}
                </p>
              </CardContent>
            </Card>

            {/* Phase Evolution */}
            <Card className="border-slate-700 bg-slate-900/50">
              <CardContent className="p-6">
                <p className="text-xs uppercase tracking-wider text-muted-foreground mb-3">
                  Phase Evolution
                </p>
                
                {growth_arc.phase_evolution.changed ? (
                  <p className="text-sm text-slate-300">
                    Primary instability has shifted from <span className="text-white">{growth_arc.phase_evolution.early}</span> to <span className="text-white">{growth_arc.phase_evolution.recent}</span> over time.
                  </p>
                ) : (
                  <p className="text-sm text-slate-300">
                    <span className="text-white">{growth_arc.phase_evolution.recent}</span> has remained your primary instability phase.
                  </p>
                )}
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </Layout>
  );
};

export default Journey;
