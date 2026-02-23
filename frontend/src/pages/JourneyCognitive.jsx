/**
 * JOURNEY PAGE - Cognitive Evolution Dashboard
 * 
 * Purpose: Answer one question - Is my decision-making becoming more stable over time?
 * 
 * NOT an analytics dump. NOT a drill recommender.
 * A reflection page showing stability evolution.
 * 
 * Sections:
 * 1. Cognitive Stability Overview (TSI + Gap Analysis)
 * 2. Instability Pattern Context (Position distribution)
 * 3. Cognitive Pattern Ranking (Top 3 drivers)
 * 4. Cognitive Trend Timeline (30-game graph)
 * 5. Phase Stability Insight
 */

import { useState, useEffect } from "react";
import { API } from "@/App";
import { Card, CardContent } from "@/components/ui/card";
import Layout from "@/components/Layout";
import { 
  Loader2, 
  TrendingUp,
  TrendingDown,
  Minus,
  ArrowRight
} from "lucide-react";

// Simple line chart component for TSI trend
const TrendChart = ({ data, height = 120 }) => {
  if (!data || data.length === 0) return null;
  
  const maxVal = Math.max(...data.map(d => d.value), 100);
  const minVal = Math.min(...data.map(d => d.value), 0);
  const range = maxVal - minVal || 1;
  
  const points = data.map((d, i) => {
    const x = (i / (data.length - 1)) * 100;
    const y = 100 - ((d.value - minVal) / range) * 100;
    return `${x},${y}`;
  }).join(' ');
  
  return (
    <div className="w-full" style={{ height }}>
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="w-full h-full">
        {/* Grid lines */}
        <line x1="0" y1="25" x2="100" y2="25" stroke="currentColor" strokeOpacity="0.1" />
        <line x1="0" y1="50" x2="100" y2="50" stroke="currentColor" strokeOpacity="0.1" />
        <line x1="0" y1="75" x2="100" y2="75" stroke="currentColor" strokeOpacity="0.1" />
        
        {/* Trend line */}
        <polyline
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          points={points}
          className="text-primary"
        />
      </svg>
    </div>
  );
};

