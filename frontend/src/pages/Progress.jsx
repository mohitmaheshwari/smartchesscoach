/**
 * PROGRESS PAGE - Simplified, Actionable
 * 
 * 3 focused sections:
 * 1. Thinking Score (primary metric)
 * 2. Biggest Problem (one issue + Fix This)
 * 3. Improvement Signals (max 3 metrics)
 * + Optional: Opening Insight (bottom, max 2 items)
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
  BookOpen,
  RefreshCw
} from "lucide-react";

const Progress = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
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
      if (progressRes.ok) setData(await progressRes.json());
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
  const thinkingScore = homeData?.development_phase?.score || 0;
  const previousScore = data?.accuracy?.previous ? Math.round(data.accuracy.previous / 4) : thinkingScore;
  const scoreDelta = Math.round(thinkingScore - previousScore);
  
  const patterns = homeData?.specific_patterns;
  const biggestProblem = patterns?.dominant_pattern;
  const problemCount = patterns?.pattern_count || 0;
  const problemDescription = patterns?.pattern_description;
  
  const accuracy = data?.accuracy || {};
  const blunders = data?.blunders || {};
  const progressTrend = homeData?.progress_trend;
  
  const gamesAnalyzed = homeData?.games_analyzed || data?.valid_analysis_count || 0;

  // Get status message based on score
  const getStatusMessage = () => {
    if (scoreDelta >= 3) return "You're improving fast!";
    if (scoreDelta > 0) return "Moving in the right direction";
    if (scoreDelta === 0) return "Holding steady";
    if (scoreDelta >= -2) return "Slight dip - stay focused";
    return "Time to refocus";
  };

  // Get trend arrow component
  const TrendArrow = ({ value, size = "sm" }) => {
    const iconSize = size === "lg" ? "w-5 h-5" : "w-4 h-4";
    if (value > 0) return <TrendingUp className={`${iconSize} text-emerald-500`} />;
    if (value < 0) return <TrendingDown className={`${iconSize} text-red-500`} />;
    return <Minus className={`${iconSize} text-zinc-500`} />;
  };

  return (
    <Layout user={user}>
      <div className="max-w-lg mx-auto space-y-6 px-4" data-testid="progress-page">
        
        {/* ═══════════════════════════════════════════════════════════════
            SECTION 1: THINKING SCORE (Primary, Large)
        ═══════════════════════════════════════════════════════════════ */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <Card className="overflow-hidden bg-gradient-to-br from-zinc-900 to-zinc-950 border-zinc-800">
            <CardContent className="p-6 text-center">
              <p className="text-sm text-zinc-500 mb-2">Your Thinking Score</p>
              
              {/* Big Score */}
              <div className="flex items-center justify-center gap-3 mb-2">
                <span className="text-6xl font-bold text-white">{Math.round(thinkingScore)}</span>
                {scoreDelta !== 0 && (
                  <div className={`flex items-center gap-1 px-2 py-1 rounded-full text-sm font-medium ${
                    scoreDelta > 0 
                      ? 'bg-emerald-500/20 text-emerald-400' 
                      : 'bg-red-500/20 text-red-400'
                  }`}>
                    <TrendArrow value={scoreDelta} />
                    {scoreDelta > 0 ? '+' : ''}{scoreDelta}
                  </div>
                )}
              </div>
              
              {/* Status Line */}
              <p className="text-zinc-400 text-sm">{getStatusMessage()}</p>
              
              {/* Games count */}
              <p className="text-xs text-zinc-600 mt-4">Based on {gamesAnalyzed} games</p>
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
            <Card className="border-amber-500/30 bg-amber-500/5">
              <CardContent className="p-5">
                <div className="flex items-start gap-4">
                  <div className="w-10 h-10 rounded-lg bg-amber-500/20 flex items-center justify-center flex-shrink-0">
                    <AlertTriangle className="w-5 h-5 text-amber-500" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-amber-500/80 font-medium uppercase tracking-wide mb-1">
                      Biggest Problem
                    </p>
                    <h3 className="text-lg font-semibold text-white mb-1 capitalize">
                      {biggestProblem.replace(/_/g, " ")}
                    </h3>
                    <p className="text-sm text-zinc-400 mb-3">
                      {problemCount}x in recent games • {problemDescription || "This is costing you points"}
                    </p>
                    <Button 
                      onClick={() => navigate(`/training/prescribed?weakness=${biggestProblem}`)}
                      className="bg-amber-500 hover:bg-amber-600 text-black font-medium"
                      size="sm"
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
          <Card>
            <CardContent className="p-5">
              <h3 className="text-sm font-medium text-zinc-400 mb-4">Improvement Signals</h3>
              
              <div className="space-y-4">
                {/* Accuracy */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-zinc-800 flex items-center justify-center">
                      <Brain className="w-4 h-4 text-zinc-400" />
                    </div>
                    <span className="text-sm text-zinc-300">Move Accuracy</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{accuracy.current?.toFixed(0) || '--'}%</span>
                    <TrendArrow value={
                      accuracy.trend === 'improving' ? 1 : 
                      accuracy.trend === 'declining' ? -1 : 0
                    } />
                  </div>
                </div>
                
                {/* Blunders */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-zinc-800 flex items-center justify-center">
                      <AlertTriangle className="w-4 h-4 text-zinc-400" />
                    </div>
                    <span className="text-sm text-zinc-300">Blunders/Game</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{blunders.avg_per_game?.toFixed(1) || '--'}</span>
                    {/* For blunders, improving means LESS, so invert the arrow */}
                    <TrendArrow value={
                      blunders.trend === 'improving' ? 1 : 
                      blunders.trend === 'worsening' ? -1 : 0
                    } />
                  </div>
                </div>
                
                {/* Time Trouble */}
                {homeData?.stats?.time_trouble_rate !== undefined && (
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-zinc-800 flex items-center justify-center">
                        <Target className="w-4 h-4 text-zinc-400" />
                      </div>
                      <span className="text-sm text-zinc-300">Time Trouble Rate</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{Math.round(homeData.stats.time_trouble_rate)}%</span>
                      <TrendArrow value={homeData.stats.time_trouble_rate > 50 ? -1 : 1} />
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* ═══════════════════════════════════════════════════════════════
            SECTION 4: OPENING INSIGHT (Optional, bottom, max 2 items)
        ═══════════════════════════════════════════════════════════════ */}
        {homeData?.active_advice?.primary && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
          >
            <Card className="border-zinc-800 bg-zinc-900/50">
              <CardContent className="p-4">
                <div className="flex items-start gap-3">
                  <BookOpen className="w-4 h-4 text-zinc-500 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-xs text-zinc-500 mb-1">Coach's Focus</p>
                    <p className="text-sm text-zinc-300">{homeData.active_advice.primary}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Sync footer */}
        <div className="flex justify-center pt-2 pb-6">
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

export default Progress;
