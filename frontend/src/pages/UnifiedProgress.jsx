/**
 * PROGRESS — Your chess journey dashboard
 *
 * Professional, clean design showing:
 * - Focus area with before/after proof
 * - Opening repertoire with win rates
 * - Recent game results
 * - Clear next actions
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import {
  ChevronRight, Target, Swords, Check, X as XIcon, ArrowRight,
  Crown, BookOpen, TrendingUp, TrendingDown, Minus,
  Activity, Flame, Shield, Loader2, Zap
} from "lucide-react";
import LichessBoard from "@/components/LichessBoard";

const UnifiedProgress = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [progress, setProgress] = useState(null);
  const [openings, setOpenings] = useState(null);
  const [narrative, setNarrative] = useState(null);
  const [proof, setProof] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const [progressRes, openingsRes, narrativeRes, proofRes] = await Promise.all([
          fetch(`${API}/progress/real`, { credentials: "include" }),
          fetch(`${API}/coach/play/opening-suggestions`, { credentials: "include" }),
          fetch(`${API}/progress/narrative`, { credentials: "include" }),
          fetch(`${API}/progress/improvement-proof`, { credentials: "include" }),
        ]);
        if (progressRes.ok) setProgress(await progressRes.json());
        if (openingsRes.ok) setOpenings(await openingsRes.json());
        if (narrativeRes.ok) setNarrative(await narrativeRes.json());
        if (proofRes.ok) setProof(await proofRes.json());
      } catch (e) { console.error(e); }
      finally { setLoading(false); }
    })();
  }, []);

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center h-[60vh]">
          <Loader2 className="w-6 h-6 text-primary animate-spin" />
        </div>
      </Layout>
    );
  }

  const state = progress?.state || "not_started";

  return (
    <Layout user={user}>
      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-8" data-testid="progress-page">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          {/* Page Header */}
          <div className="mb-8">
            <h1 className="text-2xl font-bold text-foreground tracking-tight">Your Progress</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Track your improvement and see what's working.
            </p>
          </div>

          {/* Narrative: Who You Are */}
          {narrative?.who_you_are && <NarrativeSection
            title={null}
            content={<>
              <p className="text-sm text-foreground leading-relaxed">{narrative.who_you_are.style}</p>
              <p className="text-xs text-muted-foreground mt-1.5">{narrative.who_you_are.record}</p>
            </>}
          />}

          {/* Proof of Improvement — OR Journey (not both, to avoid contradiction) */}
          {proof?.has_data && proof?.primary_pattern?.reduction_pct > 0 ? (
            <ImprovementProof proof={proof} />
          ) : narrative?.journey ? (
            <JourneyCard journey={narrative.journey} />
          ) : null}

          {/* Narrative: What You Do Well */}
          {narrative?.strengths?.length > 0 && <NarrativeSection
            title="What you do well"
            icon={<Check className="w-4 h-4 text-emerald-500" strokeWidth={2.5} />}
            content={
              <div className="space-y-2">
                {narrative.strengths.map((s, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <Check className="w-3.5 h-3.5 text-emerald-500 mt-0.5 flex-shrink-0" strokeWidth={2.5} />
                    <p className="text-sm text-foreground leading-snug">{s}</p>
                  </div>
                ))}
              </div>
            }
          />}

          {/* Narrative: What Costs You Games */}
          {narrative?.weaknesses?.length > 0 && <NarrativeSection
            title="What costs you games"
            icon={<Target className="w-4 h-4 text-red-400" strokeWidth={2} />}
            content={
              <div className="space-y-3">
                {narrative.weaknesses.map((w, i) => (
                  <p key={i} className="text-sm text-foreground leading-snug">{w.description}</p>
                ))}
              </div>
            }
          />}

          {/* Your Openings — merged: coach stories + real game win rates */}
          {(narrative?.openings?.length > 0 || (openings && openings.total_games > 0)) && (
            <NarrativeSection
              title="Your openings"
              icon={<BookOpen className="w-4 h-4 text-primary" strokeWidth={2} />}
              content={
                <div className="space-y-3">
                  {/* Coach session openings with stories (deduplicated) */}
                  {narrative?.openings?.filter((o, i, arr) => arr.findIndex(x => x.name === o.name) === i).map((o, i) => {
                    // Find matching win rate from real games
                    const allReal = [...(openings?.white || []), ...(openings?.black || [])];
                    const match = allReal.find(r => r.name?.toLowerCase().includes(o.name?.toLowerCase().split(" ")[0]));
                    return (
                      <div key={i}
                        onClick={() => navigate(`/play-with-coach?opening=${encodeURIComponent(o.name)}`)}
                        className="p-3 rounded-xl bg-muted/30 hover:bg-muted/50 cursor-pointer transition-all"
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm font-medium text-foreground">{o.name}</span>
                          <div className="flex items-center gap-2">
                            {match && (
                              <span className={`text-xs font-mono ${match.win_rate >= 50 ? "text-emerald-600" : "text-muted-foreground"}`}>
                                {match.win_rate}% in {match.games}g
                              </span>
                            )}
                            <span className="text-[10px] text-muted-foreground">{o.games} with coach</span>
                          </div>
                        </div>
                        <p className="text-xs text-muted-foreground leading-snug">{o.story}</p>
                      </div>
                    );
                  })}

                  {/* Real game openings NOT covered by coach sessions */}
                  {openings && [...(openings.white || []), ...(openings.black || [])].filter(r => {
                    const coachNames = (narrative?.openings || []).map(o => o.name?.toLowerCase().split(" ")[0]);
                    return !coachNames.some(cn => r.name?.toLowerCase().includes(cn));
                  }).slice(0, 4).map((r, i) => (
                    <div key={`real-${i}`}
                      onClick={() => navigate(`/play-with-coach?opening=${encodeURIComponent(r.name)}`)}
                      className="p-3 rounded-xl hover:bg-muted/50 cursor-pointer transition-all flex items-center justify-between"
                    >
                      <span className="text-sm text-foreground">{r.name}</span>
                      <div className="flex items-center gap-2">
                        <span className={`text-xs font-mono ${r.win_rate >= 50 ? "text-emerald-600" : "text-muted-foreground"}`}>
                          {r.win_rate}%
                        </span>
                        <span className="text-[10px] text-muted-foreground">{r.games}g</span>
                      </div>
                    </div>
                  ))}
                </div>
              }
            />
          )}

          {/* Narrative: Next Step */}
          {narrative?.next_step && (
            <div className="rounded-2xl border-2 border-primary/20 bg-primary/[0.03] p-5 mb-6">
              <p className="text-[10px] uppercase tracking-widest font-bold text-primary mb-2">Next step</p>
              <p className="text-sm text-foreground leading-relaxed mb-4">{narrative.next_step}</p>
              <button
                onClick={() => navigate("/play-with-coach")}
                className="w-full py-3 text-sm font-semibold rounded-xl bg-foreground text-background hover:opacity-90 transition-all flex items-center justify-center gap-2"
              >
                <Swords className="w-4 h-4" strokeWidth={2} />
                Play with Coach
                <ChevronRight className="w-4 h-4 opacity-60" />
              </button>
            </div>
          )}

          {/* Focus Area — removed, replaced by focus plan on Home page */}

          {/* Quick Actions */}
          <QuickActions state={state} progress={progress} navigate={navigate} />

        </motion.div>
      </div>
    </Layout>
  );
};


