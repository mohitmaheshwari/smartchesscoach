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
import { ChevronRight, Swords, Target, ArrowRight, Import } from "lucide-react";

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
          <div className="w-5 h-5 border border-border border-t-foreground/50 rounded-full animate-spin" />
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
          <h1 className="text-3xl text-foreground tracking-tight mb-3 font-heading">
            Welcome to ChessGuru
          </h1>
          <p className="text-muted-foreground mb-8 font-light">Import your games to get started. After 5 games, your coach will know your strengths. After 15, it'll know your weaknesses by name.</p>
          <div className="flex gap-3 justify-center">
            <button onClick={() => navigate("/import")} className="px-6 py-3 text-sm text-white rounded-sm" style={{ background: WINE }} data-testid="import-cta">
              <Import className="w-4 h-4 inline mr-2" strokeWidth={1.5} />
              Import Games
            </button>
            <button onClick={() => navigate("/play-with-coach")} className="px-6 py-3 text-sm text-foreground border border-border rounded-sm" data-testid="play-cta">
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
          <p className="text-sm text-muted-foreground font-light">{greeting}</p>
          {streak && streak.count >= 2 && (
            <span className="text-xs font-mono" style={{ color: streak.type === "W" ? "#16a34a" : streak.type === "L" ? WINE : undefined }}>
              {streak.count} {streak.type === "W" ? "wins" : streak.type === "L" ? "losses" : "draws"} in a row
            </span>
          )}
        </motion.div>

        {/* ── LAST BATTLE (compact) ── */}
        {battle && (
          <motion.div initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }} className="mb-6">
            <SectionLabel>Last Game</SectionLabel>
            <div
              className="bg-card border border-border cursor-pointer transition-all duration-200 hover:shadow-sm rounded-sm overflow-hidden"
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
                      <span className="text-sm text-muted-foreground font-light">vs {battle.opponent}</span>
                      <ResultBadge result={battle.result} userColor={battle.user_color} />
                    </div>
                    <p className="text-sm text-foreground leading-snug font-light">{dna?.root_cause || "Review this game"}</p>
                  </div>
                  <div className="flex items-center gap-1.5 mt-2">
                    <span className="text-[10px] text-muted-foreground font-mono">Move {battle.move_number}</span>
                    <span className="text-[10px] font-mono" style={{ color: WINE }}>{battle.your_move}</span>
                    <ArrowRight className="w-2.5 h-2.5 text-border" />
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
            <SectionLabel>Your Chess DNA</SectionLabel>
            <div className="bg-card border border-border rounded-sm">
              <div className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <h2 className="text-xl text-foreground tracking-tight font-heading">
                    {dna.archetype}
                  </h2>
                  <span className="text-[9px] tracking-[0.15em] uppercase px-1.5 py-0.5 border font-mono rounded-sm"
                    style={{ borderColor: `${WINE}40`, color: WINE }}>
                    {dna.diagnosis?.replace(/_/g, " ")}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground font-light">{dna.before_line}</p>
                <p className="text-xs text-foreground font-light mt-0.5">{dna.after_line}</p>
              </div>
            </div>
          </motion.div>
        )}

        {/* ── PATTERNS ACROSS GAMES ── */}
        {patterns.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }} className="mb-6">
            <SectionLabel>Patterns Across Games</SectionLabel>
            <div className="bg-card border border-border rounded-sm divide-y divide-border">
              {patterns.map((p) => (
                <div
                  key={p.pattern_type}
                  className="flex items-center justify-between px-4 py-3 cursor-pointer transition-colors hover:bg-muted/50"
                  onClick={() => navigate(`/training?focus=${p.pattern_type}`)}
                  data-testid={`pattern-${p.pattern_type}`}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-1.5 h-1.5 rounded-full" style={{ background: p.severity === "critical" ? WINE : "#CBA135" }} />
                    <span className="text-sm text-foreground font-light">{p.label}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground font-mono">{p.recent_count}x</span>
                    <span className="text-[9px] px-1.5 py-0.5 uppercase font-mono rounded-sm"
                      style={{
                        background: p.severity === "critical" ? `${WINE}10` : "#CBA13515",
                        color: p.severity === "critical" ? WINE : GOLD_TEXT,
                      }}>
                      {p.severity}
                    </span>
                    <ChevronRight className="w-3.5 h-3.5 text-muted-foreground/40" strokeWidth={1.5} />
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}

        {/* ── FIX THIS ONE THING ── */}
        {fix && (
          <motion.div initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="mb-6">
            <SectionLabel>If You Fixed One Thing</SectionLabel>
            <div
              className="bg-card border border-border rounded-sm cursor-pointer transition-all duration-200 hover:shadow-sm"
              onClick={() => navigate("/training?focus=calculation_depth")}
              data-testid="one-thing-to-fix"
            >
              <div className="p-4">
                <p className="text-xs text-muted-foreground font-light mb-1">{fix.stat_line}</p>
                <p className="text-sm text-foreground font-light font-heading">{fix.fix_line}</p>
                {fix.diff_line && (
                  <p className="text-base mt-1 font-heading text-emerald-600">{fix.diff_line}</p>
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
                className={`flex-1 p-3.5 cursor-pointer transition-all duration-200 hover:shadow-sm flex items-center gap-3 rounded-sm ${
                  action.type === "review_loss" ? "text-white" : "bg-card border border-border text-foreground"
                }`}
                style={action.type === "review_loss" ? { background: WINE } : undefined}
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
                className="p-3.5 cursor-pointer transition-all duration-200 hover:opacity-90 flex items-center gap-2 rounded-sm"
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
          className="flex items-center justify-between text-muted-foreground/60 mt-8 pt-3 border-t border-border">
          <span className="text-[10px] font-mono">{gamesAnalyzed} games</span>
          <span className="text-[10px] font-mono">{accuracy.toFixed(0)}% accuracy</span>
        </motion.div>
      </div>
    </Layout>
  );
};

// Reusable section label
const SectionLabel = ({ children }) => (
  <p className="text-[10px] tracking-[0.2em] uppercase mb-2 font-mono" style={{ color: GOLD_TEXT }}>
    {children}
  </p>
);

// Win/Loss badge
const ResultBadge = ({ result, userColor }) => {
  const won = (result === "1-0" && userColor === "white") || (result === "0-1" && userColor === "black");
  const draw = (result || "").includes("1/2");
  return (
    <span className="text-[10px] px-1.5 py-0.5 font-mono rounded-sm" style={{
      background: won ? "rgba(22,163,74,0.1)" : draw ? "rgba(0,0,0,0.05)" : `${WINE}15`,
      color: won ? "#16a34a" : draw ? "#888" : WINE,
    }}>
      {won ? "WON" : draw ? "DRAW" : "LOST"}
    </span>
  );
};

export default HomePage;
