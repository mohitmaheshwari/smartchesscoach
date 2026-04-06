/**
 * PROGRESS PAGE — "Why are you stuck? What should you fix?"
 *
 * NOT a stats dashboard.
 * A coaching mirror that shows ONE main problem, ONE rule, ONE action.
 * Stats are supporting evidence, pushed below.
 *
 * Structure:
 * 1. Identity header — "You are losing because..."
 * 2. Main weakness — one pattern, with pressure
 * 3. Rule + action lock
 * 4. Supporting data (recent vs overall, trends, phases)
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import {
  TrendingUp, TrendingDown, Minus,
  ChevronRight, Target, Brain, AlertTriangle, Lock, CheckCircle2
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
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center h-[60vh]">
          <div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
        </div>
      </Layout>
    );
  }

  if (!report?.has_data) {
    return (
      <Layout user={user}>
        <div className="max-w-xl mx-auto px-4 py-16 text-center" data-testid="progress-page">
          <h1 className="text-2xl text-foreground tracking-tight mb-3 font-heading">Progress</h1>
          <p className="text-sm text-muted-foreground mb-6">Play and analyze a few games to see your coaching report.</p>
          <button onClick={() => navigate("/import")} className="px-5 py-2.5 text-sm bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition-opacity">
            Import Games
          </button>
        </div>
      </Layout>
    );
  }

  const { recent_form, big_picture, weakness_control, phase_understanding } = report;
  const root = coaching?.root_problem;
  const diag = coaching?.diagnosis;
  const rule = coaching?.rule;
  const lock = coaching?.training_lock;

  // Find the #1 weakness from trends
  const topWeakness = weakness_control?.find(w => w.direction !== "improving") || weakness_control?.[0];

  return (
    <Layout user={user}>
      <div className="max-w-2xl mx-auto px-4 py-6 space-y-6" data-testid="progress-page">

        {/* ═══ 1. IDENTITY HEADER — the uncomfortable truth ═══ */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
          {root && diag ? (
            <div className="rounded-2xl border border-border bg-card relative overflow-hidden p-6">
              <div className="absolute top-0 right-0 w-48 h-48 rounded-full blur-3xl -translate-y-1/3 translate-x-1/3 bg-red-500/5" />
              <div className="relative">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-amber-500/20 to-amber-600/10 flex items-center justify-center">
                    <Brain className="w-5 h-5 text-amber-500" />
                  </div>
                  <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Why you're stuck</p>
                </div>

                <h1 className="text-xl sm:text-2xl font-heading text-foreground tracking-tight leading-snug mb-2">
                  {diag.short}
                </h1>
                <p className="text-sm text-muted-foreground leading-relaxed mb-1">
                  {diag.detail}
                </p>
                {root.detail && (
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {root.detail}
                  </p>
                )}
              </div>
            </div>
          ) : (
            <div className="rounded-2xl border border-border bg-card p-6">
              <h1 className="text-2xl font-heading text-foreground tracking-tight mb-2">Progress</h1>
              <p className="text-sm text-muted-foreground">Here's what your coach sees in your games.</p>
            </div>
          )}
        </motion.div>

        {/* ═══ 2. MAIN WEAKNESS — one pattern with pressure ═══ */}
        {topWeakness && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
            <div className="bg-card border border-border rounded-xl p-5">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-red-400" strokeWidth={2} />
                  <p className="text-xs font-bold uppercase tracking-wider text-red-400">Your biggest leak</p>
                </div>
                <span className="text-lg font-mono font-bold text-foreground">{topWeakness.total}x</span>
              </div>

              <h3 className="text-base font-semibold text-foreground mb-1">{topWeakness.label}</h3>
              <p className="text-sm text-muted-foreground mb-3">{topWeakness.message}</p>

              {/* Pressure line */}
              {topWeakness.direction !== "improving" && (
                <p className="text-xs text-red-400 font-medium mb-4">
                  Until this is fixed, your rating will not grow.
                </p>
              )}
              {topWeakness.direction === "improving" && (
                <p className="text-xs text-emerald-500 font-medium mb-4">
                  This is improving. Keep going.
                </p>
              )}

              <button
                onClick={() => navigate(`/training?focus=${topWeakness.pattern}`)}
                className="w-full py-2.5 text-sm font-semibold rounded-lg gradient-gold text-black hover:opacity-90 transition-all flex items-center justify-center gap-2"
              >
                <Target className="w-4 h-4" strokeWidth={2} />
                Train {topWeakness.label}
              </button>
            </div>
          </motion.div>
        )}

        {/* ═══ 3. RULE + TRAINING LOCK ═══ */}
        {rule && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}>
            <div className="p-4 rounded-xl bg-amber-500/5 border border-amber-500/15">
              <p className="text-[10px] font-bold uppercase tracking-wider text-amber-600 dark:text-amber-400 mb-1">{rule.name}</p>
              <p className="text-sm text-foreground">{rule.rule}</p>
            </div>
          </motion.div>
        )}

        {lock && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
            <div className={`rounded-xl border p-4 ${lock.unlocked ? "border-emerald-500/20 bg-emerald-500/[0.02]" : "border-border bg-card"}`}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  {lock.unlocked
                    ? <CheckCircle2 className="w-4 h-4 text-emerald-500" strokeWidth={2} />
                    : <Lock className="w-4 h-4 text-muted-foreground" strokeWidth={2} />}
                  <p className={`text-xs font-bold uppercase tracking-wider ${lock.unlocked ? "text-emerald-500" : "text-muted-foreground"}`}>
                    {lock.unlocked ? "Training complete" : "Training progress"}
                  </p>
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

        {/* ═══ 4. SUPPORTING DATA — stats pushed below ═══ */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.14 }}>
          <div className="border-t border-border pt-6">
            <p className="text-[10px] tracking-[0.15em] uppercase font-bold text-muted-foreground/50 mb-4">Supporting Data</p>

            {/* Recent vs Overall */}
            {big_picture?.games > 5 && (
              <div className="mb-6">
                <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-2">Recent vs Overall</p>
                <div className="grid grid-cols-2 gap-3">
                  <CompactStatCard title="Last 5 Games" form={recent_form} highlight />
                  <CompactStatCard title={`All ${big_picture.games} Games`} form={big_picture} />
                </div>
              </div>
            )}

            {/* Weakness Trends */}
            {weakness_control && weakness_control.length > 0 && (
              <div className="mb-6">
                <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-2">All Patterns</p>
                <div className="space-y-1.5">
                  {weakness_control.map((w) => (
                    <div
                      key={w.pattern}
                      className="flex items-center justify-between px-3 py-2.5 bg-card border border-border rounded-lg cursor-pointer hover:border-primary/20 transition-all"
                      onClick={() => navigate(`/training?focus=${w.pattern}`)}
                    >
                      <div className="flex items-center gap-2">
                        <DirectionDot direction={w.direction} />
                        <span className="text-sm text-foreground">{w.label}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-xs text-muted-foreground">{w.message}</span>
                        <span className="text-sm font-mono font-bold text-foreground">{w.total}x</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Phase Understanding */}
            {phase_understanding && (
              <div>
                <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-2">Game Phase Accuracy</p>
                <div className="grid grid-cols-3 gap-2">
                  {["opening", "middlegame", "endgame"].map((phase) => {
                    const p = phase_understanding[phase];
                    if (!p || p.total_moves === 0) return null;
                    const acc = Math.round(p.accuracy || 0);
                    return (
                      <div key={phase} className="bg-card border border-border rounded-lg p-3 text-center">
                        <p className={`text-lg font-mono font-bold ${acc >= 70 ? "text-emerald-500" : acc >= 50 ? "text-foreground" : "text-red-400"}`}>
                          {acc}%
                        </p>
                        <p className="text-[10px] uppercase tracking-wider text-muted-foreground mt-0.5">
                          {phase}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </motion.div>

      </div>
    </Layout>
  );
};


// ═══ Components ═══

const CompactStatCard = ({ title, form, highlight }) => {
  if (!form) return null;
  const wins = form.wins || 0;
  const losses = form.losses || 0;
  const draws = form.draws || 0;
  const acc = form.accuracy || 0;
  const blunders = form.blunder_rate || 0;

  return (
    <div className={`border rounded-xl p-4 ${highlight ? "border-primary/15 bg-card" : "border-border bg-card"}`}>
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-2">{title}</p>
      <p className={`text-2xl font-mono font-bold mb-1 ${acc >= 70 ? "text-emerald-500" : acc >= 50 ? "text-foreground" : "text-red-400"}`}>
        {acc.toFixed(0)}%
      </p>
      <p className="text-xs text-muted-foreground">
        {wins}W {losses}L{draws > 0 ? ` ${draws}D` : ""}
        {blunders > 0 && ` · ${blunders.toFixed(1)}/g blunders`}
      </p>
    </div>
  );
};

const DirectionDot = ({ direction }) => (
  <div className={`w-2 h-2 rounded-full ${
    direction === "improving" ? "bg-emerald-500" :
    direction === "worsening" ? "bg-red-400" :
    direction === "general" ? "bg-muted-foreground/30" :
    "bg-amber-400"
  }`} />
);

export default UnifiedProgress;
