/**
 * HOME PAGE — "Your coach tells you the truth."
 *
 * No dashboards. No metrics. No counts.
 * Behavior -> Pattern -> Correction.
 *
 * 1. Coach speaks — one uncomfortable truth + the rule to fix it
 * 2. Your focus — pattern tracker with visual (did it show up or not?)
 * 3. Last game — one line, clickable
 * 4. Actions — Play / Lab / Progress (small, bottom)
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import {
  ChevronRight, Swords, Import, FlaskConical,
  Trophy, TrendingUp,
  Zap, AlertTriangle, Target,
  Brain, Flame, Check, X as XIcon
} from "lucide-react";

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
  const fix = data?.one_thing_to_fix;
  const streak = data?.streak;
  const patterns = data?.patterns || [];
  const gamesAnalyzed = data?.games_analyzed || 0;
  const review = data?.review_progress || {};
  const trainingReady = data?.training_ready;
  const gamesImported = data?.games_imported || 0;

  const moodOverride = coachIntel?.mood_override;
  const progressTrend = coachIntel?.progress_trend;
  const trainingRec = coachIntel?.training_recommendation;
  const topPattern = patterns[0];

  // ── Empty state ──
  if (!battle && gamesAnalyzed === 0 && gamesImported === 0) {
    return (
      <Layout user={user}>
        <div className="max-w-xl mx-auto px-4 py-20 text-center" data-testid="home-page">
          <div className="w-16 h-16 rounded-2xl gradient-gold flex items-center justify-center mx-auto mb-6 shadow-lg shadow-amber-500/20">
            <Brain className="w-7 h-7 text-black" strokeWidth={2} />
          </div>
          <h1 className="text-3xl font-heading text-foreground tracking-tight mb-3">Your coach is waiting.</h1>
          <p className="text-muted-foreground mb-8 text-[15px] leading-relaxed max-w-md mx-auto">
            Import your games. After 5 games, your coach will know your strengths. After 15, it'll know your weaknesses by name.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <button onClick={() => navigate("/import")} className="px-6 py-3 text-sm gradient-gold text-black rounded-lg hover:opacity-90 transition-all font-semibold shadow-lg shadow-amber-500/20" data-testid="import-cta">
              <Import className="w-4 h-4 inline mr-2" strokeWidth={2} />Import Games
            </button>
            <button onClick={() => navigate("/play-with-coach")} className="px-6 py-3 text-sm text-foreground border border-border rounded-lg hover:bg-card hover:border-primary/30 transition-all" data-testid="play-cta">
              <Swords className="w-4 h-4 inline mr-2" strokeWidth={1.5} />Play with Coach
            </button>
          </div>
        </div>
      </Layout>
    );
  }

  // ── Analyzing state ──
  if (!battle && gamesAnalyzed === 0 && gamesImported > 0) {
    return (
      <Layout user={user}>
        <div className="max-w-xl mx-auto px-4 py-16" data-testid="home-page">
          <div className="text-center mb-8">
            <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-5">
              <div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
            </div>
            <h1 className="text-2xl font-heading text-foreground tracking-tight mb-2">Your coach is studying your games.</h1>
            <p className="text-muted-foreground text-sm max-w-sm mx-auto">Analyzing every move across {gamesImported} games. This takes a few minutes.</p>
          </div>
          <div className="bg-card border border-border rounded-xl p-5 mb-6">
            <p className="text-sm text-foreground mb-4">Play a game with your coach while it works.</p>
            <button onClick={() => navigate("/play-with-coach")} className="w-full px-6 py-3 text-sm gradient-gold text-black rounded-lg hover:opacity-90 transition-all font-semibold shadow-lg shadow-amber-500/20">
              <Swords className="w-4 h-4 inline mr-2" strokeWidth={2} />Play with Coach
            </button>
          </div>
          <div className="text-center">
            <button onClick={() => window.location.reload()} className="text-xs text-muted-foreground/50 hover:text-muted-foreground transition-colors">Check if analysis is ready</button>
          </div>
        </div>
      </Layout>
    );
  }

  // ═══ MAIN HOME PAGE ═══
  const coach = getCoachTruth({ moodOverride, streak, topPattern, fix, battle, progressTrend, trainingRec, review, patterns });
  const userWon = battle && ((battle.result === "1-0" && battle.user_color === "white") || (battle.result === "0-1" && battle.user_color === "black"));
  const userLost = battle && !userWon && !(battle.result || "").includes("1/2");

  return (
    <Layout user={user}>
      <div className="max-w-2xl mx-auto px-4 py-6 space-y-5" data-testid="home-page">

        {/* ═══ 1. COACH SPEAKS ═══ */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
          <div className={`rounded-2xl border relative overflow-hidden ${coach.borderClass}`}>
            <div className={`absolute top-0 right-0 w-64 h-64 rounded-full blur-3xl -translate-y-1/3 translate-x-1/3 ${coach.glowClass}`} />
            <div className="relative p-6">
              {/* Coach identity */}
              <div className="flex items-center gap-3 mb-5">
                <div className="relative">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-amber-500/20 to-amber-600/10 flex items-center justify-center">
                    <Brain className="w-5 h-5 text-amber-500" />
                  </div>
                  <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-emerald-500 border-2 border-background" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-foreground">Coach says</p>
                  {coach.badge && <p className={`text-[10px] font-semibold ${coach.badgeColor}`}>{coach.badge}</p>}
                </div>
              </div>

              {/* The truth */}
              <blockquote className="text-lg sm:text-xl font-heading text-foreground tracking-tight leading-snug mb-3">
                {coach.truth}
              </blockquote>

              {/* Evidence */}
              {coach.evidence && (
                <p className="text-sm text-muted-foreground leading-relaxed mb-4">{coach.evidence}</p>
              )}

              {/* The rule */}
              {coach.rule && (
                <div className="p-3 rounded-lg bg-amber-500/5 border border-amber-500/15 mb-5">
                  <p className="text-xs font-bold uppercase tracking-wider text-amber-600 dark:text-amber-400 mb-1">{coach.ruleName || "Rule"}</p>
                  <p className="text-sm text-foreground leading-relaxed">{coach.rule}</p>
                </div>
              )}

              {/* Action */}
              <button
                onClick={() => navigate(coach.actionHref)}
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 text-sm font-semibold rounded-xl gradient-gold text-black hover:opacity-90 transition-all shadow-lg shadow-amber-500/15"
                data-testid="coach-cta"
              >
                <coach.actionIcon className="w-4 h-4" strokeWidth={2} />
                {coach.actionLabel}
                <ChevronRight className="w-3.5 h-3.5 opacity-60" />
              </button>
            </div>
          </div>
        </motion.div>

        {/* ═══ 2. YOUR FOCUS ═══ */}
        {topPattern && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.06 }}>
            <div className="bg-card border border-border rounded-xl p-5">
              <div className="flex items-center justify-between mb-3">
                <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Your Focus</p>
                <span className="text-xs text-amber-500 font-semibold">{topPattern.label}</span>
              </div>

              {/* Visual tracker */}
              {topPattern.recent_games && topPattern.recent_games.length > 0 ? (
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-[10px] text-muted-foreground mr-1">Last 5:</span>
                  {(topPattern.recent_games || []).slice(0, 5).map((appeared, i) => (
                    <div key={i} className={`w-7 h-7 rounded-lg flex items-center justify-center ${appeared ? "bg-red-500/15" : "bg-emerald-500/15"}`}>
                      {appeared
                        ? <XIcon className="w-3.5 h-3.5 text-red-400" strokeWidth={2.5} />
                        : <Check className="w-3.5 h-3.5 text-emerald-500" strokeWidth={2.5} />}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-[10px] text-muted-foreground">Appeared in</span>
                  <span className="text-sm font-bold text-foreground">{topPattern.recent_count || 0}</span>
                  <span className="text-[10px] text-muted-foreground">of your recent games</span>
                </div>
              )}

              <button
                onClick={() => navigate(`/training?focus=${topPattern.pattern_type}`)}
                className="w-full py-2.5 text-sm font-medium text-primary border border-primary/20 rounded-lg hover:bg-primary/5 transition-all flex items-center justify-center gap-2"
              >
                <Target className="w-3.5 h-3.5" />
                Train {topPattern.label}
                {trainingReady?.puzzles_available > 0 && (
                  <span className="text-[10px] font-mono text-muted-foreground">({trainingReady.puzzles_available})</span>
                )}
              </button>
            </div>
          </motion.div>
        )}

        {/* ═══ 3. LAST GAME ═══ */}
        {battle && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
            <div
              className="bg-card border border-border rounded-xl cursor-pointer transition-all hover:border-primary/20 group"
              onClick={() => navigate(`/game/${battle.game_id}`)}
              data-testid="last-battle-card"
            >
              <div className="p-4 flex items-center gap-4">
                <div className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${userWon ? "bg-emerald-500" : userLost ? "bg-red-400" : "bg-muted-foreground/40"}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-sm font-medium text-foreground">vs {battle.opponent}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 font-bold rounded border ${
                      userWon ? "bg-emerald-500/15 text-emerald-500 border-emerald-500/25"
                      : userLost ? "bg-red-500/15 text-red-400 border-red-500/25"
                      : "bg-muted text-muted-foreground border-border"
                    }`}>{userWon ? "W" : userLost ? "L" : "D"}</span>
                    {battle.brilliant_moves > 0 && <Zap className="w-3 h-3 text-amber-400" strokeWidth={2.5} />}
                  </div>
                  <p className="text-xs text-muted-foreground line-clamp-1">
                    {battle.behavior || battle.lesson_label || "Review this game"}
                  </p>
                </div>
                <ChevronRight className="w-4 h-4 text-muted-foreground/20 group-hover:text-primary transition-colors flex-shrink-0" />
              </div>
            </div>
          </motion.div>
        )}

        {/* ═══ 4. ACTIONS ═══ */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.14 }}>
          <div className="grid grid-cols-3 gap-2.5">
            <ActionCard icon={Swords} label="Play" onClick={() => navigate("/play-with-coach")} />
            <ActionCard icon={FlaskConical} label="Lab" badge={review.pending > 0 ? review.pending : null} onClick={() => navigate("/lab")} />
            <ActionCard icon={TrendingUp} label="Progress" onClick={() => navigate("/progress")} />
          </div>
        </motion.div>

        {/* ═══ 5. STREAK ═══ */}
        {streak?.count >= 2 && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.18 }}>
            <div className="flex items-center justify-center gap-2 py-2">
              <Flame className={`w-3.5 h-3.5 ${streak.type === "W" ? "text-emerald-500" : "text-red-400"}`} />
              <span className={`text-xs font-semibold ${streak.type === "W" ? "text-emerald-500" : "text-red-400"}`}>
                {streak.count}-game {streak.type === "W" ? "win" : "loss"} streak
              </span>
            </div>
          </motion.div>
        )}
      </div>
    </Layout>
  );
};


// ═══ COACH TRUTH ENGINE ═══

const RULE_MAP = {
  piece_safety:       { name: "Piece Safety Check",    rule: "Before every move, ask: is anything I own under attack?" },
  ignore_threat:      { name: "Threat Awareness",      rule: "Before every move, ask: what is my opponent attacking right now?" },
  calculation_depth:  { name: "Calculation Depth",     rule: "Don't stop at your move. Ask: what will they do next?" },
  missed_tactic:      { name: "Tactics Scan",          rule: "Before deciding, check: are there any captures, checks, or threats?" },
  tactical_oversight: { name: "Opponent Response",     rule: "After picking your move, pause. What can your opponent do?" },
  king_safety:        { name: "King Safety First",     rule: "Before attacking, check: is my king safe?" },
  time_pressure:      { name: "Clock Discipline",      rule: "When you have less than 2 minutes, simplify the position." },
  time_management:    { name: "Clock Management",      rule: "Track your time. If under 2 minutes, simplify." },
  conversion:         { name: "Winning Discipline",    rule: "When you're ahead, trade pieces. Don't give chances." },
  endgame_technique:  { name: "Endgame Activation",   rule: "In endgames, activate your king and push passed pawns." },
  pawn_structure:     { name: "Structure Awareness",   rule: "Think about pawn structure before exchanges." },
};

function getCoachTruth({ moodOverride, streak, topPattern, fix, battle, progressTrend, trainingRec, review, patterns }) {
  const defaults = {
    borderClass: "border-border bg-card",
    glowClass: "bg-primary/5",
    badge: null, badgeColor: "text-muted-foreground",
    truth: "Your coach is ready. Let's play.",
    evidence: null,
    rule: null, ruleName: null,
    actionLabel: "Play with Coach",
    actionHref: "/play-with-coach",
    actionIcon: Swords,
  };

  // ── Win streak ──
  if (moodOverride?.type === "positive_momentum" && moodOverride.streak >= 3) {
    return { ...defaults,
      borderClass: "border-emerald-500/20 bg-emerald-500/[0.03]",
      glowClass: "bg-emerald-500/10",
      badge: `${moodOverride.streak} wins in a row`, badgeColor: "text-emerald-500",
      truth: "You're playing the best chess I've seen from you.",
      evidence: "Don't change anything. Don't overthink. Just play.",
      actionLabel: "Play Another", actionIcon: Swords,
    };
  }

  // ── Loss streak ──
  if (streak?.type === "L" && streak.count >= 3) {
    return { ...defaults,
      borderClass: "border-red-500/15 bg-red-500/[0.02]",
      glowClass: "bg-red-500/5",
      badge: `${streak.count} losses in a row`, badgeColor: "text-red-400",
      truth: "Stop playing. You're repeating the same mistake.",
      evidence: "Every loss in this streak has the same pattern. Review one game before you play again.",
      actionLabel: "Review Last Game",
      actionHref: battle ? `/game/${battle.game_id}` : "/lab",
      actionIcon: FlaskConical,
    };
  }

  // ── Training recommendation (behavior-aware) ──
  if (trainingRec) {
    const matched = RULE_MAP[trainingRec.pattern] || null;
    const patternLabel = trainingRec.label || "this pattern";

    if (trainingRec.status === "knowledge_gap") {
      return { ...defaults,
        borderClass: "border-amber-500/15 bg-amber-500/[0.02]",
        glowClass: "bg-amber-500/5",
        badge: patternLabel, badgeColor: "text-amber-500",
        truth: `You know ${patternLabel.toLowerCase()} \u2014 you solve it in training. But you still miss it in your games.`,
        evidence: "This isn't a knowledge problem. It's a focus problem. You need to slow down in real games.",
        rule: matched?.rule || null, ruleName: matched?.name || null,
        actionLabel: "Play with Focus", actionIcon: Swords,
      };
    }
    if (trainingRec.status === "needs_practice") {
      return { ...defaults,
        borderClass: "border-amber-500/15 bg-amber-500/[0.02]",
        glowClass: "bg-amber-500/5",
        badge: patternLabel, badgeColor: "text-amber-500",
        truth: `You are losing games because of ${patternLabel.toLowerCase()}.`,
        evidence: "This keeps showing up. You need to train it until you see it automatically.",
        rule: matched?.rule || null, ruleName: matched?.name || null,
        actionLabel: `Train ${patternLabel}`,
        actionHref: `/training?focus=${trainingRec.pattern}`,
        actionIcon: Target,
      };
    }
    if (trainingRec.status === "untrained") {
      return { ...defaults,
        borderClass: "border-primary/15 bg-card",
        glowClass: "bg-primary/5",
        badge: patternLabel, badgeColor: "text-primary",
        truth: `${patternLabel} is your biggest leak. You haven't trained it yet.`,
        evidence: "Puzzles from your own games are waiting. Start now.",
        rule: matched?.rule || null, ruleName: matched?.name || null,
        actionLabel: "Start Training",
        actionHref: `/training?focus=${trainingRec.pattern}`,
        actionIcon: Target,
      };
    }
  }

  // ── Critical pattern (no training rec but pattern exists) ──
  if (topPattern && topPattern.recent_count >= 3) {
    const matched = RULE_MAP[topPattern.pattern_type] || null;
    return { ...defaults,
      borderClass: "border-amber-500/15 bg-amber-500/[0.02]",
      glowClass: "bg-amber-500/5",
      badge: topPattern.label, badgeColor: "text-amber-500",
      truth: `${topPattern.label} is showing up in almost every game.`,
      evidence: `${topPattern.recent_count} times in your recent games. This is the one thing holding you back.`,
      rule: matched?.rule || null, ruleName: matched?.name || topPattern.label,
      actionLabel: `Train ${topPattern.label}`,
      actionHref: `/training?focus=${topPattern.pattern_type}`,
      actionIcon: Target,
    };
  }

  // ── Unreviewed games ──
  if (review.pending >= 3) {
    return { ...defaults,
      borderClass: "border-primary/15 bg-card",
      glowClass: "bg-primary/5",
      truth: "Your coach found things in your recent games.",
      evidence: "There are patterns you need to see before you play again.",
      actionLabel: "Open Lab", actionHref: "/lab", actionIcon: FlaskConical,
    };
  }

  // ── Improving ──
  if (progressTrend?.trend === "improving") {
    return { ...defaults,
      borderClass: "border-emerald-500/10 bg-card",
      glowClass: "bg-emerald-500/5",
      badge: "Getting better", badgeColor: "text-emerald-500",
      truth: progressTrend.message || "Your play is getting sharper.",
      evidence: "Keep the same routine. Consistency is what breaks plateaus.",
    };
  }

  // ── Fix suggestion ──
  if (fix?.fix_line) {
    const matched = RULE_MAP[fix.pattern] || null;
    return { ...defaults,
      truth: fix.fix_line,
      evidence: fix.stat_line || null,
      rule: matched?.rule || null, ruleName: matched?.name || null,
      actionLabel: fix.pattern ? `Train ${fix.pattern.replace(/_/g, " ")}` : "Play with Coach",
      actionHref: fix.pattern ? `/training?focus=${fix.pattern}` : "/play-with-coach",
      actionIcon: fix.pattern ? Target : Swords,
    };
  }

  return defaults;
}


// ═══ Components ═══

const ActionCard = ({ icon: Icon, label, onClick, badge }) => (
  <button
    onClick={onClick}
    className="bg-card border border-border rounded-xl p-4 text-center transition-all hover:border-primary/20 hover:shadow-sm group relative"
  >
    {badge && (
      <span className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full gradient-gold text-[10px] font-bold text-black flex items-center justify-center shadow-sm">{badge}</span>
    )}
    <Icon className="w-5 h-5 mx-auto mb-1.5 text-muted-foreground group-hover:text-primary transition-colors" strokeWidth={1.5} />
    <p className="text-xs font-semibold text-foreground">{label}</p>
  </button>
);

export default HomePage;
