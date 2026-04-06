/**
 * LAB PAGE — Coach-first game review.
 *
 * NOT a game list. A coaching experience.
 *
 * 1. Root Problem — the one pattern costing you games
 * 2. Priority Game — the most painful example, one click to review
 * 3. Coach Insight — behavioral, not technical
 * 4. Rule — named, repeatable
 * 5. Training Lock — complete puzzles to unlock game list
 * 6. Game list — hidden behind the lock (or shown if unlocked)
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import {
  Import, ChevronRight, Check, Target, Zap, Eye,
  Brain, Lock, AlertTriangle, ArrowRight, FlaskConical
} from "lucide-react";

const Dashboard = ({ user }) => {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showGames, setShowGames] = useState(false);

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API}/lab-coach-pick`, { credentials: "include" });
      if (res.ok) setData(await res.json());
    } catch (err) {
      console.error("Error:", err);
    } finally {
      setLoading(false);
    }
  };

  const markReviewed = async (gameId) => {
    try {
      await fetch(`${API}/lab-mark-reviewed/${gameId}`, { method: "POST", credentials: "include" });
      fetchData();
    } catch (e) {}
  };

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center h-[60vh]">
          <div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
        </div>
      </Layout>
    );
  }

  const coaching = data?.coaching;
  const games = data?.games || [];
  const pick = data?.pick;
  const totalCount = data?.total_count || 0;
  const unreviewedGames = games.filter(g => !g.reviewed);
  const reviewedGames = games.filter(g => g.reviewed);
  const isUnlocked = !coaching?.training_lock || coaching.training_lock.unlocked;

  // Empty state
  if (games.length === 0) {
    return (
      <Layout user={user}>
        <div className="max-w-xl mx-auto px-4 py-20 text-center" data-testid="lab-page">
          <div className="w-16 h-16 rounded-2xl bg-muted/50 border border-border flex items-center justify-center mx-auto mb-6">
            <Import className="w-7 h-7 text-muted-foreground/40" strokeWidth={1.5} />
          </div>
          <h2 className="text-xl font-heading font-semibold text-foreground mb-2">No games yet</h2>
          <p className="text-sm text-muted-foreground max-w-sm mx-auto mb-8">
            Import your games from Chess.com or Lichess. Your coach will analyze them and tell you exactly what to work on.
          </p>
          <button onClick={() => navigate("/import")}
            className="px-6 py-3 text-sm font-semibold rounded-lg gradient-gold text-black shadow-lg shadow-amber-500/20 hover:opacity-90 transition-all"
            data-testid="lab-empty-import-btn">
            Import your games
          </button>
        </div>
      </Layout>
    );
  }

  return (
    <Layout user={user}>
      <div className="max-w-2xl mx-auto py-8 px-4 space-y-5" data-testid="lab-page">

        {/* ═══ 1. ROOT PROBLEM ═══ */}
        {coaching?.root_problem && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
            <div className="rounded-2xl border border-red-500/15 bg-red-500/[0.02] relative overflow-hidden">
              <div className="absolute top-0 right-0 w-48 h-48 rounded-full blur-3xl -translate-y-1/3 translate-x-1/3 bg-red-500/5" />
              <div className="relative p-6">
                <div className="flex items-center gap-2 mb-4">
                  <AlertTriangle className="w-4 h-4 text-red-400" strokeWidth={2} />
                  <p className="text-xs font-bold uppercase tracking-wider text-red-400">Your biggest leak</p>
                </div>

                <blockquote className="text-lg sm:text-xl font-heading text-foreground tracking-tight leading-snug mb-2">
                  {coaching.root_problem.message}
                </blockquote>

                <p className="text-sm text-muted-foreground leading-relaxed">
                  {coaching.root_problem.detail}
                </p>
              </div>
            </div>
          </motion.div>
        )}

        {/* ═══ 2. PRIORITY GAME ═══ */}
        {coaching?.priority_game && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
            <div
              className="bg-card border border-border rounded-xl cursor-pointer transition-all hover:border-primary/20 group"
              onClick={() => navigate(`/game/${coaching.priority_game.game_id}`)}
            >
              <div className="p-5">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Eye className="w-3.5 h-3.5 text-primary" strokeWidth={2} />
                    <p className="text-[10px] font-bold uppercase tracking-wider text-primary">Review this game</p>
                  </div>
                  <ChevronRight className="w-4 h-4 text-muted-foreground/20 group-hover:text-primary transition-colors" />
                </div>

                <div className="flex items-center gap-2 mb-2">
                  <span className="text-sm font-semibold text-foreground">vs {coaching.priority_game.opponent}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 font-bold rounded border ${
                    coaching.priority_game.result === "L" ? "bg-red-500/15 text-red-400 border-red-500/25"
                    : coaching.priority_game.result === "W" ? "bg-emerald-500/15 text-emerald-500 border-emerald-500/25"
                    : "bg-muted text-muted-foreground border-border"
                  }`}>{coaching.priority_game.result === "L" ? "LOST" : coaching.priority_game.result === "W" ? "WON" : "DRAW"}</span>
                  {coaching.priority_game.opening && (
                    <span className="text-xs text-muted-foreground/50">{coaching.priority_game.opening}</span>
                  )}
                </div>

                <p className="text-sm text-foreground/80 leading-relaxed">
                  {coaching.priority_game.description}
                </p>
              </div>
            </div>
          </motion.div>
        )}

        {/* ═══ 3. COACH INSIGHT ═══ */}
        {coaching?.insight && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}>
            <div className="px-1">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-amber-500/20 to-amber-600/10 flex items-center justify-center flex-shrink-0">
                  <Brain className="w-4 h-4 text-amber-500" />
                </div>
                <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Coach insight</p>
              </div>
              <p className="text-sm text-foreground leading-relaxed pl-11">
                {coaching.insight}
              </p>
            </div>
          </motion.div>
        )}

        {/* ═══ 4. RULE ═══ */}
        {coaching?.rule && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
            <div className="p-4 rounded-xl bg-amber-500/5 border border-amber-500/15">
              <p className="text-xs font-bold uppercase tracking-wider text-amber-600 dark:text-amber-400 mb-1.5">
                {coaching.rule.name}
              </p>
              <p className="text-sm text-foreground leading-relaxed">
                {coaching.rule.rule}
              </p>
            </div>
          </motion.div>
        )}

        {/* ═══ 5. TRAINING LOCK ═══ */}
        {coaching?.training_lock && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.12 }}>
            <div className={`rounded-xl border p-5 ${
              coaching.training_lock.unlocked
                ? "border-emerald-500/20 bg-emerald-500/[0.02]"
                : "border-border bg-card"
            }`}>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  {coaching.training_lock.unlocked
                    ? <Check className="w-4 h-4 text-emerald-500" strokeWidth={2.5} />
                    : <Lock className="w-4 h-4 text-muted-foreground" strokeWidth={2} />
                  }
                  <p className={`text-xs font-bold uppercase tracking-wider ${
                    coaching.training_lock.unlocked ? "text-emerald-500" : "text-muted-foreground"
                  }`}>
                    {coaching.training_lock.unlocked ? "Training complete" : "Training required"}
                  </p>
                </div>
                <span className="text-sm font-mono font-bold text-foreground">
                  {coaching.training_lock.progress} / {coaching.training_lock.target}
                </span>
              </div>

              {/* Progress bar */}
              <div className="w-full h-2 bg-muted rounded-full overflow-hidden mb-3">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    coaching.training_lock.unlocked ? "bg-emerald-500" : "gradient-gold"
                  }`}
                  style={{ width: `${(coaching.training_lock.progress / coaching.training_lock.target) * 100}%` }}
                />
              </div>

              {!coaching.training_lock.unlocked ? (
                <button
                  onClick={() => navigate(`/training?focus=${coaching.training_lock.pattern}`)}
                  className="w-full py-2.5 text-sm font-semibold rounded-lg gradient-gold text-black hover:opacity-90 transition-all flex items-center justify-center gap-2"
                >
                  <Target className="w-4 h-4" strokeWidth={2} />
                  Solve {coaching.training_lock.target - coaching.training_lock.progress} {coaching.training_lock.label} puzzles
                </button>
              ) : (
                <p className="text-xs text-emerald-500 text-center">
                  You've completed your training. Review your games below.
                </p>
              )}
            </div>
          </motion.div>
        )}

        {/* ═══ 6. GAME LIST (unlocked or no coaching) ═══ */}
        {(isUnlocked || !coaching) && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
            {/* Unreviewed */}
            {unreviewedGames.length > 0 && (
              <div className="mb-4">
                <p className="text-[10px] tracking-[0.15em] uppercase mb-2.5 font-bold text-muted-foreground/70">To Review</p>
                <div className="space-y-2">
                  {unreviewedGames.map((game) => (
                    <GameCard key={game.game_id} game={game} navigate={navigate} markReviewed={markReviewed} />
                  ))}
                </div>
              </div>
            )}

            {/* Reviewed */}
            {reviewedGames.length > 0 && (
              <div>
                <button
                  onClick={() => setShowGames(!showGames)}
                  className="flex items-center gap-2 text-[10px] tracking-[0.15em] uppercase font-bold text-muted-foreground/40 hover:text-muted-foreground transition-colors mb-2.5"
                >
                  <Check className="w-3 h-3" strokeWidth={2} />
                  Reviewed ({reviewedGames.length})
                  <ChevronRight className={`w-3 h-3 transition-transform ${showGames ? 'rotate-90' : ''}`} />
                </button>
                {showGames && (
                  <div className="space-y-2">
                    {reviewedGames.map((game) => (
                      <GameCard key={game.game_id} game={game} navigate={navigate} markReviewed={markReviewed} isReviewed />
                    ))}
                  </div>
                )}
              </div>
            )}
          </motion.div>
        )}

        {/* ═══ LOCKED STATE — game list blurred behind lock ═══ */}
        {!isUnlocked && coaching && unreviewedGames.length > 0 && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.18 }}>
            <div className="relative">
              <div className="blur-sm opacity-30 pointer-events-none select-none">
                <p className="text-[10px] tracking-[0.15em] uppercase mb-2.5 font-bold text-muted-foreground/70">
                  {unreviewedGames.length} games waiting
                </p>
                <div className="space-y-2">
                  {unreviewedGames.slice(0, 3).map((game) => (
                    <GameCard key={game.game_id} game={game} navigate={navigate} markReviewed={markReviewed} />
                  ))}
                </div>
              </div>
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="bg-card/90 backdrop-blur-sm border border-border rounded-lg px-5 py-3 flex items-center gap-2">
                  <Lock className="w-4 h-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground font-medium">Complete training to unlock</span>
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {/* Import button */}
        {totalCount > 0 && (
          <div className="text-center pt-4">
            <button
              onClick={() => navigate("/import")}
              className="text-xs text-muted-foreground/40 hover:text-muted-foreground transition-colors"
            >
              Import more games
            </button>
          </div>
        )}
      </div>
    </Layout>
  );
};


