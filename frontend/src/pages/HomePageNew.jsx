/**
 * HOME — One coach. One priority. One week.
 *
 * NEW DESIGN (2026-07-11):
 *   - Coach's opening (personality, one-sentence focus)
 *   - TODAY (immediate exercise from active training)
 *   - You're improving (proof metrics)
 *   - Next in queue (detected but not started)
 *   - Navigation tiles
 *
 * Removes: generic rules, progress bars on untouched, info overload.
 * Focuses: singular active training plan.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import { pageEnter, staggerContainer, staggerItem, fadeInUp, scaleIn } from "@/lib/motion";
import Layout from "@/components/Layout";
import CoachRecommendationsGrid from "@/components/CoachRecommendationsGrid";
import CoachWeeklySignalCard from "@/components/Home/CoachWeeklySignalCard";
import {
  ChevronRight,
  Swords,
  FlaskConical,
  Target,
  BookOpen,
  Import,
  ArrowRight,
  TrendingUp,
  Zap,
  Flame,
  Award,
} from "lucide-react";

const DOMAIN_LABELS = {
  tactical_vision: "Tactical Vision",
  calculation_depth: "Calculation Depth",
  positional_sense: "Positional Sense",
  endgame_technique: "Endgame Technique",
  opening_knowledge: "Opening Knowledge",
  pressure_handling: "Pressure Handling",
};

const timeOfDayGreeting = () => {
  const h = new Date().getHours();
  if (h < 5) return "Up late";
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
};

const formatWhen = () => {
  const now = new Date();
  const day = now.toLocaleDateString(undefined, { weekday: "long" });
  const time = now.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
  return `${day} · ${time}`;
};

const NAV = [
  { id: "play", icon: Swords, label: "Play with Coach", sub: "coached games", href: "/play-with-coach" },
  { id: "lab", icon: FlaskConical, label: "Lab", sub: "review games", href: "/lab" },
  { id: "training", icon: Target, label: "Training", sub: "drill patterns", href: "/training" },
  { id: "openings", icon: BookOpen, label: "Openings", sub: "your repertoire", href: "/openings" },
];

export default function HomePageNew({ user }) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [hasGames, setHasGames] = useState(false);
  const [prescription, setPrescription] = useState(null);
  const [todayExercise, setTodayExercise] = useState(null);
  const [proof, setProof] = useState(null);
  const [queuedModules, setQueuedModules] = useState([]);
  const [dailyFix, setDailyFix] = useState(null);
  const [streak, setStreak] = useState(null);
  const [diagnosticStatus, setDiagnosticStatus] = useState(null);
  const [strengthProfile, setStrengthProfile] = useState(null);
  const [identitySummary, setIdentitySummary] = useState(null);
  const [breakthroughSignal, setBreakthroughSignal] = useState(null);
  const [showAllDomains, setShowAllDomains] = useState(false);
  const [lastSession, setLastSession] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        // Check diagnostic status
        const diagRes = await fetch(`${API}/diagnostic/status`, { credentials: "include" });
        if (diagRes.ok) {
          const diag = await diagRes.json();
          setDiagnosticStatus(diag);
        }

        // Check if user has games
        const dashRes = await fetch(`${API}/home/dashboard-v2`, { credentials: "include" });
        if (dashRes.ok) {
          const d = await dashRes.json();
          if (d.games_analyzed > 0 || d.games_imported > 0) setHasGames(true);
          if (d.strength_profile) setStrengthProfile(d.strength_profile);
          if (d.last_session) setLastSession(d.last_session);
        }

        // Fetch active prescription
        const presRes = await fetch(`${API}/coaching/current-prescriptions`, { credentials: "include" });
        if (presRes.ok) {
          const presData = await presRes.json();
          const activePres = presData.prescriptions?.find(p => p.status === 'active');
          if (activePres) {
            setPrescription(activePres);

            // Fetch modules for today's exercise
            const modRes = await fetch(
              `${API}/coaching/training-modules?prescription_id=${activePres.prescription_id}`,
              { credentials: "include" }
            );
            if (modRes.ok) {
              const modData = await modRes.json();
              if (modData.modules && modData.modules.length > 0) {
                setTodayExercise(modData.modules[0]);
                if (modData.modules.length > 1) {
                  setQueuedModules(modData.modules.slice(1));
                }
              }
            }
          }
        }

        // Fetch improvement proof
        const proofRes = await fetch(`${API}/progress/improvement-proof`, { credentials: "include" });
        if (proofRes.ok) {
          setProof(await proofRes.json());
        }

        // Fetch today's daily fix + practice streak
        const fixRes = await fetch(`${API}/daily-fix/today`, { credentials: "include" });
        if (fixRes.ok) {
          const fixData = await fixRes.json();
          setDailyFix(fixData);
          if (fixData.streak) setStreak(fixData.streak);
        }

        // Fetch identity trajectory summary
        const idRes = await fetch(`${API}/coach/identity/summary`, { credentials: "include" });
        if (idRes.ok) {
          const idData = await idRes.json();
          if (idData.has_data) setIdentitySummary(idData);
        }

        // Fetch weekly breakthrough/plateau signal
        const btRes = await fetch(`${API}/coach/breakthrough-signal`, { credentials: "include" });
        if (btRes.ok) {
          const btData = await btRes.json();
          if (btData.show_card) setBreakthroughSignal(btData);
        }
      } catch (e) {
        console.error("Error loading home data:", e);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // ─── Pretty name ───────────────────────────────────────────────────
  const rawName = user?.display_name || user?.name || user?.email?.split("@")[0] || "";
  const firstName = rawName.split(/[._-]/).filter(Boolean)[0] || "";
  const displayName =
    firstName.length <= 12
      ? firstName.charAt(0).toUpperCase() + firstName.slice(1).toLowerCase()
      : "";

  // ─── Onboarding ────────────────────────────────────────────────────
  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center h-[60vh]">
          <div className="w-6 h-6 border-2 border-violet-400/30 border-t-violet-400 rounded-full animate-spin" />
        </div>
      </Layout>
    );
  }

  if (!hasGames) {
    return (
      <Layout user={user}>
        <div className="max-w-[640px] mx-auto px-6 md:px-10 py-12 md:py-16" data-testid="home-page">
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-12">
            <div className="flex items-baseline justify-between">
              <p className="text-muted-foreground text-[13px]">
                {displayName ? `${timeOfDayGreeting()}, ${displayName}.` : `${timeOfDayGreeting()}.`}
              </p>
              <p className="text-muted-foreground/60 text-[11px] uppercase tracking-[0.22em]">{formatWhen()}</p>
            </div>

            {/* ─── DIAGNOSTIC CTA (ONBOARDING) ─── */}
            {(() => {
              const shouldShow = diagnosticStatus && diagnosticStatus.status !== "complete" && diagnosticStatus.status !== "superseded";
              return shouldShow;
            })() && (
              <section>
                <div className="bg-gradient-to-br from-purple-50 to-blue-50 dark:from-purple-950/30 dark:to-blue-950/30 border border-purple-200 dark:border-purple-900/50 rounded-lg p-6">
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="text-[16px] font-semibold text-foreground mb-2">Get your Chess DNA</h3>
                      <p className="text-[13px] text-foreground/85 mb-4">
                        {diagnosticStatus.status === "in_progress"
                          ? `Continue your diagnostic — ${diagnosticStatus.attempts_so_far || 0} puzzles done`
                          : "Take a 25-puzzle diagnostic to see your strengths and where to focus"}
                      </p>
                      <button
                        onClick={() => navigate("/diagnostic")}
                        className="h-9 px-4 rounded-lg bg-purple-600 hover:bg-purple-700 text-white font-medium text-[13px] transition-colors inline-flex items-center gap-2"
                      >
                        {diagnosticStatus.status === "in_progress" ? "Continue" : "Start"} diagnostic
                        <ArrowRight className="h-3.5 w-3.5" strokeWidth={2} />
                      </button>
                    </div>
                    <Zap className="h-5 w-5 text-purple-600 dark:text-purple-400 flex-shrink-0 mt-0.5" />
                  </div>
                </div>
              </section>
            )}

            <section>
              <p className="text-[10.5px] uppercase tracking-[0.22em] text-violet-500 dark:text-violet-300/80 font-semibold mb-5">
                First session
              </p>
              <h1 className="font-serif text-[32px] md:text-[44px] leading-[1.06] tracking-[-0.02em] font-medium text-foreground max-w-[560px]">
                I'm your personal chess coach. Let's find out how you play.
              </h1>
              <p className="mt-6 text-[14px] text-muted-foreground max-w-[520px] leading-relaxed">
                Play a game and I'll watch how you think. No preparation — your natural game is what I need to see.
              </p>

              <div className="mt-10 flex flex-wrap items-center gap-5">
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => navigate("/play-with-coach")}
                  className="h-12 px-7 rounded-xl bg-violet-500 hover:bg-violet-400 text-white font-medium text-[15px] transition-colors inline-flex items-center gap-2"
                >
                  <Swords className="h-4 w-4" strokeWidth={2} />
                  Play my first game
                  <ArrowRight className="h-4 w-4" strokeWidth={2} />
                </motion.button>
              </div>
            </section>

            <section className="pt-8 border-t border-border/60">
              <p className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-3">
                Already play elsewhere?
              </p>
              <p className="text-[13.5px] text-muted-foreground mb-5 leading-relaxed max-w-[480px]">
                Connect your Chess.com or Lichess account and I'll analyze your existing games.
              </p>
              <button
                onClick={() => navigate("/import")}
                className="text-[13px] text-foreground hover:underline transition-colors inline-flex items-center gap-1.5"
              >
                <Import className="h-3.5 w-3.5" strokeWidth={1.75} />
                Connect Chess.com or Lichess
              </button>
            </section>
          </motion.div>
        </div>
      </Layout>
    );
  }

  // ─── Main page ──────────────────────────────────────────────────────
  return (
    <Layout user={user}>
      <motion.div
        variants={pageEnter}
        initial="initial"
        animate="animate"
        className="max-w-[880px] mx-auto px-6 md:px-10 py-10 md:py-16"
        data-testid="home-page"
      >
        <motion.div variants={staggerContainer} initial="initial" animate="animate">
          {/* ─── GREETING ─── */}
          <motion.div variants={fadeInUp} className="flex items-baseline justify-between mb-10 md:mb-12">
            <p className="text-muted-foreground text-[13px]">
              {displayName ? `${timeOfDayGreeting()}, ${displayName}.` : `${timeOfDayGreeting()}.`}
            </p>
            <p className="text-muted-foreground/60 text-[11px] uppercase tracking-[0.22em]">{formatWhen()}</p>
          </motion.div>

          {/* ─── SINCE YOU LAST PLAYED (the Mirror) ─── */}
          {lastSession?.story && (
            <motion.section variants={fadeInUp} className="mb-12 md:mb-16">
              <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-4">
                Since you last played
              </div>
              <div className="bg-white dark:bg-slate-950 border border-gray-200 dark:border-slate-800 rounded-lg p-6">
                <p className="text-[14px] leading-relaxed text-foreground">{lastSession.story}</p>
                {(lastSession.game_id || lastSession.game_ids?.[0]) && (
                  <button
                    onClick={() => navigate(`/game/${lastSession.game_id || lastSession.game_ids[0]}`)}
                    className="mt-4 text-[12.5px] text-violet-600 dark:text-violet-400 hover:underline inline-flex items-center gap-1"
                  >
                    Review this game
                    <ChevronRight className="h-3 w-3" strokeWidth={2} />
                  </button>
                )}
              </div>
            </motion.section>
          )}

          {/* ─── COACH WEEKLY SIGNAL (breakthrough/plateau detection) ─── */}
          {breakthroughSignal && (
            <motion.section variants={fadeInUp} className="mb-12 md:mb-16">
              <CoachWeeklySignalCard
                signal={breakthroughSignal}
                onCtaClick={() => navigate("/play-with-coach")}
              />
            </motion.section>
          )}

          {/* ─── DIAGNOSTIC CTA ─── */}
          {(() => {
            const shouldShow = diagnosticStatus && diagnosticStatus.status !== "complete" && diagnosticStatus.status !== "superseded";
            return shouldShow;
          })() && (
            <motion.section variants={fadeInUp} className="mb-12 md:mb-16">
              <div className="bg-gradient-to-br from-purple-50 to-blue-50 dark:from-purple-950/30 dark:to-blue-950/30 border border-purple-200 dark:border-purple-900/50 rounded-lg p-6">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-[16px] font-semibold text-foreground mb-2">Get your Chess DNA</h3>
                    <p className="text-[13px] text-foreground/85 mb-4">
                      {diagnosticStatus.status === "in_progress"
                        ? `Continue your diagnostic — ${diagnosticStatus.attempts_so_far || 0} puzzles done`
                        : "Take a 25-puzzle diagnostic to see your strengths and where to focus"}
                    </p>
                    <button
                      onClick={() => navigate("/diagnostic")}
                      className="h-9 px-4 rounded-lg bg-purple-600 hover:bg-purple-700 text-white font-medium text-[13px] transition-colors inline-flex items-center gap-2"
                    >
                      {diagnosticStatus.status === "in_progress" ? "Continue" : "Start"} diagnostic
                      <ArrowRight className="h-3.5 w-3.5" strokeWidth={2} />
                    </button>
                  </div>
                  <Zap className="h-5 w-5 text-purple-600 dark:text-purple-400 flex-shrink-0 mt-0.5" />
                </div>
              </div>
            </motion.section>
          )}

          {/* ─── DAILY FIX ─── */}
          {dailyFix && (
            <motion.section variants={fadeInUp} className="mb-12 md:mb-16">
              <div className="flex items-center justify-between mb-4">
                <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold">
                  Today's fix
                </div>
                {streak && (streak.current > 0 ? (
                  <span className="inline-flex items-center gap-1.5 text-[12px] font-semibold text-amber-600 dark:text-amber-400">
                    <Flame className="h-3.5 w-3.5" strokeWidth={2} /> {streak.current}-day streak
                  </span>
                ) : (
                  <span className="text-[11px] text-muted-foreground">Start your streak</span>
                ))}
              </div>
              <div className="bg-white dark:bg-slate-950 border border-gray-200 dark:border-slate-800 rounded-lg p-6">
                {streak?.done_today ? (
                  <div>
                    <p className="text-[15px] font-medium text-foreground mb-1">
                      Done for today. 🔥 {streak.current}-day streak.
                    </p>
                    <p className="text-[13px] text-muted-foreground">Come back tomorrow to keep it going.</p>
                  </div>
                ) : dailyFix.drill_type === "rush_test" ? (
                  <div>
                    <h3 className="text-[16px] font-semibold text-foreground mb-2">Beat the clock</h3>
                    <p className="text-[13px] text-muted-foreground mb-4">
                      {(dailyFix.drills?.length || 5)} positions you played too fast last time. Slow down — find the move you missed.
                    </p>
                    <button
                      onClick={() => navigate("/daily-fix/drill")}
                      className="h-9 px-4 rounded-lg bg-amber-600 hover:bg-amber-700 text-white font-medium text-[13px] transition-colors inline-flex items-center gap-2"
                    >
                      Start timed fix
                      <ArrowRight className="h-3.5 w-3.5" strokeWidth={2} />
                    </button>
                  </div>
                ) : (
                  <div>
                    <h3 className="text-[16px] font-semibold text-foreground mb-2">
                      {dailyFix.mission?.focus_label || "Today's drill"}
                    </h3>
                    <p className="text-[13px] text-muted-foreground mb-4">
                      A few drills from your own games
                      {dailyFix.mission?.estimated_minutes ? ` · ~${dailyFix.mission.estimated_minutes} min` : ""}.
                    </p>
                    <button
                      onClick={() => navigate("/training/prescribed")}
                      className="h-9 px-4 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium text-[13px] transition-colors inline-flex items-center gap-2"
                    >
                      Start today's fix
                      <ArrowRight className="h-3.5 w-3.5" strokeWidth={2} />
                    </button>
                  </div>
                )}
              </div>
            </motion.section>
          )}

          {/* ─── COACH RECOMMENDATIONS & PLAN SELECTION ─── */}
          <motion.section variants={fadeInUp} className="mb-16 md:mb-20">
            <CoachRecommendationsGrid />
          </motion.section>

          {/* ─── COACH OPENING ─── */}
          {prescription && (
            <motion.section variants={fadeInUp} className="mb-12 md:mb-16">
              <div className="p-6 rounded-lg border border-blue-200/50 bg-blue-50/50 dark:bg-blue-950/20 dark:border-blue-900/50">
                <p className="text-[14px] leading-relaxed text-foreground">
                  <span className="font-medium">Coach:</span> "This week we're fixing one thing.{" "}
                  <span className="font-semibold">{prescription.reasoning}</span> For the next seven days, I only want you to focus on your {prescription.issue_detected} training."
                </p>
              </div>
            </motion.section>
          )}

          {/* ─── TODAY ─── */}
          {todayExercise && (
            <motion.section variants={fadeInUp} className="mb-12 md:mb-16">
              <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-4">
                Today
              </div>
              <div className="bg-white dark:bg-slate-950 border border-gray-200 dark:border-slate-800 rounded-lg p-6">
                <h3 className="text-[16px] font-semibold text-foreground mb-2">{todayExercise.title}</h3>
                <p className="text-[13px] text-muted-foreground mb-4">{todayExercise.description}</p>
                <button
                  onClick={() => navigate(`/training/prescribed?plan=${prescription?.plan_id}`)}
                  className="h-9 px-4 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium text-[13px] transition-colors inline-flex items-center gap-2"
                >
                  Practice
                  <ArrowRight className="h-3.5 w-3.5" strokeWidth={2} />
                </button>
                {todayExercise.duration_minutes && (
                  <p className="text-[11px] text-muted-foreground mt-3">
                    Estimated: {todayExercise.duration_minutes} min
                  </p>
                )}
              </div>
            </motion.section>
          )}

          {/* ─── YOU'RE IMPROVING ─── */}
          {proof?.has_data && proof?.primary_pattern?.reduction_pct > 0 && (
            <motion.section variants={fadeInUp} className="mb-12 md:mb-16">
              <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-4">
                You're improving
              </div>
              <div className="bg-gradient-to-br from-emerald-50 to-emerald-50/50 dark:from-emerald-950/30 dark:to-emerald-950/10 border border-emerald-200 dark:border-emerald-900/50 rounded-lg p-6">
                <div className="flex items-start gap-3">
                  <div className="pt-1">
                    <TrendingUp className="w-5 h-5 text-emerald-600 dark:text-emerald-400" strokeWidth={2} />
                  </div>
                  <div>
                    <p className="text-[14px] font-medium text-foreground mb-1">
                      {proof.primary_pattern.reduction_pct}% fewer events per game
                    </p>
                    <p className="text-[12px] text-muted-foreground">
                      {proof.primary_pattern.recent_count} events across {proof.primary_pattern.games_checked} games (7d). Keep the discipline.
                    </p>
                  </div>
                </div>
              </div>
            </motion.section>
          )}

          {/* ─── WHAT YOUR GAMES SHOW (strength profile) ─── */}
          {strengthProfile?.strongest && strengthProfile?.weakest && (
            <motion.section variants={fadeInUp} className="mb-12 md:mb-16">
              <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-4">
                What your games show
              </div>
              <div className="bg-white dark:bg-slate-950 border border-gray-200 dark:border-slate-800 rounded-lg p-6">
                <div className="flex items-start gap-3 mb-4">
                  <Award className="w-5 h-5 text-violet-500 dark:text-violet-400 flex-shrink-0 mt-0.5" strokeWidth={2} />
                  <div>
                    <p className="text-[14px] font-medium text-foreground mb-1">
                      Strongest: {DOMAIN_LABELS[strengthProfile.strongest] || strengthProfile.strongest}
                    </p>
                    <p className="text-[13px] text-muted-foreground">
                      Rated around {strengthProfile.domains?.[strengthProfile.strongest]?.rating || strengthProfile.overall_rating} on this — {strengthProfile.domains?.[strengthProfile.strongest]?.label || "strong"} play across your games.
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <Target className="w-5 h-5 text-amber-500 dark:text-amber-400 flex-shrink-0 mt-0.5" strokeWidth={2} />
                  <div>
                    <p className="text-[14px] font-medium text-foreground mb-1">
                      Needs work: {DOMAIN_LABELS[strengthProfile.weakest] || strengthProfile.weakest}
                    </p>
                    <p className="text-[13px] text-muted-foreground">
                      This is closer to {strengthProfile.domains?.[strengthProfile.weakest]?.rating || strengthProfile.overall_rating} level — the real gap between your best and weakest area right now.
                    </p>
                  </div>
                </div>

                <button
                  onClick={() => setShowAllDomains(v => !v)}
                  className="mt-4 text-[12.5px] text-violet-600 dark:text-violet-400 hover:underline inline-flex items-center gap-1"
                >
                  {showAllDomains ? "Hide" : "See all 6 areas"}
                  <ChevronRight className={`h-3 w-3 transition-transform ${showAllDomains ? "rotate-90" : ""}`} strokeWidth={2} />
                </button>

                {showAllDomains && strengthProfile.domains && (
                  <div className="mt-4 pt-4 border-t border-gray-200 dark:border-slate-800 grid grid-cols-2 gap-3">
                    {Object.entries(strengthProfile.domains)
                      .sort((a, b) => (b[1]?.score || 0) - (a[1]?.score || 0))
                      .map(([key, d]) => (
                        <div key={key} className="text-[12.5px]">
                          <span className="text-foreground font-medium">{DOMAIN_LABELS[key] || key}</span>
                          <span className="text-muted-foreground"> — {Math.round(d?.score || 0)} ({d?.label || "emerging"})</span>
                        </div>
                      ))}
                  </div>
                )}
              </div>
            </motion.section>
          )}

          {/* ─── WHO YOU ARE AS A PLAYER (identity trajectory) ─── */}
          {identitySummary && (
            <motion.section variants={fadeInUp} className="mb-12 md:mb-16">
              <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-4">
                Who you are as a player
              </div>
              <div className="bg-white dark:bg-slate-950 border border-gray-200 dark:border-slate-800 rounded-lg p-6">
                <p className="text-[15px] font-medium text-foreground mb-2">{identitySummary.archetype}</p>
                {identitySummary.summary && (
                  <p className="text-[13px] text-muted-foreground leading-relaxed">{identitySummary.summary}</p>
                )}
                <p className="text-[12px] text-muted-foreground/70 mt-3">
                  {identitySummary.comparative_insight || "Still building your trajectory — this becomes “you used to be X, now you're Y” as you play more."}
                </p>
              </div>
            </motion.section>
          )}

          {/* ─── NEXT IN QUEUE ─── */}
          {queuedModules.length > 0 && (
            <motion.section variants={fadeInUp} className="mb-12 md:mb-16">
              <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-4">
                Coming up next
              </div>
              <div className="space-y-3">
                {queuedModules.map((mod, i) => (
                  <div key={i} className="p-4 rounded-lg border border-gray-200 dark:border-slate-800 bg-white dark:bg-slate-950">
                    <p className="text-[14px] font-medium text-foreground mb-1">{mod.title}</p>
                    <p className="text-[12px] text-muted-foreground">
                      {mod.puzzle_count} puzzles · {mod.duration_minutes} min
                    </p>
                  </div>
                ))}
              </div>
            </motion.section>
          )}

          {/* ─── TRACKING (held) ─── */}
          {/* Section reserved for future decision */}

          {/* ─── NAVIGATION TILES ─── */}
          <motion.section variants={fadeInUp} className="mt-16 pt-12 border-t border-border/40">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {NAV.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    onClick={() => navigate(item.href)}
                    className="group p-4 rounded-lg border border-border/60 hover:border-border bg-white dark:bg-slate-950 hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors text-left"
                  >
                    <Icon className="w-5 h-5 text-foreground/70 group-hover:text-foreground mb-3 transition-colors" strokeWidth={1.5} />
                    <p className="text-[12px] font-medium text-foreground">{item.label}</p>
                    <p className="text-[10px] text-muted-foreground mt-1">{item.sub}</p>
                  </button>
                );
              })}
            </div>
          </motion.section>
        </motion.div>
      </motion.div>
    </Layout>
  );
}
