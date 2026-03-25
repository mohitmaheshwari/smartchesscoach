/**
 * PROGRESS PAGE - Status & Confidence
 * 
 * Shows where you are, not what to do.
 * 
 * 1. Thinking Score (with delta)
 * 2. Simple trend summary (last 5 games)
 * 3. Stability / improvement summary
 * 4. Optional opening improvement insight
 *
 * NO: problem statements, "Fix This" CTA, action prompts
 */

import { useState, useEffect } from "react";
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
  RefreshCw,
  Circle
} from "lucide-react";

const UnifiedProgress = ({ user }) => {
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
  const accuracy = progressData?.accuracy || {};
  const blunders = progressData?.blunders || {};
  const progressTrend = homeData?.progress_trend || {};
  const gamesAnalyzed = homeData?.games_analyzed || progressData?.valid_analysis_count || 0;
  
  // Calculate delta (simplified)
  const previousScore = accuracy.previous ? Math.round(accuracy.previous / 4) : thinkingScore;
  const scoreDelta = Math.round(thinkingScore - previousScore);

  // Get stability assessment
  const getStabilityStatus = () => {
    const blunderTrend = blunders.trend;
    const accTrend = accuracy.trend;
    
    if (blunderTrend === 'improving' && accTrend === 'improving') {
      return { label: "Solid", color: "text-emerald-400", bg: "bg-emerald-500/10" };
    }
    if (blunderTrend === 'worsening' || accTrend === 'declining') {
      return { label: "Volatile", color: "text-amber-400", bg: "bg-amber-500/10" };
    }
    return { label: "Stable", color: "text-zinc-400", bg: "bg-zinc-500/10" };
  };

  const stability = getStabilityStatus();

  // Trend arrow
  const TrendIcon = ({ value }) => {
    if (value > 0) return <TrendingUp className="w-5 h-5 text-emerald-500" />;
    if (value < 0) return <TrendingDown className="w-5 h-5 text-red-500" />;
    return <Minus className="w-5 h-5 text-zinc-500" />;
  };

  // Recent games trend (simulated from available data)
  const recentTrend = progressTrend.trend || 'stable';
  const trendMessage = {
    'improving': 'Getting stronger',
    'declining': 'Slight dip',
    'stable': 'Holding steady'
  }[recentTrend] || 'Steady';

  return (
    <Layout user={user}>
      <div className="max-w-md mx-auto space-y-5 px-4 py-8" data-testid="progress-page">
        
        {/* ═══════════════════════════════════════════════════════════════
            SECTION 1: THINKING SCORE (with delta)
        ═══════════════════════════════════════════════════════════════ */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <Card className="overflow-hidden bg-gradient-to-br from-zinc-900 to-zinc-950 border-zinc-800">
            <CardContent className="p-8 text-center">
              <p className="text-xs text-zinc-500 uppercase tracking-widest mb-4">Thinking Score</p>
              
              <div className="flex items-center justify-center gap-4 mb-2">
                <span className="text-8xl font-bold text-white tracking-tight">{Math.round(thinkingScore)}</span>
                {scoreDelta !== 0 && (
                  <div className={`flex items-center gap-1 px-3 py-1.5 rounded-full text-sm font-medium ${
                    scoreDelta > 0 
                      ? 'bg-emerald-500/15 text-emerald-400' 
                      : 'bg-red-500/15 text-red-400'
                  }`}>
                    <TrendIcon value={scoreDelta} />
                    <span>{scoreDelta > 0 ? '+' : ''}{scoreDelta}</span>
                  </div>
                )}
              </div>
              
              <p className="text-xs text-zinc-600">{gamesAnalyzed} games analyzed</p>
            </CardContent>
          </Card>
        </motion.div>

        {/* ═══════════════════════════════════════════════════════════════
            SECTION 2: TREND SUMMARY (last 5 games)
        ═══════════════════════════════════════════════════════════════ */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <Card className="border-zinc-800">
            <CardContent className="p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-zinc-500 uppercase tracking-wide mb-1">Recent Trend</p>
                  <p className="text-lg text-white font-medium">{trendMessage}</p>
                </div>
                <TrendIcon value={recentTrend === 'improving' ? 1 : recentTrend === 'declining' ? -1 : 0} />
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* ═══════════════════════════════════════════════════════════════
            SECTION 3: STABILITY SUMMARY
        ═══════════════════════════════════════════════════════════════ */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
        >
          <Card className="border-zinc-800">
            <CardContent className="p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-zinc-500 uppercase tracking-wide mb-1">Consistency</p>
                  <p className="text-lg text-white font-medium">
                    {accuracy.current?.toFixed(0) || '--'}% accuracy
                  </p>
                </div>
                <div className={`px-3 py-1.5 rounded-full text-sm font-medium ${stability.bg} ${stability.color}`}>
                  {stability.label}
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* ═══════════════════════════════════════════════════════════════
            SECTION 4: OPENING INSIGHT (optional)
        ═══════════════════════════════════════════════════════════════ */}
        {devPhase.phase_name && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <Card className="border-zinc-800/50 bg-zinc-900/30">
              <CardContent className="p-4">
                <p className="text-xs text-zinc-500 uppercase tracking-wide mb-2">Current Focus Area</p>
                <p className="text-sm text-zinc-300">{devPhase.phase_name}</p>
                {devPhase.description && (
                  <p className="text-xs text-zinc-500 mt-1">{devPhase.description}</p>
                )}
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Sync footer */}
        <div className="flex justify-center pt-4">
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
            Sync games
          </Button>
        </div>
      </div>
    </Layout>
  );
};

export default UnifiedProgress;