// ─── Improvement Proof ──────────────────────────────────────────

const ImprovementProof = ({ proof }) => {
  const primary = proof.primary_pattern;
  const examples = proof.before_after || [];
  const streaks = proof.streaks || {};
  const acc = proof.accuracy || {};

  if (!primary || primary.reduction_pct <= 0) return null;

  // Streak text
  const streakParts = [];
  if (streaks.no_blunder_games >= 2) streakParts.push(`${streaks.no_blunder_games} games with no blunders`);
  if (streaks.no_big_mistake_games >= 2) streakParts.push(`${streaks.no_big_mistake_games} games without a major mistake`);
  if (streaks.no_threat_miss_games >= 3) streakParts.push(`${streaks.no_threat_miss_games} games without missing a threat`);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.15 }}
      className="rounded-2xl border-2 border-emerald-500/20 bg-emerald-500/[0.03] p-5 mb-6"
    >
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <div className="w-8 h-8 rounded-lg bg-emerald-500/15 flex items-center justify-center">
          <TrendingUp className="w-4 h-4 text-emerald-500" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-foreground">
            You're improving in {primary.label}
          </h3>
          <p className="text-xs text-muted-foreground">{primary.description}</p>
        </div>
      </div>

      {/* Stats */}
      <div className="flex items-center gap-4 mb-4">
        <div className="text-center">
          <p className="text-2xl font-bold font-mono text-emerald-500">{primary.reduction_pct}%</p>
          <p className="text-[10px] text-muted-foreground">fewer mistakes</p>
        </div>
        <div className="text-xs text-muted-foreground leading-relaxed">
          <p>{primary.old_per_game}/game → {primary.new_per_game}/game</p>
          {streakParts.length > 0 && (
            <p className="text-emerald-500/70 mt-0.5">
              Current streak: {streakParts.join(", ")}
            </p>
          )}
        </div>
      </div>

      {/* Before vs After Boards — only show FIRST example */}
      {examples.length > 0 && (
        <div>
          {[examples[0]].map((ex, i) => (
            <div key={i}>
              <p className="text-xs text-muted-foreground mb-2">{ex.message}</p>
              <div className="grid grid-cols-2 gap-3">
                {/* Before board */}
                <div>
                  <p className="text-[10px] uppercase tracking-widest font-bold text-red-400/60 mb-1">Before</p>
                  <div className="rounded-lg overflow-hidden border border-red-500/20">
                    <LichessBoard
                      fen={ex.old_fen}
                      viewOnly={true}
                      width={180}
                    />
                  </div>
                  <p className="text-[10px] text-muted-foreground mt-1">
                    Move {ex.old_move_number}: <span className="font-mono text-red-400">{ex.old_move}</span>
                    <span className="text-red-400/50 ml-1">mistake</span>
                  </p>
                </div>

                {/* After board */}
                <div>
                  <p className="text-[10px] uppercase tracking-widest font-bold text-emerald-400/60 mb-1">Now</p>
                  <div className="rounded-lg overflow-hidden border border-emerald-500/20">
                    <LichessBoard
                      fen={ex.new_fen}
                      viewOnly={true}
                      width={180}
                    />
                  </div>
                  <p className="text-[10px] text-muted-foreground mt-1">
                    Move {ex.new_move_number}: <span className="font-mono text-emerald-400">{ex.new_move}</span>
                    <span className="text-emerald-400/50 ml-1">clean</span>
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Accuracy improvement */}
      {acc.delta > 0 && (
        <p className="text-xs text-muted-foreground mt-3">
          Overall accuracy: {acc.older}% → {acc.recent}%
          <span className="text-emerald-500 ml-1">(+{acc.delta}%)</span>
        </p>
      )}

      {/* Emotional close */}
      <p className="text-sm text-foreground mt-4 font-medium">
        This used to happen every game. Now it doesn't.
      </p>
    </motion.div>
  );
};


// ─── Narrative Section (generic card) ────────────────────────────

const NarrativeSection = ({ title, icon, content }) => (
  <div className="rounded-2xl border border-border bg-card p-5 mb-6">
    {title && (
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      </div>
    )}
    {content}
  </div>
);


// ─── Journey Card ───────────────────────────────────────────────

const JourneyCard = ({ journey }) => {
  const verdictConfig = {
    improving: { icon: <TrendingUp className="w-5 h-5 text-emerald-500" />, bg: "border-emerald-500/20 bg-emerald-500/[0.03]" },
    slipping: { icon: <TrendingDown className="w-5 h-5 text-red-400" />, bg: "border-red-400/20 bg-red-500/[0.03]" },
    mixed: { icon: <Activity className="w-5 h-5 text-amber-500" />, bg: "border-amber-400/20 bg-amber-500/[0.03]" },
    steady: { icon: <Minus className="w-5 h-5 text-muted-foreground" />, bg: "border-border" },
    early: { icon: <Activity className="w-5 h-5 text-blue-500" />, bg: "border-blue-400/20 bg-blue-500/[0.03]" },
  };
  const config = verdictConfig[journey.verdict] || verdictConfig.steady;

  return (
    <div className={`rounded-2xl border-2 ${config.bg} p-5 mb-6`}>
      <div className="flex items-start gap-3">
        <div className="mt-0.5">{config.icon}</div>
        <div>
          <h3 className="text-sm font-semibold text-foreground mb-1">Your Journey</h3>
          <p className="text-sm text-foreground leading-relaxed">{journey.story}</p>
        </div>
      </div>
    </div>
  );
};


// ─── Focus Card ─────────────────────────────────────────────────

// NOTE: Score-based components (PlayerHeader, ThinkingHabits, PhaseAccuracy,
// AccuracyTrend, PatternLifecycle, OpeningMastery) were removed.
// The narrative sections above replace them with human-readable stories.

const _UNUSED_PlayerHeader = ({ profile }) => {
  const identity = profile.identity;
  const strength = profile.strength;
  const memory = profile.coach_memory;
  if (!identity && !strength && !memory) return null;

  const style = identity?.style_profile?.primary_style;
  const gamesPlayed = identity?.games_analyzed || memory?.games_played || 0;
  const wins = identity?.total_wins || 0;
  const losses = identity?.total_losses || 0;
  const draws = identity?.total_draws || 0;
  const winRate = gamesPlayed > 0 ? Math.round((wins / gamesPlayed) * 100) : 0;

  return (
    <div className="rounded-2xl border border-border bg-card p-5 mb-6">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h2 className="text-base font-semibold text-foreground">
            {style ? style.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()) : "Your Profile"}
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            {gamesPlayed} games analyzed
            {memory?.avg_accuracy ? ` · ${Math.round(memory.avg_accuracy)}% avg accuracy` : ""}
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="text-emerald-600 font-mono">{wins}W</span>
          <span className="text-muted-foreground font-mono">{draws}D</span>
          <span className="text-red-400 font-mono">{losses}L</span>
        </div>
      </div>

      {/* Strength domains */}
      {strength?.domains && Object.keys(strength.domains).length > 0 && (
        <div className="grid grid-cols-3 gap-2">
          {Object.entries(strength.domains).slice(0, 6).map(([key, val]) => {
            const score = val?.score || 0;
            const color = score >= 70 ? "text-emerald-500 bg-emerald-500" :
                          score >= 40 ? "text-amber-500 bg-amber-500" :
                          "text-red-400 bg-red-400";
            return (
              <div key={key} className="text-center p-2 rounded-lg bg-muted/30">
                <div className="w-full h-1 bg-muted rounded-full mb-1.5 overflow-hidden">
                  <div className={`h-full rounded-full ${color.split(" ")[1]}`} style={{ width: `${score}%` }} />
                </div>
                <p className="text-[10px] text-muted-foreground truncate">{key.replace(/_/g, " ")}</p>
                <p className={`text-xs font-mono font-semibold ${color.split(" ")[0]}`}>{score}</p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};


// ─── Thinking Habits ────────────────────────────────────────────

const HABIT_LABELS = {
  threat_awareness: "Seeing opponent threats",
  tactical_vision: "Finding tactics",
  move_verification: "Double-checking before moving",
  king_safety: "Keeping your king safe",
  patience: "Not rushing moves",
};

const ThinkingHabits = ({ data }) => {
  const habits = data.habits || {};
  if (Object.keys(habits).length === 0) return null;

  return (
    <div className="rounded-2xl border border-border bg-card p-5 mb-6">
      <div className="flex items-center gap-2.5 mb-4">
        <div className="w-8 h-8 rounded-lg bg-purple-500/10 flex items-center justify-center">
          <Activity className="w-4 h-4 text-purple-500" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-foreground">Thinking Habits</h3>
          <p className="text-[10px] text-muted-foreground">Last {data.games_sampled} games averaged</p>
        </div>
        <span className="ml-auto text-lg font-bold font-mono text-foreground">{data.overall}</span>
      </div>

      <div className="space-y-2">
        {Object.entries(habits).map(([key, score]) => {
          const label = HABIT_LABELS[key] || key.replace(/_/g, " ");
          const color = score >= 70 ? "bg-emerald-500" : score >= 40 ? "bg-amber-400" : "bg-red-400";
          return (
            <div key={key} className="flex items-center gap-3">
              <span className="text-xs text-muted-foreground w-48 text-right">{label}</span>
              <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${color}`} style={{ width: `${score}%` }} />
              </div>
              <span className="text-xs font-mono w-6 text-right">{score}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};


// ─── Phase Accuracy ─────────────────────────────────────────────

const PhaseAccuracy = ({ data }) => {
  const phases = ["opening", "middlegame", "endgame"];
  const hasData = phases.some(p => data[p] != null);
  if (!hasData) return null;

  return (
    <div className="rounded-2xl border border-border bg-card p-5 mb-6">
      <div className="flex items-center gap-2.5 mb-4">
        <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center">
          <Shield className="w-4 h-4 text-blue-500" />
        </div>
        <h3 className="text-sm font-semibold text-foreground">Phase Accuracy</h3>
      </div>

      <div className="grid grid-cols-3 gap-3">
        {phases.map(phase => {
          const acc = data[phase];
          if (acc == null) return (
            <div key={phase} className="text-center p-3 rounded-xl bg-muted/30">
              <p className="text-2xl font-bold font-mono text-muted-foreground/30">—</p>
              <p className="text-[10px] text-muted-foreground mt-1 capitalize">{phase}</p>
            </div>
          );
          const color = acc >= 80 ? "text-emerald-500" : acc >= 60 ? "text-amber-500" : "text-red-400";
          return (
            <div key={phase} className="text-center p-3 rounded-xl bg-muted/30">
              <p className={`text-2xl font-bold font-mono ${color}`}>{acc}%</p>
              <p className="text-[10px] text-muted-foreground mt-1 capitalize">{phase}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
};


// ─── Accuracy Trend ─────────────────────────────────────────────

const AccuracyTrend = ({ data }) => {
  const max = Math.max(...data.map(d => d.accuracy), 100);
  const min = Math.min(...data.map(d => d.accuracy), 0);
  const range = max - min || 1;

  // Trend direction
  const first3 = data.slice(0, 3).reduce((s, d) => s + d.accuracy, 0) / 3;
  const last3 = data.slice(-3).reduce((s, d) => s + d.accuracy, 0) / 3;
  const trend = last3 - first3;

  return (
    <div className="rounded-2xl border border-border bg-card p-5 mb-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
            trend >= 3 ? "bg-emerald-500/10" : trend <= -3 ? "bg-red-500/10" : "bg-muted"
          }`}>
            {trend >= 3 ? <TrendingUp className="w-4 h-4 text-emerald-500" /> :
             trend <= -3 ? <TrendingDown className="w-4 h-4 text-red-400" /> :
             <Minus className="w-4 h-4 text-muted-foreground" />}
          </div>
          <h3 className="text-sm font-semibold text-foreground">Accuracy Trend</h3>
        </div>
        <span className={`text-xs font-medium ${
          trend >= 3 ? "text-emerald-600" : trend <= -3 ? "text-red-400" : "text-muted-foreground"
        }`}>
          {trend >= 3 ? `+${trend.toFixed(0)}% improving` : trend <= -3 ? `${trend.toFixed(0)}% declining` : "Steady"}
        </span>
      </div>

      {/* Mini bar chart */}
      <div className="flex items-end gap-1 h-16">
        {data.map((d, i) => {
          const height = Math.max(8, ((d.accuracy - min) / range) * 100);
          const color = d.accuracy >= 80 ? "bg-emerald-500" :
                        d.accuracy >= 60 ? "bg-amber-400" : "bg-red-400";
          return (
            <div key={i} className="flex-1 flex flex-col items-center gap-0.5">
              <div className={`w-full rounded-sm ${color}`} style={{ height: `${height}%` }}
                   title={`${d.accuracy}% accuracy, ${d.blunders} blunders`} />
            </div>
          );
        })}
      </div>
      <div className="flex justify-between mt-1">
        <span className="text-[9px] text-muted-foreground/40">Oldest</span>
        <span className="text-[9px] text-muted-foreground/40">Latest</span>
      </div>
    </div>
  );
};


// ─── Pattern Lifecycle ──────────────────────────────────────────

const ANGER_COLORS = {
  first_time: "text-blue-500 bg-blue-500/10",
  recurring: "text-amber-500 bg-amber-500/10",
  returned: "text-orange-500 bg-orange-500/10",
  chronic: "text-red-500 bg-red-500/10",
};

const PatternLifecycle = ({ patterns }) => {
  const active = patterns.filter(p => p.state === "active");
  const declining = patterns.filter(p => p.state === "declining");
  const fading = patterns.filter(p => p.state === "fading");

  return (
    <div className="rounded-2xl border border-border bg-card p-5 mb-6">
      <div className="flex items-center gap-2.5 mb-4">
        <div className="w-8 h-8 rounded-lg bg-red-500/10 flex items-center justify-center">
          <Flame className="w-4 h-4 text-red-400" />
        </div>
        <h3 className="text-sm font-semibold text-foreground">Mistake Patterns</h3>
      </div>

      {active.length > 0 && (
        <div className="mb-3">
          <p className="text-[10px] uppercase tracking-widest font-bold text-red-400/60 mb-1.5">Active</p>
          {active.map(p => <PatternRow key={p.category} pattern={p} />)}
        </div>
      )}
      {declining.length > 0 && (
        <div className="mb-3">
          <p className="text-[10px] uppercase tracking-widest font-bold text-amber-400/60 mb-1.5">Declining</p>
          {declining.map(p => <PatternRow key={p.category} pattern={p} />)}
        </div>
      )}
      {fading.length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-widest font-bold text-emerald-400/60 mb-1.5">Fading</p>
          {fading.map(p => <PatternRow key={p.category} pattern={p} />)}
        </div>
      )}
    </div>
  );
};

const PatternRow = ({ pattern }) => {
  const label = pattern.category.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
  const anger = ANGER_COLORS[pattern.anger] || ANGER_COLORS.first_time;
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-sm text-foreground">{label}</span>
      <div className="flex items-center gap-2">
        <span className="text-xs font-mono text-muted-foreground">{pattern.count}x</span>
        <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${anger}`}>
          {pattern.anger?.replace(/_/g, " ")}
        </span>
      </div>
    </div>
  );
};


// ─── Opening Mastery (Coach sessions) ───────────────────────────

const PHASE_LABELS = {
  introduction: { label: "Learning", color: "text-blue-500 bg-blue-500/10" },
  awareness: { label: "Practicing", color: "text-amber-500 bg-amber-500/10" },
  free_play: { label: "Testing", color: "text-purple-500 bg-purple-500/10" },
  mastered: { label: "Mastered", color: "text-emerald-500 bg-emerald-500/10" },
};

const OpeningMastery = ({ data, navigate }) => (
  <div className="rounded-2xl border border-border bg-card p-5 mb-6">
    <div className="flex items-center gap-2.5 mb-4">
      <div className="w-8 h-8 rounded-lg bg-indigo-500/10 flex items-center justify-center">
        <Crown className="w-4 h-4 text-indigo-500" />
      </div>
      <h3 className="text-sm font-semibold text-foreground">Opening Mastery</h3>
      <span className="text-[10px] text-muted-foreground">with Coach</span>
    </div>

    <div className="space-y-2">
      {data.map(m => {
        const phaseInfo = PHASE_LABELS[m.phase] || PHASE_LABELS.introduction;
        const key = m.opening_key?.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
        return (
          <div key={m.opening_key}
               onClick={() => navigate(`/play-with-coach?opening=${encodeURIComponent(key)}`)}
               className="flex items-center justify-between p-3 rounded-xl hover:bg-muted/50 cursor-pointer transition-all"
          >
            <div>
              <p className="text-sm font-medium text-foreground">{key}</p>
              <p className="text-[10px] text-muted-foreground">
                {m.games_played} game{m.games_played !== 1 ? "s" : ""}
                {m.branches_seen?.length > 0 && ` · ${m.branches_seen.length} variation${m.branches_seen.length !== 1 ? "s" : ""}`}
              </p>
            </div>
            <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${phaseInfo.color}`}>
              {phaseInfo.label}
            </span>
          </div>
        );
      })}
    </div>
  </div>
);


// ─── Focus Card ─────────────────────────────────────────────────

const FocusCard = ({ state, progress, navigate }) => {

  // NOT STARTED
  if (state === "not_started") {
    return (
      <div className="rounded-2xl border border-border bg-card p-6 mb-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-muted flex items-center justify-center">
            <Target className="w-5 h-5 text-muted-foreground" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-foreground">No focus area yet</h2>
            <p className="text-xs text-muted-foreground">Analyze your games to find what to improve</p>
          </div>
        </div>
        <p className="text-sm text-muted-foreground leading-relaxed mb-5">
          Go to Lab to review your games. The coach will identify your biggest weakness and build a training plan around it.
        </p>
        <button
          onClick={() => navigate("/lab")}
          className="w-full py-3 text-sm font-semibold rounded-xl bg-foreground text-background hover:opacity-90 transition-all flex items-center justify-center gap-2"
        >
          Go to Lab
          <ChevronRight className="w-4 h-4 opacity-60" />
        </button>
      </div>
    );
  }

  // WAITING FOR GAMES
  if (state === "waiting_for_games") {
    const played = progress.post_games_played || 0;
    const needed = progress.post_games_needed || 3;
    const pct = Math.round((played / needed) * 100);

    return (
      <div className="rounded-2xl border border-border bg-card p-6 mb-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center">
            <Activity className="w-5 h-5 text-amber-500" />
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Working on</p>
            <h2 className="text-base font-semibold text-foreground">{progress.focus_label}</h2>
          </div>
          <div className="ml-auto flex items-center gap-1.5">
            <Check className="w-3.5 h-3.5 text-emerald-500" strokeWidth={2.5} />
            <span className="text-xs text-emerald-600 font-medium">Trained</span>
          </div>
        </div>

        {/* Progress bar */}
        <div className="mb-3">
          <div className="flex items-center justify-between mb-1.5">
            <p className="text-xs text-muted-foreground">Apply in real games</p>
            <p className="text-xs font-mono text-muted-foreground">{played}/{needed}</p>
          </div>
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-amber-500 rounded-full"
              initial={{ width: 0 }}
              animate={{ width: `${pct}%` }}
              transition={{ duration: 0.6, ease: "easeOut" }}
            />
          </div>
        </div>

        {/* Game dots */}
        <div className="flex items-center gap-1.5 mb-5">
          {Array.from({ length: needed }).map((_, i) => (
            <div key={i} className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs ${
              i < played
                ? "bg-emerald-500/10 border border-emerald-500/20"
                : "bg-muted/50 border border-border/50"
            }`}>
              {i < played
                ? <Check className="w-3 h-3 text-emerald-500" strokeWidth={2.5} />
                : <span className="text-muted-foreground/30">{i + 1}</span>
              }
            </div>
          ))}
        </div>

        <button
          onClick={() => navigate("/play-with-coach")}
          className="w-full py-3 text-sm font-semibold rounded-xl bg-foreground text-background hover:opacity-90 transition-all flex items-center justify-center gap-2"
        >
          <Swords className="w-4 h-4" strokeWidth={2} />
          Play Game {played + 1}
        </button>
      </div>
    );
  }

  // TRACKING — the proof
  const pre = progress.pre_training || {};
  const post = progress.post_training || {};
  const verdict = progress.verdict || "no_change";
  const postGames = progress.post_training_games || [];

  const verdictConfig = {
    improving: {
      icon: TrendingUp,
      text: "You're improving",
      color: "text-emerald-500",
      bg: "bg-emerald-500/10",
      border: "border-emerald-500/20",
      iconColor: "text-emerald-500",
    },
    slipping: {
      icon: TrendingDown,
      text: "Needs more work",
      color: "text-red-400",
      bg: "bg-red-500/10",
      border: "border-red-500/20",
      iconColor: "text-red-400",
    },
    no_change: {
      icon: Minus,
      text: "No change yet",
      color: "text-muted-foreground",
      bg: "bg-muted",
      border: "border-border",
      iconColor: "text-muted-foreground",
    },
  };

  const v = verdictConfig[verdict] || verdictConfig.no_change;
  const VerdictIcon = v.icon;
  const delta = (pre.mistakes || 0) - (post.mistakes || 0);

  return (
    <div className="rounded-2xl border border-border bg-card mb-6 overflow-hidden">
      {/* Header */}
      <div className="px-6 pt-6 pb-4">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-xl ${v.bg} flex items-center justify-center`}>
            <VerdictIcon className={`w-5 h-5 ${v.iconColor}`} />
          </div>
          <div className="flex-1">
            <p className="text-xs text-muted-foreground">Working on</p>
            <h2 className="text-base font-semibold text-foreground">{progress.focus_label}</h2>
          </div>
          <div className={`px-3 py-1.5 rounded-full text-xs font-semibold ${v.bg} ${v.color} ${v.border} border`}>
            {v.text}
          </div>
        </div>
      </div>

      {/* Before / After comparison */}
      <div className="px-6 pb-5">
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-xl bg-muted/50 p-4">
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground/50 font-semibold mb-2">Before</p>
            <div className="flex items-baseline gap-1">
              <span className="text-3xl font-bold font-mono text-foreground">{pre.mistakes ?? "—"}</span>
              <span className="text-xs text-muted-foreground">mistakes</span>
            </div>
            <p className="text-[11px] text-muted-foreground mt-1">in {pre.games ?? 0} games</p>
          </div>
          <div className={`rounded-xl p-4 ${
            verdict === "improving" ? "bg-emerald-500/[0.05]" :
            verdict === "slipping" ? "bg-red-500/[0.05]" :
            "bg-muted/50"
          }`}>
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground/50 font-semibold mb-2">After</p>
            <div className="flex items-baseline gap-1">
              <span className={`text-3xl font-bold font-mono ${v.color}`}>{post.mistakes ?? "—"}</span>
              <span className="text-xs text-muted-foreground">mistakes</span>
            </div>
            <p className="text-[11px] text-muted-foreground mt-1">in {post.games ?? 0} games</p>
          </div>
        </div>

        {/* Delta indicator */}
        {delta !== 0 && (
          <div className="flex items-center justify-center mt-3">
            <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium ${
              delta > 0 ? "bg-emerald-500/10 text-emerald-600" : "bg-red-500/10 text-red-500"
            }`}>
              {delta > 0 ? <TrendingDown className="w-3 h-3" /> : <TrendingUp className="w-3 h-3" />}
              {delta > 0 ? `${delta} fewer mistakes` : `${Math.abs(delta)} more mistakes`}
            </div>
          </div>
        )}
      </div>

      {/* Recent games strip */}
      {postGames.length > 0 && (
        <div className="px-6 pb-5">
          <p className="text-[10px] uppercase tracking-widest font-semibold text-muted-foreground/40 mb-2">Recent games</p>
          <div className="flex items-center gap-1.5">
            {postGames.map((g, i) => (
              <div
                key={i}
                className={`h-8 flex-1 rounded-md flex items-center justify-center transition-all ${
                  g.had_mistake
                    ? "bg-red-500/8 border border-red-500/12"
                    : "bg-emerald-500/8 border border-emerald-500/12"
                }`}
                title={`vs ${g.opponent} — ${g.had_mistake ? "had mistake" : "clean"}`}
              >
                {g.had_mistake
                  ? <XIcon className="w-3 h-3 text-red-400" strokeWidth={2.5} />
                  : <Check className="w-3 h-3 text-emerald-500" strokeWidth={2.5} />
                }
              </div>
            ))}
          </div>
          <div className="flex items-center justify-between mt-1.5">
            <p className="text-[10px] text-muted-foreground/40">
              {postGames.filter(g => !g.had_mistake).length} clean
            </p>
            <p className="text-[10px] text-muted-foreground/40">
              {postGames.filter(g => g.had_mistake).length} with mistakes
            </p>
          </div>
        </div>
      )}
    </div>
  );
};


// ─── Opening Repertoire ─────────────────────────────────────────

const OpeningRepertoire = ({ openings, navigate }) => {
  if (!openings || openings.total_games === 0) return null;

  const bestWhite = openings.white?.length > 0
    ? openings.white.reduce((a, b) => (b.win_rate > a.win_rate && b.games >= 3) ? b : a, openings.white[0])
    : null;
  const bestBlack = openings.black?.length > 0
    ? openings.black.reduce((a, b) => (b.win_rate > a.win_rate && b.games >= 3) ? b : a, openings.black[0])
    : null;

  return (
    <div className="rounded-2xl border border-border bg-card mb-6 overflow-hidden">
      <div className="px-6 pt-5 pb-2">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
            <BookOpen className="w-4 h-4 text-primary" />
          </div>
          <h3 className="text-sm font-semibold text-foreground">Your Openings</h3>
        </div>
      </div>

      <div className="px-6 pb-5 space-y-4">
        <OpeningColorSection label="As White" list={openings.white} best={bestWhite} />
        <OpeningColorSection label="As Black" list={openings.black} best={bestBlack} />
      </div>

      {/* Coach recommendation */}
      {(bestWhite || bestBlack) && (
        <div className="px-6 pb-5">
          <div className="rounded-xl bg-primary/[0.04] border border-primary/10 p-4">
            <div className="flex items-start gap-3">
              <div className="w-7 h-7 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Flame className="w-3.5 h-3.5 text-primary" />
              </div>
              <div className="flex-1">
                <p className="text-xs font-semibold text-primary mb-0.5">Coach recommends</p>
                <p className="text-sm text-foreground leading-relaxed">
                  Focus on{" "}
                  {bestWhite && <span className="font-semibold">{bestWhite.name}</span>}
                  {bestWhite && bestBlack && " and "}
                  {bestBlack && <span className="font-semibold">{bestBlack.name}</span>}
                  . Mastering 1-2 openings deeply is how you climb.
                </p>
              </div>
            </div>
            <button
              onClick={() => {
                const opening = bestWhite?.name || bestBlack?.name || "";
                navigate(`/play-with-coach${opening ? `?opening=${encodeURIComponent(opening)}` : ""}`);
              }}
              className="mt-3 ml-10 text-xs font-medium text-primary hover:text-primary/80 flex items-center gap-1 transition-colors"
            >
              Practice with Coach
              <ChevronRight className="w-3 h-3" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

const OpeningColorSection = ({ label, list, best }) => {
  if (!list?.length) return null;

  return (
    <div>
      <p className="text-[10px] uppercase tracking-widest font-bold text-muted-foreground/40 mb-2">{label}</p>
      <div className="space-y-1">
        {list.slice(0, 4).map((o) => {
          const isBest = best && o.name === best.name && best.games >= 3;
          return (
            <div
              key={o.name}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all ${
                isBest
                  ? "bg-emerald-500/[0.04] border border-emerald-500/15"
                  : "hover:bg-muted/50"
              }`}
            >
              {isBest && <Crown className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />}
              <span className={`text-sm text-foreground flex-1 truncate ${isBest ? "font-medium" : ""}`}>
                {o.name}
              </span>

              {/* Win rate bar */}
              <div className="flex items-center gap-2 flex-shrink-0">
                <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      o.win_rate >= 55 ? "bg-emerald-500" :
                      o.win_rate >= 45 ? "bg-amber-400" :
                      "bg-red-400"
                    }`}
                    style={{ width: `${Math.min(100, o.win_rate)}%` }}
                  />
                </div>
                <span className={`text-xs font-mono w-8 text-right ${
                  o.win_rate >= 55 ? "text-emerald-600" :
                  o.win_rate >= 45 ? "text-foreground" :
                  "text-red-400"
                }`}>
                  {o.win_rate}%
                </span>
                <span className="text-[10px] text-muted-foreground/50 w-5 text-right">{o.games}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};


// ─── Quick Actions ──────────────────────────────────────────────

const QuickActions = ({ state, progress, navigate }) => {
  const verdict = progress?.verdict;

  return (
    <div className="grid grid-cols-2 gap-3">
      <button
        onClick={() => navigate("/play-with-coach")}
        className="flex items-center gap-3 p-4 rounded-2xl border border-border bg-card hover:bg-muted/50 transition-all group"
      >
        <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center group-hover:bg-primary/15 transition-colors">
          <Swords className="w-4 h-4 text-primary" strokeWidth={2} />
        </div>
        <div className="text-left">
          <p className="text-sm font-medium text-foreground">Play with Coach</p>
          <p className="text-[11px] text-muted-foreground">Practice your openings</p>
        </div>
      </button>

      <button
        onClick={() => navigate("/lab")}
        className="flex items-center gap-3 p-4 rounded-2xl border border-border bg-card hover:bg-muted/50 transition-all group"
      >
        <div className="w-9 h-9 rounded-xl bg-amber-500/10 flex items-center justify-center group-hover:bg-amber-500/15 transition-colors">
          <Target className="w-4 h-4 text-amber-500" strokeWidth={2} />
        </div>
        <div className="text-left">
          <p className="text-sm font-medium text-foreground">Review Games</p>
          <p className="text-[11px] text-muted-foreground">Find your weaknesses</p>
        </div>
      </button>
    </div>
  );
};

export default UnifiedProgress;
