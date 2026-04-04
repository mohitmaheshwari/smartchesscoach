/**
 * LAB PAGE — Your Analyzed Games
 *
 * Coach picks the most important game to review.
 * Each game shows what happened, what went wrong (or right), and why.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Import, ChevronRight, Check, TrendingDown, TrendingUp, Minus, Target, Sparkles, Zap, Eye } from "lucide-react";

const Dashboard = ({ user }) => {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showReviewed, setShowReviewed] = useState(false);

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

  const pick = data?.pick;
  const pickReason = data?.pick_reason;
  const pickPattern = data?.pick_pattern;
  const verdict = data?.verdict;
  const games = data?.games || [];
  const reviewedCount = data?.reviewed_count || 0;
  const totalCount = data?.total_count || 0;
  const unreviewedGames = games.filter(g => !g.reviewed);
  const reviewedGames = games.filter(g => g.reviewed);

  return (
    <Layout user={user}>
      <div className="max-w-3xl mx-auto py-8 px-4" data-testid="lab-page">

        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-heading text-foreground tracking-tight" data-testid="lab-heading">Your Games</h1>
            {totalCount > 0 && (
              <p className="text-sm text-muted-foreground mt-1">
                {reviewedCount} of {totalCount} reviewed
              </p>
            )}
          </div>
          <button
            onClick={() => navigate("/import")}
            className="flex items-center gap-2 px-4 py-2.5 text-sm border border-border text-foreground hover:bg-card hover:border-primary/30 transition-all rounded-lg font-medium"
            data-testid="lab-import-btn"
          >
            <Import className="w-4 h-4" strokeWidth={1.5} />
            Import
          </button>
        </div>

        {/* ── REVIEW PROGRESS BAR ── */}
        {totalCount > 0 && (
          <div className="mb-6">
            <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full gradient-gold rounded-full transition-all duration-500"
                style={{ width: `${(reviewedCount / totalCount) * 100}%` }}
              />
            </div>
          </div>
        )}

        {/* ── VERDICT STRIP ── */}
        {verdict && verdict.total > 0 && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mb-6">
            <div className="bg-card border border-border rounded-xl p-4 flex items-center gap-4">
              <div className="flex items-center gap-2 font-mono text-base font-bold">
                <span className="text-emerald-500">{verdict.wins}W</span>
                <span className="text-muted-foreground/30">/</span>
                <span className="text-red-400">{verdict.losses}L</span>
              </div>
              <p className="text-sm text-muted-foreground flex-1 leading-relaxed">{verdict.insight}</p>
              {verdict.losses > verdict.wins ? (
                <TrendingDown className="w-4 h-4 text-red-400 flex-shrink-0" />
              ) : verdict.wins > verdict.losses ? (
                <TrendingUp className="w-4 h-4 text-emerald-500 flex-shrink-0" />
              ) : (
                <Minus className="w-4 h-4 text-muted-foreground flex-shrink-0" />
              )}
            </div>
          </motion.div>
        )}

        {/* ── COACH'S PICK ── */}
        {pick && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }} className="mb-6">
            <div className="flex items-center gap-2 mb-2.5">
              <Sparkles className="w-3.5 h-3.5 text-primary" strokeWidth={2} />
              <p className="text-[10px] tracking-[0.15em] uppercase font-bold text-primary">
                Start here
              </p>
            </div>
            <div
              className="bg-card border-2 border-primary/25 rounded-xl cursor-pointer transition-all duration-300 hover:border-primary/50 group glow-gold relative overflow-hidden"
              onClick={() => navigate(`/game/${pick.game_id}`)}
              data-testid="coach-pick-card"
            >
              <div className="absolute top-0 right-0 w-40 h-40 bg-primary/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />
              <div className="relative p-5">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-3">
                    <AccuracyBar accuracy={pick.accuracy} />
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-base font-semibold text-foreground">vs {pick.opponent}</span>
                        <ResultBadge result={pick.result} />
                        {pick.brilliant_moves > 0 && <BrilliantBadge count={pick.brilliant_moves} />}
                      </div>
                      {pick.opening && <span className="text-xs text-muted-foreground">{pick.opening}</span>}
                    </div>
                  </div>
                  <ChevronRight className="w-5 h-5 text-muted-foreground/30 group-hover:text-primary transition-colors" strokeWidth={1.5} />
                </div>

                {pick.lesson_label && (
                  <span className="inline-block text-[10px] font-bold uppercase tracking-[0.12em] px-2 py-0.5 rounded-md bg-primary/10 text-primary border border-primary/20 mb-2">
                    {pick.lesson_label}
                  </span>
                )}

                <p className="text-sm leading-relaxed text-foreground/80" data-testid="coach-pick-reason">{pickReason}</p>

                {pickPattern && (
                  <button
                    className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-primary hover:text-primary/80 transition-colors bg-primary/5 px-3 py-1.5 rounded-lg"
                    onClick={(e) => { e.stopPropagation(); navigate(`/training/pattern/${pickPattern}`); }}
                    data-testid="train-pattern-btn"
                  >
                    <Target className="w-3 h-3" />
                    Practice {pickPattern.replace(/_/g, " ")} puzzles
                  </button>
                )}
              </div>
            </div>
          </motion.div>
        )}

        {/* ── UNREVIEWED GAMES ── */}
        {unreviewedGames.length > (pick ? 1 : 0) && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
            <p className="text-[10px] tracking-[0.15em] uppercase mb-2.5 font-bold text-muted-foreground/70">
              To Review
            </p>
            <div className="space-y-2">
              {unreviewedGames.filter(g => g.game_id !== pick?.game_id).map((game) => (
                <GameCard key={game.game_id} game={game} navigate={navigate} markReviewed={markReviewed} />
              ))}
            </div>
          </motion.div>
        )}

        {/* ── REVIEWED GAMES ── */}
        {reviewedGames.length > 0 && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.15 }} className="mt-8">
            <button
              onClick={() => setShowReviewed(!showReviewed)}
              className="flex items-center gap-2 text-[10px] tracking-[0.15em] uppercase font-bold text-muted-foreground/40 hover:text-muted-foreground transition-colors mb-2.5"
            >
              <Check className="w-3 h-3" strokeWidth={2} />
              Reviewed ({reviewedGames.length})
              <ChevronRight className={`w-3 h-3 transition-transform ${showReviewed ? 'rotate-90' : ''}`} />
            </button>
            {showReviewed && (
              <div className="space-y-2">
                {reviewedGames.map((game) => (
                  <GameCard key={game.game_id} game={game} navigate={navigate} markReviewed={markReviewed} isReviewed />
                ))}
              </div>
            )}
          </motion.div>
        )}

        {/* Empty state */}
        {games.length === 0 && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="text-center py-20" data-testid="lab-empty-state">
            <div className="w-16 h-16 rounded-2xl bg-muted/50 border border-border flex items-center justify-center mx-auto mb-6">
              <Import className="w-7 h-7 text-muted-foreground/40" strokeWidth={1.5} />
            </div>
            <h2 className="text-xl font-heading font-semibold text-foreground mb-2">No games yet</h2>
            <p className="text-sm text-muted-foreground max-w-sm mx-auto mb-8 leading-relaxed">
              Import your games from Chess.com or Lichess. Your coach will analyze them and tell you exactly what to work on.
            </p>
            <button
              onClick={() => navigate("/import")}
              className="px-6 py-3 text-sm font-semibold rounded-lg gradient-gold text-black shadow-lg shadow-amber-500/20 hover:shadow-amber-500/30 hover:opacity-90 transition-all"
              data-testid="lab-empty-import-btn"
            >
              Import your games
            </button>
          </motion.div>
        )}
      </div>
    </Layout>
  );
};

