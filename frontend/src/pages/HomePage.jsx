/**
 * HOME PAGE — "What should I do right now?"
 *
 * Design philosophy:
 * - One big coaching action (not a dashboard of stats)
 * - Daily puzzle from their own games (creates login habit)
 * - Last game with ONE takeaway (not a data dump)
 * - Streak/momentum indicator (emotional feedback)
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import LichessBoard from "@/components/LichessBoard";
import {
  ChevronRight, Swords, Import, FlaskConical,
  Trophy, TrendingUp, ArrowRight,
  Zap, AlertTriangle, Target, BarChart3,
  Brain, Clock, Flame
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
  const dna = data?.chess_dna;
  const fix = data?.one_thing_to_fix;
  const streak = data?.streak;
  const patterns = data?.patterns || [];
  const accuracy = data?.accuracy || 0;
  const gamesAnalyzed = data?.games_analyzed || 0;
  const review = data?.review_progress || {};
  const strengthProfile = data?.strength_profile;
  const trainingReady = data?.training_ready;
  const gamesImported = data?.games_imported || 0;

  const moodOverride = coachIntel?.mood_override;
  const progressTrend = coachIntel?.progress_trend;
  const trainingRec = coachIntel?.training_recommendation;
  const topPattern = patterns[0];

  // ── Empty state: no games at all ──
  if (!battle && gamesAnalyzed === 0 && gamesImported === 0) {
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
            <button onClick={() => navigate("/import")} className="px-6 py-3 text-sm gradient-gold text-black rounded-lg hover:opacity-90 transition-all font-semibold shadow-lg shadow-amber-500/20" data-testid="import-cta">
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

  // ── Analyzing state ──
  if (!battle && gamesAnalyzed === 0 && gamesImported > 0) {
    return (
      <Layout user={user}>
        <div className="max-w-xl mx-auto px-4 py-16" data-testid="home-page">
          <div className="text-center mb-8">
            <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-5">
              <div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
            </div>
            <h1 className="text-2xl font-heading text-foreground tracking-tight mb-2">
              Analyzing {gamesImported} games
            </h1>
            <p className="text-muted-foreground text-sm leading-relaxed max-w-sm mx-auto">
              Your coach is studying every move. This takes a few minutes.
            </p>
          </div>

          <div className="bg-card border border-border rounded-xl p-5 mb-6">
            <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-3">What your coach is doing</p>
            <div className="space-y-2.5">
              {["Analyzing every move with Stockfish", "Finding your recurring mistake patterns", "Extracting training positions from your blunders", "Building your strength profile across 6 domains"].map((step, i) => (
                <div key={i} className="flex items-center gap-2.5 text-sm text-muted-foreground">
                  <div className="w-5 h-5 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                    <span className="text-[10px] font-bold text-primary">{i + 1}</span>
                  </div>
                  {step}
                </div>
              ))}
            </div>
          </div>

          <div className="bg-card border border-border rounded-xl p-5 mb-6">
            <p className="text-sm text-foreground mb-4">Play a game with your coach while analysis runs.</p>
            <button onClick={() => navigate("/play-with-coach")} className="w-full px-6 py-3 text-sm gradient-gold text-black rounded-lg hover:opacity-90 transition-all font-semibold shadow-lg shadow-amber-500/20">
              <Swords className="w-4 h-4 inline mr-2" strokeWidth={2} />
              Play with Coach
            </button>
          </div>

          <div className="text-center">
            <button onClick={() => window.location.reload()} className="text-xs text-muted-foreground/50 hover:text-muted-foreground transition-colors">
              Check if analysis is ready
            </button>
          </div>
        </div>
      </Layout>
    );
  }

  // ── MAIN HOME PAGE ──
  const coach = getCoachAction({
    moodOverride, streak, topPattern, fix, dna, review, battle, progressTrend, strengthProfile, trainingRec
  });

  const showBoard = battle?.fen && battle?.move_number > 0;
  const userWon = battle && ((battle.result === "1-0" && battle.user_color === "white") || (battle.result === "0-1" && battle.user_color === "black"));
  const userLost = battle && !userWon && !(battle.result || "").includes("1/2");

  return (
    <Layout user={user}>
      <div className="max-w-2xl mx-auto px-4 py-6" data-testid="home-page">

        {/* ═══ THE ONE THING — Coach's instruction ═══ */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
          <div className={`rounded-2xl border relative overflow-hidden mb-6 ${coach.borderClass}`}>
            <div className={`absolute top-0 right-0 w-64 h-64 rounded-full blur-3xl -translate-y-1/3 translate-x-1/3 ${coach.glowClass}`} />

            <div className="relative p-6">
              {/* Coach avatar + status */}
              <div className="flex items-center gap-3 mb-4">
                <div className="relative">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-amber-500/20 to-amber-600/10 flex items-center justify-center">
                    <Brain className="w-5 h-5 text-amber-500" />
                  </div>
                  <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-emerald-500 border-2 border-background" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-foreground">Your Coach</p>
                  {coach.badge && (
                    <div className={`inline-flex items-center gap-1 text-[10px] font-semibold ${coach.badgeTextClass}`}>
                      <coach.badgeIcon className="w-2.5 h-2.5" strokeWidth={2.5} />
                      {coach.badge}
                    </div>
                  )}
                </div>
              </div>

              {/* The message */}
              <h1 className="text-xl sm:text-[22px] font-heading text-foreground tracking-tight leading-snug mb-2">
                {coach.message}
              </h1>
              {coach.sub && (
                <p className="text-sm text-muted-foreground leading-relaxed mb-5">{coach.sub}</p>
              )}

              {/* Primary action — big, obvious */}
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

        {/* ═══ LAST GAME — one line, not a data dump ═══ */}
        {battle && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.06 }} className="mb-4">
            <div
              className="bg-card border border-border rounded-xl cursor-pointer transition-all hover:border-primary/20 group"
              onClick={() => navigate(`/game/${battle.game_id}`)}
              data-testid="last-battle-card"
            >
              <div className="p-4 flex items-center gap-4">
                {/* Result dot */}
                <div className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${userWon ? "bg-emerald-500" : userLost ? "bg-red-400" : "bg-muted-foreground/40"}`} />

                {/* Info */}
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
                    {battle.behavior || battle.lesson_label || (battle.opening ? `${battle.opening}` : "Review this game")}
                  </p>
                </div>

                {/* Mini board */}
                {showBoard && (
                  <div className="hidden sm:block w-[56px] h-[56px] flex-shrink-0 rounded overflow-hidden border border-border/50">
                    <LichessBoard fen={battle.fen} orientation={battle.user_color} viewOnly={true} />
                  </div>
                )}

                <ChevronRight className="w-4 h-4 text-muted-foreground/20 group-hover:text-primary transition-colors flex-shrink-0" />
              </div>
            </div>
          </motion.div>
        )}

        {/* ═══ QUICK ACTIONS — 3 cards ═══ */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
          <div className="grid grid-cols-3 gap-2.5">
            <ActionCard
              icon={Swords}
              label="Play"
              sub="with coach"
              onClick={() => navigate("/play-with-coach")}
              highlight={!topPattern}
            />
            <ActionCard
              icon={FlaskConical}
              label="Lab"
              sub={review.pending > 0 ? `${review.pending} to review` : "game review"}
              onClick={() => navigate("/lab")}
              badge={review.pending > 0 ? review.pending : null}
            />
            <ActionCard
              icon={BarChart3}
              label="Progress"
              sub={accuracy > 0 ? `${accuracy.toFixed(0)}% acc` : "your stats"}
              onClick={() => navigate("/progress")}
            />
          </div>
        </motion.div>

        {/* ═══ MOMENTUM — streak or form ═══ */}
        {(streak?.count >= 2 || (accuracy > 0 && gamesAnalyzed >= 5)) && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.14 }} className="mt-4">
            <div className="bg-card border border-border rounded-xl px-4 py-3 flex items-center justify-between">
              {streak?.count >= 2 ? (
                <>
                  <div className="flex items-center gap-2">
                    <Flame className={`w-4 h-4 ${streak.type === "W" ? "text-emerald-500" : "text-red-400"}`} />
                    <span className="text-sm text-foreground font-medium">
                      {streak.count}-game {streak.type === "W" ? "win" : "loss"} streak
                    </span>
                  </div>
                  <span className={`text-xs font-mono font-bold ${streak.type === "W" ? "text-emerald-500" : "text-red-400"}`}>
                    {streak.count}{streak.type}
                  </span>
                </>
              ) : (
                <>
                  <div className="flex items-center gap-2">
                    <Target className="w-4 h-4 text-primary" />
                    <span className="text-sm text-foreground font-medium">
                      {gamesAnalyzed} games analyzed
                    </span>
                  </div>
                  <span className="text-xs font-mono text-muted-foreground">
                    {accuracy.toFixed(0)}% accuracy
                  </span>
                </>
              )}
            </div>
          </motion.div>
        )}

      </div>
    </Layout>
  );
};


// ═══ COACH ACTION ENGINE ═══
// Returns THE ONE THING the coach wants the user to do right now.

function getCoachAction({ moodOverride, streak, topPattern, fix, dna, review, battle, progressTrend, strengthProfile, trainingRec }) {
  const defaults = {
    borderClass: "border-border bg-card",
    glowClass: "bg-primary/5",
    badge: null, badgeIcon: Zap, badgeTextClass: "text-muted-foreground",
    message: "Ready to play?",
    sub: null,
    actionLabel: "Play with Coach",
    actionHref: "/play-with-coach",
    actionIcon: Swords,
  };

  // P0: Win streak — keep momentum
  if (moodOverride?.type === "positive_momentum" && moodOverride.streak >= 3) {
    return { ...defaults,
      borderClass: "border-emerald-500/20 bg-emerald-500/[0.03]",
      glowClass: "bg-emerald-500/10",
      badge: `${moodOverride.streak} wins in a row`, badgeIcon: Trophy,
      badgeTextClass: "text-emerald-500",
      message: "You're on fire. Don't stop now.",
      sub: "Your play is clicking. Keep the same approach — don't change what's working.",
      actionLabel: "Play Another", actionIcon: Swords,
    };
  }

  // P1: Loss streak — stop and review
  if (streak?.type === "L" && streak.count >= 3) {
    return { ...defaults,
      borderClass: "border-red-500/15 bg-red-500/[0.02]",
      glowClass: "bg-red-500/5",
      badge: `${streak.count} losses`, badgeIcon: AlertTriangle,
      badgeTextClass: "text-red-400",
      message: "Stop playing. Review first.",
      sub: "Losing streaks come from one repeating mistake. Let's find it before you play again.",
      actionLabel: "Review Last Loss",
      actionHref: battle ? `/game/${battle.game_id}` : "/lab",
      actionIcon: FlaskConical,
    };
  }

  // P2: Training recommendation — knows vs doesn't know
  if (trainingRec) {
    if (trainingRec.status === "knowledge_gap") {
      return { ...defaults,
        borderClass: "border-amber-500/15 bg-amber-500/[0.02]",
        glowClass: "bg-amber-500/5",
        badge: trainingRec.label, badgeIcon: Brain,
        badgeTextClass: "text-amber-500",
        message: trainingRec.message,
        sub: "You solve it in training but miss it in games. That's a focus problem, not a knowledge problem.",
        actionLabel: "Play with Focus",
        actionHref: "/play-with-coach",
        actionIcon: Swords,
      };
    }
    if (trainingRec.status === "needs_practice") {
      return { ...defaults,
        borderClass: "border-amber-500/15 bg-amber-500/[0.02]",
        glowClass: "bg-amber-500/5",
        badge: trainingRec.label, badgeIcon: Target,
        badgeTextClass: "text-amber-500",
        message: trainingRec.message,
        actionLabel: `Train ${trainingRec.label}`,
        actionHref: `/training?focus=${trainingRec.pattern}`,
        actionIcon: Target,
      };
    }
    if (trainingRec.status === "untrained") {
      return { ...defaults,
        borderClass: "border-primary/15 bg-card",
        glowClass: "bg-primary/5",
        badge: trainingRec.label, badgeIcon: Target,
        badgeTextClass: "text-primary",
        message: trainingRec.message,
        actionLabel: `Start Training`,
        actionHref: `/training?focus=${trainingRec.pattern}`,
        actionIcon: Target,
      };
    }
  }

  // P3: Many unreviewed games
  if (review.pending >= 3) {
    return { ...defaults,
      borderClass: "border-primary/15 bg-card",
      glowClass: "bg-primary/5",
      badge: `${review.pending} insights`, badgeIcon: FlaskConical,
      badgeTextClass: "text-primary",
      message: `${review.pending} games analyzed. Your coach found things to show you.`,
      actionLabel: "Open Lab", actionHref: "/lab", actionIcon: FlaskConical,
    };
  }

  // P4: Critical pattern
  if (topPattern && topPattern.recent_count >= 4) {
    return { ...defaults,
      borderClass: "border-amber-500/15 bg-card",
      glowClass: "bg-amber-500/5",
      badge: `${topPattern.recent_count}x recently`, badgeIcon: Target,
      badgeTextClass: "text-amber-500",
      message: `${topPattern.label} keeps showing up. Train it until it stops.`,
      actionLabel: `Train ${topPattern.label}`,
      actionHref: `/training?focus=${topPattern.pattern_type}`,
      actionIcon: Target,
    };
  }

  // P5: Improving
  if (progressTrend?.trend === "improving") {
    return { ...defaults,
      borderClass: "border-emerald-500/10 bg-card", glowClass: "bg-emerald-500/5",
      badge: "Improving", badgeIcon: TrendingUp,
      badgeTextClass: "text-emerald-500",
      message: progressTrend.message || "Your play is getting sharper. Keep going.",
    };
  }

  // P6: Fix suggestion
  if (fix?.fix_line) {
    return { ...defaults, message: fix.fix_line, sub: fix.stat_line || null,
      actionLabel: fix.pattern ? `Train ${fix.pattern.replace(/_/g, " ")}` : "Play with Coach",
      actionHref: fix.pattern ? `/training?focus=${fix.pattern}` : "/play-with-coach",
      actionIcon: fix.pattern ? Target : Swords,
    };
  }

  // Default: play
  return defaults;
}


// ═══ Components ═══

const ActionCard = ({ icon: Icon, label, sub, onClick, highlight, badge }) => (
  <button
    onClick={onClick}
    className={`bg-card border rounded-xl p-4 text-left transition-all hover:border-primary/20 hover:shadow-sm group ${
      highlight ? "border-primary/15" : "border-border"
    }`}
  >
    <div className="flex items-center justify-between mb-2">
      <Icon className={`w-4.5 h-4.5 ${highlight ? "text-primary" : "text-muted-foreground"} group-hover:text-primary transition-colors`} strokeWidth={1.5} />
      {badge && (
        <span className="w-5 h-5 rounded-full gradient-gold text-[10px] font-bold text-black flex items-center justify-center">{badge}</span>
      )}
    </div>
    <p className="text-sm font-semibold text-foreground">{label}</p>
    <p className="text-[11px] text-muted-foreground mt-0.5">{sub}</p>
  </button>
);

export default HomePage;
