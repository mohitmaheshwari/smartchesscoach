/**
 * PROGRESS PAGE — Coaching Progress Report
 * 
 * Not a stats dashboard. A coach telling you how you're growing.
 * 
 * Sections:
 * 1. Coaching headline + recent form vs big picture
 * 2. Weakness control (are patterns shrinking?)
 * 3. Phase understanding (opening/middlegame/endgame)
 * 4. Review impact (did reviewing help?)
 * 5. Game timeline (accuracy dots, clickable)
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import {
  TrendingUp, TrendingDown, Minus, AlertTriangle,
  ChevronRight, FlaskConical, Check, Shield,
  Crosshair, Crown, Swords
} from "lucide-react";

const UnifiedProgress = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [report, setReport] = useState(null);

  useEffect(() => {
    fetch(`${API}/progress/coaching-report`, { credentials: "include" })
      .then(r => r.ok ? r.json() : null)
      .then(d => setReport(d))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center h-[60vh]">
          <div className="w-5 h-5 border border-border border-t-foreground/50 rounded-full animate-spin" />
        </div>
      </Layout>
    );
  }

  if (!report?.has_data) {
    return (
      <Layout user={user}>
        <div className="max-w-xl mx-auto px-4 py-16 text-center" data-testid="progress-page">
          <h1 className="text-2xl text-foreground tracking-tight mb-3" style={{ fontFamily: "'Playfair Display', serif" }}>Progress</h1>
          <p className="text-sm text-muted-foreground mb-6">Play and analyze a few games to see your coaching report.</p>
          <button onClick={() => navigate("/import")} className="px-5 py-2.5 text-sm bg-foreground text-background rounded-lg hover:opacity-90 transition-opacity">
            Import Games
          </button>
        </div>
      </Layout>
    );
  }

  const { headline, recent_form, big_picture, weakness_control, habits_evolution, phase_understanding, review_impact, game_stats } = report;

  return (
    <Layout user={user}>
      <div className="max-w-3xl mx-auto px-4 py-6" data-testid="progress-page">

        {/* ── HEADLINE ── */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mb-8">
          <h1 className="text-2xl text-foreground tracking-tight mb-1.5" style={{ fontFamily: "'Playfair Display', serif" }}>
            Progress
          </h1>
          <p className="text-sm text-muted-foreground leading-relaxed" data-testid="coaching-headline">{headline}</p>
        </motion.div>

        {/* ── RECENT FORM vs BIG PICTURE ── */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }} className="mb-8">
          <div className="grid grid-cols-2 gap-3">
            <FormCard
              title="Last 5 Games"
              form={recent_form}
              isCurrent
            />
            <FormCard
              title="Overall"
              form={big_picture}
            />
          </div>
        </motion.div>

        {/* ── WEAKNESS CONTROL ── */}
        {weakness_control.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="mb-8">
            <Label>Your Weaknesses — Are They Shrinking?</Label>
            <div className="space-y-2.5">
              {weakness_control.map((w) => (
                <div
                  key={w.pattern}
                  className={`bg-card border rounded-lg p-4 cursor-pointer transition-all hover:shadow-sm ${
                    w.direction === "worsening" ? "border-red-500/30 hover:border-red-500/50" :
                    w.direction === "improving" ? "border-emerald-500/30 hover:border-emerald-500/50" :
                    "border-border hover:border-border"
                  }`}
                  onClick={() => navigate(`/training?focus=${w.pattern}`)}
                  data-testid={`weakness-${w.pattern}`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-2">
                      <DirectionIcon direction={w.direction} />
                      <span className="text-sm font-medium text-foreground">{w.label}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <WeaknessBar total={w.total} recent={w.recent} direction={w.direction} />
                      <span className="text-xs text-muted-foreground" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{w.total}x total</span>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">{w.message}</p>
                </div>
              ))}
            </div>
          </motion.div>
        )}

        {/* ── PHASE UNDERSTANDING ── */}
        {phase_understanding && Object.keys(phase_understanding).length > 1 && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }} className="mb-8">
            <Label>Chess Understanding by Phase</Label>
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
                  <div
                    key={key}
                    className={`bg-card border rounded-lg p-4 text-center ${isWeakest ? "border-red-500/30" : "border-border"}`}
                    data-testid={`phase-${key}`}
                  >
                    <Icon className={`w-4 h-4 mx-auto mb-2 ${isWeakest ? "text-red-500" : "text-muted-foreground"}`} strokeWidth={1.5} />
                    <p className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground mb-1">{label}</p>
                    {phase.score > 0 ? (
                      <>
                        <p className={`text-xl font-light ${
                          phase.score >= 80 ? "text-emerald-600 dark:text-emerald-400" :
                          phase.score >= 60 ? "text-foreground" :
                          "text-red-500"
                        }`} style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                          {phase.score.toFixed(0)}%
                        </p>
                        <DirectionIcon direction={phase.direction} small />
                      </>
                    ) : (
                      <p className="text-xs text-muted-foreground/50 mt-1">No data yet</p>
                    )}
                    {isWeakest && phase.score > 0 && (
                      <span className="text-[8px] uppercase text-red-500 font-bold tracking-wider mt-1 block">weakest</span>
                    )}
                  </div>
                );
              })}
            </div>
          </motion.div>
        )}

        {/* ── REVIEW IMPACT ── */}
        {review_impact?.has_data && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="mb-8">
            <Label>Review Impact</Label>
            <div className={`bg-card border rounded-lg p-5 ${review_impact.improving ? "border-emerald-500/20" : "border-border"}`} data-testid="review-impact">
              <div className="flex items-center gap-2 mb-3">
                <FlaskConical className={`w-4 h-4 ${review_impact.improving ? "text-emerald-500" : "text-muted-foreground"}`} strokeWidth={1.5} />
                <span className="text-sm text-foreground font-medium">
                  {review_impact.games_reviewed} games reviewed
                </span>
              </div>
              
              <div className="grid grid-cols-2 gap-4 mb-3">
                <div>
                  <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">Blunder Rate</p>
                  <div className="flex items-center gap-1.5">
                    <span className="text-muted-foreground text-sm" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{review_impact.before_blunders}/g</span>
                    <span className="text-muted-foreground/30">→</span>
                    <span className={`text-sm font-medium ${review_impact.after_blunders < review_impact.before_blunders ? "text-emerald-600 dark:text-emerald-400" : "text-red-500"}`} style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {review_impact.after_blunders}/g
                    </span>
                    {review_impact.blunder_change_pct !== 0 && (
                      <span className={`text-[10px] ${review_impact.blunder_change_pct < 0 ? "text-emerald-600" : "text-red-500"}`}>
                        ({review_impact.blunder_change_pct > 0 ? "+" : ""}{review_impact.blunder_change_pct.toFixed(0)}%)
                      </span>
                    )}
                  </div>
                </div>
                <div>
                  <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">Accuracy</p>
                  <div className="flex items-center gap-1.5">
                    <span className="text-muted-foreground text-sm" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{review_impact.before_accuracy.toFixed(0)}%</span>
                    <span className="text-muted-foreground/30">→</span>
                    <span className={`text-sm font-medium ${review_impact.accuracy_change > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-500"}`} style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {review_impact.after_accuracy.toFixed(0)}%
                    </span>
                    {review_impact.accuracy_change !== 0 && (
                      <span className={`text-[10px] ${review_impact.accuracy_change > 0 ? "text-emerald-600" : "text-red-500"}`}>
                        ({review_impact.accuracy_change > 0 ? "+" : ""}{review_impact.accuracy_change.toFixed(1)})
                      </span>
                    )}
                  </div>
                </div>
              </div>
              
              <p className="text-xs text-muted-foreground leading-relaxed">
                {review_impact.improving
                  ? "Reviewing is working. Your play is measurably better after reviews."
                  : "Keep reviewing. The impact takes a few more games to show."
                }
              </p>
            </div>
          </motion.div>
        )}

        {/* ── GAME TIMELINE ── */}
        {game_stats.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }} className="mb-8">
            <Label>Game Timeline</Label>
            <div className="bg-card border border-border rounded-lg p-4">
              <div className="space-y-1">
                {game_stats.slice(-15).map((g, i) => {
                  const barWidth = Math.max(g.accuracy, 8);
                  const barColor = g.result === "W" ? "#16a34a" : g.result === "L" ? "#EF4444" : "#888";
                  return (
                    <div
                      key={g.game_id}
                      className="flex items-center gap-2 cursor-pointer group py-1 hover:bg-muted/20 rounded px-1 -mx-1 transition-colors"
                      onClick={() => navigate(`/game/${g.game_id}`)}
                      data-testid={`timeline-game-${i}`}
                    >
                      <span className="text-[10px] text-muted-foreground w-14 truncate" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                        {g.opponent.substring(0, 8)}
                      </span>
                      <div className="flex-1 h-5 bg-muted/30 rounded overflow-hidden relative">
                        <div
                          className="h-full rounded transition-all"
                          style={{ width: `${barWidth}%`, background: barColor, opacity: 0.7 }}
                        />
                        <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[9px] text-foreground/60" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                          {g.accuracy.toFixed(0)}%
                        </span>
                      </div>
                      <span className={`text-[9px] w-5 text-center font-bold ${g.result === "W" ? "text-emerald-600" : g.result === "L" ? "text-red-500" : "text-muted-foreground"}`}>
                        {g.result}
                      </span>
                      {g.lesson_label && (
                        <span className="text-[8px] text-amber-700 dark:text-amber-400 uppercase tracking-wider font-bold w-28 truncate hidden sm:block">
                          {g.lesson_label}
                        </span>
                      )}
                      {g.reviewed && <Check className="w-3 h-3 text-emerald-500/50 flex-shrink-0" />}
                    </div>
                  );
                })}
              </div>
              <div className="flex justify-between mt-2 text-[9px] text-muted-foreground/30" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                <span>older</span>
                <span>recent</span>
              </div>
            </div>
          </motion.div>
        )}

        {/* ── FOOTER ── */}
        <div className="text-center text-[10px] text-muted-foreground/40 pb-4" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
          {report.total_games} games analyzed
        </div>
      </div>
    </Layout>
  );
};