/* ── Game Card — richer layout with accuracy bar, badges, behavioral insight ── */
const GameCard = ({ game, navigate, markReviewed, isReviewed }) => (
  <div
    className={`bg-card border border-border rounded-xl cursor-pointer transition-all hover:border-primary/20 group ${isReviewed ? 'opacity-60 hover:opacity-80' : ''}`}
    onClick={() => navigate(`/game/${game.game_id}`)}
    data-testid={`game-row-${game.game_id}`}
  >
    <div className="p-4 flex items-start gap-3.5">
      {/* Accuracy bar */}
      <AccuracyBar accuracy={game.accuracy} />

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1 flex-wrap">
          <span className="text-sm font-semibold text-foreground">vs {game.opponent}</span>
          <ResultBadge result={game.result} small />
          {game.brilliant_moves > 0 && <BrilliantBadge count={game.brilliant_moves} />}
          {game.opening && (
            <span className="text-xs text-muted-foreground/50 hidden sm:inline">{game.opening}</span>
          )}
        </div>

        {/* Coach's game story */}
        <div className="mt-0.5">
          {game.lesson_label && (
            <span className="text-[9px] font-bold uppercase tracking-[0.1em] text-primary mr-1.5">{game.lesson_label}</span>
          )}
          <span className="text-xs text-muted-foreground leading-relaxed">
            {game.behavior || game.lesson || (game.accuracy >= 75 ? "Clean, solid game." : "Tap to see what your coach found.")}
          </span>
        </div>
      </div>

      {/* Right side: review button or check */}
      {isReviewed ? (
        <Check className="w-4 h-4 text-emerald-500/50 flex-shrink-0 mt-1" strokeWidth={2} />
      ) : (
        <button
          onClick={(e) => { e.stopPropagation(); markReviewed(game.game_id); }}
          className="p-1.5 text-muted-foreground/20 hover:text-emerald-500 transition-colors opacity-0 group-hover:opacity-100 flex-shrink-0"
          title="Mark as reviewed"
          data-testid={`mark-reviewed-${game.game_id}`}
        >
          <Check className="w-4 h-4" strokeWidth={1.5} />
        </button>
      )}
    </div>
  </div>
);

