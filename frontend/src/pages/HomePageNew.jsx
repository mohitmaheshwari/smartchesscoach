/**
 * HOME — the coach conversation, not a dashboard.
 *
 * See docs/home_page_coach_conversation_scope.md for the full spec. The
 * page is one continuous narrative from GET /home/coach-conversation:
 * relationship-stage opener, continuity callback, a hedged belief about
 * why the headline pattern exists, one action, encouragement. No cards,
 * no percentages, no confidence scores, no elo predictions.
 */

import { useState, useEffect, useMemo, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import { ANALYTICS_EVENTS, track, trackCurriculum } from "@/lib/analytics";
import { pageEnter, staggerContainer, staggerItem, fadeInUp, scaleIn } from "@/lib/motion";
import Layout from "@/components/Layout";
import CanonicalFocusRail from "@/components/experience/CanonicalFocusRail";
import CurriculumHome from "@/components/curriculum/CurriculumHome";
import {
  ChevronRight,
  Swords,
  FlaskConical,
  Target,
  BookOpen,
  Import,
  ArrowRight,
  Zap,
} from "lucide-react";

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
  const [diagnosticStatus, setDiagnosticStatus] = useState(null);
  const [lastSession, setLastSession] = useState(null);
  const [activeFocus, setActiveFocus] = useState(null);
  const [focusGameBusy, setFocusGameBusy] = useState(false);
  const [curriculum, setCurriculum] = useState(null);
  const [curriculumLoading, setCurriculumLoading] = useState(true);
  // The single coach conversation — see docs/home_page_coach_conversation_scope.md.
  // Replaces the old recommendations grid / improvement-% / domain-score-grid
  // stack below with one narrative: relationship stage, continuity, a
  // hedged belief about why the headline pattern exists, and one action.
  const [coachConversation, setCoachConversation] = useState(null);

  // Experiment 0 (2026-08-05) — Home had zero analytics; this is pure
  // observation before any redesign, per the product-residency agreement.
  // Refs, not state, so mounting/observing doesn't trigger re-renders.
  const mirrorRef = useRef(null);
  const conversationEndRef = useRef(null);
  const mirrorSeenRef = useRef(false);
  const conversationSeenRef = useRef(false);
  const curriculumDecisionShownRef = useRef(null);
  const curriculumDecisionElementRef = useRef(null);

  useEffect(() => {
    (async () => {
      try {
        // The coach conversation — primary content for a returning user.
        const convRes = await fetch(`${API}/home/coach-conversation`, { credentials: "include" });
        if (convRes.ok) {
          const convData = await convRes.json();
          if (convData.has_conversation) setCoachConversation(convData);
        }

        const focusRes = await fetch(`${API}/coach/active-focus`, {
          credentials: "include",
        });
        if (focusRes.ok) {
          setActiveFocus(await focusRes.json());
        }

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
          if (d.last_session) setLastSession(d.last_session);
        }
      } catch (e) {
        console.error("Error loading home data:", e);
      } finally {
        setLoading(false);
        // Fired once per page load regardless of which branch (onboarding
        // / no-focus-yet / full conversation) renders — "home_viewed" is
        // the denominator every other Home event is a rate against.
        // "Return within 24h" is deliberately NOT a client event here —
        // it's computed downstream from repeat home_viewed timestamps,
        // not something a single page load can observe about itself.
        track(ANALYTICS_EVENTS.FUNNEL_HOME_VIEWED);
      }
    })();
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetch(API + "/coach/personal-curriculum", { credentials: "include" })
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (!cancelled) setCurriculum(data);
      })
      .catch(() => {
        if (!cancelled) setCurriculum(null);
      })
      .finally(() => {
        if (!cancelled) setCurriculumLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const pic = activeFocus?.personal_improvement_cycle?.eligible
    ? activeFocus.personal_improvement_cycle
    : null;
  const canonicalContext = activeFocus?.coaching_context || null;
  const currentLearningDecision = useMemo(() => (
    pic
      ? {
          decision_id: `legacy_pic:${pic.focus_kind || "piece_safety"}`,
          decision_source: "personal_improvement_cycle",
          recommendation_kind: "repair",
          content_type: "pattern_drill",
          content_id: pic.focus_kind || "piece_safety",
        }
      : null
  ), [pic]);

  useEffect(() => {
    if (!currentLearningDecision) return;
    const element = curriculumDecisionElementRef.current;
    if (!element) return;
    const observer = new IntersectionObserver((entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return;
      if (curriculumDecisionShownRef.current === currentLearningDecision.decision_id) return;
      curriculumDecisionShownRef.current = currentLearningDecision.decision_id;
      trackCurriculum(ANALYTICS_EVENTS.CURRICULUM_DECISION_SHOWN, {
        surface: "legacy_home",
        ...currentLearningDecision,
        origin: "recommendation",
        is_recommended: true,
      });
      observer.disconnect();
    }, { threshold: 0.6 });
    observer.observe(element);
    return () => observer.disconnect();
  }, [currentLearningDecision]);

  const updateFocusGame = async (action, body = null) => {
    setFocusGameBusy(true);
    try {
      const response = await fetch(
        `${API}/coach/active-focus/focus-game/${action}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: body ? JSON.stringify(body) : undefined,
        }
      );
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Focus Game update failed");
      setActiveFocus((current) => ({
        ...current,
        personal_improvement_cycle: {
          ...current.personal_improvement_cycle,
          focus_game: result.pending_focus_game,
        },
      }));
      track(ANALYTICS_EVENTS.PIC_FOCUS_GAME_UPDATED, {
        action,
        status: result.pending_focus_game?.status,
      });
    } catch (error) {
      console.error("Focus Game update failed:", error);
    } finally {
      setFocusGameBusy(false);
    }
  };

  // Mirror / Coach Conversation "seen" — IntersectionObserver, not mount,
  // since both can render off-screen below the fold on a short viewport.
  // Fires once each, ever, per page load.
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          if (entry.target === mirrorRef.current && !mirrorSeenRef.current) {
            mirrorSeenRef.current = true;
            track(ANALYTICS_EVENTS.FUNNEL_HOME_MIRROR_READ);
          }
          if (entry.target === conversationEndRef.current && !conversationSeenRef.current) {
            conversationSeenRef.current = true;
            track(ANALYTICS_EVENTS.FUNNEL_HOME_CONVERSATION_SCROLLED);
          }
        }
      },
      { threshold: 0.6 }
    );
    if (mirrorRef.current) observer.observe(mirrorRef.current);
    if (conversationEndRef.current) observer.observe(conversationEndRef.current);
    return () => observer.disconnect();
  }, [lastSession, coachConversation]);


  // ─── Pretty name ───────────────────────────────────────────────────
  const rawName = user?.display_name || user?.name || user?.email?.split("@")[0] || "";
  const firstName = rawName.split(/[._-]/).filter(Boolean)[0] || "";
  const displayName =
    firstName.length <= 12
      ? firstName.charAt(0).toUpperCase() + firstName.slice(1).toLowerCase()
      : "";

  // ─── Onboarding ────────────────────────────────────────────────────
  if (loading || curriculumLoading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center h-[60vh]">
          <div className="experience-spinner w-6 h-6 border-2 border-violet-400/30 border-t-violet-400 rounded-full animate-spin" />
        </div>
      </Layout>
    );
  }

  if (curriculum?.enabled) {
    return (
      <CurriculumHome
        user={user}
        curriculum={curriculum}
        greeting={
          displayName
            ? timeOfDayGreeting() + ", " + displayName + "."
            : timeOfDayGreeting() + "."
        }
      />
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
                <div className="experience-focus-card rounded-2xl bg-gradient-to-br from-purple-50 to-blue-50 dark:from-purple-950/30 dark:to-blue-950/30 border border-purple-200 dark:border-purple-900/50 p-6">
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
                        className="experience-primary h-9 px-4 rounded-lg bg-purple-600 hover:bg-purple-700 text-white font-medium text-[13px] transition-colors inline-flex items-center gap-2"
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
              <p className="experience-eyebrow text-[10.5px] uppercase tracking-[0.22em] text-violet-500 dark:text-violet-300/80 font-semibold mb-5">
                First session
              </p>
              <h1 className="experience-coach-copy font-serif text-[32px] md:text-[44px] leading-[1.06] tracking-[-0.02em] font-medium text-foreground max-w-[560px]">
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
                  className="experience-primary h-12 px-7 rounded-xl bg-violet-500 hover:bg-violet-400 text-white font-medium text-[15px] transition-colors inline-flex items-center gap-2"
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
            <motion.section ref={mirrorRef} variants={fadeInUp} className="mb-12 md:mb-16">
              <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-4">
                Since you last played
              </div>
              <div className="experience-surface bg-white dark:bg-slate-950 border border-gray-200 dark:border-slate-800 rounded-2xl p-6">
                <p className="text-[14px] leading-relaxed text-foreground">{lastSession.story}</p>
                {(lastSession.game_id || lastSession.game_ids?.[0]) && (
                  <button
                    onClick={() => {
                      track(ANALYTICS_EVENTS.FUNNEL_HOME_CTA_CLICKED, { cta: "review_this_game" });
                      navigate(`/game/${lastSession.game_id || lastSession.game_ids[0]}`);
                    }}
                    className="experience-link mt-4 text-[12.5px] text-violet-600 dark:text-violet-400 hover:underline inline-flex items-center gap-1"
                  >
                    Review this game
                    <ChevronRight className="h-3 w-3" strokeWidth={2} />
                  </button>
                )}
              </div>
            </motion.section>
          )}

          {/* ─── THE COACH CONVERSATION ───
              See docs/home_page_coach_conversation_scope.md. This is the
              whole page now: relationship-stage opener, continuity, a
              hedged belief about why the headline pattern exists, one
              action, encouragement. Replaces the old ten-section stack
              (recommendations grid with elo/confidence numbers, a raw
              percentage-improvement line, a numeric domain-score grid,
              and five smaller cards that all competed for "the one thing
              to do today") with a single flow. No cards, no stats. */}
          {coachConversation?.has_conversation || canonicalContext ? (
            <motion.section variants={fadeInUp} className="experience-home-coach mb-16 md:mb-20 max-w-[660px]">
              {coachConversation?.thinking_signature && (
                <p className="text-[15px] leading-relaxed text-foreground mb-5">
                  {coachConversation.thinking_signature}
                </p>
              )}
              {coachConversation?.narrative && (
                <>
                  <p className="text-[15px] leading-relaxed text-foreground mb-5">
                    {coachConversation.narrative.stage_opener}
                  </p>
                  <p className="text-[15px] leading-relaxed text-foreground mb-5">
                    {coachConversation.narrative.continuity}{" "}
                    {coachConversation.narrative.belief}
                  </p>
                </>
              )}
              {canonicalContext ? (
                <CanonicalFocusRail
                  context={canonicalContext}
                  onAction={(action) => {
                    track(ANALYTICS_EVENTS.FUNNEL_HOME_CTA_CLICKED, {
                      cta: "coaching_context_next_action",
                      schema_version: canonicalContext.schema_version,
                      context_id: canonicalContext.context_id,
                      instruction_id: canonicalContext.primary_focus?.instruction_id || null,
                      action_type: action.type,
                    });
                    navigate(action.href);
                  }}
                />
              ) : pic ? (
                <div ref={curriculumDecisionElementRef} className="experience-focus-rail border-l-2 border-violet-400/50 pl-4 mb-7 max-w-[600px]">
                  <p className="experience-eyebrow text-[10px] uppercase tracking-[0.2em] text-violet-600 dark:text-violet-400 font-semibold mb-2">
                    {pic.learner_state?.label || "Learning"}
                    {pic.learner_state?.refresh_needed ? " · Refresh needed" : ""}
                  </p>
                  <p className="text-[17px] font-medium text-foreground mb-2">
                    {pic.focus_label}
                  </p>
                  <p className="text-[14px] leading-relaxed text-foreground mb-2">
                    {pic.instruction_text || "Before you move, check whether the piece will be safe on its new square."}
                  </p>
                  <p className="text-[12.5px] leading-relaxed text-muted-foreground">
                    I verified {pic.diagnosis?.count || 0} clear example{pic.diagnosis?.count === 1 ? "" : "s"} in your games.
                    {" "}I am collecting comparable decisions, but I have not claimed improvement yet.
                  </p>
                  <div className="flex flex-wrap gap-2 mt-4">
                    <button
                      onClick={() => {
                        track(ANALYTICS_EVENTS.PIC_NEXT_ACTION_CLICKED, { action: "practice" });
                        if (currentLearningDecision) {
                          trackCurriculum(ANALYTICS_EVENTS.CURRICULUM_PRIMARY_CLICKED, {
                            surface: "legacy_home",
                            ...currentLearningDecision,
                            origin: "recommendation",
                            is_recommended: true,
                          });
                        }
                        navigate("/training/pattern/piece_safety");
                      }}
                      className="experience-primary h-9 px-4 rounded-lg bg-violet-500 hover:bg-violet-400 text-white font-medium text-[13px] transition-colors"
                    >
                      Practise this
                    </button>
                    {!pic.focus_game || ["cancelled", "completed"].includes(pic.focus_game.status) ? (
                      <button
                        disabled={focusGameBusy}
                        onClick={() => updateFocusGame("commit")}
                        className="h-9 px-4 rounded-lg border border-border text-[13px] font-medium hover:bg-muted/50 disabled:opacity-50"
                      >
                        Make my next game a Focus Game
                      </button>
                    ) : pic.focus_game.status === "waiting" ? (
                      <>
                        <span className="h-9 px-3 inline-flex items-center text-[12.5px] text-muted-foreground">
                          Committed — play on Chess.com or Lichess, then sync.
                        </span>
                        <button
                          disabled={focusGameBusy}
                          onClick={() => updateFocusGame("cancel")}
                          className="h-9 px-3 text-[12px] text-muted-foreground hover:text-foreground disabled:opacity-50"
                        >
                          Cancel
                        </button>
                      </>
                    ) : pic.focus_game.status === "claimed" ? (
                      <>
                        <span className="h-9 px-3 inline-flex items-center text-[12.5px] text-muted-foreground">
                          Focus Game captured. Analysis is measurement only for now.
                        </span>
                        <button
                          disabled={focusGameBusy}
                          onClick={() => updateFocusGame("correct", { game_id: pic.focus_game.game_id })}
                          className="h-9 px-3 text-[12px] text-muted-foreground hover:text-foreground disabled:opacity-50"
                        >
                          That was not my Focus Game
                        </button>
                      </>
                    ) : null}
                  </div>
                </div>
              ) : (
                <p className="text-[15px] leading-relaxed text-foreground font-medium mb-6">
                  {coachConversation.one_action}
                </p>
              )}
              {coachConversation?.encouragement && (
                <p className="text-[13px] text-muted-foreground mb-2">
                  {coachConversation.encouragement}
                </p>
              )}
              {coachConversation?.closing_line && (
                <p className="text-[13px] text-muted-foreground mb-8">
                  {coachConversation.closing_line}
                </p>
              )}
              {!canonicalContext && !pic && <button
                ref={conversationEndRef}
                onClick={() => {
                  track(ANALYTICS_EVENTS.FUNNEL_HOME_CTA_CLICKED, { cta: "play_with_coach", has_conversation: true });
                  navigate("/play-with-coach");
                }}
                className="experience-primary h-11 px-6 rounded-lg bg-violet-500 hover:bg-violet-400 text-white font-medium text-[14px] transition-colors inline-flex items-center gap-2"
              >
                Play with Coach
                <ArrowRight className="h-4 w-4" strokeWidth={2} />
              </button>}
            </motion.section>
          ) : (
            // No active focus assigned yet — real edge case (games exist,
            // but the coach hasn't settled on a headline pattern). Keep
            // this minimal rather than falling back to the old stack.
            <>
              {(() => {
                const shouldShow = diagnosticStatus && diagnosticStatus.status !== "complete" && diagnosticStatus.status !== "superseded";
                return shouldShow;
              })() && (
                <motion.section variants={fadeInUp} className="mb-12 md:mb-16">
                  <div className="experience-focus-card rounded-2xl bg-gradient-to-br from-purple-50 to-blue-50 dark:from-purple-950/30 dark:to-blue-950/30 border border-purple-200 dark:border-purple-900/50 p-6">
                    <div className="flex items-start justify-between">
                      <div>
                        <h3 className="text-[16px] font-semibold text-foreground mb-2">Get your Chess DNA</h3>
                        <p className="text-[13px] text-foreground/85 mb-4">
                          {diagnosticStatus.status === "in_progress"
                            ? `Continue your diagnostic — ${diagnosticStatus.attempts_so_far || 0} puzzles done`
                            : "Take a puzzle diagnostic to see your strengths and where to focus"}
                        </p>
                        <button
                          onClick={() => navigate("/diagnostic")}
                          className="experience-primary h-9 px-4 rounded-lg bg-purple-600 hover:bg-purple-700 text-white font-medium text-[13px] transition-colors inline-flex items-center gap-2"
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
              <motion.section variants={fadeInUp} className="mb-12 md:mb-16 max-w-[620px]">
                <p className="text-[15px] leading-relaxed text-foreground mb-5">
                  I'm still learning how you play. Play a game or two and I'll start noticing your habits.
                </p>
                <button
                  onClick={() => {
                    track(ANALYTICS_EVENTS.FUNNEL_HOME_CTA_CLICKED, { cta: "play_with_coach", has_conversation: false });
                    navigate("/play-with-coach");
                  }}
                  className="experience-primary h-11 px-6 rounded-lg bg-violet-500 hover:bg-violet-400 text-white font-medium text-[14px] transition-colors inline-flex items-center gap-2"
                >
                  Play with Coach
                  <ArrowRight className="h-4 w-4" strokeWidth={2} />
                </button>
              </motion.section>
            </>
          )}

          {/* ─── NAVIGATION TILES ───
              Deliberately faded — utilities, not today's mission. Mohit,
              2026-07-31 §7: "Now I'm back inside software... I'd fade
              those into the background." */}
          <motion.section variants={fadeInUp} className="mt-20 pt-10 border-t border-border/30 opacity-70 hover:opacity-100 transition-opacity">
            <p className="text-[10px] uppercase tracking-[0.22em] text-muted-foreground/70 font-medium mb-4">
              Other ways to improve
            </p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {NAV.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    onClick={() => {
                      track(ANALYTICS_EVENTS.FUNNEL_HOME_NAV_TILE_CLICKED, { tile: item.id });
                      navigate(item.href);
                    }}
                    className="experience-utility group p-3 rounded-xl border border-border/40 hover:border-border/70 bg-transparent hover:bg-slate-50 dark:hover:bg-slate-900/60 transition-colors text-left"
                  >
                    <Icon className="w-4 h-4 text-muted-foreground/70 group-hover:text-foreground mb-2 transition-colors" strokeWidth={1.5} />
                    <p className="text-[11.5px] font-medium text-muted-foreground group-hover:text-foreground transition-colors">{item.label}</p>
                    <p className="text-[9.5px] text-muted-foreground/60 mt-0.5">{item.sub}</p>
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
