/**
 * LAB — "The Diagnosis"
 *
 * Shows the accumulated problem across ALL games.
 * Not one game. The pattern.
 *
 * LOCKED: root problem → sub-causes preview → training lock
 * UNLOCKED: root problem → sub-causes → current game to review → rule → remaining games
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import LichessBoard from "@/components/LichessBoard";
import {
  Import, ChevronRight, Check, Target, Zap,
  Brain, Lock, Eye
} from "lucide-react";

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
          <p className="text-sm text-muted-foreground max-w-sm mx-auto mb-8">Import your games. Your coach will tell you what's wrong.</p>
          <button onClick={() => navigate("/import")} className="px-6 py-3 text-sm font-semibold rounded-lg gradient-gold text-black shadow-lg shadow-amber-500/20 hover:opacity-90 transition-all" data-testid="lab-empty-import-btn">
            Import your games
          </button>
        </div>
      </Layout>
    );
  }

  const lock = coaching?.training_lock;
  const isUnlocked = lock?.unlocked;
  const pg = coaching?.priority_game;
  const problemGames = coaching?.problem_games || [];
  const subCauses = coaching?.sub_causes || [];
  const totalProblem = coaching?.total_problem_games || 0;
  const reviewedProblem = coaching?.reviewed_problem_games || 0;
  const topProblem = coaching?.top_problems?.[0];
  const headline = topProblem?.label || coaching?.root_problem?.message || "Your coach found a pattern.";
  const ruleData = coaching?.rule;
  const explanation = coaching?.diagnosis?.detail || "";

  // ═══════════════════════════════════════════
  // LOCKED STATE
  // ═══════════════════════════════════════════
  if (!isUnlocked) {
    return (
      <Layout user={user}>
        <div className="max-w-md mx-auto px-6 py-10" data-testid="lab-page">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>

            {/* Headline */}
            <h1 className="text-2xl sm:text-[28px] font-heading text-foreground tracking-tight leading-[1.2] mb-6">
              {headline}
            </h1>

            {/* Sub-causes preview — show the pattern is not random */}
            {subCauses.length > 0 && (
              <div className="mb-6">
                <p className="text-sm text-muted-foreground mb-3">
                  This happened {totalProblem} times. Here's why:
                </p>
                <div className="space-y-2">
                  {subCauses.slice(0, 3).map((sc, i) => (
                    <div key={i} className="flex items-center gap-3">
                      <div className="w-1.5 h-1.5 rounded-full bg-red-400/60" />
                      <p className="text-sm text-foreground/70">
                        {sc.cause} <span className="text-muted-foreground/50">— {sc.count} game{sc.count !== 1 ? "s" : ""}</span>
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Repetition signal */}
            <p className="text-sm text-foreground/50 mb-8">
              You did this again and again in your recent games.
            </p>

            {/* Lock block */}
            <div className="rounded-xl border border-border bg-card p-6 mb-8">
              <div className="flex items-center gap-2.5 mb-4">
                <Lock className="w-4 h-4 text-muted-foreground" strokeWidth={2} />
                <p className="text-sm font-semibold text-foreground">Unlock your lesson</p>
                {lock && (
                  <span className="ml-auto text-sm font-mono font-bold text-foreground">{lock.progress} / {lock.target}</span>
                )}
              </div>

              {lock && lock.progress > 0 && (
                <div className="w-full h-2 bg-muted rounded-full overflow-hidden mb-4">
                  <div className="h-full gradient-gold rounded-full transition-all duration-500"
                    style={{ width: `${(lock.progress / lock.target) * 100}%` }} />
                </div>
              )}

              <p className="text-sm text-muted-foreground mb-4">
                Complete {lock ? lock.target - lock.progress : 3} quick training exercises to see:
              </p>

              <div className="space-y-2 mb-6">
                {["What exactly goes wrong", "The rule you're breaking", `${totalProblem} examples from your own games`].map((item, i) => (
                  <div key={i} className="flex items-center gap-2.5">
                    <div className="w-1.5 h-1.5 rounded-full bg-amber-500/50" />
                    <p className="text-sm text-foreground/70">{item}</p>
                  </div>
                ))}
              </div>

              <button onClick={() => navigate(coaching?.root_problem?.pattern ? `/training?focus=${coaching.root_problem.pattern}` : "/training")}
                className="w-full py-3.5 text-[15px] font-semibold rounded-xl gradient-gold text-black hover:opacity-90 transition-all shadow-lg shadow-amber-500/20 flex items-center justify-center gap-2">
                <Target className="w-4 h-4" strokeWidth={2} />
                Start training (3 min)
                <ChevronRight className="w-4 h-4 opacity-60" />
              </button>
            </div>

          </motion.div>
        </div>
      </Layout>
    );
  }

  // ═══════════════════════════════════════════
  // UNLOCKED STATE
  // ═══════════════════════════════════════════

  const unreviewedProblemGames = problemGames.filter(g => !g.reviewed);
  const reviewedProblemGames = problemGames.filter(g => g.reviewed);

  return (
    <Layout user={user}>
      <div className="max-w-md mx-auto px-6 py-10" data-testid="lab-page">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>

          {/* Reward line */}
          <p className="text-sm text-emerald-500 font-medium mb-6">
            Now you can see it clearly.
          </p>

          {/* Explanation */}
          {explanation && (
            <p className="text-[15px] text-foreground leading-[1.8] whitespace-pre-line mb-6">
              {explanation}
            </p>
          )}

          {/* Sub-causes — the accumulated breakdown */}
          {subCauses.length > 0 && (
            <div className="rounded-xl border border-border bg-card p-5 mb-6">
              <div className="flex items-center justify-between mb-3">
                <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  Why this keeps happening
                </p>
                <p className="text-xs text-muted-foreground/50">
                  {totalProblem} game{totalProblem !== 1 ? "s" : ""}
                </p>
              </div>
              <div className="space-y-2.5">
                {subCauses.map((sc, i) => (
                  <div key={i} className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <div className={`w-2 h-2 rounded-full ${i === 0 ? "bg-red-400" : i === 1 ? "bg-amber-400" : "bg-muted-foreground/30"}`} />
                      <p className="text-sm text-foreground">{sc.cause}</p>
                    </div>
                    <p className="text-xs font-mono text-muted-foreground">{sc.count}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Rule */}
          {ruleData && (
            <div className="rounded-xl bg-amber-500/[0.05] border border-amber-500/15 p-5 mb-6">
              <p className="text-base font-heading font-semibold text-foreground mb-1.5">
                {ruleData.name}
              </p>
              <p className="text-[15px] text-foreground/80 leading-relaxed">
                {ruleData.rule}
              </p>
            </div>
          )}

          {/* Current game to review — with board */}
          {pg && !pg.reviewed && (
            <div className="mb-6">
              <div className="flex items-center justify-between mb-3">
                <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  {reviewedProblem > 0 ? `Game ${reviewedProblem + 1} of ${totalProblem}` : "Start with this one"}
                </p>
                {totalProblem > 1 && (
                  <p className="text-xs text-muted-foreground/50">
                    {reviewedProblem} of {totalProblem} reviewed
                  </p>
                )}
              </div>

              <div className="rounded-xl border border-border bg-card overflow-hidden">
                {pg.replay?.mistake_fen && (
                  <div className="relative">
                    <div className="aspect-square max-h-[240px]">
                      <LichessBoard
                        fen={pg.replay.setup_fen || pg.replay.mistake_fen}
                        orientation={pg.user_color || "white"}
                        viewOnly={true}
                      />
                    </div>
                    <div className="absolute top-2 left-2 bg-black/60 text-white text-[10px] font-medium px-2.5 py-1 rounded backdrop-blur-sm">
                      Before your mistake
                    </div>
                  </div>
                )}
                <div className="p-5">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm font-medium text-foreground">vs {pg.opponent}</span>
                    {pg.opening && <span className="text-xs text-muted-foreground/50">{pg.opening}</span>}
                  </div>
                  <p className="text-xs text-muted-foreground mb-1">{pg.sub_cause}</p>
                  <p className="text-sm text-foreground/70 leading-[1.7] mb-4">
                    You were in control. Then it slipped.
                  </p>
                  <motion.button
                    onClick={() => navigate(`/replay/${pg.game_id}`)}
                    className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:text-primary/80 transition-colors group"
                    whileHover={{ x: 3 }}
                  >
                    <Eye className="w-3.5 h-3.5" strokeWidth={2} />
                    Show me what I missed
                    <ChevronRight className="w-3.5 h-3.5 opacity-40 group-hover:opacity-80 transition-opacity" />
                  </motion.button>
                </div>
              </div>
            </div>
          )}

          {/* Remaining games — compact list */}
          {unreviewedProblemGames.length > 1 && (
            <div className="mb-6">
              <p className="text-[10px] tracking-[0.15em] uppercase mb-2 font-bold text-muted-foreground/50">
                More games with this problem
              </p>
              <div className="space-y-1.5">
                {unreviewedProblemGames.filter(g => g.game_id !== pg?.game_id).map((g) => (
                  <div key={g.game_id}
                    className="flex items-center gap-3 px-3 py-2.5 bg-card border border-border rounded-lg cursor-pointer hover:border-primary/20 transition-all"
                    onClick={() => navigate(`/replay/${g.game_id}`)}>
                    <div className="w-2 h-2 rounded-full bg-red-400" />
                    <div className="flex-1 min-w-0">
                      <span className="text-sm text-foreground">vs {g.opponent}</span>
                    </div>
                    <span className="text-xs text-muted-foreground/50">{g.sub_cause}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Reviewed games — collapsed */}
          {reviewedProblemGames.length > 0 && (
            <div className="mb-4">
              <p className="text-[10px] tracking-[0.15em] uppercase mb-2 font-bold text-muted-foreground/30">
                <Check className="w-3 h-3 inline mr-1" strokeWidth={2} />
                Reviewed ({reviewedProblemGames.length})
              </p>
              <div className="space-y-1">
                {reviewedProblemGames.map((g) => (
                  <div key={g.game_id}
                    className="flex items-center gap-3 px-3 py-2 bg-card border border-border rounded-lg opacity-40 cursor-pointer hover:opacity-60 transition-all"
                    onClick={() => navigate(`/game/${g.game_id}`)}>
                    <Check className="w-3 h-3 text-emerald-500/50" strokeWidth={2} />
                    <span className="text-sm text-foreground">vs {g.opponent}</span>
                    <span className="text-xs text-muted-foreground/40 ml-auto">{g.sub_cause}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* All reviewed — celebration */}
          {unreviewedProblemGames.length === 0 && totalProblem > 0 && (
            <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/[0.03] p-5 mb-6 text-center">
              <Check className="w-6 h-6 text-emerald-500 mx-auto mb-2" strokeWidth={2} />
              <p className="text-sm text-emerald-500 font-medium">
                You've reviewed all {totalProblem} games with this problem.
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Now apply the rule in your next game.
              </p>
            </div>
          )}

          {/* Import more */}
          <div className="text-center pt-2">
            <button onClick={() => navigate("/import")} className="text-xs text-muted-foreground/40 hover:text-muted-foreground transition-colors">
              Import more games
            </button>
          </div>

        </motion.div>
      </div>
    </Layout>
  );
};

export default Dashboard;
