/**
 * PROGRESS — "Am I improving?"
 *
 * ONE focus. ONE metric. ONE answer.
 *
 * 1. Current focus — what you're fixing
 * 2. Improvement tracker — is it getting better?
 * 3. Reinforce — keep going or adjust
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import {
  TrendingUp, TrendingDown, Target, Brain, ChevronRight, Lock
} from "lucide-react";

const UnifiedProgress = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [report, setReport] = useState(null);
  const [coaching, setCoaching] = useState(null);

  useEffect(() => {
    Promise.all([
      fetch(`${API}/progress/coaching-report`, { credentials: "include" }).then(r => r.ok ? r.json() : null),
      fetch(`${API}/lab-coach-pick`, { credentials: "include" }).then(r => r.ok ? r.json() : null).catch(() => null),
    ])
      .then(([r, labData]) => {
        setReport(r);
        setCoaching(labData?.coaching || null);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <Layout user={user}><div className="flex items-center justify-center h-[60vh]"><div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin" /></div></Layout>;
  }

  if (!report?.has_data) {
    return (
      <Layout user={user}>
        <div className="max-w-md mx-auto px-4 py-16 text-center" data-testid="progress-page">
          <h1 className="text-2xl text-foreground tracking-tight mb-3 font-heading">Progress</h1>
          <p className="text-sm text-muted-foreground mb-6">Play and analyze a few games to track your improvement.</p>
          <button onClick={() => navigate("/import")} className="px-5 py-2.5 text-sm bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition-opacity">Import Games</button>
        </div>
      </Layout>
    );
  }

  const { weakness_control, recent_form, big_picture } = report;
  const root = coaching?.root_problem;
  const diag = coaching?.diagnosis;
  const topProblem = coaching?.top_problems?.[0];
  const lock = coaching?.training_lock;

  // Find the main weakness trend
  const mainTrend = weakness_control?.find(w => w.pattern === root?.pattern) || weakness_control?.[0];

  // Determine if improving
  const isImproving = mainTrend?.direction === "improving";
  const isWorsening = mainTrend?.direction === "worsening";

  // Compute recent vs older for the focus pattern
  const recentCount = mainTrend?.recent || 0;
  const totalCount = mainTrend?.total || 0;

  return (
    <Layout user={user}>
      <div className="max-w-md mx-auto px-4 py-8 space-y-6" data-testid="progress-page">

        {/* ═══ 1. CURRENT FOCUS ═══ */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
          <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground mb-2">Your current focus</p>
          <h1 className="text-xl font-heading text-foreground tracking-tight leading-snug">
            {topProblem?.label || diag?.short || mainTrend?.label || "No active focus"}
          </h1>
          {(topProblem?.description || diag?.detail) && (
            <p className="text-sm text-muted-foreground mt-1.5 leading-relaxed">
              {topProblem?.description || diag?.detail}
            </p>
          )}
        </motion.div>

        {/* ═══ 2. IMPROVEMENT TRACKER ═══ */}
        {mainTrend && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
            <div className={`rounded-xl border p-5 ${
              isImproving ? "border-emerald-500/20 bg-emerald-500/[0.02]" :
              isWorsening ? "border-red-500/15 bg-red-500/[0.02]" :
              "border-border bg-card"
            }`}>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  {isImproving
                    ? <TrendingUp className="w-4 h-4 text-emerald-500" strokeWidth={2} />
                    : isWorsening
                    ? <TrendingDown className="w-4 h-4 text-red-400" strokeWidth={2} />
                    : <Target className="w-4 h-4 text-muted-foreground" strokeWidth={2} />
                  }
                  <p className={`text-sm font-semibold ${
                    isImproving ? "text-emerald-500" : isWorsening ? "text-red-400" : "text-foreground"
                  }`}>
                    {isImproving ? "You are improving" : isWorsening ? "No improvement yet" : "Tracking"}
                  </p>
                </div>
              </div>

              {/* The one metric */}
              <div className="flex items-baseline gap-3 mb-2">
                <span className="text-3xl font-mono font-bold text-foreground">{recentCount}</span>
                <span className="text-sm text-muted-foreground">mistakes in your last {mainTrend?.recent_games || 20} games</span>
              </div>

              {totalCount > recentCount && (
                <p className="text-xs text-muted-foreground">
                  Total across all games: {totalCount}
                </p>
              )}

              {/* Verdict */}
              <div className="mt-4 pt-3 border-t border-border/50">
                {isImproving ? (
                  <p className="text-sm text-emerald-500 font-medium">This is working. Keep training this.</p>
                ) : isWorsening ? (
                  <p className="text-sm text-red-400 font-medium">This is getting worse. You need more focused practice.</p>
                ) : (
                  <p className="text-sm text-muted-foreground">Steady. Keep applying the rule in your games.</p>
                )}
              </div>
            </div>
          </motion.div>
        )}

        {/* ═══ 3. TRAINING PROGRESS ═══ */}
        {lock && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}>
            <div className="rounded-xl border border-border bg-card p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Lock className="w-3.5 h-3.5 text-muted-foreground" strokeWidth={2} />
                  <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Training</p>
                </div>
                <span className="text-sm font-mono font-bold text-foreground">{lock.progress} / {lock.target}</span>
              </div>
              <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
                <div className={`h-full rounded-full transition-all duration-500 ${lock.unlocked ? "bg-emerald-500" : "gradient-gold"}`}
                  style={{ width: `${(lock.progress / lock.target) * 100}%` }} />
              </div>
            </div>
          </motion.div>
        )}

        {/* ═══ 4. REINFORCE ═══ */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
          <button
            onClick={() => {
              if (lock && !lock.unlocked) navigate(`/training?focus=${lock.pattern}`);
              else navigate("/play-with-coach");
            }}
            className="w-full py-3.5 text-sm font-semibold rounded-xl gradient-gold text-black hover:opacity-90 transition-all shadow-lg shadow-amber-500/15 flex items-center justify-center gap-2"
          >
            {lock && !lock.unlocked ? (
              <><Target className="w-4 h-4" strokeWidth={2} />Continue Training</>
            ) : (
              <><Brain className="w-4 h-4" strokeWidth={2} />Apply It In a Game</>
            )}
            <ChevronRight className="w-3.5 h-3.5 opacity-60" />
          </button>
        </motion.div>

        {/* ═══ FORM COMPARISON (small, supporting) ═══ */}
        {big_picture?.games > 5 && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.14 }}>
            <div className="border-t border-border pt-4 mt-2">
              <p className="text-[10px] tracking-[0.15em] uppercase font-bold text-muted-foreground/40 mb-3">Recent form</p>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-card border border-border rounded-lg p-3 text-center">
                  <p className={`text-xl font-mono font-bold ${(recent_form?.accuracy || 0) >= 65 ? "text-emerald-500" : "text-foreground"}`}>
                    {(recent_form?.accuracy || 0).toFixed(0)}%
                  </p>
                  <p className="text-[10px] text-muted-foreground mt-0.5">Last 5 accuracy</p>
                </div>
                <div className="bg-card border border-border rounded-lg p-3 text-center">
                  <p className={`text-xl font-mono font-bold ${(big_picture?.accuracy || 0) >= 65 ? "text-emerald-500" : "text-foreground"}`}>
                    {(big_picture?.accuracy || 0).toFixed(0)}%
                  </p>
                  <p className="text-[10px] text-muted-foreground mt-0.5">All {big_picture.games} games</p>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </div>
    </Layout>
  );
};

export default UnifiedProgress;
