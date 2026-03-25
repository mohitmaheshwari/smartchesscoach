/**
 * PROGRESS PAGE → CONFIDENCE
 * "Am I getting better?"
 * 
 * One screen = one job
 * - No problems (that's Home's job)
 * - Only improvement signals
 * - Build confidence, not anxiety
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
  Sparkles
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
      console.error(e);
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
          <Loader2 className="w-6 h-6 animate-spin text-zinc-500" />
        </div>
      </Layout>
    );
  }

  // Data extraction
  const score = homeData?.development_phase?.score || 0;
  const accuracy = progressData?.accuracy || {};
  const blunders = progressData?.blunders || {};
  const gamesAnalyzed = homeData?.games_analyzed || 0;
  
  // Calculate improvement signals
  const accuracyTrend = accuracy.trend;
  const blunderTrend = blunders.trend;
  
  // Overall momentum
  const getMomentum = () => {
    if (accuracyTrend === 'improving' && blunderTrend === 'improving') {
      return { label: "You're improving", icon: TrendingUp, color: "text-emerald-400" };
    }
    if (accuracyTrend === 'declining' || blunderTrend === 'worsening') {
      return { label: "Slight dip lately", icon: TrendingDown, color: "text-amber-400" };
    }
    return { label: "Holding steady", icon: Minus, color: "text-zinc-400" };
  };
  
  const momentum = getMomentum();
  const MomentumIcon = momentum.icon;

  return (
    <Layout user={user}>
      <div className="max-w-md mx-auto px-4 py-10 min-h-[60vh]" data-testid="progress-page">
        
        {/* ═══════════════════════════════════════════════════════════════
            PRIMARY: THINKING SCORE
            Big, confident, celebratory
        ═══════════════════════════════════════════════════════════════ */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="text-center mb-10"
        >
          <p className="text-xs text-zinc-500 uppercase tracking-widest mb-3">Your Thinking Score</p>
          <div className="text-8xl font-bold text-white mb-4">{Math.round(score)}</div>
          <div className={`inline-flex items-center gap-2 ${momentum.color}`}>
            <MomentumIcon className="w-5 h-5" />
            <span className="text-sm font-medium">{momentum.label}</span>
          </div>
        </motion.div>

        {/* ═══════════════════════════════════════════════════════════════
            SECONDARY: SIMPLE SIGNALS
            3 metrics max, just arrows, no charts
        ═══════════════════════════════════════════════════════════════ */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <Card className="bg-zinc-900/50 border-zinc-800">
            <CardContent className="p-6 space-y-5">
              
              {/* Accuracy */}
              <div className="flex items-center justify-between">
                <span className="text-zinc-400">Accuracy</span>
                <div className="flex items-center gap-3">
                  <span className="text-white font-medium">{accuracy.current?.toFixed(0) || '--'}%</span>
                  {accuracyTrend === 'improving' && <TrendingUp className="w-4 h-4 text-emerald-500" />}
                  {accuracyTrend === 'declining' && <TrendingDown className="w-4 h-4 text-red-500" />}
                  {accuracyTrend === 'stable' && <Minus className="w-4 h-4 text-zinc-500" />}
                </div>
              </div>
              
              {/* Blunders */}
              <div className="flex items-center justify-between">
                <span className="text-zinc-400">Blunders per game</span>
                <div className="flex items-center gap-3">
                  <span className="text-white font-medium">{blunders.avg_per_game?.toFixed(1) || '--'}</span>
                  {blunderTrend === 'improving' && <TrendingUp className="w-4 h-4 text-emerald-500" />}
                  {blunderTrend === 'worsening' && <TrendingDown className="w-4 h-4 text-red-500" />}
                  {blunderTrend === 'stable' && <Minus className="w-4 h-4 text-zinc-500" />}
                </div>
              </div>
              
              {/* Games Analyzed */}
              <div className="flex items-center justify-between">
                <span className="text-zinc-400">Games analyzed</span>
                <span className="text-white font-medium">{gamesAnalyzed}</span>
              </div>
              
            </CardContent>
          </Card>
        </motion.div>

        {/* ═══════════════════════════════════════════════════════════════
            TERTIARY: POSITIVE REINFORCEMENT (optional)
            Only show if there's good news
        ═══════════════════════════════════════════════════════════════ */}
        {accuracyTrend === 'improving' && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="mt-6"
          >
            <Card className="bg-emerald-500/10 border-emerald-500/20">
              <CardContent className="p-4 flex items-center gap-3">
                <Sparkles className="w-5 h-5 text-emerald-400 flex-shrink-0" />
                <p className="text-sm text-emerald-300">
                  Your accuracy is trending up. Keep playing!
                </p>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Sync */}
        <div className="flex justify-center mt-8">
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
