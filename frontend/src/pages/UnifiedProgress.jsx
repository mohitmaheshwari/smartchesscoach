/**
 * PROGRESS PAGE — Are You Improving?
 *
 * Not a stats dump. A clear answer to "am I getting better?"
 *
 * Sections:
 * 1. Big verdict: improving / stable / declining
 * 2. Before vs After (last 5 games vs overall)
 * 3. Weakness trends (are patterns shrinking?)
 * 4. Strength profile (what you're good at)
 * 5. Game timeline (visual accuracy history)
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import {
  TrendingUp, TrendingDown, Minus,
  ChevronRight, FlaskConical, Check, Shield,
  Crown, Swords, Zap, Brain, Target, BookOpen
} from "lucide-react";

const UnifiedProgress = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [report, setReport] = useState(null);
  const [strengthProfile, setStrengthProfile] = useState(null);

  useEffect(() => {
    Promise.all([
      fetch(`${API}/progress/coaching-report`, { credentials: "include" }).then(r => r.ok ? r.json() : null),
      fetch(`${API}/profile/strength-profile`, { credentials: "include" }).then(r => r.ok ? r.json() : null).catch(() => null),
    ])
      .then(([r, sp]) => { setReport(r); setStrengthProfile(sp); })
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

  const { headline, recent_form, big_picture, weakness_control, phase_understanding, review_impact, game_stats } = report;

  // Determine overall trend
  const isImproving = recent_form?.accuracy > big_picture?.accuracy && recent_form?.blunder_rate < big_picture?.blunder_rate;
  const isDeclining = recent_form?.accuracy < big_picture?.accuracy - 5;

  return (
    <Layout user={user}>
      <div className="max-w-3xl mx-auto px-4 py-6" data-testid="progress-page">

        {/* ── BIG VERDICT ── */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mb-8">
          <h1 className="text-2xl text-foreground tracking-tight mb-2 font-heading">Progress</h1>

          {/* Verdict banner */}
          <div className={`flex items-center gap-3 p-4 rounded-xl border ${
            isImproving ? 'border-emerald-500/20 bg-emerald-500/5' :
            isDeclining ? 'border-red-500/20 bg-red-500/5' :
            'border-border bg-card'
          }`}>
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${
              isImproving ? 'bg-emerald-500/15' : isDeclining ? 'bg-red-500/15' : 'bg-muted'
            }`}>
              {isImproving ? <TrendingUp className="w-5 h-5 text-emerald-500" strokeWidth={2} /> :
               isDeclining ? <TrendingDown className="w-5 h-5 text-red-400" strokeWidth={2} /> :
               <Minus className="w-5 h-5 text-muted-foreground" strokeWidth={2} />}
            </div>
            <div>
              <p className={`text-sm font-semibold ${
                isImproving ? 'text-emerald-500' : isDeclining ? 'text-red-400' : 'text-foreground'
              }`}>
                {isImproving ? "You're improving" : isDeclining ? "Needs attention" : "Steady progress"}
              </p>
              <p className="text-xs text-muted-foreground mt-0.5" data-testid="coaching-headline">{headline}</p>
            </div>
          </div>
        </motion.div>

        {/* ── BEFORE vs AFTER ── */}
        {/* Only show side-by-side when there are enough games to make a meaningful comparison */}
        {big_picture?.games > 5 ? (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }} className="mb-8">
            <Label>Recent vs Overall</Label>
            <div className="grid grid-cols-2 gap-3">
              <StatCard
                title="Last 5 Games"
                form={recent_form}
                highlight
              />
              <StatCard
                title={`All ${big_picture.games} Games`}
                form={big_picture}
              />
            </div>
          </motion.div>
        ) : big_picture?.games > 0 && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }} className="mb-8">
            <Label>Your Stats ({big_picture.games} game{big_picture.games !== 1 ? "s" : ""})</Label>
            <div className="grid grid-cols-1 gap-3">
              <StatCard
                title={`${big_picture.games} Game${big_picture.games !== 1 ? "s" : ""} Analyzed`}
                form={big_picture}
                highlight
              />
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              Play more games to see your improvement trend. Need 6+ for comparison.
            </p>
          </motion.div>
        )}

        {/* ── WEAKNESS TRENDS ── */}
        {weakness_control && weakness_control.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="mb-8">
            <Label>Weakness Trends</Label>
            <div className="space-y-2">
              {weakness_control.map((w) => (
                <div
                  key={w.pattern}
                  className={`bg-card border rounded-xl p-4 cursor-pointer transition-all hover:border-primary/20 ${
                    w.direction === "improving" ? "border-emerald-500/20" :
                    w.direction === "worsening" ? "border-red-500/20" :
                    "border-border"
                  }`}
                  onClick={() => navigate(`/training?focus=${w.pattern}`)}
                  data-testid={`weakness-${w.pattern}`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2.5">
                      <DirectionIcon direction={w.direction} />
                      <span className="text-sm font-medium text-foreground">{w.label}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <WeaknessBar total={w.total} recent={w.recent} direction={w.direction} />
                      <span className="text-xs font-mono text-muted-foreground">{w.total}x</span>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed ml-6">{w.message}</p>
                </div>
              ))}
            </div>
          </motion.div>
        )}

        {/* ── STRENGTH PROFILE ── */}
        {strengthProfile && strengthProfile.domains && Object.keys(strengthProfile.domains).length > 0 && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }} className="mb-8">
            <div className="flex items-center justify-between mb-2.5">
              <Label>Your Strengths</Label>
              {strengthProfile.headline_stats?.brilliant_moves > 0 && (
                <span className="inline-flex items-center gap-1 text-xs font-mono text-amber-400">
                  <Zap className="w-3 h-3" strokeWidth={2} />
                  {strengthProfile.headline_stats.brilliant_moves} brilliant
                </span>
              )}
            </div>
            <div className="bg-card border border-border rounded-xl p-5">
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                {STRENGTH_DOMAINS.map(({ key, label, icon: Icon }) => {
                  const domain = strengthProfile.domains[key];
                  if (!domain) return null;
                  const isStrongest = strengthProfile.strongest === key;
                  const isWeakest = strengthProfile.weakest === key;
                  return (
                    <div key={key} className={`text-center p-3 rounded-lg border ${
                      isStrongest ? 'border-emerald-500/20 bg-emerald-500/5' :
                      isWeakest ? 'border-red-500/15 bg-red-500/5' :
                      'border-transparent'
                    }`}>
                      <Icon className={`w-4 h-4 mx-auto mb-1.5 ${
                        isStrongest ? 'text-emerald-500' : isWeakest ? 'text-red-400' : 'text-muted-foreground'
                      }`} strokeWidth={1.5} />
                      <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">{label}</p>
                      <p className={`text-lg font-mono font-semibold ${
                        domain.score >= 70 ? 'text-emerald-500' :
                        domain.score >= 40 ? 'text-foreground' :
                        'text-red-400'
                      }`}>{domain.score}</p>
                      {isStrongest && <span className="text-[8px] font-bold uppercase text-emerald-500 tracking-wider">best</span>}
                      {isWeakest && <span className="text-[8px] font-bold uppercase text-red-400 tracking-wider">focus</span>}
                    </div>
                  );
                })}
              </div>
            </div>
          </motion.div>
        )}

        {/* ── PHASE UNDERSTANDING ── */}
        {phase_understanding && Object.keys(phase_understanding).length > 1 && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="mb-8">
            <Label>Game Phase Accuracy</Label>
            <div className="grid grid-cols-3 gap-3">
              {[
                { key: "opening", label: "Opening", icon: Crown },
                { key: "middlegame", label: "Middlegame", icon: Swords },
                { key: "endgame", label: "Endgame", icon: Shield },
              ].map(({ key, label, icon: Icon }) => {
                const phase = phase_understanding[key];
                if (!phase) return null;
                const isWeakest = phase_understanding.weakest === key;
                return (
                  <div key={key} className={`bg-card border rounded-xl p-4 text-center ${isWeakest ? "border-red-500/20" : "border-border"}`} data-testid={`phase-${key}`}>
                    <Icon className={`w-4 h-4 mx-auto mb-2 ${isWeakest ? "text-red-400" : "text-muted-foreground"}`} strokeWidth={1.5} />
                    <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">{label}</p>
                    {phase.score > 0 ? (
                      <>
                        <p className={`text-xl font-mono font-semibold ${
                          phase.score >= 80 ? "text-emerald-500" : phase.score >= 60 ? "text-foreground" : "text-red-400"
                        }`}>{phase.score.toFixed(0)}%</p>
                        <DirectionIcon direction={phase.direction} small />
                      </>
                    ) : (
                      <p className="text-xs text-muted-foreground/50 mt-1">No data</p>
                    )}
                    {isWeakest && phase.score > 0 && (
                      <span className="text-[8px] uppercase text-red-400 font-bold tracking-wider mt-1 block">weakest</span>
                    )}
                  </div>
                );
              })}
            </div>
          </motion.div>
        )}

        {/* ── REVIEW IMPACT ── */}
        {review_impact?.has_data && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }} className="mb-8">
            <Label>Review Impact</Label>
            <div className={`bg-card border rounded-xl p-5 ${review_impact.improving ? "border-emerald-500/20" : "border-border"}`} data-testid="review-impact">
              <div className="flex items-center gap-2 mb-3">
                <FlaskConical className={`w-4 h-4 ${review_impact.improving ? "text-emerald-500" : "text-muted-foreground"}`} strokeWidth={1.5} />
                <span className="text-sm text-foreground font-medium">{review_impact.games_reviewed} games reviewed</span>
              </div>

              <div className="grid grid-cols-2 gap-4 mb-3">
                <MetricChange
                  label="Blunder Rate"
                  before={`${review_impact.before_blunders}/g`}
                  after={`${review_impact.after_blunders}/g`}
                  improved={review_impact.after_blunders < review_impact.before_blunders}
                  pct={review_impact.blunder_change_pct}
                />
                <MetricChange
                  label="Accuracy"
                  before={`${review_impact.before_accuracy.toFixed(0)}%`}
                  after={`${review_impact.after_accuracy.toFixed(0)}%`}
                  improved={review_impact.accuracy_change > 0}
                  pct={review_impact.accuracy_change}
                  pctSuffix=""
                />
              </div>

              <p className="text-xs text-muted-foreground leading-relaxed">
                {review_impact.improving
                  ? "Reviewing is working. Your play is measurably better after reviews."
                  : "Keep reviewing. The impact takes a few more games to show."}
              </p>
            </div>
          </motion.div>
        )}

        {/* ── GAME TIMELINE ── */}
        {game_stats && game_stats.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} className="mb-8">
            <Label>Recent Games</Label>
            <div className="bg-card border border-border rounded-xl p-4">
              <div className="flex items-end gap-1 h-20">
                {game_stats.slice(-20).map((g, i) => {
                  const height = Math.max(8, (g.accuracy / 100) * 100);
                  const color = g.result === "W" ? "bg-emerald-500" : g.result === "L" ? "bg-red-400" : "bg-muted-foreground/40";
                  return (
                    <div
                      key={g.game_id || i}
                      className="flex-1 flex flex-col items-center justify-end cursor-pointer group"
                      onClick={() => navigate(`/game/${g.game_id}`)}
                      title={`vs ${g.opponent} · ${g.accuracy.toFixed(0)}% · ${g.result}`}
                    >
                      <div
                        className={`w-full max-w-[12px] rounded-t-sm ${color} group-hover:opacity-80 transition-all`}
                        style={{ height: `${height}%` }}
                      />
                    </div>
                  );
                })}
              </div>
              <div className="flex justify-between mt-2 text-[9px] text-muted-foreground/30 font-mono">
                <span>older</span>
                <span>recent</span>
              </div>
            </div>
          </motion.div>
        )}

        {/* ── FOOTER ── */}
        <div className="text-center text-[10px] text-muted-foreground/40 font-mono pb-4">
          {report.total_games} games analyzed
        </div>
      </div>
    </Layout>
  );
};


// ── Strength Domains Config ──
const STRENGTH_DOMAINS = [
  { key: "tactical_vision", label: "Tactics", icon: Zap },
  { key: "calculation_depth", label: "Calculation", icon: Brain },
  { key: "positional_sense", label: "Positional", icon: Target },
  { key: "endgame_technique", label: "Endgame", icon: Crown },
  { key: "opening_knowledge", label: "Openings", icon: BookOpen },
  { key: "pressure_handling", label: "Pressure", icon: Shield },
];


// ── Components ──

const Label = ({ children }) => (
  <p className="text-[10px] tracking-[0.15em] uppercase mb-2.5 font-bold text-muted-foreground/70">{children}</p>
);

const StatCard = ({ title, form, highlight }) => {
  if (!form?.games) return null;
  return (
    <div className={`bg-card border rounded-xl p-4 ${highlight ? "border-primary/15" : "border-border"}`} data-testid={`form-${form.label}`}>
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-2">{title}</p>
      <div className="flex items-baseline gap-1.5 mb-2">
        <span className="text-2xl font-mono font-semibold text-foreground">
          {form.accuracy > 0 ? `${form.accuracy.toFixed(0)}%` : "\u2014"}
        </span>
        <span className="text-[10px] text-muted-foreground/50">accuracy</span>
      </div>
      <div className="flex items-center gap-2 text-xs font-mono">
        <span className="text-emerald-500 font-medium">{form.wins}W</span>
        <span className="text-red-400 font-medium">{form.losses}L</span>
        {form.draws > 0 && <span className="text-muted-foreground">{form.draws}D</span>}
        <span className="text-muted-foreground/30">&middot;</span>
        <span className="text-muted-foreground">{form.blunder_rate}/g blunders</span>
      </div>
    </div>
  );
};

const MetricChange = ({ label, before, after, improved, pct, pctSuffix = "%" }) => (
  <div>
    <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">{label}</p>
    <div className="flex items-center gap-1.5">
      <span className="text-sm font-mono text-muted-foreground">{before}</span>
      <span className="text-muted-foreground/30">&rarr;</span>
      <span className={`text-sm font-mono font-medium ${improved ? "text-emerald-500" : "text-red-400"}`}>{after}</span>
      {pct !== 0 && pct !== undefined && (
        <span className={`text-[10px] ${improved ? "text-emerald-500" : "text-red-400"}`}>
          ({pct > 0 ? "+" : ""}{typeof pct === 'number' ? pct.toFixed(pctSuffix ? 0 : 1) : pct}{pctSuffix})
        </span>
      )}
    </div>
  </div>
);

const DirectionIcon = ({ direction, small }) => {
  const size = small ? "w-3 h-3" : "w-3.5 h-3.5";
  if (direction === "improving") return <TrendingDown className={`${size} text-emerald-500`} strokeWidth={1.5} />;
  if (direction === "worsening") return <TrendingUp className={`${size} text-red-400`} strokeWidth={1.5} />;
  return <Minus className={`${size} text-muted-foreground/40`} strokeWidth={1.5} />;
};

const WeaknessBar = ({ total, recent, direction }) => {
  const maxWidth = 80;
  const recentWidth = Math.min((recent / Math.max(total, 1)) * maxWidth, maxWidth);
  const color = direction === "improving" ? "#16a34a" : direction === "worsening" ? "#EF4444" : "#888";
  return (
    <div className="w-20 h-1.5 bg-muted rounded-full overflow-hidden">
      <div className="h-full rounded-full transition-all" style={{ width: `${recentWidth}px`, background: color }} />
    </div>
  );
};

export default UnifiedProgress;
