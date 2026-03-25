/**
 * UNIFIED PROGRESS PAGE - Simplified, Actionable
 * 
 * 3 focused sections:
 * 1. Thinking Score (primary metric)
 * 2. Biggest Problem (one issue + Fix This)
 * 3. Improvement Signals (max 3 metrics)
 * + Optional: Opening Insight (bottom, max 2 items)
 *
 * REMOVED: tabs, charts, multiple breakdowns, complex analytics
 * GOAL: Simple, actionable, focused on next improvement
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { 
  Loader2, 
  TrendingUp,
  TrendingDown,
  Minus,
  Target,
  AlertTriangle,
  ArrowRight,
  Brain,
  Zap,
  BookOpen,
  RefreshCw
} from "lucide-react";

const UnifiedProgress = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [progressData, setProgressData] = useState(null);
  const [homeData, setHomeData] = useState(null);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    fetchAll();
  }, []);

  const fetchAll = async () => {
    try {
      const [progressRes, homeRes] = await Promise.all([
        fetch(`${API}/progress`, { credentials: "include" }),
        fetch(`${API}/coach/home-intelligence`, { credentials: "include" })
      ]);
      if (progressRes.ok) setProgressData(await progressRes.json());
      if (homeRes.ok) setHomeData(await homeRes.json());
    } catch (e) {
      console.error("Failed to fetch:", e);
    } finally {
      setLoading(false);
    }
  };

  const syncNow = async () => {
    setSyncing(true);
    try {
      await fetch(`${API}/journey/sync-now`, { method: "POST", credentials: "include" });
      setTimeout(fetchAll, 3000);
    } catch (e) {
      console.error(e);
    } finally {
      setSyncing(false);
    }
  };

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      </Layout>
    );
  }

  // Extract data
  const devPhase = homeData?.development_phase || {};
  const thinkingScore = devPhase.score || 0;
  const previousScore = progressData?.accuracy?.previous ? Math.round(progressData.accuracy.previous / 4) : thinkingScore;
  const scoreDelta = Math.round(thinkingScore - previousScore);
  
  const patterns = homeData?.specific_patterns;
  const biggestProblem = patterns?.dominant_pattern;
  const problemCount = patterns?.pattern_count || 0;
  const problemDescription = patterns?.pattern_description;
  
  const accuracy = progressData?.accuracy || {};
  const blunders = progressData?.blunders || {};
  const stats = homeData?.stats || {};
  
  const gamesAnalyzed = homeData?.games_analyzed || progressData?.valid_analysis_count || 0;

  // Get status message based on score and trend
  const getStatusMessage = () => {
    const trend = homeData?.progress_trend?.trend;
    if (scoreDelta >= 3) return "You're improving fast!";
    if (scoreDelta > 0) return "Moving in the right direction";
    if (trend === 'improving') return "Steady improvement";
    if (scoreDelta === 0) return "Holding steady";
    if (scoreDelta >= -2) return "Slight dip - stay focused";
    return "Time to refocus";
  };

  // Trend arrow component
  const TrendArrow = ({ value, inverted = false }) => {
    const actualValue = inverted ? -value : value;
    if (actualValue > 0) return <TrendingUp className="w-4 h-4 text-emerald-500" />;
    if (actualValue < 0) return <TrendingDown className="w-4 h-4 text-red-500" />;
    return <Minus className="w-4 h-4 text-zinc-500" />;
  };

  // Get trend value for a metric
  const getTrendValue = (trend) => {
    if (trend === 'improving') return 1;
    if (trend === 'declining' || trend === 'worsening') return -1;
    return 0;
  };

  return (
    <Layout user={user}>
      <div className="max-w-lg mx-auto space-y-6 px-4 py-6" data-testid="progress-page">
        
        {/* ═══════════════════════════════════════════════════════════════
            SECTION 1: THINKING SCORE (Primary, Large)
        ═══════════════════════════════════════════════════════════════ */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <Card className="overflow-hidden bg-gradient-to-br from-zinc-900 to-zinc-950 border-zinc-800">
            <CardContent className="p-8 text-center">
              <p className="text-sm text-zinc-500 mb-3 uppercase tracking-wide">Thinking Score</p>
              
              {/* Big Score */}
              <div className="flex items-center justify-center gap-4 mb-3">
                <span className="text-7xl font-bold text-white">{Math.round(thinkingScore)}</span>
                {scoreDelta !== 0 && (
                  <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-semibold ${
                    scoreDelta > 0 
                      ? 'bg-emerald-500/20 text-emerald-400' 
                      : 'bg-red-500/20 text-red-400'
                  }`}>
                    {scoreDelta > 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                    {scoreDelta > 0 ? '+' : ''}{scoreDelta}
                  </div>
                )}
              </div>
              
              {/* Status Line */}
              <p className="text-zinc-400">{getStatusMessage()}</p>
              
              {/* Games count */}
              <p className="text-xs text-zinc-600 mt-4">Based on {gamesAnalyzed} analyzed games</p>
            </CardContent>
          </Card>
        </motion.div>

        {/* ═══════════════════════════════════════════════════════════════
            SECTION 2: BIGGEST PROBLEM (One Issue + Fix This CTA)
        ═══════════════════════════════════════════════════════════════ */}
        {biggestProblem && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <Card className="border-amber-500/30 bg-amber-950/20">
              <CardContent className="p-5">
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-xl bg-amber-500/20 flex items-center justify-center flex-shrink-0">
                    <AlertTriangle className="w-6 h-6 text-amber-500" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-amber-500/80 font-semibold uppercase tracking-wide mb-1">
                      Biggest Problem
                    </p>
                    <h3 className="text-xl font-bold text-white mb-1 capitalize">
                      {biggestProblem.replace(/_/g, " ")}
                    </h3>
                    <p className="text-sm text-zinc-400 mb-4">
                      {problemCount}x in recent games
                      {problemDescription && <span className="block mt-1">{problemDescription}</span>}
                    </p>
                    <Button 
                      onClick={() => navigate(`/training/prescribed?weakness=${biggestProblem}`)}
                      className="bg-amber-500 hover:bg-amber-600 text-black font-semibold"
                      data-testid="fix-this-btn"
                    >
                      <Target className="w-4 h-4 mr-2" />
                      Fix This
                      <ArrowRight className="w-4 h-4 ml-2" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* ═══════════════════════════════════════════════════════════════
            SECTION 3: IMPROVEMENT SIGNALS (Max 3 metrics, simple arrows)
        ═══════════════════════════════════════════════════════════════ */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <Card className="border-zinc-800">
            <CardContent className="p-5">
              <h3 className="text-sm font-semibold text-zinc-400 mb-4 uppercase tracking-wide">
                Improvement Signals
              </h3>
              
              <div className="space-y-4">
                {/* Move Accuracy */}
                <div className="flex items-center justify-between py-2">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-zinc-800 flex items-center justify-center">
                      <Brain className="w-4 h-4 text-blue-400" />
                    </div>
                    <span className="text-zinc-300">Move Accuracy</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-lg font-semibold text-white">{accuracy.current?.toFixed(0) || '--'}%</span>
                    <TrendArrow value={getTrendValue(accuracy.trend)} />
                  </div>
                </div>
                
                {/* Blunders per Game */}
                <div className="flex items-center justify-between py-2">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-zinc-800 flex items-center justify-center">
                      <Zap className="w-4 h-4 text-red-400" />
                    </div>
                    <span className="text-zinc-300">Blunders/Game</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-lg font-semibold text-white">{blunders.avg_per_game?.toFixed(1) || '--'}</span>
                    {/* For blunders, improving = less blunders = good */}
                    <TrendArrow value={getTrendValue(blunders.trend)} />
                  </div>
                </div>
                
                {/* Time Trouble Rate (if available) */}
                {stats.time_trouble_rate !== undefined && (
                  <div className="flex items-center justify-between py-2">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-lg bg-zinc-800 flex items-center justify-center">
                        <Target className="w-4 h-4 text-orange-400" />
                      </div>
                      <span className="text-zinc-300">Time Trouble</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-lg font-semibold text-white">{Math.round(stats.time_trouble_rate)}%</span>
                      {/* Lower time trouble = better */}
                      <TrendArrow value={stats.time_trouble_rate > 50 ? -1 : stats.time_trouble_rate < 30 ? 1 : 0} />
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* ═══════════════════════════════════════════════════════════════
            SECTION 4: COACH'S FOCUS (Optional, bottom, simple)
        ═══════════════════════════════════════════════════════════════ */}
        {homeData?.active_advice?.primary && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
          >
            <Card className="border-zinc-800/50 bg-zinc-900/30">
              <CardContent className="p-4">
                <div className="flex items-start gap-3">
                  <BookOpen className="w-5 h-5 text-zinc-500 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-xs text-zinc-500 font-medium uppercase tracking-wide mb-1">Coach's Focus</p>
                    <p className="text-sm text-zinc-300">{homeData.active_advice.primary}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Sync footer */}
        <div className="flex justify-center pt-4 pb-8">
          <Button
            variant="ghost"
            size="sm"
            onClick={syncNow}
            disabled={syncing}
            className="text-zinc-600 hover:text-zinc-400"
          >
            {syncing ? (
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
            ) : (
              <RefreshCw className="w-4 h-4 mr-2" />
            )}
            Sync latest games
          </Button>
        </div>
      </div>
    </Layout>
  );
};

export default UnifiedProgress;