/* ── Game Card ── */
const GameCard = ({ game, navigate, markReviewed, isReviewed }) => (
  <div
    className={`bg-card border border-border rounded-xl cursor-pointer transition-all hover:border-primary/20 group ${isReviewed ? 'opacity-50' : ''}`}
    onClick={() => navigate(`/game/${game.game_id}`)}
    data-testid={`game-row-${game.game_id}`}
  >
    <div className="p-3.5 flex items-center gap-3">
      <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
        game.result === "W" ? "bg-emerald-500" : game.result === "L" ? "bg-red-400" : "bg-muted-foreground/40"
      }`} />

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-sm font-medium text-foreground">vs {game.opponent}</span>
          <span className={`text-[9px] px-1.5 py-0 font-bold rounded border ${
            game.result === "W" ? "bg-emerald-500/15 text-emerald-500 border-emerald-500/25"
            : game.result === "L" ? "bg-red-500/15 text-red-400 border-red-500/25"
            : "bg-muted text-muted-foreground border-border"
          }`}>{game.result === "W" ? "W" : game.result === "L" ? "L" : "D"}</span>
          {game.brilliant_moves > 0 && <Zap className="w-2.5 h-2.5 text-amber-400" strokeWidth={2.5} />}
          {game.termination_label && (
            <span className="text-[9px] text-muted-foreground/50">{game.termination_label}</span>
          )}
        </div>
        <p className="text-xs text-muted-foreground line-clamp-1">
          {game.behavior || game.lesson_label || game.opening || ""}
        </p>
      </div>

      {!isReviewed ? (
        <button
          onClick={(e) => { e.stopPropagation(); markReviewed(game.game_id); }}
          className="p-1 text-muted-foreground/20 hover:text-emerald-500 transition-colors opacity-0 group-hover:opacity-100 flex-shrink-0"
          title="Mark reviewed"
        >
          <Check className="w-3.5 h-3.5" strokeWidth={1.5} />
        </button>
      ) : (
        <Check className="w-3.5 h-3.5 text-emerald-500/40 flex-shrink-0" strokeWidth={2} />
      )}
    </div>
  </div>
);

export default Dashboard;
