/**
 * LAB — "Let me show you the exact moment you keep losing."
 *
 * ONE problem. ONE board. ONE question.
 * Below: tabs to browse your games (imported vs with Coach).
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import LichessBoard from "@/components/LichessBoard";
import {
  Import, ChevronRight, Eye, Swords, Target
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

const PATTERN_MAP = {
  threw_winning: "calculation_depth",
  tactical_miss: "tactical_oversight",
  one_move_blunder: "piece_safety",
  calculation_error: "calculation_depth",
  time_collapse: "calculation_depth",
  opening_disaster: "piece_safety",
  endgame_collapse: "endgame_technique",
};

const resultWord = (g) => {
  const r = String(g.result || "").toLowerCase().trim();
  if (r === "win" || r === "w") return "Won";
  if (r === "loss" || r === "l") return "Lost";
  if (r === "draw" || r === "d" || r === "1/2-1/2" || r === "½-½") return "Drew";
  const color = String(g.user_color || "").toLowerCase();
  if (r === "1-0") return color === "white" ? "Won" : "Lost";
  if (r === "0-1") return color === "black" ? "Won" : "Lost";
  return r ? r.charAt(0).toUpperCase() + r.slice(1) : "—";
};

const fmtDate = (g) => {
  const d = g.analyzed_at || g.created_at || g.date;
  if (!d) return "";
  const ts = new Date(d);
  const diffH = (Date.now() - ts.getTime()) / 3600000;
  if (diffH < 1) return `${Math.floor(diffH * 60)}m ago`;
  if (diffH < 24) return `${Math.floor(diffH)}h ago`;
  const days = Math.floor(diffH / 24);
  if (days < 7) return `${days}d ago`;
  return ts.toLocaleDateString();
};

const Dashboard = ({ user }) => {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expandedGameId, setExpandedGameId] = useState(null);

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API}/lab-coach-pick`, { credentials: "include" });
      if (res.ok) setData(await res.json());
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
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
  const priorityGame = coaching?.priority_game;
  const primaryProblem = topProblems[0] || null;
  const primaryGames = primaryProblem ? (groupedGames[primaryProblem.category]?.games || []) : [];
  const unreviewed = primaryGames.filter(g => !g.reviewed);

  let featuredGame = null;
  try {
    if (priorityGame) {
      featuredGame = {
        ...priorityGame,
        critical_fen: priorityGame.critical_fen || priorityGame.replay?.mistake_fen || null,
        critical_move: priorityGame.critical_move || priorityGame.move_number || null,
      };
    }
    if (!featuredGame?.critical_fen && unreviewed.length > 0) {
      featuredGame = unreviewed[0];
    }
    if (featuredGame?.critical_fen && featuredGame.critical_fen.split(" ").length < 2) {
      featuredGame.critical_fen = null;
    }
  } catch (e) {
    featuredGame = null;
  }

  // Games tagged with the primary issue (excluding the featured one at top)
  const sortByDate = (a, b) => {
    const da = new Date(a.analyzed_at || a.created_at || a.date || 0).getTime();
    const db = new Date(b.analyzed_at || b.created_at || b.date || 0).getTime();
    return db - da;
  };
  const issueGames = [...primaryGames]
    .filter(g => g.game_id !== featuredGame?.game_id)
    .sort(sortByDate);

  const GameRow = ({ g }) => {
    const isExpanded = expandedGameId === g.game_id;
    return (
      <div className="rounded-xl overflow-hidden border border-border/40">
        <div
          onClick={() => setExpandedGameId(isExpanded ? null : g.game_id)}
          className="flex items-center justify-between p-3 hover:bg-muted/40 cursor-pointer transition-all group"
        >
          <div className="flex items-center gap-3 min-w-0">
            <Swords className="w-3.5 h-3.5 flex-shrink-0 text-muted-foreground/60" strokeWidth={2} />
            <div className="min-w-0 flex-1">
              <div className="text-sm text-foreground truncate">
                {resultWord(g)}
                {g.platform === "coach"
                  ? " vs Coach"
                  : g.opponent && g.opponent !== "Opponent"
                  ? ` vs ${g.opponent}`
                  : ""}
                {g.opening ? (
                  <span className="text-[10px] text-muted-foreground/40 ml-2">{g.opening}</span>
                ) : null}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <span className="text-[10px] text-muted-foreground/50">{fmtDate(g)}</span>
            <ChevronRight
              className={`w-3.5 h-3.5 text-muted-foreground/30 group-hover:text-primary transition-all ${isExpanded ? "rotate-90" : ""}`}
            />
          </div>
        </div>

        {isExpanded && (
          <div className="px-3 pb-3 pt-1 bg-muted/20 border-t border-muted/30">
            {g.coach_take && (
              <p className="text-xs text-foreground/80 italic mb-2">{g.coach_take}</p>
            )}
            {g.critical_move && (
              <p className="text-[11px] text-muted-foreground/60 mb-2">
                Critical moment: move {g.critical_move}
                {g.critical_best ? ` — best was ${g.critical_best}` : ""}
              </p>
            )}
            <button
              onClick={(e) => { e.stopPropagation(); navigate(`/game/${g.game_id}`); }}
              className="text-xs font-medium px-3 py-1.5 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition"
            >
              Review game
            </button>
          </div>
        )}
      </div>
    );
  };

  return (
    <Layout user={user}>
      <div className="max-w-lg mx-auto px-4 py-8" data-testid="lab-page">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">

          {/* THE PROBLEM */}
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

          {/* THE MOMENT — board + context */}
          {featuredGame && featuredGame.critical_fen && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="rounded-2xl border border-border bg-card overflow-hidden"
            >
              <div className="px-4 pt-4 pb-2 flex items-center justify-between">
                <p className="text-[10px] uppercase tracking-widest font-bold text-red-400/60">
                  The moment that decided it
                </p>
                {featuredGame.is_new && (
                  <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/15">New</span>
                )}
              </div>
              <p className="px-4 text-sm text-foreground">
                vs {featuredGame.opponent} — {featuredGame.opening || "Unknown opening"}
              </p>

              <div className="px-4 pt-3">
                <div className="rounded-lg overflow-hidden border border-border">
                  <LichessBoard fen={featuredGame.critical_fen} viewOnly={true} width={400} />
                </div>
              </div>

              <div className="p-4">
                <p className="text-sm text-foreground mb-3">
                  <span className="font-mono text-red-400">Move {featuredGame.critical_move || featuredGame.move_number}</span>
                  {featuredGame.was_winning && <span className="text-muted-foreground"> — you were winning.</span>}
                </p>

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

          {/* OTHER GAMES WITH THIS SAME ISSUE */}
          {issueGames.length > 0 && (
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.18 }}>
              <p className="text-[10px] uppercase tracking-widest font-bold text-muted-foreground/40 mb-2">
                Other games with this pattern
              </p>
              <div className="space-y-1.5">
                {issueGames.slice(0, 5).map(g => <GameRow key={g.game_id} g={g} />)}
              </div>
            </motion.div>
          )}

          {/* See all games link */}
          <button
            onClick={() => navigate("/games")}
            className="w-full flex items-center justify-center gap-1 text-xs text-muted-foreground hover:text-foreground transition py-2"
          >
            See all games
            <ChevronRight className="w-3 h-3" strokeWidth={2} />
          </button>

          {/* ACTIONS */}
          <div className="space-y-2 pt-2">
            {primaryProblem && (
              <button
                onClick={() => {
                  const pattern = PATTERN_MAP[primaryProblem.category] || primaryProblem.category;
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
