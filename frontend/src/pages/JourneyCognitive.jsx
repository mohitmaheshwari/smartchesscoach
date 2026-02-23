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
 * 2. Blunder Context Distribution
 * 3. Top Instability Drivers (Last 20 Games)
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
  Minus
} from "lucide-react";

// Professional line chart - single dark blue line, subtle grid, no animations
const TrendChart = ({ data, height = 160 }) => {
  if (!data || data.length === 0) return null;
  
  // Fixed 0-100 Y-axis scale for TSI
  const maxVal = 100;
  const minVal = 0;
  const range = 100;
  
  // SVG dimensions with padding for labels
  const padding = { top: 10, right: 10, bottom: 20, left: 30 };
  const chartWidth = 100;
  const chartHeight = 100;
  
  const points = data.map((d, i) => {
    const x = padding.left + (i / (data.length - 1)) * (chartWidth - padding.left - padding.right);
    const y = padding.top + (1 - (d.value - minVal) / range) * (chartHeight - padding.top - padding.bottom);
    return `${x},${y}`;
  }).join(' ');
  
  return (
    <div className="w-full" style={{ height }}>
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="w-full h-full">
        {/* Y-axis labels */}
        <text x="2" y="15" className="fill-slate-500 text-[3px]">100</text>
        <text x="2" y="38" className="fill-slate-500 text-[3px]">75</text>
        <text x="2" y="60" className="fill-slate-500 text-[3px]">50</text>
        <text x="2" y="83" className="fill-slate-500 text-[3px]">25</text>
        
        {/* Horizontal grid lines - subtle gray */}
        <line x1={padding.left} y1="15" x2="90" y2="15" stroke="#334155" strokeWidth="0.3" />
        <line x1={padding.left} y1="37.5" x2="90" y2="37.5" stroke="#334155" strokeWidth="0.3" />
        <line x1={padding.left} y1="60" x2="90" y2="60" stroke="#334155" strokeWidth="0.3" />
        <line x1={padding.left} y1="82.5" x2="90" y2="82.5" stroke="#334155" strokeWidth="0.3" />
        
        {/* Single dark blue trend line - #1e3a8a */}
        <polyline
          fill="none"
          stroke="#1e3a8a"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          points={points}
        />
      </svg>
    </div>
  );
};

const Journey = ({ user }) => {
  const [loading, setLoading] = useState(true);
  const [cognitiveData, setCognitiveData] = useState(null);
  const [trendData, setTrendData] = useState([]);
  const [blunderContext, setBlunderContext] = useState(null);
  const [phaseInsight, setPhaseInsight] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchCognitiveData();
  }, []);

  const fetchCognitiveData = async () => {
    try {
      // Fetch all data in parallel
      const [patternsRes, trendRes, blunderRes, phaseRes] = await Promise.all([
        fetch(`${API}/cognitive/patterns`, { credentials: "include" }),
        fetch(`${API}/cognitive/trend`, { credentials: "include" }).catch(() => null),
        fetch(`${API}/cognitive/blunder-context`, { credentials: "include" }).catch(() => null),
        fetch(`${API}/cognitive/phase-insight`, { credentials: "include" }).catch(() => null)
      ]);
      
      if (patternsRes.ok) {
        const patterns = await patternsRes.json();
        setCognitiveData(patterns);
      }
      
      if (trendRes && trendRes.ok) {
        const trend = await trendRes.json();
        setTrendData(trend.data || []);
      }
      
      if (blunderRes && blunderRes.ok) {
        const blunder = await blunderRes.json();
        setBlunderContext(blunder);
      }
      
      if (phaseRes && phaseRes.ok) {
        const phase = await phaseRes.json();
        setPhaseInsight(phase);
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

  // Get position distribution from fetched blunder context data
  const getPositionDistribution = () => {
    if (blunderContext && blunderContext.distribution) {
      return blunderContext.distribution;
    }
    return { winning: 33, equal: 34, losing: 33 };
  };

  // Get blunder context interpretation - single line, no advice
  const getBlunderInterpretation = (dist) => {
    if (dist.winning >= 45) return "Instability spikes when ahead.";
    if (dist.losing >= 45) return "Instability appears under pressure.";
    if (dist.equal >= 45) return "Instability peaks in balanced positions.";
    return "Decision quality is position-independent.";
  };

  // Get phase insight from fetched data
  const getPhaseData = () => {
    if (phaseInsight) {
      return {
        mostUnstable: phaseInsight.most_unstable || "Middlegame",
        mostStable: phaseInsight.most_stable || "Endgame"
      };
    }
    return { mostUnstable: "Middlegame", mostStable: "Endgame" };
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
  const phaseData = getPhaseData();
  
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
