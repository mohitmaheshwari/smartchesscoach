/**
 * HOME PAGE — Coach Session Start
 *
 * 3 sections:
 * 1. Coach Card — context-aware message + board position + training CTA + quick actions
 * 2. Last Game — what just happened
 * 3. This Week — 3 numbers
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
  Zap, AlertTriangle, Target, BarChart3
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
  const topPattern = patterns[0];

  const coachState = getCoachState({
    moodOverride, streak, topPattern, fix, dna, review, battle, progressTrend, strengthProfile
  });

  // Determine if we have a board position to show (the mistake that matters)
  const showBoard = battle?.fen && battle?.move_number > 0;

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

  // ── Analyzing state: games imported but not yet analyzed by Stockfish ──
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

          {/* What's happening */}
          <div className="bg-card border border-border rounded-xl p-5 mb-6">
            <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-3">What your coach is doing right now</p>
            <div className="space-y-2.5">
              {[
                "Analyzing every move with Stockfish",
                "Finding your recurring mistake patterns",
                "Extracting training positions from your blunders",
                "Building your strength profile across 6 domains",
              ].map((step, i) => (
                <div key={i} className="flex items-center gap-2.5 text-sm text-muted-foreground">
                  <div className="w-5 h-5 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                    <span className="text-[10px] font-bold text-primary">{i + 1}</span>
                  </div>
                  {step}
                </div>
              ))}
            </div>
          </div>

          {/* While you wait */}
          <div className="bg-card border border-border rounded-xl p-5 mb-6">
            <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-3">While you wait</p>
            <p className="text-sm text-foreground mb-4">Play a game with your coach — it'll give you real-time feedback even before analysis finishes.</p>
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

  return (
    <Layout user={user}>
      <div className="max-w-3xl mx-auto px-4 py-6" data-testid="home-page">

        {/* ═══ SECTION 1: COACH CARD ═══ */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
          <div className={`rounded-xl border relative overflow-hidden ${coachState.borderClass}`}>
            {/* Glow */}
            <div className={`absolute top-0 right-0 w-56 h-56 rounded-full blur-3xl -translate-y-1/3 translate-x-1/3 ${coachState.glowClass}`} />

            <div className="relative">
              {/* ── Top section: Message + Board ── */}
              <div className={`p-5 ${showBoard ? 'pb-4' : ''}`}>
                {/* Badge */}
                {coachState.badge && (
                  <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold mb-3 ${coachState.badgeClass}`}>
                    <coachState.badgeIcon className="w-3 h-3" strokeWidth={2.5} />
                    {coachState.badge}
                  </div>
                )}

                <div className={showBoard ? "flex gap-5" : ""}>
                  {/* Coach message */}
                  <div className="flex-1 min-w-0">
                    <h1 className="text-xl sm:text-2xl font-heading text-foreground tracking-tight leading-snug mb-2">
                      {coachState.message}
                    </h1>
                    {coachState.sub && (
                      <p className="text-sm text-muted-foreground leading-relaxed mb-4">{coachState.sub}</p>
                    )}

                    {/* Primary CTA */}
                    <button
                      onClick={() => navigate(coachState.actionHref)}
                      className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold rounded-lg gradient-gold text-black hover:opacity-90 transition-all shadow-md shadow-amber-500/15"
                      data-testid="coach-cta"
                    >
                      <coachState.actionIcon className="w-4 h-4" strokeWidth={2} />
                      {coachState.actionLabel}
                      <ChevronRight className="w-3.5 h-3.5 opacity-60" />
                    </button>
                  </div>

                  {/* Board position — the move that matters */}
                  {showBoard && (
                    <div
                      className="hidden sm:block w-[120px] flex-shrink-0 cursor-pointer rounded-lg overflow-hidden border border-border/50 hover:border-primary/30 transition-all"
                      onClick={() => navigate(`/game/${battle.game_id}`)}
                      title={`Move ${battle.move_number}: ${battle.your_move} → ${battle.best_move}`}
                    >
                      <LichessBoard fen={battle.fen} orientation={battle.user_color} viewOnly={true} />
                    </div>
                  )}
                </div>
              </div>

              {/* ── Bottom section: Quick Actions ── */}
              <div className="border-t border-border/50 px-5 py-3 flex items-center gap-2 flex-wrap">
                <QuickAction
                  icon={Swords}
                  label="Play"
                  onClick={() => navigate("/play-with-coach")}
                  active={coachState.actionHref === "/play-with-coach"}
                />
                {topPattern && (
                  <QuickAction
                    icon={Target}
                    label={`Train ${topPattern.label}`}
                    onClick={() => navigate(`/training?focus=${topPattern.pattern_type}`)}
                    active={coachState.actionHref?.includes("training")}
                    count={trainingReady?.puzzles_available}
                  />
                )}
                <QuickAction
                  icon={FlaskConical}
                  label={review.pending > 0 ? `Lab (${review.pending})` : "Lab"}
                  onClick={() => navigate("/lab")}
                  active={coachState.actionHref === "/lab"}
                />
                <QuickAction
                  icon={BarChart3}
                  label="Progress"
                  onClick={() => navigate("/progress")}
                />
              </div>
            </div>
          </div>
        </motion.div>

        {/* ═══ SECTION 2: LAST GAME ═══ */}
        {battle && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }} className="mb-8">
            <Label>Last Game</Label>
            <div
              className="bg-card border border-border cursor-pointer transition-all duration-200 hover:border-primary/25 rounded-xl overflow-hidden group"
              onClick={() => navigate(`/game/${battle.game_id}`)}
              data-testid="last-battle-card"
            >
              <div className="p-4 flex items-center gap-4">
                {/* Result indicator */}
                <ResultDot result={battle.result} userColor={battle.user_color} />

                {/* Game info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                    <span className="text-sm font-semibold text-foreground">vs {battle.opponent}</span>
                    <ResultBadge result={battle.result} userColor={battle.user_color} />
                    {battle.brilliant_moves > 0 && (
                      <span className="inline-flex items-center gap-0.5 text-[9px] font-bold uppercase tracking-wider text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded-md border border-amber-500/20">
                        <Zap className="w-2.5 h-2.5" strokeWidth={2.5} />
                      </span>
                    )}
                    {battle.opening && <span className="text-xs text-muted-foreground/40 hidden sm:inline">{battle.opening}</span>}
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed line-clamp-1">
                    {battle.lesson_label ? `${battle.lesson_label} — ` : ""}{battle.behavior || dna?.root_cause || "Review this game"}
                  </p>
                </div>

                {/* Move comparison */}
                {battle.move_number > 0 && battle.your_move && (
                  <div className="hidden sm:flex items-center gap-1.5 text-[11px] font-mono flex-shrink-0">
                    <span className="text-red-400 bg-red-500/10 px-1.5 py-0.5 rounded">{battle.your_move}</span>
                    <ArrowRight className="w-3 h-3 text-muted-foreground/20" />
                    <span className="text-emerald-500 bg-emerald-500/10 px-1.5 py-0.5 rounded">{battle.best_move}</span>
                  </div>
                )}

                <ChevronRight className="w-4 h-4 text-muted-foreground/20 group-hover:text-primary transition-colors flex-shrink-0" />
              </div>
            </div>
          </motion.div>
        )}

        {/* ═══ SECTION 3: THIS WEEK ═══ */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.14 }}>
          <Label>This Week</Label>
          <div className="grid grid-cols-3 gap-3">
            <StatCard value={gamesAnalyzed} label="Games" />
            <StatCard
              value={accuracy > 0 ? `${accuracy.toFixed(0)}%` : "\u2014"}
              label="Accuracy"
              color={accuracy >= 75 ? 'text-emerald-500' : accuracy >= 55 ? 'text-foreground' : accuracy > 0 ? 'text-red-400' : 'text-muted-foreground'}
            />
            {streak && streak.count >= 2 ? (
              <StatCard
                value={`${streak.count}${streak.type}`}
                label="Streak"
                color={streak.type === "W" ? "text-emerald-500" : streak.type === "L" ? "text-red-400" : "text-muted-foreground"}
              />
            ) : review.pending > 0 ? (
              <StatCard value={review.pending} label="Insights" color="text-primary" />
            ) : (
              <StatCard value={patterns.length} label="Patterns" />
            )}
          </div>
        </motion.div>

      </div>
    </Layout>
  );
};


// ═══ COACH STATE ENGINE ═══

function getCoachState({ moodOverride, streak, topPattern, fix, dna, review, battle, progressTrend, strengthProfile }) {
  const defaults = {
    borderClass: "border-border bg-card",
    glowClass: "bg-primary/5",
    badge: null, badgeIcon: Zap, badgeClass: "",
    message: "Ready for some chess?",
    sub: null,
    actionLabel: "Play with Coach",
    actionHref: "/play-with-coach",
    actionIcon: Swords,
  };

  // P1: Win streak
  if (moodOverride?.type === "positive_momentum" && moodOverride.streak >= 3) {
    return { ...defaults,
      borderClass: "border-emerald-500/20 bg-emerald-500/5",
      glowClass: "bg-emerald-500/10",
      badge: `${moodOverride.streak}-game win streak`, badgeIcon: Trophy,
      badgeClass: "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20",
      message: moodOverride.message || "You're on fire. Keep this momentum.",
      sub: "Your play is clicking. Don't change anything — just keep playing.",
      actionLabel: "Play Another", actionIcon: Swords,
    };
  }

  // P2: Loss streak
  if (streak?.type === "L" && streak.count >= 3) {
    return { ...defaults,
      borderClass: "border-red-500/20 bg-red-500/5",
      glowClass: "bg-red-500/8",
      badge: `${streak.count} losses in a row`, badgeIcon: AlertTriangle,
      badgeClass: "bg-red-500/10 text-red-400 border border-red-500/20",
      message: "Let's stop the bleeding. Review your last loss before playing again.",
      sub: "Losing streaks usually come from one repeating mistake. Let's find it.",
      actionLabel: "Review Last Loss",
      actionHref: battle ? `/game/${battle.game_id}` : "/lab",
      actionIcon: FlaskConical,
    };
  }

  // P3: Many insights waiting
  if (review.pending >= 3) {
    return { ...defaults,
      borderClass: "border-primary/15 bg-card",
      glowClass: "bg-primary/5",
      badge: `${review.pending} new insights`, badgeIcon: FlaskConical,
      badgeClass: "bg-primary/10 text-primary border border-primary/20",
      message: `Your coach analyzed ${review.pending} games and found things worth seeing.`,
      sub: "Patterns, mistakes, and moments you can learn from — all waiting in the Lab.",
      actionLabel: "See What Coach Found", actionHref: "/lab", actionIcon: FlaskConical,
    };
  }

  // P4: Critical pattern — direct to training
  if (topPattern && (topPattern.severity === "critical" || topPattern.severity === "high") && topPattern.recent_count >= 4) {
    return { ...defaults,
      borderClass: "border-amber-500/15 bg-card",
      glowClass: "bg-amber-500/5",
      badge: `${topPattern.recent_count}x recently`, badgeIcon: Target,
      badgeClass: "bg-amber-500/10 text-amber-400 border border-amber-500/20",
      message: `${topPattern.label} keeps coming back. Let's drill it until it stops.`,
      sub: topPattern.recent_count >= 5
        ? "This is showing up in almost every game. It's your biggest leak."
        : "This pattern is recurring. Targeted practice can break it.",
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
      badgeClass: "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20",
      message: progressTrend.message || "Your play is getting better. Keep the momentum.",
      sub: topPattern ? `Focus area: ${topPattern.label} (${topPattern.recent_count}x recently)` : null,
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

  // P7: DNA insight
  if (dna?.root_cause) {
    return { ...defaults, message: dna.root_cause, sub: dna.after_line || null };
  }

  return defaults;
}


// ═══ Components ═══

const Label = ({ children }) => (
  <p className="text-[10px] tracking-[0.15em] uppercase mb-2.5 font-bold text-muted-foreground/70">{children}</p>
);

const QuickAction = ({ icon: Icon, label, onClick, active, count }) => (
  <button
    onClick={onClick}
    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
      active
        ? "bg-primary/10 text-primary border border-primary/20"
        : "text-muted-foreground hover:text-foreground hover:bg-muted/50 border border-transparent"
    }`}
  >
    <Icon className="w-3.5 h-3.5" strokeWidth={1.5} />
    {label}
    {count > 0 && <span className="font-mono text-[10px] text-muted-foreground">({count})</span>}
  </button>
);

const StatCard = ({ value, label, color = "text-foreground" }) => (
  <div className="bg-card border border-border rounded-xl p-4 text-center">
    <p className={`text-2xl font-mono font-bold ${color}`}>{value}</p>
    <p className="text-[10px] uppercase tracking-wider text-muted-foreground mt-1">{label}</p>
  </div>
);

const ResultDot = ({ result, userColor }) => {
  const won = (result === "1-0" && userColor === "white") || (result === "0-1" && userColor === "black");
  const draw = (result || "").includes("1/2");
  return (
    <div className={`w-3 h-3 rounded-full flex-shrink-0 ${won ? "bg-emerald-500" : draw ? "bg-muted-foreground/40" : "bg-red-400"}`} />
  );
};

const ResultBadge = ({ result, userColor }) => {
  const won = (result === "1-0" && userColor === "white") || (result === "0-1" && userColor === "black");
  const draw = (result || "").includes("1/2");
  const cls = won ? "bg-emerald-500/15 text-emerald-500 border-emerald-500/25"
    : draw ? "bg-muted text-muted-foreground border-border"
    : "bg-red-500/15 text-red-400 border-red-500/25";
  return <span className={`text-[10px] px-2 py-0.5 font-bold rounded-md border ${cls}`}>{won ? "WON" : draw ? "DRAW" : "LOST"}</span>;
};

export default HomePage;
