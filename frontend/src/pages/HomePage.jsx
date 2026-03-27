/**
 * HOME PAGE — Reimagined
 * 
 * Not a dashboard. A mirror.
 * Shows: Your last battle, who you are, what to fix, what to do next.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import LichessBoard from "@/components/LichessBoard";
import { ChevronRight, Swords, Target, ArrowRight } from "lucide-react";

const WINE = "#722F37";
const GOLD = "#CBA135";

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
          <div className="w-5 h-5 border border-gray-700 border-t-white animate-spin" />
        </div>
      </Layout>
    );
  }

  const battle = data?.last_battle;
  const dna = data?.chess_dna;
  const fix = data?.one_thing_to_fix;
  const action = data?.context_action;
  const accuracy = data?.accuracy || 0;
  const gamesAnalyzed = data?.games_analyzed || 0;

  // Greeting
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  return (
    <Layout user={user}>
      <div className="max-w-2xl mx-auto px-4 py-6" data-testid="home-page">

        {/* ── GREETING ── */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mb-8">
          <p className="text-sm text-gray-600 font-light">{greeting}</p>
        </motion.div>

        {/* ── LAST BATTLE: The Board ── */}
        {battle && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="mb-8"
          >
            <p className="text-[10px] tracking-[0.2em] uppercase mb-3" style={{ color: GOLD, fontFamily: "'JetBrains Mono', monospace" }}>
              Your Last Battle
            </p>
            <div
              className="cursor-pointer transition-all duration-200 hover:border-white/10"
              style={{ background: "#0a0a0a", border: "1px solid rgba(255,255,255,0.05)" }}
              onClick={() => navigate(`/game/${battle.game_id}`)}
              data-testid="last-battle-card"
            >
              <div className="flex">
                {/* Board */}
                <div className="w-[220px] h-[220px] flex-shrink-0">
                  <LichessBoard
                    fen={battle.fen}
                    orientation={battle.user_color}
                    viewOnly={true}
                    arrows={battle.best_move ? [] : []}
                    lastMove={null}
                  />
                </div>
                {/* Info */}
                <div className="flex-1 p-5 flex flex-col justify-between min-w-0">
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-sm text-gray-400 font-light">vs {battle.opponent}</span>
                      <span className="text-xs px-2 py-0.5" style={{
                        background: battle.result === "1-0" && battle.user_color === "white" || battle.result === "0-1" && battle.user_color === "black"
                          ? "rgba(39,111,75,0.3)" : "rgba(114,47,55,0.3)",
                        color: battle.result === "1-0" && battle.user_color === "white" || battle.result === "0-1" && battle.user_color === "black"
                          ? "#4ade80" : "#f87171",
                        fontFamily: "'JetBrains Mono', monospace",
                      }}>
                        {battle.result === "1-0" && battle.user_color === "white" || battle.result === "0-1" && battle.user_color === "black" ? "WON" : "LOST"}
                      </span>
                    </div>
                    <p className="text-white text-base leading-relaxed font-light" style={{ fontFamily: "'Cormorant Garamond', serif" }}>
                      {dna?.root_cause || "Review this game"}
                    </p>
                  </div>
                  <div className="flex items-center gap-3 mt-3">
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs text-gray-600" style={{ fontFamily: "'JetBrains Mono', monospace" }}>Move {battle.move_number}</span>
                      <span className="text-xs font-mono text-red-400">{battle.your_move}</span>
                      <ArrowRight className="w-3 h-3 text-gray-700" />
                      <span className="text-xs font-mono text-emerald-400">{battle.best_move}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {/* ── CHESS DNA: Identity Card ── */}
        {dna && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="mb-8"
          >
            <p className="text-[10px] tracking-[0.2em] uppercase mb-3" style={{ color: GOLD, fontFamily: "'JetBrains Mono', monospace" }}>
              Your Chess DNA
            </p>
            <div style={{ background: "#0a0a0a", border: "1px solid rgba(255,255,255,0.05)" }}>
              <div className="p-5">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-2xl text-white tracking-tight" style={{ fontFamily: "'Cormorant Garamond', serif" }}>
                    {dna.archetype}
                  </h2>
                  <span className="text-[10px] tracking-[0.15em] uppercase px-2 py-1" style={{
                    border: `1px solid rgba(114,47,55,0.4)`,
                    color: WINE,
                    fontFamily: "'JetBrains Mono', monospace"
                  }}>
                    {dna.diagnosis?.replace(/_/g, " ")}
                  </span>
                </div>
                <div className="space-y-2">
                  <p className="text-sm text-gray-500 font-light">{dna.before_line}</p>
                  <p className="text-sm text-white font-light">{dna.after_line}</p>
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {/* ── ONE THING TO FIX ── */}
        {fix && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="mb-8"
          >
            <p className="text-[10px] tracking-[0.2em] uppercase mb-3" style={{ color: GOLD, fontFamily: "'JetBrains Mono', monospace" }}>
              Fix This One Thing
            </p>
            <div
              className="cursor-pointer transition-all duration-200 hover:border-white/10"
              style={{ background: "#0a0a0a", border: "1px solid rgba(255,255,255,0.05)" }}
              onClick={() => navigate("/training?focus=calculation_depth")}
              data-testid="one-thing-to-fix"
            >
              <div className="p-5 space-y-3">
                <p className="text-sm text-gray-400 font-light">{fix.stat_line}</p>
                <p className="text-base text-white font-light" style={{ fontFamily: "'Cormorant Garamond', serif" }}>
                  {fix.fix_line}
                </p>
                {fix.diff_line && (
                  <p className="text-lg font-light" style={{ color: "#4ade80", fontFamily: "'Cormorant Garamond', serif" }}>
                    {fix.diff_line}
                  </p>
                )}
                <div className="flex items-center justify-between pt-2" style={{ borderTop: "1px solid rgba(255,255,255,0.03)" }}>
                  <span className="text-xs px-2 py-0.5" style={{
                    background: fix.severity === "CRITICAL" ? "rgba(114,47,55,0.2)" : "rgba(203,161,53,0.15)",
                    color: fix.severity === "CRITICAL" ? WINE : GOLD,
                    fontFamily: "'JetBrains Mono', monospace"
                  }}>
                    {fix.severity}
                  </span>
                  <span className="text-xs text-gray-600 flex items-center gap-1">
                    Train this <ChevronRight className="w-3 h-3" />
                  </span>
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {/* ── CONTEXTUAL ACTION ── */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="mb-6"
        >
          <div className="flex gap-3">
            {/* Primary action */}
            {action && (
              <div
                className="flex-1 p-4 cursor-pointer transition-all duration-200 hover:opacity-90 flex items-center gap-3"
                style={{ background: action.type === "review_loss" ? WINE : "#0a0a0a", border: action.type === "review_loss" ? "none" : `1px solid rgba(255,255,255,0.05)` }}
                onClick={() => navigate(action.href)}
                data-testid="context-action"
              >
                {action.type === "review_loss" ? (
                  <Target className="w-5 h-5 text-white/70 flex-shrink-0" strokeWidth={1.5} />
                ) : (
                  <Swords className="w-5 h-5 text-gray-500 flex-shrink-0" strokeWidth={1.5} />
                )}
                <div className="flex-1">
                  <p className="text-sm text-white font-light">{action.label}</p>
                </div>
                <ChevronRight className="w-4 h-4 text-white/40 flex-shrink-0" strokeWidth={1.5} />
              </div>
            )}
            {/* Play */}
            {action?.type !== "play" && (
              <div
                className="p-4 cursor-pointer transition-all duration-200 hover:opacity-90 flex items-center gap-3"
                style={{ background: GOLD, color: "#050505" }}
                onClick={() => navigate("/play-with-coach")}
                data-testid="play-btn"
              >
                <Swords className="w-5 h-5 flex-shrink-0" strokeWidth={1.5} />
                <span className="text-sm font-medium whitespace-nowrap">Play</span>
              </div>
            )}
          </div>
        </motion.div>

        {/* ── FOOTER ── */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }}
          className="flex items-center justify-between text-gray-700 mt-10 pt-4" style={{ borderTop: "1px solid rgba(255,255,255,0.03)" }}>
          <span className="text-xs" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{gamesAnalyzed} games</span>
          <span className="text-xs" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{accuracy.toFixed(0)}% accuracy</span>
        </motion.div>
      </div>
    </Layout>
  );
};

export default HomePage;
