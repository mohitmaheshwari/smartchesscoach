/**
 * LAB PAGE — Coach's Review Queue
 * 
 * The coach picks which game to review and tells you WHY.
 * Each game card shows your behavioral story, not just stats.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Loader2, Import, ChevronRight, Check, TrendingDown, TrendingUp, Minus } from "lucide-react";

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
          <div className="w-5 h-5 border border-border border-t-foreground/50 rounded-full animate-spin" />
        </div>
      </Layout>
    );
  }

  const pick = data?.pick;
  const pickReason = data?.pick_reason;
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
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl text-foreground tracking-tight font-heading" data-testid="lab-heading">Lab</h1>
            {totalCount > 0 && (
              <p className="text-xs text-muted-foreground mt-1" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                {reviewedCount}/{totalCount} reviewed
              </p>
            )}
          </div>
          <button
            onClick={() => navigate("/import")}
            className="flex items-center gap-1.5 px-4 py-2 text-sm border border-border text-foreground hover:bg-muted/50 transition-colors rounded-md"
            data-testid="lab-import-btn"
          >
            <Import className="w-3.5 h-3.5" strokeWidth={1.5} />
            Import
          </button>
        </div>

        {/* ── VERDICT STRIP ── */}
        {verdict && verdict.total > 0 && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
            <div className="bg-card border border-border rounded-lg p-5">
              <div className="flex items-center gap-4 mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-lg font-bold text-emerald-600" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{verdict.wins}W</span>
                  <span className="text-lg font-bold text-red-500" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{verdict.losses}L</span>
                </div>
                <span className="text-xs text-muted-foreground">last {verdict.total} games</span>
                {verdict.losses > verdict.wins ? (
                  <TrendingDown className="w-4 h-4 text-red-400 ml-auto" />
                ) : verdict.wins > verdict.losses ? (
                  <TrendingUp className="w-4 h-4 text-emerald-500 ml-auto" />
                ) : (
                  <Minus className="w-4 h-4 text-muted-foreground ml-auto" />
                )}
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">{verdict.insight}</p>
            </div>
          </motion.div>
        )}

        {/* ── COACH'S PICK ── */}
        {pick && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="mb-8">
            <p className="text-[10px] tracking-[0.15em] uppercase mb-2.5 font-bold text-muted-foreground">
              Coach's Pick
            </p>
            <div
              className="bg-card border-2 border-amber-500/30 rounded-lg cursor-pointer transition-all duration-200 hover:border-amber-500/50 hover:shadow-md group"
              onClick={() => navigate(`/game/${pick.game_id}`)}
              data-testid="coach-pick-card"
            >
              <div className="p-5">
                {/* Game header */}
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <AccuracyDot accuracy={pick.accuracy} />
                    <span className="text-base font-semibold text-foreground">vs {pick.opponent}</span>
                    <ResultBadge result={pick.result} />
                    {pick.opening && (
                      <span className="text-xs text-muted-foreground hidden sm:inline">{pick.opening}</span>
                    )}
                  </div>
                  <ChevronRight className="w-5 h-5 text-muted-foreground/40 group-hover:text-amber-500 transition-colors" strokeWidth={1.5} />
                </div>

                {/* Behavioral label */}
                {pick.lesson_label && (
                  <span className="inline-block text-[10px] font-bold uppercase tracking-[0.12em] px-2 py-0.5 rounded bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/20 mb-2.5">
                    {pick.lesson_label}
                  </span>
                )}

                {/* The reason — this is the coach talking */}
                <p className="text-sm leading-relaxed text-foreground/80" data-testid="coach-pick-reason">{pickReason}</p>
              </div>
            </div>
          </motion.div>
        )}

        {/* ── UNREVIEWED GAMES ── */}
        {unreviewedGames.length > (pick ? 1 : 0) && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
            <p className="text-[10px] tracking-[0.15em] uppercase mb-2.5 font-bold text-muted-foreground">
              To Review ({unreviewedGames.length - (pick ? 1 : 0)} more)
            </p>
            <div className="bg-card border border-border rounded-lg divide-y divide-border overflow-hidden">
              {unreviewedGames.filter(g => g.game_id !== pick?.game_id).map((game) => (
                <GameRow key={game.game_id} game={game} navigate={navigate} markReviewed={markReviewed} />
              ))}
            </div>
          </motion.div>
        )}

        {/* ── REVIEWED GAMES ── */}
        {reviewedGames.length > 0 && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }} className="mt-8">
            <p className="text-[10px] tracking-[0.15em] uppercase mb-2.5 font-bold text-muted-foreground/50">
              Reviewed ({reviewedGames.length})
            </p>
            <div className="bg-card/50 border border-border/50 rounded-lg divide-y divide-border/50 overflow-hidden">
              {reviewedGames.map((game) => (
                <div
                  key={game.game_id}
                  className="flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors hover:bg-muted/20 opacity-60 hover:opacity-80"
                  onClick={() => navigate(`/game/${game.game_id}`)}
                  data-testid={`reviewed-game-${game.game_id}`}
                >
                  <Check className="w-3.5 h-3.5 text-emerald-500 flex-shrink-0" strokeWidth={2} />
                  <span className="text-sm text-foreground truncate">vs {game.opponent}</span>
                  <ResultBadge result={game.result} small />
                  {game.lesson_label && (
                    <span className="text-[10px] text-muted-foreground ml-auto hidden sm:inline">{game.lesson_label}</span>
                  )}
                </div>
              ))}
            </div>
          </motion.div>
        )}

        {/* Empty state */}
        {games.length === 0 && (
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center py-16"
            data-testid="lab-empty-state"
          >
            <div className="w-16 h-16 rounded-full bg-muted/50 border border-border flex items-center justify-center mx-auto mb-5">
              <Import className="w-7 h-7 text-muted-foreground/50" strokeWidth={1.5} />
            </div>
            <h2 className="text-lg font-semibold text-foreground mb-2">Your lab is empty</h2>
            <p className="text-sm text-muted-foreground max-w-sm mx-auto mb-6 leading-relaxed">
              Import your games from Chess.com or Lichess. Your coach will analyze them and tell you exactly what to work on.
            </p>
            <button
              onClick={() => navigate("/import")}
              className="px-6 py-3 text-sm font-medium text-white rounded-lg bg-foreground hover:opacity-90 transition-opacity"
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

/* ── Game Row ── Shows behavioral story, not just stats ── */
const GameRow = ({ game, navigate, markReviewed }) => {
  return (
    <div
      className="flex items-start gap-3.5 px-4 py-3.5 cursor-pointer transition-colors hover:bg-muted/30 group"
      onClick={() => navigate(`/game/${game.game_id}`)}
      data-testid={`game-row-${game.game_id}`}
    >
      {/* Accuracy dot */}
      <div className="mt-0.5 flex-shrink-0">
        <AccuracyDot accuracy={game.accuracy} />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-sm font-medium text-foreground">vs {game.opponent}</span>
          <ResultBadge result={game.result} small />
          {game.opening && (
            <>
              <span className="text-muted-foreground/30">·</span>
              <span className="text-xs text-muted-foreground truncate">{game.opening}</span>
            </>
          )}
        </div>

        {/* Behavioral insight — the key differentiator */}
        {(game.behavior || game.lesson) ? (
          <div className="mt-1">
            {game.lesson_label && (
              <span className="text-[9px] font-bold uppercase tracking-[0.1em] text-amber-700 dark:text-amber-400 mr-2">
                {game.lesson_label}
              </span>
            )}
            <span className="text-xs text-muted-foreground leading-relaxed">
              {game.behavior || game.lesson}
            </span>
          </div>
        ) : (
          game.blunders > 0 && (
            <p className="text-xs text-muted-foreground mt-0.5">
              {game.blunders} blunder{game.blunders > 1 ? 's' : ''}{game.mistakes > 0 ? `, ${game.mistakes} mistake${game.mistakes > 1 ? 's' : ''}` : ''}
            </p>
          )
        )}
      </div>

      {/* Mark reviewed */}
      <button
        onClick={(e) => { e.stopPropagation(); markReviewed(game.game_id); }}
        className="mt-0.5 p-1.5 text-muted-foreground/20 hover:text-emerald-600 transition-colors opacity-0 group-hover:opacity-100"
        title="Mark as reviewed"
        data-testid={`mark-reviewed-${game.game_id}`}
      >
        <Check className="w-4 h-4" strokeWidth={1.5} />
      </button>
    </div>
  );
};

/* ── Accuracy Dot ── Tiny colored circle representing game accuracy ── */
const AccuracyDot = ({ accuracy }) => {
  if (!accuracy || accuracy <= 0) return <div className="w-2.5 h-2.5 rounded-full bg-muted" />;
  
  const color = accuracy >= 85 ? 'bg-emerald-500' 
    : accuracy >= 70 ? 'bg-emerald-400' 
    : accuracy >= 55 ? 'bg-amber-500' 
    : 'bg-red-500';
  
  return (
    <div className={`w-2.5 h-2.5 rounded-full ${color}`} title={`${accuracy.toFixed(0)}% accuracy`} />
  );
};

/* ── Result Badge ── */
const ResultBadge = ({ result, small }) => {
  const base = small ? "text-[9px] px-1.5 py-0" : "text-[10px] px-2 py-0.5";
  const isWin = result === "W";
  const isLoss = result === "L";
  const cls = isWin 
    ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20"
    : isLoss 
      ? "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20"
      : "bg-muted text-muted-foreground border-border";
  
  return (
    <span className={`${base} font-semibold rounded border ${cls}`}>
      {isWin ? "WON" : isLoss ? "LOST" : "DRAW"}
    </span>
  );
};

export default Dashboard;
