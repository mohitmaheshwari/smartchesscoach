/**
 * LAB — "The Diagnosis"
 *
 * Like a doctor showing test results.
 * Here are the 3 things wrong with your chess, ranked by damage.
 *
 * 1. Root Problem — #1 issue
 * 2. Training Lock — force action
 * 3. Top 3 Problems — the full diagnosis
 * 4. Priority Game — most painful example
 * 5. Rule — memory hook
 * 6. Game list (after unlock)
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import {
  Import, ChevronRight, Check, Target, Zap,
  Brain, Lock, AlertTriangle, Eye
} from "lucide-react";

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
  const unreviewedGames = games.filter(g => !g.reviewed);
  const reviewedGames = games.filter(g => g.reviewed);
  const isUnlocked = !coaching?.training_lock || coaching.training_lock.unlocked;

  // ── Empty ──
  if (games.length === 0) {
    return (
      <Layout user={user}>
        <div className="max-w-xl mx-auto px-4 py-20 text-center" data-testid="lab-page">
          <div className="w-16 h-16 rounded-2xl bg-muted/50 border border-border flex items-center justify-center mx-auto mb-6">
            <Import className="w-7 h-7 text-muted-foreground/40" strokeWidth={1.5} />
          </div>
          <h2 className="text-xl font-heading font-semibold text-foreground mb-2">No games yet</h2>
          <p className="text-sm text-muted-foreground max-w-sm mx-auto mb-8">Import your games. Your coach will analyze them and show you exactly what's wrong.</p>
          <button onClick={() => navigate("/import")} className="px-6 py-3 text-sm font-semibold rounded-lg gradient-gold text-black shadow-lg shadow-amber-500/20 hover:opacity-90 transition-all" data-testid="lab-empty-import-btn">
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
            <div className="rounded-xl border border-border bg-card p-5">
              <p className="text-[10px] font-bold uppercase tracking-wider text-red-400 mb-3">Your diagnosis</p>
              <h2 className="text-lg font-heading text-foreground tracking-tight leading-snug mb-2">
                {coaching.top_problems?.[0]?.label || coaching.root_problem.message}
              </h2>
              {coaching.diagnosis?.detail && (
                <p className="text-sm text-muted-foreground leading-relaxed">{coaching.diagnosis.detail}</p>
              )}
              {coaching.root_problem.detail && (
                <p className="text-sm text-muted-foreground/70 leading-relaxed mt-1">{coaching.root_problem.detail}</p>
              )}
            </div>
          </motion.div>
        )}

        {/* ═══ 2. TRAINING LOCK ═══ */}
        {coaching?.training_lock && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.04 }}>
            <div className={`rounded-xl border p-5 ${
              coaching.training_lock.unlocked
                ? "border-emerald-500/20 bg-emerald-500/[0.02]"
                : "border-amber-500/15 bg-amber-500/[0.02]"
            }`}>
              {!coaching.training_lock.unlocked ? (
                <>
                  <div className="flex items-center gap-2 mb-3">
                    <Lock className="w-4 h-4 text-amber-500" strokeWidth={2} />
                    <p className="text-xs font-bold uppercase tracking-wider text-amber-500">Fix this first</p>
                    <span className="ml-auto text-sm font-mono font-bold text-foreground">
                      {coaching.training_lock.progress} / {coaching.training_lock.target}
                    </span>
                  </div>
                  <div className="w-full h-2 bg-muted rounded-full overflow-hidden mb-4">
                    <div className="h-full gradient-gold rounded-full transition-all duration-500"
                      style={{ width: `${(coaching.training_lock.progress / coaching.training_lock.target) * 100}%` }} />
                  </div>
                  <button onClick={() => navigate(`/training?focus=${coaching.training_lock.pattern}`)}
                    className="w-full py-3 text-sm font-semibold rounded-xl gradient-gold text-black hover:opacity-90 transition-all flex items-center justify-center gap-2">
                    <Target className="w-4 h-4" strokeWidth={2} />
                    Start {coaching.training_lock.target - coaching.training_lock.progress} {coaching.training_lock.label} Puzzles
                    <ChevronRight className="w-3.5 h-3.5 opacity-60" />
                  </button>
                </>
              ) : (
                <div className="flex items-center gap-2">
                  <Check className="w-4 h-4 text-emerald-500" strokeWidth={2.5} />
                  <p className="text-sm text-emerald-500 font-medium">Training complete. Review your games below.</p>
                </div>
              )}
            </div>
          </motion.div>
        )}

        {/* ═══ 3. TOP 3 PROBLEMS — The Full Diagnosis ═══ */}
        {coaching?.top_problems && coaching.top_problems.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.06 }}>
            <div className="bg-card border border-border rounded-xl p-5">
              <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground mb-4">Why you're losing games</p>
              <div className="space-y-4">
                {coaching.top_problems.map((p, i) => (
                  <div key={i} className="flex items-start gap-3">
                    <span className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 text-xs font-bold ${
                      i === 0 ? "bg-red-500/15 text-red-400" :
                      i === 1 ? "bg-amber-500/10 text-amber-500" :
                      "bg-muted text-muted-foreground"
                    }`}>{i + 1}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-0.5">
                        <p className="text-sm font-semibold text-foreground">{p.label}</p>
                        <span className="text-xs font-mono text-muted-foreground">{p.count} game{p.count !== 1 ? "s" : ""}</span>
                      </div>
                      <p className="text-xs text-muted-foreground leading-relaxed">{p.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        )}

        {/* ═══ LOCKED OVERLAY ═══ */}
        {!isUnlocked && coaching && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.08 }}>
            <div className="relative">
              <div className="blur-sm opacity-20 pointer-events-none select-none space-y-4">
                <div className="bg-card border border-border rounded-xl p-5 h-24" />
                <div className="bg-card border border-border rounded-xl p-5 h-16" />
                <div className="bg-card border border-border rounded-xl p-3 h-12" />
              </div>
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="bg-card/90 backdrop-blur-sm border border-border rounded-lg px-5 py-3 flex items-center gap-2 shadow-lg">
                  <Lock className="w-4 h-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground font-medium">Complete training to unlock</span>
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {/* ═══ UNLOCKED CONTENT ═══ */}
        {isUnlocked && (
          <>
            {/* ═══ 4. PRIORITY GAME ═══ */}
            {coaching?.priority_game && (
              <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}>
                <div className="bg-card border border-border rounded-xl cursor-pointer transition-all hover:border-primary/20 group"
                  onClick={() => navigate(`/game/${coaching.priority_game.game_id}`)}>
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
                    <p className="text-sm text-foreground/80 leading-relaxed">{coaching.priority_game.description}</p>
                  </div>
                </div>
              </motion.div>
            )}

            {/* ═══ 5. RULE ═══ */}
            {coaching?.rule && (
              <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
                <div className="p-4 rounded-xl bg-amber-500/5 border border-amber-500/15">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-amber-600 dark:text-amber-400 mb-1.5">{coaching.rule.name}</p>
                  <p className="text-sm text-foreground">{coaching.rule.rule}</p>
                </div>
              </motion.div>
            )}

            {/* ═══ 6. GAME LIST ═══ */}
            {unreviewedGames.length > 0 && (
              <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.12 }}>
                <p className="text-[10px] tracking-[0.15em] uppercase mb-2.5 font-bold text-muted-foreground/70">Your Games</p>
                <div className="space-y-1.5">
                  {unreviewedGames.map((game) => (
                    <GameCard key={game.game_id} game={game} navigate={navigate} markReviewed={markReviewed} />
                  ))}
                </div>
              </motion.div>
            )}

            {reviewedGames.length > 0 && (
              <div>
                <button onClick={() => setShowReviewed(!showReviewed)}
                  className="flex items-center gap-2 text-[10px] tracking-[0.15em] uppercase font-bold text-muted-foreground/40 hover:text-muted-foreground transition-colors mb-2">
                  <Check className="w-3 h-3" strokeWidth={2} />Reviewed ({reviewedGames.length})
                  <ChevronRight className={`w-3 h-3 transition-transform ${showReviewed ? 'rotate-90' : ''}`} />
                </button>
                {showReviewed && (
                  <div className="space-y-1.5">
                    {reviewedGames.map((game) => (
                      <GameCard key={game.game_id} game={game} navigate={navigate} markReviewed={markReviewed} isReviewed />
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}

        <div className="text-center pt-2">
          <button onClick={() => navigate("/import")} className="text-xs text-muted-foreground/40 hover:text-muted-foreground transition-colors">
            Import more games
          </button>
        </div>
      </div>
    </Layout>
  );
};

const GameCard = ({ game, navigate, markReviewed, isReviewed }) => (
  <div className={`bg-card border border-border rounded-lg cursor-pointer transition-all hover:border-primary/20 group ${isReviewed ? 'opacity-40' : ''}`}
    onClick={() => navigate(`/game/${game.game_id}`)}>
    <div className="p-3 flex items-center gap-3">
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
          }`}>{game.result}</span>
          {game.brilliant_moves > 0 && <Zap className="w-2.5 h-2.5 text-amber-400" strokeWidth={2.5} />}
        </div>
        <p className="text-xs text-muted-foreground line-clamp-1">
          {game.game_reason?.label || game.opening || ""}
        </p>
      </div>
      {!isReviewed && (
        <button onClick={(e) => { e.stopPropagation(); markReviewed(game.game_id); }}
          className="p-1 text-muted-foreground/20 hover:text-emerald-500 transition-colors opacity-0 group-hover:opacity-100 flex-shrink-0">
          <Check className="w-3.5 h-3.5" strokeWidth={1.5} />
        </button>
      )}
    </div>
  </div>
);

export default Dashboard;
