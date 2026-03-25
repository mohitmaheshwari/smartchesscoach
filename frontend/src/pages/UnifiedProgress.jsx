/**
 * PROGRESS PAGE → Confidence
 * "Am I getting better?"
 * 
 * Real data. Real comparison. Real confidence.
 * 
 * - Score now vs before
 * - Recent form (real game results)
 * - One improving stat
 * - One encouraging line
 */

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Loader2, RefreshCw, TrendingUp, TrendingDown, Minus } from "lucide-react";

const UnifiedProgress = ({ user }) => {
  const [loading, setLoading] = useState(true);
  const [progressData, setProgressData] = useState(null);
  const [homeData, setHomeData] = useState(null);
  const [recentGames, setRecentGames] = useState([]);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    fetchAll();
  }, []);

  const fetchAll = async () => {
    try {
      const [progressRes, homeRes, gamesRes] = await Promise.all([
        fetch(`${API}/progress`, { credentials: "include" }),
        fetch(`${API}/coach/home-intelligence`, { credentials: "include" }),
        fetch(`${API}/games`, { credentials: "include" })
      ]);
      if (progressRes.ok) setProgressData(await progressRes.json());
      if (homeRes.ok) setHomeData(await homeRes.json());
      if (gamesRes.ok) {
        const games = await gamesRes.json();
        // Get last 10 games for recent form
        setRecentGames(Array.isArray(games) ? games.slice(0, 10) : []);
      }
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

  // Real data extraction
  const scoreNow = homeData?.development_phase?.score || 0;
  const accuracy = progressData?.accuracy || {};
  const blunders = progressData?.blunders || {};
  const gamesAnalyzed = homeData?.games_analyzed || 0;
  
  // Calculate score change
  const accuracyNow = accuracy.current || 0;
  const accuracyBefore = accuracy.previous || accuracyNow;
  const accuracyDelta = accuracyNow - accuracyBefore;
  
  const scoreBefore = Math.max(0, Math.round(scoreNow - (accuracyDelta / 3)));
  const scoreDelta = scoreNow - scoreBefore;
  
  // Process recent games for the form chart
  const getGameResult = (game) => {
    const result = game.result;
    const userColor = game.user_color || (game.white_player === user?.lichess_username ? 'white' : 'black');
    
    if (result === '1-0') return userColor === 'white' ? 'win' : 'loss';
    if (result === '0-1') return userColor === 'black' ? 'win' : 'loss';
    if (result === '1/2-1/2') return 'draw';
    return 'unknown';
  };
  
  const recentForm = recentGames.map(g => getGameResult(g)).reverse(); // Oldest first
  const wins = recentForm.filter(r => r === 'win').length;
  const losses = recentForm.filter(r => r === 'loss').length;
  const draws = recentForm.filter(r => r === 'draw').length;
  
  // Find the ONE improving stat
  const getImprovingStat = () => {
    if (accuracy.trend === 'improving') {
      return {
        label: "Accuracy",
        now: `${accuracyNow.toFixed(0)}%`,
        delta: accuracyDelta > 0 ? `+${Math.abs(accuracyDelta).toFixed(0)}%` : null,
        isImproving: true
      };
    }
    if (blunders.trend === 'improving') {
      const delta = (blunders.previous || blunders.avg_per_game) - blunders.avg_per_game;
      return {
        label: "Blunders per game",
        now: blunders.avg_per_game?.toFixed(1),
        delta: delta > 0 ? `-${delta.toFixed(1)}` : null,
        isImproving: true
      };
    }
    return {
      label: "Accuracy",
      now: `${accuracyNow.toFixed(0)}%`,
      delta: null,
      isImproving: false
    };
  };
  
  const improvingStat = getImprovingStat();
  
  // Get encouragement based on real data
  const getEncouragement = () => {
    if (wins > losses && scoreDelta > 0) return "Strong form. Keep it up.";
    if (scoreDelta > 5) return "Real progress. Keep going.";
    if (scoreDelta > 0) return "Moving forward.";
    if (wins > losses) return "Winning more than losing.";
    if (improvingStat.isImproving) return "The work is showing.";
    if (gamesAnalyzed >= 10) return "Consistency builds strength.";
    return "Keep playing. Data builds over time.";
  };

  return (
    <Layout user={user}>
      <div className="max-w-md mx-auto px-4 py-10 min-h-[60vh]" data-testid="progress-page">
        
        {/* ═══════════════════════════════════════════════════════════════
            SCORE: NOW vs BEFORE
        ═══════════════════════════════════════════════════════════════ */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-10"
        >
          <p className="text-xs text-zinc-500 uppercase tracking-widest mb-6">Thinking Score</p>
          
          <div className="flex items-center justify-center gap-6 mb-4">
            {/* Before */}
            <div className="text-right">
              <p className="text-4xl font-light text-zinc-600">{Math.round(scoreBefore)}</p>
              <p className="text-xs text-zinc-600 mt-1">before</p>
            </div>
            
            {/* Arrow */}
            <div className={`${scoreDelta >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
              {scoreDelta > 0 ? (
                <TrendingUp className="w-6 h-6" />
              ) : scoreDelta < 0 ? (
                <TrendingDown className="w-6 h-6" />
              ) : (
                <Minus className="w-6 h-6 text-zinc-500" />
              )}
            </div>
            
            {/* Now */}
            <div className="text-left">
              <p className="text-6xl font-bold text-white">{Math.round(scoreNow)}</p>
              <p className="text-xs text-zinc-500 mt-1">now</p>
            </div>
          </div>
          
          {/* Delta badge */}
          {scoreDelta !== 0 && (
            <span className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${
              scoreDelta > 0 
                ? 'bg-emerald-500/20 text-emerald-400' 
                : 'bg-red-500/20 text-red-400'
            }`}>
              {scoreDelta > 0 ? '+' : ''}{scoreDelta} points
            </span>
          )}
        </motion.div>

        {/* ═══════════════════════════════════════════════════════════════
            RECENT FORM - Real game results
        ═══════════════════════════════════════════════════════════════ */}
        {recentForm.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="mb-10"
          >
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs text-zinc-500 uppercase tracking-wide">Recent Form</p>
              <p className="text-xs text-zinc-600">
                {wins}W {draws > 0 ? `${draws}D ` : ''}{losses}L
              </p>
            </div>
            
            {/* Game result bars */}
            <div className="flex items-end gap-1.5 h-12">
              {recentForm.map((result, i) => (
                <motion.div
                  key={i}
                  initial={{ height: 0 }}
                  animate={{ height: result === 'win' ? '100%' : result === 'draw' ? '50%' : '30%' }}
                  transition={{ delay: 0.1 + i * 0.05, duration: 0.3 }}
                  className={`flex-1 rounded-sm ${
                    result === 'win' ? 'bg-emerald-500' : 
                    result === 'draw' ? 'bg-zinc-500' : 
                    'bg-red-500/70'
                  }`}
                  title={`Game ${i + 1}: ${result}`}
                />
              ))}
            </div>
            
            <p className="text-xs text-zinc-600 mt-2 text-center">
              Last {recentForm.length} games
            </p>
          </motion.div>
        )}

        {/* ═══════════════════════════════════════════════════════════════
            ONE IMPROVING STAT
        ═══════════════════════════════════════════════════════════════ */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="text-center mb-10"
        >
          <div className="inline-block px-6 py-4 rounded-2xl bg-zinc-900 border border-zinc-800">
            <p className="text-xs text-zinc-500 uppercase tracking-wide mb-2">{improvingStat.label}</p>
            <div className="flex items-center justify-center gap-3">
              <span className="text-3xl font-semibold text-white">{improvingStat.now}</span>
              {improvingStat.delta && (
                <span className="text-emerald-400 text-sm font-medium">{improvingStat.delta}</span>
              )}
            </div>
          </div>
        </motion.div>

        {/* ═══════════════════════════════════════════════════════════════
            ONE ENCOURAGING LINE
        ═══════════════════════════════════════════════════════════════ */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="text-center"
        >
          <p className="text-zinc-400 text-lg">{getEncouragement()}</p>
          <p className="text-zinc-600 text-sm mt-2">{gamesAnalyzed} games analyzed</p>
        </motion.div>

        {/* Sync */}
        <motion.div 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.25 }}
          className="flex justify-center mt-10"
        >
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
            Sync
          </Button>
        </motion.div>
      </div>
    </Layout>
  );
};

export default UnifiedProgress;
