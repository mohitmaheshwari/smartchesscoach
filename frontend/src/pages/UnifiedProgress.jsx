/**
 * PROGRESS PAGE → Confidence
 * "Am I getting better?"
 * 
 * Real data. Real breakdown. Two journeys.
 * 
 * - Score breakdown (what makes up the score)
 * - Games analyzed vs total
 * - Long journey (older half vs newer half)
 * - Short journey (last 5 vs previous 5)
 * - Recent form
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
  const [games, setGames] = useState([]);
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
        const g = await gamesRes.json();
        setGames(Array.isArray(g) ? g : []);
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
  const gamesAnalyzed = homeData?.games_analyzed || progressData?.valid_analysis_count || 0;
  const totalGames = games.length;
  
  // Score components
  const scoreComponents = [
    { key: 'tactical_discipline', label: 'Tactics', score: allScores.tactical_discipline || 0 },
    { key: 'calculation_depth', label: 'Calculation', score: allScores.calculation_depth || 0 },
    { key: 'time_mastery', label: 'Time', score: allScores.time_mastery || 0 },
    { key: 'positional_sense', label: 'Position', score: allScores.positional_sense || 0 },
    { key: 'pattern_control', label: 'Patterns', score: allScores.pattern_control || 0 },
  ].sort((a, b) => b.score - a.score);
  
  const strongest = scoreComponents[0];
  const weakest = scoreComponents.filter(c => c.score > 0).pop() || scoreComponents[scoreComponents.length - 1];
  
  // Calculate journeys from game results
  const getGameResult = (game) => {
    const result = game.result;
    const userColor = game.user_color || (game.white_player === user?.lichess_username ? 'white' : 'black');
    if (result === '1-0') return userColor === 'white' ? 1 : 0; // 1 = win, 0 = loss
    if (result === '0-1') return userColor === 'black' ? 1 : 0;
    if (result === '1/2-1/2') return 0.5;
    return null;
  };
  
  // Recent form (last 10)
  const recentGames = games.slice(0, 10);
  const recentForm = recentGames.map(g => {
    const r = getGameResult(g);
    return r === 1 ? 'win' : r === 0 ? 'loss' : r === 0.5 ? 'draw' : 'unknown';
  }).reverse();
  
  const wins = recentForm.filter(r => r === 'win').length;
  const losses = recentForm.filter(r => r === 'loss').length;
  
  // Long journey: First half vs Second half of all games
  const calculateJourney = (older, newer) => {
    const olderWinRate = older.reduce((sum, g) => {
      const r = getGameResult(g);
      return sum + (r !== null ? r : 0);
    }, 0) / Math.max(older.length, 1);
    
    const newerWinRate = newer.reduce((sum, g) => {
      const r = getGameResult(g);
      return sum + (r !== null ? r : 0);
    }, 0) / Math.max(newer.length, 1);
    
    return {
      older: Math.round(olderWinRate * 100),
      newer: Math.round(newerWinRate * 100),
      delta: Math.round((newerWinRate - olderWinRate) * 100)
    };
  };
  
  // Long journey: older half vs newer half
  const midpoint = Math.floor(games.length / 2);
  const longJourney = games.length >= 10 ? calculateJourney(
    games.slice(midpoint), // older half
    games.slice(0, midpoint) // newer half
  ) : null;
  
  // Short journey: games 5-10 vs games 0-5
  const shortJourney = games.length >= 10 ? calculateJourney(
    games.slice(5, 10), // previous 5
    games.slice(0, 5)   // recent 5
  ) : null;

  // TrendIndicator component
  const TrendIndicator = ({ delta, size = "sm" }) => {
    const iconClass = size === "lg" ? "w-5 h-5" : "w-4 h-4";
    if (delta > 0) return <TrendingUp className={`${iconClass} text-emerald-500`} />;
    if (delta < 0) return <TrendingDown className={`${iconClass} text-red-500`} />;
    return <Minus className={`${iconClass} text-zinc-500`} />;
  };

  return (
    <Layout user={user}>
      <div className="max-w-md mx-auto px-4 py-8 min-h-[60vh]" data-testid="progress-page">
        
        {/* ═══════════════════════════════════════════════════════════════
            THINKING SCORE
        ═══════════════════════════════════════════════════════════════ */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-6"
        >
          <p className="text-xs text-zinc-500 uppercase tracking-widest mb-3">Thinking Score</p>
          <p className="text-7xl font-bold text-white mb-2">{Math.round(scoreNow)}</p>
          
          {/* Games analyzed vs total */}
          <p className="text-sm text-zinc-500">
            <span className="text-zinc-400">{gamesAnalyzed}</span> of {totalGames} games analyzed
          </p>
        </motion.div>

        {/* ═══════════════════════════════════════════════════════════════
            SCORE BREAKDOWN
        ═══════════════════════════════════════════════════════════════ */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="mb-6 p-4 rounded-xl bg-zinc-900/50 border border-zinc-800"
        >
          <p className="text-xs text-zinc-500 uppercase tracking-wide mb-4">What makes up your score</p>
          
          <div className="space-y-2.5">
            {scoreComponents.map((component, i) => (
              <div key={component.key} className="flex items-center gap-3">
                <div className="w-20 text-xs text-zinc-500">{component.label}</div>
                <div className="flex-1 h-2 bg-zinc-800 rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${Math.min(100, component.score * 2)}%` }}
                    transition={{ delay: 0.1 + i * 0.05, duration: 0.4 }}
                    className={`h-full rounded-full ${
                      component.score >= 20 ? 'bg-emerald-500' :
                      component.score >= 10 ? 'bg-blue-500' :
                      component.score > 0 ? 'bg-amber-500' : 'bg-zinc-700'
                    }`}
                  />
                </div>
                <div className="w-6 text-right text-sm text-zinc-400">{Math.round(component.score)}</div>
              </div>
            ))}
          </div>
          
          <p className="text-xs text-zinc-500 mt-3 pt-3 border-t border-zinc-800">
            <span className="text-emerald-400">{strongest.label}</span> strongest
            {weakest.score < strongest.score && (
              <> · <span className="text-amber-400">{weakest.label}</span> needs work</>
            )}
          </p>
        </motion.div>

        {/* ═══════════════════════════════════════════════════════════════
            TWO JOURNEYS: Long-term & Short-term
        ═══════════════════════════════════════════════════════════════ */}
        {(longJourney || shortJourney) && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="mb-6 grid grid-cols-2 gap-3"
          >
            {/* Long Journey */}
            {longJourney && (
              <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800">
                <p className="text-xs text-zinc-500 uppercase tracking-wide mb-3">Long Journey</p>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-zinc-600 text-sm">Older</span>
                  <span className="text-zinc-600 text-sm">Recent</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-lg text-zinc-400">{longJourney.older}%</span>
                  <TrendIndicator delta={longJourney.delta} />
                  <span className="text-lg text-white font-medium">{longJourney.newer}%</span>
                </div>
                <p className="text-xs text-zinc-600 mt-2">
                  {longJourney.delta > 0 ? `+${longJourney.delta}%` : `${longJourney.delta}%`} win rate
                </p>
              </div>
            )}
            
            {/* Short Journey */}
            {shortJourney && (
              <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800">
                <p className="text-xs text-zinc-500 uppercase tracking-wide mb-3">Recent Form</p>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-zinc-600 text-sm">Prev 5</span>
                  <span className="text-zinc-600 text-sm">Last 5</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-lg text-zinc-400">{shortJourney.older}%</span>
                  <TrendIndicator delta={shortJourney.delta} />
                  <span className="text-lg text-white font-medium">{shortJourney.newer}%</span>
                </div>
                <p className="text-xs text-zinc-600 mt-2">
                  {shortJourney.delta > 0 ? `+${shortJourney.delta}%` : `${shortJourney.delta}%`} win rate
                </p>
              </div>
            )}
          </motion.div>
        )}

        {/* ═══════════════════════════════════════════════════════════════
            RECENT FORM BAR CHART
        ═══════════════════════════════════════════════════════════════ */}
        {recentForm.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="mb-6"
          >
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs text-zinc-500 uppercase tracking-wide">Last {recentForm.length} Games</p>
              <p className="text-xs text-zinc-600">{wins}W {losses}L</p>
            </div>
            
            <div className="flex items-end gap-1.5 h-8">
              {recentForm.map((result, i) => (
                <motion.div
                  key={i}
                  initial={{ height: 0 }}
                  animate={{ height: result === 'win' ? '100%' : result === 'draw' ? '50%' : '30%' }}
                  transition={{ delay: 0.2 + i * 0.03, duration: 0.3 }}
                  className={`flex-1 rounded-sm ${
                    result === 'win' ? 'bg-emerald-500' : 
                    result === 'draw' ? 'bg-zinc-500' : 
                    'bg-red-500/70'
                  }`}
                />
              ))}
            </div>
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
          <p className="text-zinc-400">
            {longJourney?.delta > 0 && shortJourney?.delta > 0 
              ? "Improving across the board."
              : longJourney?.delta > 0 
                ? "Long-term growth is there."
                : shortJourney?.delta > 0
                  ? "Recent momentum is positive."
                  : "Keep playing. Growth takes time."}
          </p>
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