// ── Components ──

const Label = ({ children }) => (
  <p className="text-[10px] tracking-[0.15em] uppercase mb-2.5 font-bold text-muted-foreground">{children}</p>
);

const FormCard = ({ title, form, isCurrent }) => {
  if (!form?.games) return null;
  return (
    <div className={`bg-card border rounded-lg p-4 ${isCurrent ? "border-primary/20" : "border-border"}`} data-testid={`form-${form.label}`}>
      <p className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground mb-2">{title}</p>
      <div className="flex items-baseline gap-1.5 mb-2">
        <span className="text-xl font-light text-foreground" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
          {form.accuracy > 0 ? `${form.accuracy.toFixed(0)}%` : "—"}
        </span>
        <span className="text-[10px] text-muted-foreground/50">accuracy</span>
      </div>
      <div className="flex items-center gap-2 text-xs">
        <span className="text-emerald-600 font-medium" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{form.wins}W</span>
        <span className="text-red-500 font-medium" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{form.losses}L</span>
        {form.draws > 0 && <span className="text-muted-foreground" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{form.draws}D</span>}
        <span className="text-muted-foreground/30 mx-0.5">·</span>
        <span className="text-muted-foreground" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{form.blunder_rate}/g blunders</span>
      </div>
    </div>
  );
};

const DirectionIcon = ({ direction, small }) => {
  const size = small ? "w-3 h-3" : "w-3.5 h-3.5";
  if (direction === "improving") return <TrendingDown className={`${size} text-emerald-500`} strokeWidth={1.5} />;
  if (direction === "worsening") return <TrendingUp className={`${size} text-red-500`} strokeWidth={1.5} />;
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
