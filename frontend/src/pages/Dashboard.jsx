/**
 * LAB — "Let me show you the exact moment you keep losing."
 *
 * ONE problem. ONE board. ONE question.
 * Not a dashboard. Not a list. A teaching moment.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import LichessBoard from "@/components/LichessBoard";
import {
  Import, ChevronRight, Check, Zap, Trophy, Shield, Eye, Swords
} from "lucide-react";

const BEHAVIOR_DESCRIPTIONS = {
  threw_winning: "You stop paying attention once you're ahead. The game slips away.",
  tactical_miss: "You're missing tactics that are right in front of you.",
  one_move_blunder: "You're moving without checking if your pieces are safe.",
  calculation_error: "You stop thinking too early. One move deeper would save you.",
  time_collapse: "You run out of time and panic. The mistakes come from rushing.",
  opening_disaster: "Your games go wrong in the first 10 moves.",
  endgame_collapse: "You reach winning endgames but can't finish them.",
  positional: "Your opponent outplays you in small ways. The position gradually slips.",
};

const Dashboard = ({ user }) => {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API}/lab-coach-pick`, { credentials: "include" });
      if (res.ok) setData(await res.json());
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const markReviewed = async (gameId) => {
    try {
      await fetch(`${API}/lab-mark-reviewed/${gameId}`, { method: "POST", credentials: "include" });
      fetchData();
    } catch (e) {}
  };

  if (loading) {
    return <Layout user={user}><div className="flex items-center justify-center h-[60vh]"><div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin" /></div></Layout>;
  }

  const coaching = data?.coaching;
  const games = data?.games || [];

  if (games.length === 0) {
    return (
      <Layout user={user}>
        <div className="max-w-md mx-auto px-6 py-20 text-center" data-testid="lab-page">
          <div className="w-16 h-16 rounded-2xl bg-muted/50 border border-border flex items-center justify-center mx-auto mb-6">
            <Import className="w-7 h-7 text-muted-foreground/40" strokeWidth={1.5} />
          </div>
          <h2 className="text-xl font-heading font-semibold text-foreground mb-2">No games yet</h2>
          <p className="text-sm text-muted-foreground max-w-sm mx-auto mb-8">Import your games or play with the coach.</p>
          <div className="space-y-3">
            <button onClick={() => navigate("/play-with-coach")} className="w-full px-6 py-3 text-sm font-semibold rounded-xl gradient-gold text-black shadow-lg shadow-amber-500/20 hover:opacity-90 transition-all flex items-center justify-center gap-2">
              <Swords className="w-4 h-4" />Play with Coach
            </button>
            <button onClick={() => navigate("/import")} className="w-full px-6 py-3 text-sm border border-border text-foreground rounded-xl hover:bg-muted/50 transition-all">
              Import your games
            </button>
          </div>
        </div>
      </Layout>
    );
  }

  const topProblems = coaching?.top_problems || [];
  const groupedGames = coaching?.grouped_games || {};
  const strengths = coaching?.strengths || [];
  const priorityGame = coaching?.priority_game;

  // The ONE problem to focus on
  const primaryProblem = topProblems[0];
  const primaryGames = primaryProblem ? (groupedGames[primaryProblem.category]?.games || []) : [];
  const unreviewed = primaryGames.filter(g => !g.reviewed);

  // The ONE game to show with a board — priority game or first unreviewed
  // Normalize field names (priority_game uses replay.mistake_fen, grouped uses critical_fen)
  let featuredGame = null;
  if (priorityGame) {
    featuredGame = {
      ...priorityGame,
      critical_fen: priorityGame.critical_fen || priorityGame.replay?.mistake_fen,
      critical_move: priorityGame.critical_move || priorityGame.move_number,
    };
  }
  if (!featuredGame?.critical_fen && unreviewed[0]) {
    featuredGame = unreviewed[0];
  }

  return (
    <Layout user={user}>
      <div className="max-w-lg mx-auto px-4 py-8" data-testid="lab-page">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">

          {/* ═══ THE PROBLEM ═══ */}
          {primaryProblem && (
            <div>
              <p className="text-[10px] uppercase tracking-widest font-bold text-muted-foreground/40 mb-2">
                Your biggest issue right now
              </p>
              <h1 className="text-xl font-heading font-semibold text-foreground leading-snug mb-2">
                {BEHAVIOR_DESCRIPTIONS[primaryProblem.category] || primaryProblem.label}
              </h1>
              <p className="text-sm text-muted-foreground">
                {primaryProblem.count >= 8
                  ? "This is happening in almost every game."
                  : `This happened in ${primaryProblem.count} of your recent games.`
                }
              </p>
            </div>
          )}

          {/* ═══ THE MOMENT — board + context ═══ */}
          {featuredGame && featuredGame.critical_fen && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="rounded-2xl border border-border bg-card overflow-hidden"
            >
              <div className="px-4 pt-4 pb-2">
                <div className="flex items-center justify-between mb-1">
                  <p className="text-[10px] uppercase tracking-widest font-bold text-red-400/60">
                    The moment that decided it
                  </p>
                  {featuredGame.is_new && (
                    <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/15">New</span>
                  )}
                </div>
                <p className="text-sm text-foreground">
                  vs {featuredGame.opponent} — {featuredGame.opening || "Unknown opening"}
                </p>
              </div>

              {/* Chess board showing the critical position */}
              <div className="px-4">
                <div className="rounded-lg overflow-hidden border border-border">
                  <LichessBoard
                    fen={featuredGame.critical_fen}
                    viewOnly={true}
                    width={400}
                  />
                </div>
              </div>

              <div className="p-4">
                <p className="text-sm text-foreground mb-1">
                  <span className="font-mono text-red-400">Move {featuredGame.critical_move || featuredGame.move_number}</span>
                  {featuredGame.was_winning && <span className="text-muted-foreground"> — you were winning.</span>}
                </p>

                {featuredGame.behavior && (
                  <p className="text-xs text-muted-foreground leading-relaxed mb-3">
                    {featuredGame.behavior}
                  </p>
                )}

                <button
                  onClick={() => navigate(`/game/${featuredGame.game_id}${featuredGame.critical_move ? `?move=${featuredGame.critical_move}` : ""}`)}
                  className="w-full py-3 text-sm font-semibold rounded-xl bg-foreground text-background hover:opacity-90 transition-all flex items-center justify-center gap-2"
                >
                  <Eye className="w-4 h-4" strokeWidth={2} />
                  What should I have done?
                </button>
              </div>
            </motion.div>
          )}

          {/* ═══ OTHER GAMES WITH SAME ISSUE ═══ */}
          {unreviewed.length > 1 && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.15 }}
            >
              <p className="text-[10px] uppercase tracking-widest font-bold text-muted-foreground/40 mb-2">
                Same issue in other games
              </p>
              <div className="space-y-1">
                {unreviewed.filter(g => g.game_id !== featuredGame?.game_id).slice(0, 5).map(g => (
                  <div
                    key={g.game_id}
                    onClick={() => navigate(`/game/${g.game_id}${g.critical_move ? `?move=${g.critical_move}` : ""}`)}
                    className="flex items-center justify-between p-3 rounded-xl hover:bg-muted/50 cursor-pointer transition-all group"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-2 h-2 rounded-full bg-red-400 flex-shrink-0" />
                      <span className="text-sm text-foreground">vs {g.opponent}</span>
                      {g.critical_move && (
                        <span className="text-xs font-mono text-muted-foreground/50">move {g.critical_move}</span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-muted-foreground/40">{g.opening}</span>
                      <ChevronRight className="w-3.5 h-3.5 text-muted-foreground/20 group-hover:text-primary transition-colors" />
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>
          )}

          {/* ═══ REVIEWED GAMES ═══ */}
          {primaryGames.filter(g => g.reviewed).length > 0 && (
            <div>
              <p className="text-[10px] uppercase tracking-widest font-bold text-muted-foreground/20 mb-2">
                Reviewed
              </p>
              <div className="space-y-1 opacity-40">
                {primaryGames.filter(g => g.reviewed).slice(0, 3).map(g => (
                  <div key={g.game_id} className="flex items-center gap-3 p-2 rounded-lg">
                    <Check className="w-3.5 h-3.5 text-emerald-500/50" strokeWidth={2} />
                    <span className="text-xs text-muted-foreground">vs {g.opponent}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ═══ STRENGTHS (compact) ═══ */}
          {strengths.length > 0 && (
            <div className="pt-2">
              <p className="text-[10px] uppercase tracking-widest font-bold text-emerald-500/40 mb-2">What you do well</p>
              <div className="space-y-1.5">
                {strengths.slice(0, 2).map((s, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Zap className="w-3 h-3 text-emerald-500/40 flex-shrink-0" strokeWidth={2} />
                    <span>{s.description}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ═══ ACTIONS ═══ */}
          <div className="space-y-2 pt-2">
            {/* Train this weakness — links to puzzle training */}
            {primaryProblem && (
              <button
                onClick={() => {
                  const patternMap = {
                    threw_winning: "calculation_depth",
                    tactical_miss: "tactical_oversight",
                    one_move_blunder: "piece_safety",
                    calculation_error: "calculation_depth",
                    time_collapse: "calculation_depth",
                    opening_disaster: "piece_safety",
                    endgame_collapse: "endgame_technique",
                  };
                  const pattern = patternMap[primaryProblem.category] || primaryProblem.category;
                  navigate(`/training/prescribed?weakness=${pattern}`);
                }}
                className="w-full flex items-center gap-3 p-3 rounded-xl border-2 border-primary/20 bg-primary/[0.03] hover:bg-primary/[0.06] transition-all"
              >
                <Target className="w-4 h-4 text-primary" strokeWidth={2} />
                <div className="text-left">
                  <p className="text-sm font-medium text-foreground">Practice this weakness</p>
                  <p className="text-[10px] text-muted-foreground">Solve positions from your games — 3 min</p>
                </div>
                <ChevronRight className="w-4 h-4 text-muted-foreground/30 ml-auto" />
              </button>
            )}

            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => navigate("/play-with-coach")}
                className="flex items-center gap-2 p-3 rounded-xl border border-border bg-card hover:bg-muted/50 transition-all"
              >
                <Swords className="w-4 h-4 text-primary" strokeWidth={2} />
                <span className="text-sm text-foreground">Play</span>
              </button>
              <button
                onClick={() => navigate("/import")}
                className="flex items-center gap-2 p-3 rounded-xl border border-border bg-card hover:bg-muted/50 transition-all"
              >
                <Import className="w-4 h-4 text-muted-foreground" strokeWidth={2} />
                <span className="text-sm text-foreground">Import</span>
              </button>
            </div>
          </div>

          {/* No coaching data fallback */}
          {topProblems.length === 0 && (
            <div className="text-center py-8">
              <p className="text-sm text-muted-foreground mb-4">Your coach is still analyzing your games.</p>
            </div>
          )}

        </motion.div>
      </div>
    </Layout>
  );
};

export default Dashboard;
