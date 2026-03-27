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
  BookOpen,
  AlertTriangle,
  Brain
} from "lucide-react";

const HomePage = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [stats, setStats] = useState(null);
  const [prescriptions, setPrescriptions] = useState([]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [homeRes, statsRes, rxRes] = await Promise.all([
          fetch(`${API}/coach/home-intelligence`, { credentials: "include" }),
          fetch(`${API}/progress`, { credentials: "include" }),
          fetch(`${API}/home/pattern-prescription`, { credentials: "include" }),
        ]);
        if (homeRes.ok) setData(await homeRes.json());
        if (statsRes.ok) setStats(await statsRes.json());
        if (rxRes.ok) {
          const rxData = await rxRes.json();
          setPrescriptions(rxData.prescriptions || []);
        }
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

  return (
    <Layout user={user}>
      <div className="max-w-xl mx-auto px-4 py-8" data-testid="home-page">
        
        {/* Greeting */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mb-10">
          <h1 className="text-3xl text-white tracking-tight mb-1" style={{ fontFamily: "'Cormorant Garamond', serif" }}>{getGreeting()}</h1>
          <p className="text-sm text-gray-500 font-light">{getMotivation()}</p>
        </motion.div>

        {/* Quick Pulse */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }} className="mb-8">
          <div className="flex items-center gap-0" style={{ border: "1px solid rgba(255,255,255,0.05)" }}>
            <div className="flex-1 text-center py-4" style={{ borderRight: "1px solid rgba(255,255,255,0.05)" }}>
              <p className="text-2xl font-light text-white" style={{ fontFamily: "'Cormorant Garamond', serif" }}>{Math.round(score)}</p>
              <p className="text-[10px] tracking-[0.15em] uppercase text-gray-600" style={{ fontFamily: "'JetBrains Mono', monospace" }}>Score</p>
            </div>
            <div className="flex-1 text-center py-4" style={{ borderRight: "1px solid rgba(255,255,255,0.05)" }}>
              <p className="text-2xl font-light text-white" style={{ fontFamily: "'Cormorant Garamond', serif" }}>{accuracy.toFixed(0)}%</p>
              <p className="text-[10px] tracking-[0.15em] uppercase text-gray-600" style={{ fontFamily: "'JetBrains Mono', monospace" }}>Accuracy</p>
            </div>
            <div className="flex-1 text-center py-4">
              <TrendIcon className={`w-5 h-5 mx-auto ${trend === 'improving' ? 'text-emerald-500' : trend === 'declining' ? 'text-red-400' : 'text-gray-600'}`} strokeWidth={1.5} />
              <p className="text-[10px] tracking-[0.15em] uppercase text-gray-600 mt-1" style={{ fontFamily: "'JetBrains Mono', monospace" }}>Trend</p>
            </div>
          </div>
        </motion.div>

        {/* Play with Coach */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="mb-4">
          <div
            className="p-5 cursor-pointer transition-all duration-200 hover:opacity-90 group"
            style={{ background: "#722F37" }}
            onClick={() => navigate("/play-with-coach")}
            data-testid="play-card"
          >
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 flex items-center justify-center" style={{ background: "rgba(255,255,255,0.15)" }}>
                <Play className="w-6 h-6 text-white fill-white" />
              </div>
              <div className="flex-1">
                <h2 className="text-lg text-white font-light" style={{ fontFamily: "'Cormorant Garamond', serif" }}>Play with Coach</h2>
                <p className="text-sm text-white/50 font-light">Get feedback on every move</p>
              </div>
              <ChevronRight className="w-5 h-5 text-white/40" strokeWidth={1.5} />
            </div>
          </div>
        </motion.div>

        {/* Train & Study */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }} className="grid grid-cols-2 gap-3 mb-6">
          <div
            className="p-4 cursor-pointer transition-all duration-200 hover:bg-white/[0.03]"
            style={{ background: "#0a0a0a", border: "1px solid rgba(255,255,255,0.05)" }}
            onClick={() => navigate(problem ? `/training?focus=${problem}` : "/training")}
            data-testid="train-card"
          >
            <p className="text-[10px] tracking-[0.15em] uppercase mb-3" style={{ color: "#CBA135", fontFamily: "'JetBrains Mono', monospace" }}>Train</p>
            <p className="text-sm text-white font-light">
              {problem ? <span className="capitalize">{problemFormatted}</span> : "Positions to solve"}
            </p>
            <p className="text-xs text-gray-600 mt-1">{problem ? `${problemCount}x recently` : "Your games + community"}</p>
          </div>

          <div
            className="p-4 cursor-pointer transition-all duration-200 hover:bg-white/[0.03]"
            style={{ background: "#0a0a0a", border: "1px solid rgba(255,255,255,0.05)" }}
            onClick={() => navigate("/openings-overview")}
            data-testid="openings-card"
          >
            <p className="text-[10px] tracking-[0.15em] uppercase mb-3" style={{ color: "#CBA135", fontFamily: "'JetBrains Mono', monospace" }}>Study</p>
            <p className="text-sm text-white font-light">Openings & Endgames</p>
            <p className="text-xs text-gray-600 mt-1">Your repertoire + endgame lessons</p>
          </div>
        </motion.div>

        {/* Patterns to Fix */}
        {prescriptions.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.18 }} className="mb-4">
            <div style={{ background: "#0a0a0a", border: "1px solid rgba(255,255,255,0.05)" }} data-testid="pattern-prescription-card">
              <div className="p-4">
                <p className="text-[10px] tracking-[0.15em] uppercase mb-4" style={{ color: "#CBA135", fontFamily: "'JetBrains Mono', monospace" }}>Patterns to Fix</p>
                <div className="space-y-0">
                  {prescriptions.map((rx) => (
                    <div
                      key={rx.pattern_type}
                      className="flex items-center justify-between py-2.5 cursor-pointer hover:bg-white/[0.02] transition-colors -mx-4 px-4"
                      style={{ borderBottom: "1px solid rgba(255,255,255,0.03)" }}
                      data-testid={`prescription-${rx.pattern_type}`}
                      onClick={() => navigate(`/training?focus=${rx.pattern_type}`)}
                    >
                      <div className="flex items-center gap-3">
                        <span className="w-1.5 h-1.5 rounded-full" style={{ background: rx.severity === 'critical' ? '#722F37' : '#CBA135' }} />
                        <span className="text-sm text-gray-300 font-light">{rx.label}</span>
                        <span className="text-xs text-gray-600" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{rx.recent_count}x</span>
                      </div>
                      {rx.training_positions_available > 0 && (
                        <span className="text-xs" style={{ color: "#CBA135", fontFamily: "'JetBrains Mono', monospace" }}>
                          {rx.training_positions_available} waiting
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {/* Habits */}
        {stats?.habits?.length > 0 && (() => {
          const activeHabits = stats.habits.filter(h => h.is_active);
          const improvingHabits = stats.habits.filter(h => h.trend === "improving");
          const resolvedCount = stats.resolved_habits?.length || 0;
          if (activeHabits.length === 0 && improvingHabits.length === 0 && resolvedCount === 0) return null;
          return (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="mb-4">
              <div className="p-4" style={{ background: "#0a0a0a", border: "1px solid rgba(255,255,255,0.05)" }} data-testid="habit-insight-card">
                <p className="text-[10px] tracking-[0.15em] uppercase mb-3" style={{ color: "#CBA135", fontFamily: "'JetBrains Mono', monospace" }}>Habits</p>
                <div className="space-y-1.5">
                  {improvingHabits.length > 0 && (
                    <p className="text-xs text-emerald-500 flex items-center gap-1.5 font-light">
                      <TrendingUp className="w-3 h-3" strokeWidth={1.5} />
                      {improvingHabits[0].name} is improving
                    </p>
                  )}
                  {activeHabits.length > 0 && !improvingHabits.length && (
                    <p className="text-xs flex items-center gap-1.5 font-light" style={{ color: "#722F37" }}>
                      <AlertTriangle className="w-3 h-3" strokeWidth={1.5} />
                      Watch: {activeHabits[0].name} ({activeHabits[0].occurrences_recent}x recently)
                    </p>
                  )}
                  {resolvedCount > 0 && (
                    <p className="text-xs text-gray-600 font-light">{resolvedCount} habit{resolvedCount !== 1 ? 's' : ''} resolved</p>
                  )}
                </div>
              </div>
            </motion.div>
          );
        })()}

        {/* Last Game */}
        {lastGame && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.22 }} className="mb-4">
            <div
              className="p-4 cursor-pointer transition-all duration-200 hover:bg-white/[0.02]"
              style={{ background: "#0a0a0a", border: "1px solid rgba(255,255,255,0.05)" }}
              onClick={() => navigate(`/game/${lastGame.game_id}`)}
              data-testid="last-game-card"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Swords className="w-4 h-4 text-gray-600" strokeWidth={1.5} />
                  <div>
                    <p className="text-sm text-gray-300 font-light">Last game vs {lastGame.opponent || 'Opponent'}</p>
                    <p className="text-xs text-gray-600">
                      {lastGame.result === '1-0' ? 'Won' : lastGame.result === '0-1' ? 'Lost' : 'Draw'}
                      {lastGame.blunders > 0 && ` · ${lastGame.blunders} blunder${lastGame.blunders > 1 ? 's' : ''}`}
                    </p>
                  </div>
                </div>
                <span className="text-xs text-gray-600">Review →</span>
              </div>
            </div>
          </motion.div>
        )}

        <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.25 }}
          className="text-center text-xs text-gray-700 mt-10" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
          {gamesAnalyzed} games analyzed
        </motion.p>
      </div>
    </Layout>
  );
};

export default HomePage;