/* ── Accuracy Bar — visual accuracy indicator ── */
const AccuracyBar = ({ accuracy }) => {
  if (!accuracy || accuracy <= 0) {
    return (
      <div className="w-10 flex flex-col items-center flex-shrink-0 pt-0.5">
        <div className="w-1.5 h-8 bg-muted rounded-full" />
        <span className="text-[9px] text-muted-foreground/40 font-mono mt-1">—</span>
      </div>
    );
  }

  const color = accuracy >= 85 ? 'bg-emerald-500'
    : accuracy >= 70 ? 'bg-emerald-400'
    : accuracy >= 55 ? 'bg-amber-400'
    : 'bg-red-400';

  const height = Math.max(20, (accuracy / 100) * 36);

  return (
    <div className="w-10 flex flex-col items-center flex-shrink-0 pt-0.5">
      <div className="w-1.5 h-9 bg-muted rounded-full overflow-hidden flex flex-col justify-end">
        <div className={`w-full rounded-full ${color} transition-all`} style={{ height: `${height}px` }} />
      </div>
      <span className="text-[9px] font-mono text-muted-foreground mt-1">{accuracy.toFixed(0)}%</span>
    </div>
  );
};

/* ── Brilliant Badge ── */
const BrilliantBadge = ({ count }) => (
  <span className="inline-flex items-center gap-0.5 text-[9px] font-bold uppercase tracking-wider text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded-md border border-amber-500/20">
    <Zap className="w-2.5 h-2.5" strokeWidth={2.5} />
    {count > 1 ? `${count}` : ""}
  </span>
);

/* ── Result Badge ── */
const ResultBadge = ({ result, small }) => {
  const base = small ? "text-[9px] px-1.5 py-0" : "text-[10px] px-2 py-0.5";
  const isWin = result === "W";
  const isLoss = result === "L";
  const cls = isWin ? "bg-emerald-500/15 text-emerald-500 border-emerald-500/25"
    : isLoss ? "bg-red-500/15 text-red-400 border-red-500/25"
    : "bg-muted text-muted-foreground border-border";
  return <span className={`${base} font-bold rounded-md border ${cls}`}>{isWin ? "WON" : isLoss ? "LOST" : "DRAW"}</span>;
};

export default Dashboard;
