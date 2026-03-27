/**
 * HOME PAGE — V3
 * 
 * Your chess story at a glance.
 * Last battle (compact), streak, patterns across games, chess DNA, quick actions.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import LichessBoard from "@/components/LichessBoard";
import { ChevronRight, Swords, Target, ArrowRight, TrendingUp, TrendingDown, Minus, Import } from "lucide-react";

const WINE = "#722F37";
const GOLD_TEXT = "#8B6F1F";

const HomePage = ({ user }) => {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch(`${API}/home/dashboard-v2`, { credentials: "include" });
        if (res.ok) setData(await res.json());
      } catch (e) {
        console.error("Home fetch error:", e);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center h-[60vh]">
          <div className="w-5 h-5 border border-gray-300 border-t-gray-600 animate-spin" />
        </div>
      </Layout>
    );
  }

  const battle = data?.last_battle;
  const dna = data?.chess_dna;
  const fix = data?.one_thing_to_fix;
  const action = data?.context_action;
  const streak = data?.streak;
  const patterns = data?.patterns || [];
  const accuracy = data?.accuracy || 0;
  const gamesAnalyzed = data?.games_analyzed || 0;

  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  // No games state
  if (!battle && gamesAnalyzed === 0) {
    return (
      <Layout user={user}>
        <div className="max-w-xl mx-auto px-4 py-16 text-center" data-testid="home-page">
          <h1 className="text-3xl text-gray-900 tracking-tight mb-3" style={{ fontFamily: "'Playfair Display', serif" }}>
            Welcome to ChessGuru
          </h1>
          <p className="text-gray-500 mb-8 font-light">Import your games to get started. After 5 games, your coach will know your strengths. After 15, it'll know your weaknesses by name.</p>
          <div className="flex gap-3 justify-center">
            <button onClick={() => navigate("/import")} className="px-6 py-3 text-sm text-white" style={{ background: WINE }} data-testid="import-cta">
              <Import className="w-4 h-4 inline mr-2" strokeWidth={1.5} />
              Import Games
            </button>
            <button onClick={() => navigate("/play-with-coach")} className="px-6 py-3 text-sm text-gray-900" style={{ border: "1px solid rgba(0,0,0,0.15)" }} data-testid="play-cta">
              <Swords className="w-4 h-4 inline mr-2" strokeWidth={1.5} />
              Play with Coach
            </button>
          </div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout user={user}>
      <div className="max-w-2xl mx-auto px-4 py-6" data-testid="home-page">

        {/* ── GREETING + STREAK ── */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center justify-between mb-8">
          <p className="text-sm text-gray-500 font-light">{greeting}</p>
          {streak && streak.count >= 2 && (
            <div className="flex items-center gap-1.5">
              <span className={`text-xs font-medium ${streak.type === "W" ? "text-emerald-600" : streak.type === "L" ? "text-red-600" : "text-gray-500"}`}
                style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                {streak.count} {streak.type === "W" ? "wins" : streak.type === "L" ? "losses" : "draws"} in a row
              </span>
            </div>
          )}
        </motion.div>

        {/* ── LAST BATTLE (compact) ── */}
        {battle && (
          <motion.div initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }} className="mb-6">
            <p className="text-[10px] tracking-[0.2em] uppercase mb-2" style={{ color: GOLD_TEXT, fontFamily: "'JetBrains Mono', monospace" }}>
              Last Game
            </p>
            <div
              className="cursor-pointer transition-all duration-200 hover:shadow-md"
              style={{ background: "#FFFFFF", border: "1px solid rgba(0,0,0,0.08)" }}
              onClick={() => navigate(`/game/${battle.game_id}`)}
              data-testid="last-battle-card"
            >
              <div className="flex">
                <div className="w-[160px] h-[160px] flex-shrink-0">
                  <LichessBoard fen={battle.fen} orientation={battle.user_color} viewOnly={true} />
                </div>
                <div className="flex-1 p-4 flex flex-col justify-between min-w-0">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm text-gray-500 font-light">vs {battle.opponent}</span>
                      <span className="text-[10px] px-1.5 py-0.5" style={{
                        background: (battle.result === "1-0" && battle.user_color === "white") || (battle.result === "0-1" && battle.user_color === "black")
                          ? "rgba(22,163,74,0.1)" : "rgba(114,47,55,0.1)",
                        color: (battle.result === "1-0" && battle.user_color === "white") || (battle.result === "0-1" && battle.user_color === "black")
                          ? "#16a34a" : WINE,
                        fontFamily: "'JetBrains Mono', monospace",
                      }}>
                        {(battle.result === "1-0" && battle.user_color === "white") || (battle.result === "0-1" && battle.user_color === "black") ? "WON" : "LOST"}
                      </span>
                    </div>
                    <p className="text-sm text-gray-900 leading-snug font-light">{dna?.root_cause || "Review this game"}</p>
                  </div>
                  <div className="flex items-center gap-1.5 mt-2">
                    <span className="text-[10px] text-gray-500" style={{ fontFamily: "'JetBrains Mono', monospace" }}>Move {battle.move_number}</span>
                    <span className="text-[10px] font-mono text-red-600">{battle.your_move}</span>
                    <ArrowRight className="w-2.5 h-2.5 text-gray-300" />
                    <span className="text-[10px] font-mono text-emerald-600">{battle.best_move}</span>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {/* ── CHESS DNA (compact) ── */}
        {dna && (
          <motion.div initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="mb-6">
            <p className="text-[10px] tracking-[0.2em] uppercase mb-2" style={{ color: GOLD_TEXT, fontFamily: "'JetBrains Mono', monospace" }}>
              Your Chess DNA
            </p>
            <div style={{ background: "#FFFFFF", border: "1px solid rgba(0,0,0,0.08)" }}>
              <div className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <h2 className="text-xl text-gray-900 tracking-tight" style={{ fontFamily: "'Playfair Display', serif" }}>
                    {dna.archetype}
                  </h2>
                  <span className="text-[9px] tracking-[0.15em] uppercase px-1.5 py-0.5" style={{
                    border: `1px solid rgba(114,47,55,0.3)`, color: WINE, fontFamily: "'JetBrains Mono', monospace"
                  }}>
                    {dna.diagnosis?.replace(/_/g, " ")}
                  </span>
                </div>
                <p className="text-xs text-gray-500 font-light">{dna.before_line}</p>
                <p className="text-xs text-gray-900 font-light mt-0.5">{dna.after_line}</p>
              </div>
            </div>
          </motion.div>
        )}

        {/* ── PATTERNS ACROSS GAMES ── */}
        {patterns.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }} className="mb-6">
            <p className="text-[10px] tracking-[0.2em] uppercase mb-2" style={{ color: GOLD_TEXT, fontFamily: "'JetBrains Mono', monospace" }}>
              Patterns Across Games
            </p>
            <div style={{ background: "#FFFFFF", border: "1px solid rgba(0,0,0,0.08)" }}>
              {patterns.map((p, i) => (
                <div
                  key={p.pattern_type}
                  className="flex items-center justify-between px-4 py-3 cursor-pointer transition-all duration-200 hover:bg-black/[0.02]"
                  style={i < patterns.length - 1 ? { borderBottom: "1px solid rgba(0,0,0,0.04)" } : {}}
                  onClick={() => navigate(`/training?focus=${p.pattern_type}`)}
                  data-testid={`pattern-${p.pattern_type}`}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-1.5 h-1.5 rounded-full" style={{ background: p.severity === "critical" ? WINE : "#CBA135" }} />
                    <span className="text-sm text-gray-900 font-light">{p.label}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-500" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {p.recent_count}x
                    </span>
                    <span className="text-[9px] px-1.5 py-0.5 uppercase" style={{
                      background: p.severity === "critical" ? "rgba(114,47,55,0.08)" : "rgba(203,161,53,0.1)",
                      color: p.severity === "critical" ? WINE : GOLD_TEXT,
                      fontFamily: "'JetBrains Mono', monospace"
                    }}>
                      {p.severity}
                    </span>
                    <ChevronRight className="w-3.5 h-3.5 text-gray-300" strokeWidth={1.5} />
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}

        {/* ── FIX THIS ONE THING ── */}
        {fix && (
          <motion.div initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="mb-6">
            <p className="text-[10px] tracking-[0.2em] uppercase mb-2" style={{ color: GOLD_TEXT, fontFamily: "'JetBrains Mono', monospace" }}>
              If You Fixed One Thing
            </p>
            <div
              className="cursor-pointer transition-all duration-200 hover:shadow-md"
              style={{ background: "#FFFFFF", border: "1px solid rgba(0,0,0,0.08)" }}
              onClick={() => navigate("/training?focus=calculation_depth")}
              data-testid="one-thing-to-fix"
            >
              <div className="p-4">
                <p className="text-xs text-gray-500 font-light mb-1">{fix.stat_line}</p>
                <p className="text-sm text-gray-900 font-light" style={{ fontFamily: "'Playfair Display', serif" }}>{fix.fix_line}</p>
                {fix.diff_line && (
                  <p className="text-base mt-1" style={{ color: "#16a34a", fontFamily: "'Playfair Display', serif" }}>{fix.diff_line}</p>
                )}
              </div>
            </div>
          </motion.div>
        )}

        {/* ── QUICK ACTIONS ── */}
        <motion.div initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }} className="mb-6">
          <div className="flex gap-3">
            {action && (
              <div
                className="flex-1 p-3.5 cursor-pointer transition-all duration-200 hover:shadow-md flex items-center gap-3"
                style={{ background: action.type === "review_loss" ? WINE : "#FFFFFF", color: action.type === "review_loss" ? "#fff" : "#1a1a1a", border: action.type === "review_loss" ? "none" : "1px solid rgba(0,0,0,0.08)" }}
                onClick={() => navigate(action.href)}
                data-testid="context-action"
              >
                <Target className="w-4 h-4 flex-shrink-0 opacity-70" strokeWidth={1.5} />
                <span className="text-sm font-light">{action.label}</span>
                <ChevronRight className="w-4 h-4 ml-auto opacity-40" strokeWidth={1.5} />
              </div>
            )}
            {action?.type !== "play" && (
              <div
                className="p-3.5 cursor-pointer transition-all duration-200 hover:opacity-90 flex items-center gap-2"
                style={{ background: "#CBA135", color: "#1a1a1a" }}
                onClick={() => navigate("/play-with-coach")}
                data-testid="play-btn"
              >
                <Swords className="w-4 h-4 flex-shrink-0" strokeWidth={1.5} />
                <span className="text-sm font-medium whitespace-nowrap">Play</span>
              </div>
            )}
          </div>
        </motion.div>

        {/* ── FOOTER ── */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}
          className="flex items-center justify-between text-gray-400 mt-8 pt-3" style={{ borderTop: "1px solid rgba(0,0,0,0.04)" }}>
          <span className="text-[10px]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{gamesAnalyzed} games</span>
          <span className="text-[10px]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{accuracy.toFixed(0)}% accuracy</span>
        </motion.div>
      </div>
    </Layout>
  );
};

export default HomePage;
