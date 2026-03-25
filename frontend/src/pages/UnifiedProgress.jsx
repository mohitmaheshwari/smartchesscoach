/**
 * PROGRESS PAGE → Confidence
 * "Am I getting better?"
 * 
 * Real data. Real breakdown. Real confidence.
 * 
 * - Score now vs before (with component breakdown)
 * - Recent form (real game results)
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

  // Score data
  const devPhase = homeData?.development_phase || {};
  const scoreNow = devPhase.score || 0;
  const allScores = devPhase.all_scores || {};
  const accuracy = progressData?.accuracy || {};
  const gamesAnalyzed = homeData?.games_analyzed || 0;
  
  // Calculate score before (simplified)
  const accuracyNow = accuracy.current || 0;
  const accuracyBefore = accuracy.previous || accuracyNow;
  const accuracyDelta = accuracyNow - accuracyBefore;
  const scoreBefore = Math.max(0, Math.round(scoreNow - (accuracyDelta / 3)));
  const scoreDelta = Math.round(scoreNow - scoreBefore);
  
  // Score components - format nicely
  const scoreComponents = [
    { key: 'tactical_discipline', label: 'Tactics', score: allScores.tactical_discipline || 0 },
    { key: 'calculation_depth', label: 'Calculation', score: allScores.calculation_depth || 0 },
    { key: 'time_mastery', label: 'Time', score: allScores.time_mastery || 0 },
    { key: 'positional_sense', label: 'Position', score: allScores.positional_sense || 0 },
    { key: 'pattern_control', label: 'Patterns', score: allScores.pattern_control || 0 },
  ].sort((a, b) => b.score - a.score); // Highest first
  
  // Find strongest and weakest
  const strongest = scoreComponents[0];
  const weakest = scoreComponents.filter(c => c.score > 0).pop() || scoreComponents[scoreComponents.length - 1];
  
  // Recent games for form chart
  const getGameResult = (game) => {
    const result = game.result;
    const userColor = game.user_color || (game.white_player === user?.lichess_username ? 'white' : 'black');
    if (result === '1-0') return userColor === 'white' ? 'win' : 'loss';
    if (result === '0-1') return userColor === 'black' ? 'win' : 'loss';
    if (result === '1/2-1/2') return 'draw';
    return 'unknown';
  };
  
  const recentForm = recentGames.map(g => getGameResult(g)).reverse();
  const wins = recentForm.filter(r => r === 'win').length;
  const losses = recentForm.filter(r => r === 'loss').length;
  
  // Encouragement
  const getEncouragement = () => {
    if (scoreDelta > 0 && wins > losses) return "Strong form. Keep it up.";
    if (scoreDelta > 0) return "Moving forward.";
    if (wins > losses) return "Winning more than losing.";
    return "Consistency builds strength.";
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
          className="text-center mb-6"
        >
          <p className="text-xs text-zinc-500 uppercase tracking-widest mb-4">Thinking Score</p>
          
          <div className="flex items-center justify-center gap-6 mb-3">
            <div className="text-right">
              <p className="text-4xl font-light text-zinc-600">{Math.round(scoreBefore)}</p>
              <p className="text-xs text-zinc-600 mt-1">before</p>
            </div>
            
            <div className={`${scoreDelta >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
              {scoreDelta > 0 ? <TrendingUp className="w-6 h-6" /> : 
               scoreDelta < 0 ? <TrendingDown className="w-6 h-6" /> : 
               <Minus className="w-6 h-6 text-zinc-500" />}
            </div>
            
            <div className="text-left">
              <p className="text-6xl font-bold text-white">{Math.round(scoreNow)}</p>
              <p className="text-xs text-zinc-500 mt-1">now</p>
            </div>
          </div>
          
          {scoreDelta !== 0 && (
            <span className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${
              scoreDelta > 0 ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
            }`}>
              {scoreDelta > 0 ? '+' : ''}{scoreDelta} points
            </span>
          )}
        </motion.div>

        {/* ═══════════════════════════════════════════════════════════════
            SCORE BREAKDOWN - What makes up this score
        ═══════════════════════════════════════════════════════════════ */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="mb-8 p-4 rounded-xl bg-zinc-900/50 border border-zinc-800"
        >
          <p className="text-xs text-zinc-500 uppercase tracking-wide mb-4">Score Breakdown</p>
          
          <div className="space-y-3">
            {scoreComponents.map((component, i) => (
              <div key={component.key} className="flex items-center gap-3">
                <div className="w-16 text-xs text-zinc-500">{component.label}</div>
                <div className="flex-1 h-2 bg-zinc-800 rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${Math.min(100, component.score)}%` }}
                    transition={{ delay: 0.1 + i * 0.05, duration: 0.5 }}
                    className={`h-full rounded-full ${
                      component.score >= 20 ? 'bg-emerald-500' :
                      component.score >= 10 ? 'bg-blue-500' :
                      component.score > 0 ? 'bg-amber-500' :
                      'bg-zinc-700'
                    }`}
                  />
                </div>
                <div className="w-8 text-right text-sm text-zinc-400">
                  {Math.round(component.score)}
                </div>
              </div>
            ))}
          </div>
          
          {/* Insight */}
          <div className="mt-4 pt-3 border-t border-zinc-800">
            <p className="text-xs text-zinc-400">
              <span className="text-emerald-400">{strongest.label}</span> is your strongest area
              {weakest.score < strongest.score && (
                <span> · <span className="text-amber-400">{weakest.label}</span> needs work</span>
              )}
            </p>
          </div>
        </motion.div>

        {/* ═══════════════════════════════════════════════════════════════
            RECENT FORM - Real game results
        ═══════════════════════════════════════════════════════════════ */}
        {recentForm.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="mb-8"
          >
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs text-zinc-500 uppercase tracking-wide">Recent Form</p>
              <p className="text-xs text-zinc-600">{wins}W {losses}L</p>
            </div>
            
            <div className="flex items-end gap-1.5 h-10">
              {recentForm.map((result, i) => (
                <motion.div
                  key={i}
                  initial={{ height: 0 }}
                  animate={{ height: result === 'win' ? '100%' : result === 'draw' ? '50%' : '30%' }}
                  transition={{ delay: 0.15 + i * 0.03, duration: 0.3 }}
                  className={`flex-1 rounded-sm ${
                    result === 'win' ? 'bg-emerald-500' : 
                    result === 'draw' ? 'bg-zinc-500' : 
                    'bg-red-500/70'
                  }`}
                />
              ))}
            </div>
            <p className="text-xs text-zinc-600 mt-2 text-center">Last {recentForm.length} games</p>
          </motion.div>
        )}

        {/* ═══════════════════════════════════════════════════════════════
            ENCOURAGEMENT
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
          className="flex justify-center mt-8"
        >
          <Button
            variant="ghost"
            size="sm"
            onClick={syncNow}
            disabled={syncing}
            className="text-zinc-600 hover:text-zinc-400"
          >
            {syncing ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <RefreshCw className="w-4 h-4 mr-2" />}
            Sync
          </Button>
        </motion.div>
      </div>
    </Layout>
  );
};

export default UnifiedProgress;
