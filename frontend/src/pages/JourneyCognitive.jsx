/**
 * JOURNEY PAGE - Rolling 5 vs 5 Cognitive Evolution
 * 
 * Purpose: Show delta between recent 5 games and previous 5 games.
 * 
 * Activation: Requires ≥10 analyzed games.
 * 
 * Sections:
 * 1. Stability Momentum (TSI comparison)
 * 2. Cognitive Pattern Shifts (impact band changes)
 * 3. Instability Context Shift (blunder distribution)
 * 4. Phase Stability Shift
 * 
 * Tone: Clinical, reflective. No motivational copy.
 */

import { useState, useEffect } from "react";
import { API } from "@/App";
import { Card, CardContent } from "@/components/ui/card";
import Layout from "@/components/Layout";
import { Loader2, TrendingUp, TrendingDown, Minus } from "lucide-react";

// Pattern name mapping for cognitive framing
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

const Journey = ({ user }) => {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

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

  // Delta color
  const getDeltaColor = (delta) => {
    if (delta >= 5) return "text-green-400";
    if (delta <= -5) return "text-red-400";
    return "text-slate-400";
  };

  // Status color
  const getStatusColor = (status) => {
    if (status === "Improving") return "text-green-400";
    if (status === "Worsening") return "text-red-400";
    return "text-slate-400";
  };

  return (
    <Layout user={user}>
      <div className="max-w-4xl mx-auto px-4 py-8 space-y-6" data-testid="journey-page">
        {/* Page Header */}
        <div>
          <p className="text-xs uppercase tracking-wider text-muted-foreground mb-1">
            Cognitive Evolution
          </p>
          <h1 className="text-2xl font-semibold text-white">Journey</h1>
        </div>

        {/* SECTION 1: Decision Stability Momentum - FIX #4: Horizontal layout */}
        <Card className="border-slate-700 bg-slate-900/50">
          <CardContent className="p-6">
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-4">
              Decision Stability Momentum
            </p>
            
            {!stability_momentum.valid ? (
              <p className="text-sm text-slate-400">
                {stability_momentum.interpretation}
              </p>
            ) : (
              <>
                <div className="flex items-baseline gap-6 mb-3">
                  <div>
                    <span className="text-sm text-muted-foreground mr-2">Previous 5:</span>
                    <span className="text-2xl font-bold text-slate-400">{stability_momentum.previous_tsi}</span>
                  </div>
                  <div>
                    <span className="text-sm text-muted-foreground mr-2">Recent 5:</span>
                    <span className="text-2xl font-bold text-white">{stability_momentum.recent_tsi}</span>
                  </div>
                  <div>
                    <span className="text-sm text-muted-foreground mr-2">Change:</span>
                    <span className={`text-2xl font-bold ${getDeltaColor(stability_momentum.delta)}`}>
                      {stability_momentum.delta >= 0 ? "+" : ""}{stability_momentum.delta}
                    </span>
                  </div>
                </div>
                <p className="text-sm text-slate-400">
                  {stability_momentum.interpretation}
                </p>
              </>
            )}
          </CardContent>
        </Card>

        {/* SECTION 2: Cognitive Pattern Shifts - Only shows band changes */}
        <Card className="border-slate-700 bg-slate-900/50">
          <CardContent className="p-6">
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-4">
              Cognitive Pattern Shifts
            </p>
            
            {data.no_pattern_shifts ? (
              <p className="text-sm text-slate-400">
                Your cognitive patterns remain stable across recent games.
              </p>
            ) : (
              <div className="space-y-3">
                {pattern_shifts.map((shift, idx) => (
                  <div 
                    key={shift.category}
                    className="p-3 rounded-lg bg-slate-800/30"
                    data-testid={`pattern-shift-${idx}`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-white">
                        {getPatternName(shift.category)}
                      </span>
                      <span className={`text-sm ${getStatusColor(shift.status)}`}>
                        {shift.status}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      {shift.previous_band} → {shift.recent_band}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* SECTION 3: Blunder Context Shift - FIX #3: Clear directional layout */}
        <Card className="border-slate-700 bg-slate-900/50">
          <CardContent className="p-6">
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-4">
              Blunder Context Shift
            </p>
            
            {data.context_unchanged ? (
              <p className="text-sm text-slate-400">
                Blunder distribution unchanged across position types.
              </p>
            ) : (
              <div className="p-3 rounded-lg bg-slate-800/30">
                <p className="text-sm text-white mb-3">Blunders in Winning Positions</p>
                <div className="flex items-baseline gap-6 mb-2">
                  <div>
                    <span className="text-sm text-muted-foreground mr-2">Previous 5:</span>
                    <span className="text-xl font-bold text-slate-400">{context_shift.previous}%</span>
                  </div>
                  <div>
                    <span className="text-sm text-muted-foreground mr-2">Recent 5:</span>
                    <span className="text-xl font-bold text-white">{context_shift.recent}%</span>
                  </div>
                  <div>
                    <span className="text-sm text-muted-foreground mr-2">Change:</span>
                    <span className={`text-xl font-bold ${context_shift.change > 0 ? 'text-red-400' : 'text-green-400'}`}>
                      {context_shift.change > 0 ? "+" : ""}{context_shift.change}%
                    </span>
                  </div>
                </div>
                <p className="text-xs text-slate-500">
                  {context_shift.direction === "Increased" 
                    ? "Instability when ahead has increased."
                    : "Instability when ahead has decreased."}
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* SECTION 4: Phase Stability Shift */}
        <Card className="border-slate-700 bg-slate-900/50">
          <CardContent className="p-6">
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-4">
              Phase Stability Shift
            </p>
            
            {phase_shift.changed ? (
              <div className="p-3 rounded-lg bg-slate-800/30">
                <p className="text-sm text-white mb-3">Primary Instability Phase</p>
                <div className="flex items-center gap-4 text-sm">
                  <span className="text-muted-foreground">Previous: <span className="text-slate-300">{phase_shift.previous}</span></span>
                  <span className="text-slate-600">→</span>
                  <span className="text-muted-foreground">Recent: <span className="text-white">{phase_shift.recent}</span></span>
                </div>
              </div>
            ) : (
              <p className="text-sm text-slate-400">
                Primary instability phase remains: {phase_shift.recent}.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </Layout>
  );
};

export default Journey;
