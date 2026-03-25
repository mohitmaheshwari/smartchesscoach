/**
 * HOME PAGE → Decision
 * "What should I do right now?"
 * 
 * Focused but warm - like a coach greeting you
 * - Context (how you're doing)
 * - Clear primary action (Play)
 * - One focus area
 * - Quick pulse of your recent form
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
  Play, 
  ChevronRight,
  Flame,
  Target,
  TrendingUp,
  TrendingDown,
  Minus,
  Swords,
  BookOpen
} from "lucide-react";

const HomePage = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [stats, setStats] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [homeRes, statsRes] = await Promise.all([
          fetch(`${API}/coach/home-intelligence`, { credentials: "include" }),
          fetch(`${API}/progress`, { credentials: "include" })
        ]);
        if (homeRes.ok) setData(await homeRes.json());
        if (statsRes.ok) setStats(await statsRes.json());
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[70vh]">
          <Loader2 className="w-6 h-6 animate-spin text-zinc-500" />
        </div>
      </Layout>
    );
  }

  // Extract data
  const score = data?.development_phase?.score || 0;
  const gamesAnalyzed = data?.games_analyzed || 0;
  const problem = data?.specific_patterns?.dominant_pattern;
  const problemFormatted = problem?.replace(/_/g, " ");
  const problemCount = data?.specific_patterns?.pattern_count || 0;
  const accuracy = stats?.accuracy?.current || 0;
  const trend = stats?.accuracy?.trend;
  const lastGame = data?.last_game;
  
  // Get greeting based on time
  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 17) return "Good afternoon";
    return "Good evening";
  };

  // Get motivation based on trend
  const getMotivation = () => {
    if (trend === 'improving') return "You're on a roll!";
    if (trend === 'declining') return "Let's get back on track";
    return "Ready to play?";
  };

  const TrendIcon = trend === 'improving' ? TrendingUp : trend === 'declining' ? TrendingDown : Minus;
  const trendColor = trend === 'improving' ? 'text-emerald-400' : trend === 'declining' ? 'text-amber-400' : 'text-zinc-400';

  return (
    <Layout user={user}>
      <div className="max-w-xl mx-auto px-4 py-8" data-testid="home-page">
        
        {/* ═══════════════════════════════════════════════════════════════
            GREETING & CONTEXT
        ═══════════════════════════════════════════════════════════════ */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <h1 className="text-2xl font-bold text-white mb-1">{getGreeting()}</h1>
          <p className="text-zinc-400">{getMotivation()}</p>
        </motion.div>

        {/* ═══════════════════════════════════════════════════════════════
            QUICK PULSE - Your form at a glance
        ═══════════════════════════════════════════════════════════════ */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="mb-6"
        >
          <div className="flex items-center gap-4 p-4 rounded-xl bg-zinc-900/50 border border-zinc-800">
            <div className="flex-1 text-center border-r border-zinc-800">
              <p className="text-2xl font-bold text-white">{Math.round(score)}</p>
              <p className="text-xs text-zinc-500">Score</p>
            </div>
            <div className="flex-1 text-center border-r border-zinc-800">
              <p className="text-2xl font-bold text-white">{accuracy.toFixed(0)}%</p>
              <p className="text-xs text-zinc-500">Accuracy</p>
            </div>
            <div className="flex-1 text-center">
              <div className={`flex items-center justify-center gap-1 ${trendColor}`}>
                <TrendIcon className="w-5 h-5" />
              </div>
              <p className="text-xs text-zinc-500">Trend</p>
            </div>
          </div>
        </motion.div>

        {/* ═══════════════════════════════════════════════════════════════
            PRIMARY ACTION: PLAY
        ═══════════════════════════════════════════════════════════════ */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="mb-4"
        >
          <Card 
            className="bg-gradient-to-br from-emerald-600 to-emerald-700 border-0 cursor-pointer hover:from-emerald-500 hover:to-emerald-600 transition-all duration-300 shadow-lg shadow-emerald-900/20 group"
            onClick={() => navigate("/play-with-coach")}
            data-testid="play-card"
          >
            <CardContent className="p-6">
              <div className="flex items-center gap-4">
                <div className="w-14 h-14 rounded-2xl bg-white/20 flex items-center justify-center group-hover:scale-105 transition-transform">
                  <Play className="w-7 h-7 text-white fill-white" />
                </div>
                <div className="flex-1">
                  <h2 className="text-xl font-bold text-white">Play with Coach</h2>
                  <p className="text-emerald-100/70 text-sm">Get feedback on every move</p>
                </div>
                <ChevronRight className="w-5 h-5 text-white/60" />
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* ═══════════════════════════════════════════════════════════════
            SECONDARY ACTIONS: Train & Review
        ═══════════════════════════════════════════════════════════════ */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="grid grid-cols-2 gap-3 mb-6"
        >
          {/* Train weakness */}
          {problem && (
            <Card 
              className="bg-zinc-900 border-zinc-800 cursor-pointer hover:border-zinc-700 transition-all group"
              onClick={() => navigate(`/training/prescribed?weakness=${problem}`)}
              data-testid="train-card"
            >
              <CardContent className="p-4">
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-9 h-9 rounded-lg bg-amber-500/20 flex items-center justify-center">
                    <Target className="w-4 h-4 text-amber-400" />
                  </div>
                  <span className="text-xs text-zinc-500 uppercase tracking-wide">Train</span>
                </div>
                <p className="text-white font-medium capitalize text-sm">{problemFormatted}</p>
                <p className="text-xs text-zinc-500 mt-1">{problemCount}x recently</p>
              </CardContent>
            </Card>
          )}

          {/* Study openings */}
          <Card 
            className="bg-zinc-900 border-zinc-800 cursor-pointer hover:border-zinc-700 transition-all group"
            onClick={() => navigate("/openings")}
            data-testid="openings-card"
          >
            <CardContent className="p-4">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-9 h-9 rounded-lg bg-blue-500/20 flex items-center justify-center">
                  <BookOpen className="w-4 h-4 text-blue-400" />
                </div>
                <span className="text-xs text-zinc-500 uppercase tracking-wide">Study</span>
              </div>
              <p className="text-white font-medium text-sm">Openings</p>
              <p className="text-xs text-zinc-500 mt-1">Build repertoire</p>
            </CardContent>
          </Card>
        </motion.div>

        {/* ═══════════════════════════════════════════════════════════════
            RECENT GAME (if exists)
        ═══════════════════════════════════════════════════════════════ */}
        {lastGame && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <Card 
              className="bg-zinc-900/50 border-zinc-800/50 cursor-pointer hover:bg-zinc-900 transition-all"
              onClick={() => navigate(`/game/${lastGame.game_id}`)}
              data-testid="last-game-card"
            >
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Swords className="w-4 h-4 text-zinc-500" />
                    <div>
                      <p className="text-sm text-zinc-300">Last game vs {lastGame.opponent || 'Opponent'}</p>
                      <p className="text-xs text-zinc-500">
                        {lastGame.result === '1-0' ? 'Won' : lastGame.result === '0-1' ? 'Lost' : 'Draw'}
                        {lastGame.blunders > 0 && ` • ${lastGame.blunders} blunder${lastGame.blunders > 1 ? 's' : ''}`}
                      </p>
                    </div>
                  </div>
                  <span className="text-xs text-zinc-500">Review →</span>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Games count footer */}
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.25 }}
          className="text-center text-xs text-zinc-600 mt-8"
        >
          {gamesAnalyzed} games analyzed
        </motion.p>
      </div>
    </Layout>
  );
};

export default HomePage;
