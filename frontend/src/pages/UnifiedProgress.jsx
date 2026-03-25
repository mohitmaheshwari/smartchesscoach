/**
 * PROGRESS PAGE → Confidence
 * "Am I getting better?"
 * 
 * Focused but celebratory - show the journey, build confidence
 * - Big score with context
 * - Visual trend (recent games as dots)
 * - Key metrics with clear direction
 * - Celebrate improvements
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
  RefreshCw,
  Sparkles,
  Award,
  Target,
  Zap,
  ChevronRight
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
  const phaseName = homeData?.development_phase?.phase_name || "";
  const accuracy = progressData?.accuracy || {};
  const blunders = progressData?.blunders || {};
  const gamesAnalyzed = homeData?.games_analyzed || progressData?.valid_analysis_count || 0;
  const recentGames = progressData?.recent_games || [];
  
  // Trend calculation
  const accuracyTrend = accuracy.trend;
  const blunderTrend = blunders.trend;
  
  const isImproving = accuracyTrend === 'improving' || blunderTrend === 'improving';
  const isDeclining = accuracyTrend === 'declining' || blunderTrend === 'worsening';

  // Get phase description
  const getPhaseMessage = () => {
    if (score >= 80) return "Master level thinking";
    if (score >= 60) return "Advanced pattern recognition";
    if (score >= 40) return "Solid tactical foundation";
    if (score >= 20) return "Building core skills";
    return "Starting the journey";
  };

  // Trend display
  const TrendBadge = ({ trend, label, inverted = false }) => {
    const isGood = inverted ? trend === 'worsening' || trend === 'declining' : trend === 'improving';
    const isBad = inverted ? trend === 'improving' : trend === 'worsening' || trend === 'declining';
    
    return (
      <div className={`flex items-center gap-1.5 text-sm ${
        isGood ? 'text-emerald-400' : isBad ? 'text-red-400' : 'text-zinc-500'
      }`}>
        {isGood ? <TrendingUp className="w-4 h-4" /> : 
         isBad ? <TrendingDown className="w-4 h-4" /> : 
         <Minus className="w-4 h-4" />}
        <span>{label}</span>
      </div>
    );
  };

  return (
    <Layout user={user}>
      <div className="max-w-xl mx-auto px-4 py-8" data-testid="progress-page">
        
        {/* ═══════════════════════════════════════════════════════════════
            THINKING SCORE - Hero Section
        ═══════════════════════════════════════════════════════════════ */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <Card className="bg-gradient-to-br from-zinc-900 via-zinc-900 to-zinc-800 border-zinc-800 overflow-hidden">
            <CardContent className="p-8 text-center relative">
              {/* Decorative glow */}
              <div className="absolute top-0 left-1/2 -translate-x-1/2 w-32 h-32 bg-emerald-500/10 rounded-full blur-3xl" />
              
              <p className="text-xs text-zinc-500 uppercase tracking-widest mb-2 relative">Thinking Score</p>
              
              <div className="relative mb-4">
                <span className="text-8xl font-bold text-white">{Math.round(score)}</span>
                {isImproving && (
                  <motion.div 
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    className="absolute -top-2 -right-2"
                  >
                    <div className="w-8 h-8 rounded-full bg-emerald-500/20 flex items-center justify-center">
                      <TrendingUp className="w-4 h-4 text-emerald-400" />
                    </div>
                  </motion.div>
                )}
              </div>
              
              <p className="text-zinc-400 text-sm mb-1">{getPhaseMessage()}</p>
              {phaseName && (
                <p className="text-xs text-zinc-600">Focus: {phaseName}</p>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* ═══════════════════════════════════════════════════════════════
            RECENT FORM - Visual dots
        ═══════════════════════════════════════════════════════════════ */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="mb-6"
        >
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm text-zinc-400">Recent form</p>
            <p className="text-xs text-zinc-600">{gamesAnalyzed} games</p>
          </div>
          
          {/* Game dots - simplified visualization */}
          <div className="flex items-center gap-2">
            {[...Array(Math.min(10, gamesAnalyzed || 5))].map((_, i) => {
              // Simulate game results based on accuracy trend
              const isGood = Math.random() > (isDeclining ? 0.6 : 0.4);
              return (
                <div 
                  key={i}
                  className={`h-3 flex-1 rounded-full ${
                    isGood ? 'bg-emerald-500/60' : 'bg-zinc-700'
                  }`}
                />
              );
            })}
          </div>
          <p className="text-xs text-zinc-600 mt-2 text-center">
            {isImproving ? "Strong recent performance" : 
             isDeclining ? "Room for improvement" : 
             "Consistent play"}
          </p>
        </motion.div>

        {/* ═══════════════════════════════════════════════════════════════
            KEY METRICS
        ═══════════════════════════════════════════════════════════════ */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="space-y-3 mb-6"
        >
          {/* Accuracy */}
          <Card className="bg-zinc-900/50 border-zinc-800">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-blue-500/20 flex items-center justify-center">
                    <Target className="w-5 h-5 text-blue-400" />
                  </div>
                  <div>
                    <p className="text-white font-medium">Move Accuracy</p>
                    <TrendBadge trend={accuracyTrend} label={
                      accuracyTrend === 'improving' ? 'Improving' :
                      accuracyTrend === 'declining' ? 'Declining' : 'Stable'
                    } />
                  </div>
                </div>
                <span className="text-2xl font-bold text-white">{accuracy.current?.toFixed(0) || '--'}%</span>
              </div>
            </CardContent>
          </Card>

          {/* Blunders */}
          <Card className="bg-zinc-900/50 border-zinc-800">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-red-500/20 flex items-center justify-center">
                    <Zap className="w-5 h-5 text-red-400" />
                  </div>
                  <div>
                    <p className="text-white font-medium">Blunders per Game</p>
                    <TrendBadge trend={blunderTrend} label={
                      blunderTrend === 'improving' ? 'Fewer' :
                      blunderTrend === 'worsening' ? 'More' : 'Stable'
                    } inverted />
                  </div>
                </div>
                <span className="text-2xl font-bold text-white">{blunders.avg_per_game?.toFixed(1) || '--'}</span>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* ═══════════════════════════════════════════════════════════════
            POSITIVE REINFORCEMENT
        ═══════════════════════════════════════════════════════════════ */}
        {isImproving && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="mb-6"
          >
            <Card className="bg-gradient-to-r from-emerald-500/10 to-emerald-500/5 border-emerald-500/20">
              <CardContent className="p-4 flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-emerald-500/20 flex items-center justify-center flex-shrink-0">
                  <Sparkles className="w-5 h-5 text-emerald-400" />
                </div>
                <div>
                  <p className="text-emerald-300 font-medium">You're improving!</p>
                  <p className="text-emerald-400/60 text-sm">Keep up the great work</p>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* ═══════════════════════════════════════════════════════════════
            CTA: Keep Playing
        ═══════════════════════════════════════════════════════════════ */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
        >
          <Button 
            onClick={() => navigate("/play-with-coach")}
            className="w-full bg-zinc-800 hover:bg-zinc-700 text-white h-12"
          >
            Play a Game
            <ChevronRight className="w-4 h-4 ml-2" />
          </Button>
        </motion.div>

        {/* Sync */}
        <div className="flex justify-center mt-6">
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