const Journey = ({ user }) => {
  const [loading, setLoading] = useState(true);
  const [cognitiveData, setCognitiveData] = useState(null);
  const [trendData, setTrendData] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchCognitiveData();
  }, []);

  const fetchCognitiveData = async () => {
    try {
      const [patternsRes, trendRes] = await Promise.all([
        fetch(`${API}/cognitive/patterns`, { credentials: "include" }),
        fetch(`${API}/cognitive/trend`, { credentials: "include" }).catch(() => null)
      ]);
      
      if (patternsRes.ok) {
        const patterns = await patternsRes.json();
        setCognitiveData(patterns);
      }
      
      if (trendRes && trendRes.ok) {
        const trend = await trendRes.json();
        setTrendData(trend.data || []);
      }
    } catch (e) {
      console.error("Failed to fetch cognitive data:", e);
      setError("Failed to load cognitive data");
    } finally {
      setLoading(false);
    }
  };

  // Calculate derived metrics
  const getTSIInterpretation = (tsi) => {
    if (tsi >= 80) return { label: "Stable", color: "text-green-400" };
    if (tsi >= 65) return { label: "Moderate", color: "text-yellow-400" };
    if (tsi >= 50) return { label: "Unstable", color: "text-orange-400" };
    return { label: "Volatile", color: "text-red-400" };
  };

  const getTrendIcon = (trend) => {
    if (trend === "improving") return <TrendingUp className="w-5 h-5 text-green-400" />;
    if (trend === "worsening") return <TrendingDown className="w-5 h-5 text-red-400" />;
    return <Minus className="w-5 h-5 text-muted-foreground" />;
  };

  const getTopPatterns = (patterns) => {
    if (!patterns) return [];
    return Object.entries(patterns)
      .map(([key, data]) => ({
        key,
        name: key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
        severity: data.weighted_score || data.frequency * (data.avg_severity || 0.5),
        trend: data.trend || "stable",
        frequency: data.frequency
      }))
      .sort((a, b) => b.severity - a.severity)
      .slice(0, 3);
  };

  const getPrimaryDriver = (patterns) => {
    const top = getTopPatterns(patterns);
    if (top.length === 0) return null;
    return top[0];
  };

  // Mock data for position distribution (would come from backend)
  const getPositionDistribution = () => {
    // In a real implementation, this would come from cognitiveData
    return {
      winning: 45,
      equal: 35,
      losing: 20
    };
  };

  const getPhaseInsight = () => {
    // Would derive from cognitiveData.phase_breakdown
    return {
      mostUnstable: "Middlegame",
      mostStable: "Endgame"
    };
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

  const tsi = cognitiveData?.thinking_stability_index || 0;
  const tsiTrend = cognitiveData?.tsi_trend || "stable";
  const tsiInterpretation = getTSIInterpretation(tsi);
  const primaryDriver = getPrimaryDriver(cognitiveData?.patterns);
  const topPatterns = getTopPatterns(cognitiveData?.patterns);
  const positionDist = getPositionDistribution();
  const phaseInsight = getPhaseInsight();
  
  // Calculate stability metrics
  const stableStrength = Math.max(0, tsi - 15);
  const peakPerformance = Math.min(100, tsi + 20);
  const stabilityGap = peakPerformance - stableStrength;

  return (
    <Layout user={user}>
      <div className="max-w-4xl mx-auto px-4 py-8 space-y-8" data-testid="journey-page">
        {/* Page Header */}
        <div>
          <p className="text-xs uppercase tracking-wider text-muted-foreground mb-1">
            Cognitive Evolution
          </p>
          <h1 className="text-2xl font-semibold text-white">Journey</h1>
        </div>

        {/* SECTION 1: Cognitive Stability Overview */}
        <Card className="border-slate-700 bg-slate-900/50">
          <CardContent className="p-6">
            <div className="flex items-start justify-between">
              {/* TSI Display */}
              <div>
                <p className="text-xs uppercase tracking-wider text-muted-foreground mb-2">
                  Thinking Stability Index
                </p>
                <div className="flex items-center gap-3">
                  <span className={`text-5xl font-bold ${tsiInterpretation.color}`} data-testid="tsi-main">
                    {tsi}
                  </span>
                  {getTrendIcon(tsiTrend)}
                </div>
                <p className={`text-sm mt-1 ${tsiInterpretation.color}`}>
                  {tsiInterpretation.label}
                </p>
              </div>

              {/* Stability Metrics */}
              <div className="text-right space-y-1">
                <div>
                  <p className="text-xs text-muted-foreground">Stable Strength</p>
                  <p className="text-lg font-medium text-white">{stableStrength}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Peak Performance</p>
                  <p className="text-lg font-medium text-white">{peakPerformance}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Stability Gap</p>
                  <p className="text-lg font-medium text-amber-400">+{stabilityGap}</p>
                </div>
              </div>
            </div>

            {/* Gap Driver */}
            {primaryDriver && (
              <div className="mt-6 pt-4 border-t border-slate-700">
                <p className="text-xs text-muted-foreground mb-1">Gap Driver</p>
                <p className="text-sm text-white">
                  <span className="font-medium">{primaryDriver.name}</span>
                  <span className="text-muted-foreground"> — instability appears in this pattern.</span>
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* SECTION 2: Instability Pattern Context */}
        <Card className="border-slate-700 bg-slate-900/50">
          <CardContent className="p-6">
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-4">
              Blunder Context Distribution
            </p>
            
            <div className="grid grid-cols-3 gap-4">
              <div className="text-center p-4 rounded-lg bg-slate-800/50">
                <p className="text-2xl font-bold text-green-400">{positionDist.winning}%</p>
                <p className="text-xs text-muted-foreground mt-1">Winning Positions</p>
              </div>
              <div className="text-center p-4 rounded-lg bg-slate-800/50">
                <p className="text-2xl font-bold text-slate-300">{positionDist.equal}%</p>
                <p className="text-xs text-muted-foreground mt-1">Equal Positions</p>
              </div>
              <div className="text-center p-4 rounded-lg bg-slate-800/50">
                <p className="text-2xl font-bold text-red-400">{positionDist.losing}%</p>
                <p className="text-xs text-muted-foreground mt-1">Losing Positions</p>
              </div>
            </div>

            <p className="text-sm text-muted-foreground mt-4">
              {positionDist.winning > 40 
                ? "Instability spikes when ahead."
                : positionDist.losing > 40
                ? "Instability appears under pressure."
                : "Decision quality is position-independent."}
            </p>
          </CardContent>
        </Card>

        {/* SECTION 3: Cognitive Pattern Ranking */}
        <Card className="border-slate-700 bg-slate-900/50">
          <CardContent className="p-6">
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-4">
              Top Cognitive Instability Drivers (Last 20 Games)
            </p>
            
            {topPatterns.length > 0 ? (
              <div className="space-y-3">
                {topPatterns.map((pattern, idx) => (
                  <div 
                    key={pattern.key}
                    className="flex items-center justify-between p-3 rounded-lg bg-slate-800/30"
                    data-testid={`pattern-${idx}`}
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-medium text-muted-foreground w-4">
                        {idx + 1}.
                      </span>
                      <span className="text-sm text-white">{pattern.name}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-sm text-muted-foreground">
                        Severity {Math.round(pattern.severity)}
                      </span>
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        pattern.trend === "improving" 
                          ? "bg-green-500/20 text-green-400"
                          : pattern.trend === "worsening"
                          ? "bg-red-500/20 text-red-400"
                          : "bg-slate-500/20 text-slate-400"
                      }`}>
                        {pattern.trend === "improving" ? "Improving" :
                         pattern.trend === "worsening" ? "Worsening" : "Stable"}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                Not enough data to identify patterns yet.
              </p>
            )}
          </CardContent>
        </Card>

        {/* SECTION 4: Cognitive Trend Timeline */}
        <Card className="border-slate-700 bg-slate-900/50">
          <CardContent className="p-6">
            <div className="flex items-center justify-between mb-4">
              <p className="text-xs uppercase tracking-wider text-muted-foreground">
                Cognitive Trend (Last 30 Games)
              </p>
            </div>
            
            {trendData.length > 0 ? (
              <div className="relative">
                <TrendChart data={trendData} height={140} />
                <div className="flex justify-between text-xs text-muted-foreground mt-2">
                  <span>30 games ago</span>
                  <span>Recent</span>
                </div>
              </div>
            ) : (
              <div className="h-[140px] flex items-center justify-center bg-slate-800/30 rounded-lg">
                <p className="text-sm text-muted-foreground">
                  Trend data available after more games
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* SECTION 5: Phase Stability Insight */}
        <Card className="border-slate-700 bg-slate-900/50">
          <CardContent className="p-6">
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-4">
              Phase Stability Insight
            </p>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/20">
                <p className="text-xs text-red-400 mb-1">Most Unstable Phase</p>
                <p className="text-lg font-medium text-white">{phaseInsight.mostUnstable}</p>
              </div>
              <div className="p-4 rounded-lg bg-green-500/10 border border-green-500/20">
                <p className="text-xs text-green-400 mb-1">Most Stable Phase</p>
                <p className="text-lg font-medium text-white">{phaseInsight.mostStable}</p>
              </div>
            </div>

            <p className="text-sm text-muted-foreground mt-4">
              Decision quality drops during complex {phaseInsight.mostUnstable.toLowerCase()} transitions.
            </p>
          </CardContent>
        </Card>

        {/* Games Analyzed Footer */}
        <p className="text-xs text-center text-muted-foreground">
          Based on {cognitiveData?.games_analyzed || 0} analyzed games
        </p>
      </div>
    </Layout>
  );
};

export default Journey;
