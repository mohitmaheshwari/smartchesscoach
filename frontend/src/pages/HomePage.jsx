/**
 * HOME PAGE — Coach-First Dashboard
 * Shows: Coach message, review progress, last game, patterns, actions
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import LichessBoard from "@/components/LichessBoard";
import { ChevronRight, Swords, Target, Import, BookOpen, FlaskConical, Check, Trophy, TrendingUp, ArrowRight, Zap, Brain, Shield, Crown, Clock } from "lucide-react";

const HomePage = ({ user }) => {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [coachIntel, setCoachIntel] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch(`${API}/home/dashboard-v2`, { credentials: "include" }).then(r => r.ok ? r.json() : null),
      fetch(`${API}/coach/home-intelligence`, { credentials: "include" }).then(r => r.ok ? r.json() : null).catch(() => null),
    ])
      .then(([d, intel]) => { setData(d); setCoachIntel(intel); })
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

  const battle = data?.last_battle;
  const dna = data?.chess_dna;
  const fix = data?.one_thing_to_fix;
  const streak = data?.streak;
  const patterns = data?.patterns || [];
  const accuracy = data?.accuracy || 0;
  const gamesAnalyzed = data?.games_analyzed || 0;
  const review = data?.review_progress || {};

  const winStreak = coachIntel?.win_streak;
  const moodOverride = coachIntel?.mood_override;
  const progressTrend = coachIntel?.progress_trend;
  const suppressNegative = moodOverride?.suppress_negative;

  const strengthProfile = data?.strength_profile;

  const topPattern = patterns[0];
  const coachMessage = topPattern
    ? `${topPattern.label} is showing up in almost every game.`
    : fix?.fix_line || dna?.root_cause || "Let's review your recent games.";
  const coachSub = topPattern
    ? `${topPattern.recent_count} times recently. This is your biggest leak right now.`
    : fix?.stat_line || "";

  const primaryActionLabel = topPattern
    ? `Train ${topPattern.label}`
    : fix?.pattern ? `Train ${fix.pattern.replace(/_/g, " ")}` : "Train Calculation";
  const primaryActionHref = topPattern
    ? `/training?focus=${topPattern.pattern_type}`
    : `/training?focus=calculation_depth`;

  // Empty state
  if (!battle && gamesAnalyzed === 0) {
    return (
      <Layout user={user}>
        <div className="max-w-xl mx-auto px-4 py-20 text-center" data-testid="home-page">
          <div className="w-16 h-16 rounded-2xl gradient-gold flex items-center justify-center mx-auto mb-6 shadow-lg shadow-amber-500/20">
            <Swords className="w-7 h-7 text-black" strokeWidth={2} />
          </div>
          <h1 className="text-3xl font-heading text-foreground tracking-tight mb-3">
            Welcome to ChessGuru
          </h1>
          <p className="text-muted-foreground mb-8 text-[15px] leading-relaxed max-w-md mx-auto">
            Import your games to get started. After 5 games, your coach will know your strengths.
            After 15, it'll know your weaknesses by name.
          </p>
          <div className="flex gap-3 justify-center">
            <button onClick={() => navigate("/import")} className="px-6 py-3 text-sm gradient-gold text-black rounded-lg hover:opacity-90 transition-all font-semibold shadow-lg shadow-amber-500/20 hover:shadow-amber-500/30" data-testid="import-cta">
              <Import className="w-4 h-4 inline mr-2" strokeWidth={2} />
              Import Games
            </button>
            <button onClick={() => navigate("/play-with-coach")} className="px-6 py-3 text-sm text-foreground border border-border rounded-lg hover:bg-card hover:border-primary/30 transition-all" data-testid="play-cta">
              <Swords className="w-4 h-4 inline mr-2" strokeWidth={1.5} />
              Play with Coach
            </button>
          </div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout user={user}>
      <div className="max-w-3xl mx-auto px-4 py-6" data-testid="home-page">

        {/* ── COACH MESSAGE ── */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
          {streak && streak.count >= 2 && !moodOverride && (
            <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold mb-3 ${
              streak.type === "W" ? "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20"
              : streak.type === "L" ? "bg-red-500/10 text-red-400 border border-red-500/20"
              : "bg-muted text-muted-foreground border border-border"
            }`}>
              <span className="font-mono">{streak.count}</span>
              {streak.type === "W" ? "wins" : streak.type === "L" ? "losses" : "draws"} in a row
            </div>
          )}
          <h1 className="text-2xl sm:text-3xl font-heading text-foreground tracking-tight leading-snug mb-2">
            {coachMessage}
          </h1>
          {coachSub && <p className="text-[15px] text-muted-foreground leading-relaxed">{coachSub}</p>}
        </motion.div>

        {/* ── WIN STREAK BANNER ── */}
        {moodOverride?.type === "positive_momentum" && (
          <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.05 }}
            className="mb-6 flex items-center gap-4 p-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5" data-testid="win-streak-banner">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/15 flex items-center justify-center flex-shrink-0">
              <Trophy className="w-5 h-5 text-emerald-500" strokeWidth={2} />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-emerald-500">{moodOverride.streak}-game win streak</p>
              <p className="text-xs text-muted-foreground mt-0.5">{moodOverride.message}</p>
            </div>
          </motion.div>
        )}

        {/* ── PROGRESS TREND ── */}
        {progressTrend?.has_trend && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }} className="mb-6">
            <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium ${
              progressTrend.trend === "improving" ? "bg-emerald-500/10 text-emerald-500" :
              progressTrend.trend === "declining" ? "bg-red-500/10 text-red-400" : "bg-muted text-muted-foreground"
            }`}>
              {progressTrend.trend === "improving" && <TrendingUp className="w-4 h-4" strokeWidth={2} />}
              {progressTrend.trend === "stable" && <Check className="w-4 h-4" strokeWidth={2} />}
              {progressTrend.message}
            </div>
          </motion.div>
        )}

        {/* ── REVIEW PROGRESS STRIP ── */}
        {review.pending > 0 && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }} className="mb-6">
            <div
              className="flex items-center gap-3 p-4 bg-card border border-border rounded-xl cursor-pointer hover:border-primary/30 transition-all group"
              onClick={() => navigate("/lab")}
              data-testid="review-progress-strip"
            >
              <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                <FlaskConical className="w-4 h-4 text-primary" strokeWidth={2} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-foreground font-medium">
                  <strong>{review.pending}</strong> game{review.pending > 1 ? "s" : ""} waiting for review
                </p>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-24 h-2 bg-muted rounded-full overflow-hidden">
                  <div className="h-full gradient-gold rounded-full transition-all" style={{ width: `${review.total ? (review.reviewed / review.total) * 100 : 0}%` }} />
                </div>
                <span className="text-[11px] font-mono text-muted-foreground">{review.reviewed}/{review.total}</span>
              </div>
              <ChevronRight className="w-4 h-4 text-muted-foreground/30 group-hover:text-primary transition-colors flex-shrink-0" />
            </div>
          </motion.div>
        )}

        {/* ── LAST GAME + ACTIONS ── */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="mb-8">
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            {/* LAST GAME — 3/5 */}
            {battle && (
              <div className="md:col-span-3">
                <Label>Last Game</Label>
                <div
                  className="bg-card border border-border cursor-pointer transition-all duration-200 hover:border-primary/25 rounded-xl overflow-hidden h-full group"
                  onClick={() => navigate(`/game/${battle.game_id}`)}
                  data-testid="last-battle-card"
                >
                  <div className="flex h-full">
                    {battle.fen && (
                      <div className="w-[140px] sm:w-[160px] flex-shrink-0 border-r border-border">
                        <LichessBoard fen={battle.fen} orientation={battle.user_color} viewOnly={true} />
                      </div>
                    )}
                    <div className="flex-1 p-4 flex flex-col justify-between min-w-0">
                      <div>
                        <div className="flex items-center gap-2 mb-1.5">
                          <span className="text-sm text-muted-foreground">vs {battle.opponent}</span>
                          <ResultBadge result={battle.result} userColor={battle.user_color} />
                          {battle.opening && (
                            <span className="text-xs text-muted-foreground/40 hidden sm:inline">{battle.opening}</span>
                          )}
                        </div>
                        {battle.brilliant_moves > 0 && (
                          <span className="inline-flex items-center gap-1 text-[9px] font-bold uppercase tracking-wider text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded-md border border-amber-500/20 mr-1.5 mb-1">
                            <Zap className="w-2.5 h-2.5" strokeWidth={2.5} />
                            {battle.brilliant_moves > 1 ? `${battle.brilliant_moves} brilliant` : "brilliant"}
                          </span>
                        )}
                        {battle.lesson_label && (
                          <span className="inline-block text-[9px] font-bold uppercase tracking-[0.12em] text-primary bg-primary/10 px-1.5 py-0.5 rounded mr-1.5 mb-1">
                            {battle.lesson_label}
                          </span>
                        )}
                        <p className="text-sm text-foreground leading-relaxed">
                          {battle.behavior || dna?.root_cause || "Review this game"}
                        </p>
                      </div>
                      {battle.move_number > 0 && battle.your_move && (
                        <div className="flex items-center gap-2 mt-3 text-[11px] font-mono">
                          <span className="text-muted-foreground">Move {battle.move_number}</span>
                          <span className="text-red-400 font-semibold bg-red-500/10 px-1.5 py-0.5 rounded">{battle.your_move}</span>
                          <ArrowRight className="w-3 h-3 text-muted-foreground/30" />
                          <span className="text-emerald-500 font-semibold bg-emerald-500/10 px-1.5 py-0.5 rounded">{battle.best_move}</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* ACTIONS — 2/5 */}
            <div className={battle ? "md:col-span-2" : "md:col-span-5"}>
              <Label>Actions</Label>
              <div className="bg-card border border-border rounded-xl overflow-hidden h-full flex flex-col">
                <div
                  className="p-4 cursor-pointer transition-all hover:opacity-90 flex items-center gap-3 gradient-gold text-black"
                  onClick={() => navigate(primaryActionHref)}
                  data-testid="primary-action"
                >
                  <Target className="w-4 h-4 flex-shrink-0 opacity-80" strokeWidth={2} />
                  <span className="text-sm font-semibold flex-1">{primaryActionLabel}</span>
                  <ChevronRight className="w-4 h-4 opacity-60" strokeWidth={2} />
                </div>
                <ActionRow icon={Swords} label="Play with Coach" onClick={() => navigate("/play-with-coach")} testId="play-action" />
                <ActionRow icon={BookOpen} label="Study Openings" onClick={() => navigate("/openings-overview")} testId="openings-action" />
                <ActionRow icon={FlaskConical} label="Review in Lab" onClick={() => navigate("/lab")} testId="lab-action" />
              </div>
            </div>
          </div>
        </motion.div>

        {/* ── PATTERNS + CHESS DNA ── */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }} className="mb-8">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {patterns.length > 0 && !suppressNegative && (
              <div>
                <Label>Patterns Across Games</Label>
                <div className="bg-card border border-border rounded-xl overflow-hidden divide-y divide-border">
                  {patterns.map((p) => (
                    <div
                      key={p.pattern_type}
                      className="flex items-center justify-between px-4 py-3.5 cursor-pointer transition-all hover:bg-muted/30"
                      onClick={() => navigate(`/training?focus=${p.pattern_type}`)}
                      data-testid={`pattern-${p.pattern_type}`}
                    >
                      <div className="flex items-center gap-3">
                        <div className={`w-2 h-2 rounded-full flex-shrink-0 ${p.severity === "critical" || p.severity === "high" ? "bg-red-400" : "bg-amber-400"}`} />
                        <span className="text-sm text-foreground font-medium">{p.label}</span>
                      </div>
                      <div className="flex items-center gap-2.5">
                        <span className="text-xs font-mono text-muted-foreground">{p.recent_count}x</span>
                        <SeverityBadge severity={p.severity} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {dna && (
              <div>
                <Label>Your Chess DNA</Label>
                <div className="bg-card border border-border rounded-xl p-5 h-full relative overflow-hidden">
                  {/* Subtle gradient accent */}
                  <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />
                  <div className="relative">
                    <span className="text-sm text-muted-foreground">{dna.archetype || "Developing"}</span>
                    <div className="mt-3 mb-3">
                      <span className="text-[9px] tracking-[0.15em] uppercase font-bold text-red-400 bg-red-500/10 px-1.5 py-0.5 rounded">Biggest Leak</span>
                      <p className="text-lg font-heading text-foreground tracking-tight mt-2">
                        {dna.diagnosis?.replace(/_/g, " ") || "\u2014"}
                      </p>
                    </div>
                    {dna.after_line && <p className="text-xs text-muted-foreground leading-relaxed">{dna.after_line}</p>}
                  </div>
                </div>
              </div>
            )}
          </div>
        </motion.div>

        {/* ── STRENGTH PROFILE ── */}
        {strengthProfile && strengthProfile.domains && Object.keys(strengthProfile.domains).length > 0 && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.18 }} className="mb-8">
            <div className="flex items-center justify-between mb-3">
              <Label>Your Strengths</Label>
              {strengthProfile.headline_stats?.brilliant_moves > 0 && (
                <div className="flex items-center gap-1.5 text-xs font-mono text-primary">
                  <Zap className="w-3 h-3" strokeWidth={2} />
                  {strengthProfile.headline_stats.brilliant_moves} brilliant move{strengthProfile.headline_stats.brilliant_moves !== 1 ? "s" : ""}
                </div>
              )}
            </div>
            <div className="bg-card border border-border rounded-xl p-5 relative overflow-hidden">
              <div className="absolute top-0 left-0 w-40 h-40 bg-emerald-500/5 rounded-full blur-3xl -translate-y-1/2 -translate-x-1/2" />
              <div className="relative">
                {/* Domain bars */}
                <div className="space-y-3">
                  {STRENGTH_DOMAINS.map(({ key, label, icon: Icon }) => {
                    const domain = strengthProfile.domains[key];
                    if (!domain) return null;
                    const isStrongest = strengthProfile.strongest === key;
                    return (
                      <div key={key} className="flex items-center gap-3">
                        <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 ${isStrongest ? "bg-emerald-500/15" : "bg-muted/50"}`}>
                          <Icon className={`w-3.5 h-3.5 ${isStrongest ? "text-emerald-500" : "text-muted-foreground"}`} strokeWidth={1.5} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between mb-1">
                            <span className={`text-xs font-medium ${isStrongest ? "text-foreground" : "text-muted-foreground"}`}>{label}</span>
                            <span className="text-[10px] font-mono text-muted-foreground">{domain.score}%</span>
                          </div>
                          <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full transition-all ${isStrongest ? "bg-emerald-500" : "bg-muted-foreground/30"}`}
                              style={{ width: `${Math.max(domain.score, 3)}%` }}
                            />
                          </div>
                        </div>
                        {isStrongest && (
                          <span className="text-[8px] font-bold uppercase tracking-wider text-emerald-500 bg-emerald-500/10 px-1.5 py-0.5 rounded flex-shrink-0">best</span>
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* Headline */}
                {strengthProfile.strongest && strengthProfile.weakest && (
                  <div className="mt-4 pt-3 border-t border-border/50 text-xs text-muted-foreground">
                    <span className="text-emerald-500 font-medium">{DOMAIN_LABELS[strengthProfile.strongest]}</span>
                    {" is your strongest area. "}
                    <span className="text-amber-400 font-medium">{DOMAIN_LABELS[strengthProfile.weakest]}</span>
                    {" needs the most work."}
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        )}

        {/* ── FOOTER STATS ── */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.22 }}
          className="flex items-center justify-between text-muted-foreground/40 mt-8 pt-4 border-t border-border/50"
        >
          <span className="text-[11px] font-mono">{gamesAnalyzed} games</span>
          {accuracy > 0 && <span className="text-[11px] font-mono">{accuracy.toFixed(0)}% avg accuracy</span>}
        </motion.div>
      </div>
    </Layout>
  );
};

// ── Strength Profile Config ──

const STRENGTH_DOMAINS = [
  { key: "tactical_vision", label: "Tactical Vision", icon: Zap },
  { key: "calculation_depth", label: "Calculation", icon: Brain },
  { key: "positional_sense", label: "Positional Sense", icon: Target },
  { key: "endgame_technique", label: "Endgame", icon: Crown },
  { key: "opening_knowledge", label: "Openings", icon: BookOpen },
  { key: "pressure_handling", label: "Under Pressure", icon: Shield },
];

const DOMAIN_LABELS = {
  tactical_vision: "Tactical Vision",
  calculation_depth: "Calculation",
  positional_sense: "Positional Sense",
  endgame_technique: "Endgame",
  opening_knowledge: "Openings",
  pressure_handling: "Pressure Handling",
};

// ── Reusable Components ──

const Label = ({ children }) => (
  <p className="text-[10px] tracking-[0.15em] uppercase mb-2.5 font-bold text-muted-foreground/70">{children}</p>
);

const ActionRow = ({ icon: Icon, label, onClick, testId }) => (
  <div className="p-3.5 cursor-pointer transition-all hover:bg-muted/30 flex items-center gap-3 border-t border-border group" onClick={onClick} data-testid={testId}>
    <Icon className="w-4 h-4 flex-shrink-0 text-muted-foreground group-hover:text-primary transition-colors" strokeWidth={1.5} />
    <span className="text-sm text-foreground flex-1">{label}</span>
    <ChevronRight className="w-4 h-4 text-muted-foreground/20 group-hover:text-muted-foreground transition-colors" strokeWidth={1.5} />
  </div>
);

const ResultBadge = ({ result, userColor }) => {
  const won = (result === "1-0" && userColor === "white") || (result === "0-1" && userColor === "black");
  const draw = (result || "").includes("1/2");
  const cls = won ? "bg-emerald-500/15 text-emerald-500 border-emerald-500/25"
    : draw ? "bg-muted text-muted-foreground border-border"
    : "bg-red-500/15 text-red-400 border-red-500/25";
  return <span className={`text-[10px] px-2 py-0.5 font-bold rounded-md border ${cls}`}>{won ? "WON" : draw ? "DRAW" : "LOST"}</span>;
};

const SeverityBadge = ({ severity }) => {
  const high = severity === "critical" || severity === "high";
  return (
    <span className={`text-[9px] px-2 py-0.5 uppercase font-bold rounded-md ${
      high ? "bg-red-500/15 text-red-400" : "bg-amber-500/15 text-amber-400"
    }`}>
      {high ? "HIGH" : "MED"}
    </span>
  );
};

export default HomePage;
