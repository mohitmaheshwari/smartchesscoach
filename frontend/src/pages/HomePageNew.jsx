/**
 * HOME — Elite Chess Studio Edition
 *
 * All original texts, narrative sections, diagnostic checks, focus rails,
 * and analytics are 100% preserved.
 * The design and colors are converted to the Elite Chess Studio aesthetic:
 * tactile studio lighting, frosted glassmorphism, elegant serif typography,
 * glowing cyan accents, and refined studio cards.
 */

import { useState, useEffect, useMemo, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import ChancesCard from "@/components/coach/ChancesCard";
import CoachMovements from "@/components/coach/CoachMovements";
import { motion } from "framer-motion";
import { API } from "@/App";
import { ANALYTICS_EVENTS, track, trackCurriculum } from "@/lib/analytics";
import { pageEnter, staggerContainer, staggerItem, fadeInUp, scaleIn } from "@/lib/motion";
import Layout from "@/components/Layout";
import HomeLoadingSkeleton from "@/components/HomeLoadingSkeleton";
import CanonicalFocusRail from "@/components/experience/CanonicalFocusRail";
import CurriculumHome from "@/components/curriculum/CurriculumHome";
import { loadPersonalCurriculum } from "@/lib/personalCurriculum";
import {
  ChevronRight,
  Swords,
  FlaskConical,
  Target,
  BookOpen,
  Import,
  ArrowRight,
  Zap,
  Sparkles,
  Shield,
  Clock,
  Compass,
  Activity,
  CheckCircle2,
  Award,
  Flame,
  Brain,
  Trophy,
  TrendingUp
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
  const [coachConversation, setCoachConversation] = useState(null);

  const mirrorRef = useRef(null);
  const conversationEndRef = useRef(null);
  const mirrorSeenRef = useRef(false);
  const conversationSeenRef = useRef(false);
  const curriculumDecisionShownRef = useRef(null);
  const curriculumDecisionElementRef = useRef(null);

  useEffect(() => {
    (async () => {
      try {
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

        const diagRes = await fetch(`${API}/diagnostic/status`, { credentials: "include" });
        if (diagRes.ok) {
          const diag = await diagRes.json();
          setDiagnosticStatus(diag);
        }

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
        track(ANALYTICS_EVENTS.FUNNEL_HOME_VIEWED);
      }
    })();
  }, []);

  useEffect(() => {
    let cancelled = false;
    loadPersonalCurriculum(API, user?.user_id, "home")
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
  }, [user?.user_id]);

  const pic = activeFocus?.personal_improvement_cycle?.eligible
    ? activeFocus.personal_improvement_cycle
    : null;
  const canonicalContext = activeFocus?.coaching_context || null;
  const currentLearningDecision = useMemo(() => (
    canonicalContext
      ? {
          decision_id: `legacy_context:${canonicalContext.primary_focus?.topic_key || "current"}`,
          decision_source: "canonical_coaching_context",
          recommendation_kind: "repair",
          content_type: "coaching_focus",
          content_id: canonicalContext.primary_focus?.topic_key || "current",
        }
      : pic
        ? {
            decision_id: `legacy_pic:${pic.focus_kind || "piece_safety"}`,
            decision_source: "personal_improvement_cycle",
            recommendation_kind: "repair",
            content_type: "pattern_drill",
            content_id: pic.focus_kind || "piece_safety",
          }
        : null
  ), [canonicalContext, pic]);

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

  const rawName = user?.display_name || user?.name || user?.email?.split("@")[0] || "";
  const firstName = rawName.split(/[\s._-]/).filter(Boolean)[0] || "";
  const displayName =
    firstName.length <= 12
      ? firstName.charAt(0).toUpperCase() + firstName.slice(1).toLowerCase()
      : "";

  // ─── Loading Screen ───
  if (loading || curriculumLoading) {
    return (
      <Layout user={user}>
        <HomeLoadingSkeleton />
      </Layout>
    );
  }

  // ─── Personal Curriculum Home ───
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

  // ─── Paused Curriculum State ───
  if (curriculum?.paused) {
    return (
      <Layout user={user}>
        <main className="max-w-4xl mx-auto px-6 py-12" data-testid="phase8-paused-state">
          <motion.section
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-white/95 dark:bg-gradient-to-b dark:from-[#25323d]/85 dark:to-[#19222b]/85 border border-slate-200/90 dark:border-white/15 rounded-3xl p-8 sm:p-10 shadow-[0_20px_50px_rgba(0,0,0,0.06)] dark:shadow-[0_20px_50px_rgba(0,0,0,0.45)] backdrop-blur-xl relative overflow-hidden"
          >
            <div className="flex items-center space-x-2 text-cyan-700 dark:text-cyan-400 font-mono text-[10.5px] uppercase tracking-[0.22em] font-semibold mb-3">
              <span className="w-2 h-2 rounded-full bg-cyan-500 shadow-[0_0_8px_#38bdf8]" />
              <span>Your coaching plan</span>
            </div>
            <h1 className="font-serif text-3xl sm:text-4xl text-slate-900 dark:text-white font-normal tracking-tight mt-2">
              Your work is saved.
            </h1>
            <p className="text-slate-600 dark:text-slate-200/90 text-sm sm:text-base mt-4 max-w-[620px] leading-relaxed">
              {curriculum.message ||
                "Your lesson and progress are saved. Your coach is preparing the next step."}
            </p>
            <div className="mt-8 flex flex-wrap gap-4">
              <button
                type="button"
                onClick={() => navigate("/lab")}
                className="px-6 py-3 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 font-mono text-xs font-bold uppercase tracking-wider shadow-[0_0_20px_rgba(56,189,248,0.4)] transition-all"
              >
                Review my games
              </button>
              <button
                type="button"
                onClick={() => navigate("/training")}
                className="px-6 py-3 rounded-xl bg-slate-100 hover:bg-slate-200 border border-slate-200 text-slate-700 dark:bg-white/10 dark:hover:bg-white/15 dark:border-white/15 dark:text-slate-200 font-mono text-xs font-medium uppercase tracking-wider transition-all"
              >
                Keep practising
              </button>
            </div>
          </motion.section>
        </main>
      </Layout>
    );
  }

  // ─── First Time / No Games State (Elite Chess Studio Aesthetic) ───
  if (!hasGames) {
    return (
      <Layout user={user}>
        <div className="min-h-full py-6 px-4 sm:px-6 relative" data-testid="home-page">
          {/* Subtle Ambient Studio Lighting */}
          <div className="absolute top-0 right-1/4 w-96 h-96 bg-cyan-500/10 rounded-full blur-[140px] pointer-events-none" />
          <div className="absolute top-1/2 left-10 w-80 h-80 bg-blue-600/5 dark:bg-violet-600/10 rounded-full blur-[140px] pointer-events-none" />

          <motion.div 
            initial={{ opacity: 0, y: 16 }} 
            animate={{ opacity: 1, y: 0 }} 
            className="max-w-4xl mx-auto space-y-8 relative z-10"
          >
            {/* Header Greeting & Timestamp */}
            <div className="flex flex-col sm:flex-row sm:items-baseline justify-between pb-5 border-b border-white/15 gap-3">
              <div>
                <span className="inline-flex items-center gap-1.5 px-3.5 py-1 rounded-full bg-cyan-950/80 border border-cyan-500/40 text-xs font-mono font-bold uppercase tracking-wider text-cyan-300 mb-2 shadow-[0_0_15px_rgba(56,189,248,0.25)]">
                  <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
                  Studio Onboarding
                </span>
                <h1 className="font-heading font-extrabold text-3xl sm:text-4xl md:text-5xl text-white tracking-tight leading-tight">
                  {displayName ? `${timeOfDayGreeting()}, ${displayName}.` : `${timeOfDayGreeting()}.`}
                </h1>
              </div>
              <p className="text-slate-400 font-mono text-xs sm:text-sm font-semibold uppercase tracking-wider">{formatWhen()}</p>
            </div>

            {/* Diagnostic CTA */}
            {(() => {
              const shouldShow = diagnosticStatus && diagnosticStatus.status !== "complete" && diagnosticStatus.status !== "superseded";
              return shouldShow;
            })() && (
              <section>
                <div className="bg-gradient-to-b from-[#251f38] via-[#1c172b] to-[#120e1c] border border-violet-500/40 rounded-3xl p-7 sm:p-9 shadow-[0_20px_50px_rgba(139,92,246,0.15)] backdrop-blur-xl relative overflow-hidden">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h3 className="font-heading font-bold text-2xl sm:text-3xl text-white mb-2">
                        Let me learn how you see the board.
                      </h3>
                      <p className="text-slate-200 font-medium text-sm sm:text-base mb-6 max-w-[580px] leading-relaxed">
                        {diagnosticStatus.status === "in_progress"
                          ? "We have already started. Let’s pick up where you left off."
                          : "A short set of positions will help me choose the right first lesson for you."}
                      </p>
                      <button
                        onClick={() => navigate("/diagnostic")}
                        className="px-6 py-3.5 rounded-2xl bg-gradient-to-r from-violet-500 to-indigo-600 hover:from-violet-400 hover:to-indigo-500 text-white font-heading font-bold text-sm tracking-wide uppercase shadow-[0_0_25px_rgba(168,85,247,0.45)] inline-flex items-center gap-2.5 transition-all cursor-pointer"
                      >
                        <span>{diagnosticStatus.status === "in_progress" ? "Continue with me" : "Show me how I think"}</span>
                        <ArrowRight className="h-4 w-4" strokeWidth={2.5} />
                      </button>
                    </div>
                    <div className="w-12 h-12 rounded-2xl bg-violet-500/20 border border-violet-500/40 flex items-center justify-center text-violet-400 shrink-0">
                      <Zap className="h-6 w-6" />
                    </div>
                  </div>
                </div>
              </section>
            )}

            {/* Hero Session Card */}
            <section>
              <div className="bg-gradient-to-b from-[#1b2734] via-[#131d27] to-[#0b1118] border border-white/20 rounded-3xl p-7 sm:p-10 shadow-[0_25px_60px_rgba(0,0,0,0.7)] backdrop-blur-2xl relative overflow-hidden">
                <div className="flex items-center gap-2 mb-3">
                  <span className="inline-flex items-center gap-1.5 px-3.5 py-1 rounded-full bg-cyan-950/80 border border-cyan-500/40 text-xs font-mono font-bold uppercase tracking-wider text-cyan-300 shadow-[0_0_15px_rgba(56,189,248,0.25)]">
                    <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
                    Our First Session
                  </span>
                </div>
                
                <h2 className="font-heading font-extrabold text-2xl sm:text-3xl md:text-4xl text-white tracking-tight mt-1">
                  Let’s begin with your chess—not a generic course.
                </h2>
                
                <p className="text-slate-200 font-medium text-base sm:text-lg mt-3 max-w-[640px] leading-relaxed">
                  Play naturally. I’ll watch how you make decisions and choose the first idea worth working on together.
                </p>

                <div className="mt-8 flex flex-wrap items-center gap-4">
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => navigate("/play-with-coach")}
                    className="px-7 py-4 rounded-2xl bg-gradient-to-r from-cyan-400 via-cyan-500 to-blue-600 hover:from-cyan-300 hover:to-blue-500 text-slate-950 font-heading font-bold text-sm sm:text-base uppercase tracking-wider shadow-[0_0_25px_rgba(56,189,248,0.45)] hover:shadow-[0_0_35px_rgba(56,189,248,0.6)] inline-flex items-center gap-3 transition-all cursor-pointer"
                  >
                    <Swords className="h-5 w-5" strokeWidth={2.5} />
                    <span>Play my first game</span>
                    <ArrowRight className="h-5 w-5" strokeWidth={2.5} />
                  </motion.button>
                </div>
              </div>
            </section>

            {/* External Accounts Card */}
            <section className="bg-gradient-to-b from-[#18232e]/90 to-[#10171f]/95 border border-white/15 rounded-3xl p-6 sm:p-7 backdrop-blur-xl flex flex-col sm:flex-row sm:items-center justify-between gap-5 shadow-lg">
              <div>
                <p className="text-xs font-mono uppercase tracking-[0.22em] text-cyan-400 font-bold mb-1">
                  Already play elsewhere?
                </p>
                <p className="text-sm sm:text-base text-slate-200 font-medium leading-relaxed max-w-[500px]">
                  Connect your Chess.com or Lichess account and I'll analyze your existing games.
                </p>
              </div>
              <button
                onClick={() => navigate("/import")}
                className="px-5 py-3 rounded-2xl bg-white/10 hover:bg-white/15 border border-white/20 text-white font-heading font-bold text-xs sm:text-sm uppercase tracking-wider inline-flex items-center gap-2.5 transition-all self-start sm:self-auto shrink-0 shadow-sm cursor-pointer"
              >
                <Import className="h-4 w-4" strokeWidth={2} />
                <span>Connect Chess.com or Lichess</span>
              </button>
            </section>

            {/* ─── STUDIO ONBOARDING MILESTONES ─── */}
            <section className="bg-white/95 dark:bg-gradient-to-b dark:from-[#202c38]/85 dark:to-[#151e27]/85 border border-slate-200/90 dark:border-white/10 rounded-3xl p-6 sm:p-7 shadow-[0_20px_50px_rgba(0,0,0,0.06)] dark:shadow-[0_20px_50px_rgba(0,0,0,0.4)] backdrop-blur-xl">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-6">
                <div>
                  <span className="text-[10px] font-mono uppercase tracking-[0.22em] text-cyan-800 dark:text-cyan-400 font-bold bg-cyan-50 dark:bg-cyan-950/60 border border-cyan-200 dark:border-cyan-500/30 px-3 py-0.5 rounded-full inline-block mb-1.5 shadow-sm">
                    Your Pathway
                  </span>
                  <h3 className="font-serif text-xl sm:text-2xl text-slate-900 dark:text-white font-normal">
                    How coaching adapts to you
                  </h3>
                </div>
                <span className="text-xs font-mono text-slate-500 dark:text-slate-400">Step 1 of 3</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 rounded-2xl bg-cyan-50/70 dark:bg-cyan-950/30 border border-cyan-300 dark:border-cyan-500/40 relative">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="w-6 h-6 rounded-full bg-cyan-500 text-slate-950 text-xs font-bold font-mono flex items-center justify-center">1</span>
                    <span className="font-serif font-medium text-slate-900 dark:text-cyan-200 text-sm">First Coached Game</span>
                  </div>
                  <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                    Play one casual game against Stockfish at your natural pace. I'll silently observe your decision flow.
                  </p>
                </div>

                <div className="p-4 rounded-2xl bg-slate-50 dark:bg-white/5 border border-slate-200 dark:border-white/10">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="w-6 h-6 rounded-full bg-slate-200 dark:bg-white/10 text-slate-700 dark:text-slate-400 text-xs font-bold font-mono flex items-center justify-center">2</span>
                    <span className="font-serif font-medium text-slate-900 dark:text-white text-sm">Cognitive Diagnostic</span>
                  </div>
                  <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                    Solve a curated 10-position test to map your tactical blind spots, calculation depth, and time habits.
                  </p>
                </div>

                <div className="p-4 rounded-2xl bg-slate-50 dark:bg-white/5 border border-slate-200 dark:border-white/10">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="w-6 h-6 rounded-full bg-slate-200 dark:bg-white/10 text-slate-700 dark:text-slate-400 text-xs font-bold font-mono flex items-center justify-center">3</span>
                    <span className="font-serif font-medium text-slate-900 dark:text-white text-sm">Personal Mistake DNA</span>
                  </div>
                  <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                    Receive your adaptive weakness profile with custom drills derived directly from your repeated mistakes.
                  </p>
                </div>
              </div>
            </section>

            {/* ─── TACTICAL PILLARS & THINKING HABITS ─── */}
            <section className="space-y-4">
              <div className="flex items-baseline justify-between">
                <div>
                  <span className="inline-flex items-center gap-1.5 px-3 py-0.5 rounded-full bg-cyan-950/80 border border-cyan-500/40 text-xs font-mono font-bold uppercase tracking-wider text-cyan-300 mb-1.5 shadow-sm">
                    Core Curriculum
                  </span>
                  <h3 className="font-heading font-bold text-2xl text-white">
                    The 4 Foundations of 1500+ Chess
                  </h3>
                </div>
                <p className="text-xs font-mono font-semibold text-slate-400 hidden sm:block">Proven Plateau Breakers</p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-5">
                <div 
                  onClick={() => navigate("/training/pattern/piece_safety")}
                  className="group bg-gradient-to-b from-[#1b2633]/90 via-[#131d27]/95 to-[#0b1118] hover:from-[#223244] hover:via-[#192633] hover:to-[#0f1720] border border-white/15 hover:border-cyan-400/60 p-6 rounded-3xl backdrop-blur-xl shadow-lg hover:shadow-[0_15px_40px_rgba(56,189,248,0.2)] transition-all duration-300 cursor-pointer text-left relative overflow-hidden"
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className="w-12 h-12 rounded-2xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 group-hover:scale-105 transition-transform">
                      <Shield className="w-6 h-6" strokeWidth={2} />
                    </div>
                    <span className="text-xs font-mono font-bold text-cyan-300 bg-cyan-950/80 border border-cyan-500/40 px-3 py-1 rounded-full">
                      600–1200 ELO
                    </span>
                  </div>
                  <h4 className="font-heading font-bold text-xl text-white mb-2 group-hover:text-cyan-300 transition-colors">
                    Piece Safety & Hanging Radar
                  </h4>
                  <p className="text-xs sm:text-sm text-slate-300 font-medium leading-relaxed mb-5">
                    The #1 blunder for club players: moving a piece to an attacked square or leaving an unprotected defender behind.
                  </p>
                  <div className="flex items-center text-xs font-heading font-bold text-cyan-400 gap-2">
                    <span>Drill safety positions</span>
                    <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                  </div>
                </div>

                <div 
                  onClick={() => navigate("/play-with-coach")}
                  className="group bg-gradient-to-b from-[#1b2633]/90 via-[#131d27]/95 to-[#0b1118] hover:from-[#223244] hover:via-[#192633] hover:to-[#0f1720] border border-white/15 hover:border-violet-400/60 p-6 rounded-3xl backdrop-blur-xl shadow-lg hover:shadow-[0_15px_40px_rgba(168,85,247,0.2)] transition-all duration-300 cursor-pointer text-left relative overflow-hidden"
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className="w-12 h-12 rounded-2xl bg-violet-500/10 border border-violet-500/30 flex items-center justify-center text-violet-400 group-hover:scale-105 transition-transform">
                      <Target className="w-6 h-6" strokeWidth={2} />
                    </div>
                    <span className="text-xs font-mono font-bold text-violet-300 bg-violet-950/80 border border-violet-500/40 px-3 py-1 rounded-full">
                      800–1400 ELO
                    </span>
                  </div>
                  <h4 className="font-heading font-bold text-xl text-white mb-2 group-hover:text-violet-300 transition-colors">
                    King Escape Squares & Back-Rank
                  </h4>
                  <p className="text-xs sm:text-sm text-slate-300 font-medium leading-relaxed mb-5">
                    Count king flight squares under attack, recognize corridor mates early, and secure king safety during tactical storms.
                  </p>
                  <div className="flex items-center text-xs font-heading font-bold text-violet-400 gap-2">
                    <span>Try Escape Quiz in Coach Play</span>
                    <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                  </div>
                </div>

                <div 
                  onClick={() => navigate("/training")}
                  className="group bg-gradient-to-b from-[#1b2633]/90 via-[#131d27]/95 to-[#0b1118] hover:from-[#223244] hover:via-[#192633] hover:to-[#0f1720] border border-white/15 hover:border-amber-400/60 p-6 rounded-3xl backdrop-blur-xl shadow-lg hover:shadow-[0_15px_40px_rgba(245,158,11,0.2)] transition-all duration-300 cursor-pointer text-left relative overflow-hidden"
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className="w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 group-hover:scale-105 transition-transform">
                      <Zap className="w-6 h-6" strokeWidth={2} />
                    </div>
                    <span className="text-xs font-mono font-bold text-amber-300 bg-amber-950/80 border border-amber-500/40 px-3 py-1 rounded-full">
                      1000–1500 ELO
                    </span>
                  </div>
                  <h4 className="font-heading font-bold text-xl text-white mb-2 group-hover:text-amber-300 transition-colors">
                    Tactical Motifs & Double Attacks
                  </h4>
                  <p className="text-xs sm:text-sm text-slate-300 font-medium leading-relaxed mb-5">
                    Master the foundational geometry of victory: knight forks, absolute pins, skewers, and deadly discovered checks.
                  </p>
                  <div className="flex items-center text-xs font-heading font-bold text-amber-400 gap-2">
                    <span>Solve pattern puzzles</span>
                    <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                  </div>
                </div>

                <div 
                  onClick={() => navigate("/openings")}
                  className="group bg-gradient-to-b from-[#1b2633]/90 via-[#131d27]/95 to-[#0b1118] hover:from-[#223244] hover:via-[#192633] hover:to-[#0f1720] border border-white/15 hover:border-emerald-400/60 p-6 rounded-3xl backdrop-blur-xl shadow-lg hover:shadow-[0_15px_40px_rgba(16,185,129,0.2)] transition-all duration-300 cursor-pointer text-left relative overflow-hidden"
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 group-hover:scale-105 transition-transform">
                      <BookOpen className="w-6 h-6" strokeWidth={2} />
                    </div>
                    <span className="text-xs font-mono font-bold text-emerald-300 bg-emerald-950/80 border border-emerald-500/40 px-3 py-1 rounded-full">
                      1200+ ELO
                    </span>
                  </div>
                  <h4 className="font-heading font-bold text-xl text-white mb-2 group-hover:text-emerald-300 transition-colors">
                    Repertoire & Endgame Conversion
                  </h4>
                  <p className="text-xs sm:text-sm text-slate-300 font-medium leading-relaxed mb-5">
                    Build opening confidence that leads to comfortable middlegames, and convert advantages into decisive wins.
                  </p>
                  <div className="flex items-center text-xs font-heading font-bold text-emerald-400 gap-2">
                    <span>Explore openings & endgames</span>
                    <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                  </div>
                </div>
              </div>
            </section>

            {/* ─── STUDIO SPOTLIGHT: 18 TRAPS & 10 ENDGAMES ─── */}
            <section className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-5">
              <div className="bg-gradient-to-b from-[#1b2633]/90 via-[#131d27]/95 to-[#0b1118] border border-white/15 rounded-3xl p-6 sm:p-7 shadow-[0_20px_50px_rgba(0,0,0,0.5)] backdrop-blur-xl flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-xs font-mono uppercase tracking-[0.22em] text-cyan-300 font-bold bg-cyan-950/80 border border-cyan-500/40 px-3 py-1 rounded-full">
                      Teaching Engine
                    </span>
                    <span className="text-xs font-mono font-semibold text-slate-400">18 Verified Traps</span>
                  </div>
                  <h4 className="font-heading font-bold text-xl sm:text-2xl text-white mb-2">
                    Famous Opening Traps & Defenses
                  </h4>
                  <p className="text-xs sm:text-sm text-slate-300 font-medium leading-relaxed mb-6">
                    Learn to recognize and punish Scholar's Mate, the Fried Liver, Legal's Mate, and the Blackburne Shilling before your opponents catch you.
                  </p>
                </div>
                <button
                  onClick={() => navigate("/play-with-coach")}
                  className="px-5 py-3 rounded-2xl bg-white/10 hover:bg-white/15 border border-white/20 text-white font-heading font-bold text-xs uppercase tracking-wider inline-flex items-center justify-between transition-all cursor-pointer"
                >
                  <span>Practice Trap Lessons</span>
                  <ChevronRight className="w-4 h-4 text-cyan-400" />
                </button>
              </div>

              <div className="bg-gradient-to-b from-[#1b2633]/90 via-[#131d27]/95 to-[#0b1118] border border-white/15 rounded-3xl p-6 sm:p-7 shadow-[0_20px_50px_rgba(0,0,0,0.5)] backdrop-blur-xl flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-xs font-mono uppercase tracking-[0.22em] text-violet-300 font-bold bg-violet-950/80 border border-violet-500/40 px-3 py-1 rounded-full">
                      Endgame Mastery
                    </span>
                    <span className="text-xs font-mono font-semibold text-slate-400">10 Scenarios</span>
                  </div>
                  <h4 className="font-heading font-bold text-xl sm:text-2xl text-white mb-2">
                    Endgame Conversions & Techniques
                  </h4>
                  <p className="text-xs sm:text-sm text-slate-300 font-medium leading-relaxed mb-6">
                    Step-by-step interactive exercises: Lucena bridge technique, Philidor passive defense, King & Pawn opposition, and rook cutoffs.
                  </p>
                </div>
                <button
                  onClick={() => navigate("/play-with-coach")}
                  className="px-5 py-3 rounded-2xl bg-white/10 hover:bg-white/15 border border-white/20 text-white font-heading font-bold text-xs uppercase tracking-wider inline-flex items-center justify-between transition-all cursor-pointer"
                >
                  <span>Practice Endgame Lessons</span>
                  <ChevronRight className="w-4 h-4 text-violet-400" />
                </button>
              </div>
            </section>

            {/* ─── EXPLORE STUDIO TOOLS ─── */}
            <section className="pt-2">
              <p className="text-xs sm:text-sm font-mono uppercase tracking-[0.25em] text-cyan-400 font-bold mb-4 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-cyan-400" />
                Explore Studio Tools
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
                {NAV.map((item) => {
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.id}
                      onClick={() => {
                        track(ANALYTICS_EVENTS.FUNNEL_HOME_NAV_TILE_CLICKED, { tile: item.id });
                        navigate(item.href);
                      }}
                      className="group bg-gradient-to-b from-[#1b2633]/90 via-[#131d27]/95 to-[#0b1118] hover:from-[#223244] hover:via-[#192633] hover:to-[#0f1720] border border-white/15 hover:border-cyan-400/60 p-6 rounded-3xl backdrop-blur-xl shadow-lg hover:shadow-[0_15px_40px_rgba(56,189,248,0.2)] transition-all duration-300 text-left relative cursor-pointer"
                    >
                      <div className="w-12 h-12 rounded-2xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 group-hover:bg-cyan-400 group-hover:text-slate-950 group-hover:scale-110 transition-all shadow-sm mb-4">
                        <Icon className="w-5 h-5" strokeWidth={2} />
                      </div>
                      <p className="text-base sm:text-lg font-heading font-bold text-white group-hover:text-cyan-300 transition-colors tracking-tight">
                        {item.label}
                      </p>
                      <p className="text-xs sm:text-sm font-medium text-slate-400 group-hover:text-slate-200 mt-1 line-clamp-1">
                        {item.sub}
                      </p>
                    </button>
                  );
                })}
              </div>
            </section>

          </motion.div>
        </div>
      </Layout>
    );
  }

  // ─── Returning User State (Elite Chess Studio Aesthetic) ───
  return (
    <Layout user={user}>
      <motion.div
        variants={pageEnter}
        initial="initial"
        animate="animate"
        className="min-h-full py-8 px-4 sm:px-6 relative"
        data-testid="home-page"
      >
        {/* Soft Ambient Studio Lighting */}
        <div className="absolute top-0 right-1/4 w-96 h-96 bg-cyan-500/15 rounded-full blur-[140px] pointer-events-none" />
        <div className="absolute top-1/2 left-10 w-80 h-80 bg-blue-600/10 rounded-full blur-[140px] pointer-events-none" />

        <motion.div variants={staggerContainer} initial="initial" animate="animate" className="max-w-4xl mx-auto space-y-8 relative z-10">
          
          {/* ─── GREETING ─── */}
          <motion.div variants={fadeInUp} className="flex flex-col sm:flex-row sm:items-baseline justify-between pb-5 border-b border-white/15 gap-3">
            <div>
              <span className="inline-flex items-center gap-1.5 px-3.5 py-1 rounded-full bg-cyan-950/80 border border-cyan-500/40 text-xs font-mono font-bold uppercase tracking-wider text-cyan-300 mb-2 shadow-[0_0_15px_rgba(56,189,248,0.25)]">
                <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
                Active Session
              </span>
              <h1 className="font-heading font-extrabold text-3xl sm:text-4xl md:text-5xl text-white tracking-tight leading-tight">
                {displayName ? `${timeOfDayGreeting()}, ${displayName}.` : `${timeOfDayGreeting()}.`}
              </h1>
            </div>
            <p className="text-slate-300 font-mono text-xs sm:text-sm font-semibold uppercase tracking-wider">{formatWhen()}</p>
          </motion.div>

          {/* ─── THE COACHING SESSION ───
              docs/home_as_a_coach_scope.md

              Mohit, 2026-10-07: *"it is still not looking like a coach, it
              looks like a report"* — and then the process itself: a coach reads
              your games, tells you what is good and what is bad, trains the
              bad, and plays you.

              THIS IS MOUNTED HERE BECAUSE THIS IS THE PAGE PEOPLE SEE. It went
              into CurriculumHome first, which looked right — that component is
              the newer, better-written home — and reaches NOBODY: measured
              2026-10-07, all 128 users fall through to this branch, because
              PERSONAL_CURRICULUM_ENABLED is not set on prod at all, so
              `curriculum.enabled` is false for everyone including admins. It is
              mounted in both, and this is the one that counts.

              That is the fourth time this session a finished surface was wired
              into a branch users do not take. The lesson is not "check the
              branch" — it is that "mounted" and "reaching a person" are
              different claims and only the second one is worth making.

              It absorbs FindingCard (the finding is now movement one's second
              line), SessionCard (its celebrated good move is the board inside
              movement one) and ChancesCard (passed in as movement one's
              assessment, because the reading IS part of what the coach knows
              about you). Three cards became one movement; nothing was dropped. */}
          <CoachMovements assessment={<ChancesCard />} />
          {lastSession?.story && (
            <motion.section ref={mirrorRef} variants={fadeInUp}>
              <div className="bg-gradient-to-b from-[#1b2734] via-[#131d27] to-[#0b1118] border border-white/20 rounded-3xl p-7 sm:p-8 shadow-[0_20px_50px_rgba(0,0,0,0.6)] backdrop-blur-xl relative overflow-hidden">
                <div className="flex items-center space-x-2 text-xs font-mono uppercase tracking-[0.22em] text-cyan-300 font-bold mb-3">
                  <Activity className="w-4 h-4 text-cyan-400" />
                  <span>Since you last played</span>
                </div>
                
                <p className="text-base sm:text-lg leading-relaxed text-slate-100 font-medium">
                  {lastSession.story}
                </p>
                
                {(lastSession.game_id || lastSession.game_ids?.[0]) && (
                  <div className="mt-5 pt-4 border-t border-white/10">
                    <button
                      onClick={() => {
                        track(ANALYTICS_EVENTS.FUNNEL_HOME_CTA_CLICKED, { cta: "review_this_game" });
                        navigate(`/game/${lastSession.game_id || lastSession.game_ids[0]}`);
                      }}
                      className="px-5 py-2.5 rounded-2xl bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-400/50 text-cyan-200 font-heading font-bold text-xs uppercase tracking-wider inline-flex items-center gap-2 transition-all shadow-[0_0_15px_rgba(56,189,248,0.25)] cursor-pointer"
                    >
                      <span>Review this game</span>
                      <ChevronRight className="h-4 w-4 text-cyan-300" strokeWidth={2.5} />
                    </button>
                  </div>
                )}
              </div>
            </motion.section>
          )}

          {/* ─── THE COACH CONVERSATION / BRIEFING ─── */}
          {coachConversation?.has_conversation || canonicalContext ? (
            <motion.section 
              variants={fadeInUp} 
              className="bg-gradient-to-b from-[#1b2734] via-[#131d27] to-[#0b1118] border border-white/20 rounded-3xl p-7 sm:p-10 shadow-[0_25px_60px_rgba(0,0,0,0.7)] backdrop-blur-2xl relative overflow-hidden"
            >
              {/* Coach Header */}
              <div className="flex items-center gap-4 mb-6 pb-6 border-b border-white/10">
                <div className="relative shrink-0">
                  <div className="w-14 h-14 sm:w-16 sm:h-16 rounded-2xl overflow-hidden ring-2 ring-cyan-400/60 shadow-[0_0_20px_rgba(56,189,248,0.35)] bg-slate-800">
                    <img
                      src="/coach-jessica.png"
                      alt="Coach Jessica"
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        e.target.onerror = null;
                        e.target.src = "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=150&auto=format&fit=crop&q=80";
                      }}
                    />
                  </div>
                  <div className="absolute -bottom-1 -right-1 w-4 h-4 bg-emerald-500 rounded-full ring-2 ring-[#131d27] flex items-center justify-center">
                    <div className="w-1.5 h-1.5 bg-white rounded-full animate-ping" />
                  </div>
                </div>
                <div>
                  <h3 className="font-heading font-bold text-xl sm:text-2xl text-white">
                    Coach Jessica
                  </h3>
                  <p className="text-xs font-mono font-semibold text-cyan-400 uppercase tracking-wider">
                    AI Chess Mentor · Pattern Intelligence
                  </p>
                </div>
              </div>

              {coachConversation?.thinking_signature && (
                <div className="bg-black/40 border-l-4 border-cyan-400 p-4 rounded-r-2xl mb-6 text-sm font-mono text-cyan-200 leading-relaxed font-semibold">
                  {coachConversation.thinking_signature}
                </div>
              )}

              {coachConversation?.narrative && (
                <div className="space-y-4 mb-7 bg-white/[0.03] border border-white/10 rounded-2xl p-5 sm:p-6">
                  <p className="text-base sm:text-lg leading-relaxed text-slate-100 font-semibold">
                    {coachConversation.narrative.stage_opener}
                  </p>
                  <p className="text-base sm:text-lg leading-relaxed text-slate-200 font-medium">
                    {coachConversation.narrative.continuity}{" "}
                    <span className="text-white font-bold text-cyan-300">
                      {coachConversation.narrative.belief}
                    </span>
                  </p>
                </div>
              )}

              {canonicalContext ? (
                <div ref={curriculumDecisionElementRef} className="my-6">
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
                      if (currentLearningDecision) {
                        trackCurriculum(ANALYTICS_EVENTS.CURRICULUM_PRIMARY_CLICKED, {
                          surface: "legacy_home",
                          ...currentLearningDecision,
                          origin: "recommendation",
                          is_recommended: true,
                        });
                      }
                      navigate(action.href);
                    }}
                  />
                </div>
              ) : pic ? (
                <div 
                  ref={curriculumDecisionElementRef} 
                  className="bg-gradient-to-r from-cyan-950/60 to-[#131d27] border-l-4 border-cyan-400 rounded-r-3xl p-6 sm:p-7 mb-7 shadow-lg border border-white/10"
                >
                  <p className="text-xs uppercase tracking-[0.2em] text-cyan-300 font-mono font-bold mb-2.5 flex items-center gap-2">
                    <Shield className="w-4 h-4 text-cyan-400" />
                    <span>
                      {pic.learner_state?.label || "Active Focus"}
                      {pic.learner_state?.refresh_needed ? " · Refresh needed" : ""}
                    </span>
                  </p>
                  <p className="font-heading text-xl sm:text-2xl font-bold text-white mb-2.5">
                    {pic.focus_label}
                  </p>
                  <p className="text-base sm:text-lg leading-relaxed text-slate-100 font-semibold mb-3">
                    {pic.instruction_text || "Before you move, check whether the piece will be safe on its new square."}
                  </p>
                  <p className="text-sm leading-relaxed text-slate-300 italic font-medium">
                    I have seen this same decision in more than one of your games. We’ll stay with it until your response begins to change over the board.
                  </p>
                  {/* What else the games show. The picker already ranks these
                      and writes them onto the focus document, and until now
                      every one was thrown away: Home named one thing out of
                      six the system holds. components/FocusCard.jsx had this
                      block built and nothing ever mounted that component.

                      Topics only, no counts and no scores -- a mention is not
                      a plan, and the one instruction above stays the only
                      thing anyone is asked to do. */}
                                    {/* The drill for the shape this player takes least often
                      (docs/pin_skewer_drill_scope.md). The reading behind it was
                      already computed and stored and reached no screen here.
                      Deliberately one quiet link and not a card: Home names ONE
                      thing to do today, and this is not it -- it is somewhere to
                      go when they want to practise. The backend omits the field
                      entirely when there is no supply, so this cannot render a
                      dead link. */}
                  {activeFocus?.tactic_practice?.href && (
                    <div className="mt-4">
                      <Link
                        to={activeFocus.tactic_practice.href}
                        data-testid="tactic-practice-link"
                        className="inline-flex items-center text-[13px] font-medium text-emerald-700 dark:text-emerald-400 hover:underline"
                      >
                        {activeFocus.tactic_practice.label} &rarr;
                      </Link>
                      <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
                        {activeFocus.tactic_practice.because}
                      </p>
                    </div>
                  )}
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
                      className="px-6 py-3 rounded-2xl bg-gradient-to-r from-cyan-400 via-cyan-500 to-blue-600 hover:from-cyan-300 hover:to-blue-500 text-slate-950 font-heading font-bold text-xs uppercase tracking-wider shadow-[0_0_20px_rgba(56,189,248,0.4)] transition-all cursor-pointer"
                    >
                      Practise this
                    </button>
                    {!pic.focus_game || ["cancelled", "completed"].includes(pic.focus_game.status) ? (
                      <button
                        disabled={focusGameBusy}
                        onClick={() => updateFocusGame("commit")}
                        className="px-5 py-3 rounded-2xl bg-white/10 hover:bg-white/15 border border-white/20 text-white text-xs font-heading font-bold tracking-wide uppercase transition-all disabled:opacity-50 cursor-pointer"
                      >
                        Make my next game a Focus Game
                      </button>
                    ) : pic.focus_game.status === "waiting" ? (
                      <div className="flex items-center space-x-2 text-xs font-mono font-bold text-cyan-300">
                        <span>Committed — play on Chess.com or Lichess, then sync.</span>
                        <button
                          disabled={focusGameBusy}
                          onClick={() => updateFocusGame("cancel")}
                          className="text-xs underline text-slate-400 hover:text-white cursor-pointer ml-1"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : pic.focus_game.status === "claimed" ? (
                      <div className="flex items-center space-x-2 text-xs font-mono font-bold text-emerald-300">
                        <span>I found the game. I’ll use it to see whether the new habit appeared.</span>
                        <button
                          disabled={focusGameBusy}
                          onClick={() => updateFocusGame("correct", { game_id: pic.focus_game.game_id })}
                          className="text-xs underline text-slate-400 hover:text-white cursor-pointer ml-1"
                        >
                          That was not my Focus Game
                        </button>
                      </div>
                    ) : null}
                  </div>
                </div>
              ) : (
                <p className="text-base sm:text-lg md:text-xl leading-relaxed text-white font-bold mb-6">
                  {coachConversation.one_action}
                </p>
              )}

              {coachConversation?.punish_line?.text && (
                <div className="bg-white/5 border border-white/10 rounded-2xl p-4 mb-5 flex items-center space-x-3 text-sm text-slate-200">
                  <Sparkles className="w-5 h-5 text-cyan-400 shrink-0" />
                  <div>
                    <span className="font-bold text-white">{coachConversation.punish_line.headline}</span>{" "}
                    <span className="font-medium text-slate-300">{coachConversation.punish_line.habit}</span>
                  </div>
                </div>
              )}

              {coachConversation?.encouragement && (
                <p className="text-sm sm:text-base text-cyan-200/90 mb-3 italic font-medium">
                  "{coachConversation.encouragement}"
                </p>
              )}

              {coachConversation?.closing_line && (
                <p className="text-xs sm:text-sm text-slate-400 mb-8 font-mono font-semibold">
                  {coachConversation.closing_line}
                </p>
              )}

              {!canonicalContext && !pic && (
                <button
                  ref={conversationEndRef}
                  onClick={() => {
                    track(ANALYTICS_EVENTS.FUNNEL_HOME_CTA_CLICKED, { cta: "play_with_coach", has_conversation: true });
                    navigate("/play-with-coach");
                  }}
                  className="px-8 py-4 rounded-2xl bg-gradient-to-r from-cyan-400 via-cyan-500 to-blue-600 hover:from-cyan-300 hover:to-blue-500 text-slate-950 font-heading font-bold text-sm sm:text-base uppercase tracking-wider shadow-[0_0_25px_rgba(56,189,248,0.45)] hover:shadow-[0_0_35px_rgba(56,189,248,0.6)] inline-flex items-center gap-3 transition-all cursor-pointer"
                >
                  <Swords className="h-5 w-5" strokeWidth={2.5} />
                  <span>Play with Coach</span>
                  <ArrowRight className="h-5 w-5" strokeWidth={2.5} />
                </button>
              )}
            </motion.section>
          ) : (
            <motion.section 
              variants={fadeInUp} 
              className="bg-gradient-to-b from-[#1b2734] via-[#131d27] to-[#0b1118] border border-white/20 rounded-3xl p-7 sm:p-10 shadow-[0_25px_60px_rgba(0,0,0,0.7)] backdrop-blur-2xl relative overflow-hidden"
            >
              {/* Coach Header */}
              <div className="flex items-center gap-4 mb-6 pb-6 border-b border-white/10">
                <div className="relative shrink-0">
                  <div className="w-14 h-14 sm:w-16 sm:h-16 rounded-2xl overflow-hidden ring-2 ring-cyan-400/60 shadow-[0_0_20px_rgba(56,189,248,0.35)] bg-slate-800">
                    <img
                      src="/coach-jessica.png"
                      alt="Coach Jessica"
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        e.target.onerror = null;
                        e.target.src = "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=150&auto=format&fit=crop&q=80";
                      }}
                    />
                  </div>
                  <div className="absolute -bottom-1 -right-1 w-4 h-4 bg-emerald-500 rounded-full ring-2 ring-[#131d27] flex items-center justify-center">
                    <div className="w-1.5 h-1.5 bg-white rounded-full animate-ping" />
                  </div>
                </div>
                <div>
                  <h3 className="font-heading font-bold text-xl sm:text-2xl text-white">
                    Coach Jessica
                  </h3>
                  <p className="text-xs font-mono font-semibold text-cyan-400 uppercase tracking-wider">
                    AI Chess Mentor · Game Decryption
                  </p>
                </div>
              </div>

              {/* Observation Quote Container */}
              <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-5 sm:p-6 mb-7">
                <p className="text-base sm:text-lg md:text-xl leading-relaxed text-slate-100 font-semibold">
                  {hasGames
                    ? "I have been through your games. I have not settled on the one pattern to work on with you yet — in the meantime, your last game is worth a look."
                    : "I'm still learning how you play. Play a game or two and I'll start noticing your habits."}
                </p>
              </div>

              <button
                onClick={() => {
                  track(ANALYTICS_EVENTS.FUNNEL_HOME_CTA_CLICKED, {
                    cta: hasGames ? "review_games" : "play_with_coach",
                    has_conversation: false,
                  });
                  navigate(hasGames ? "/lab" : "/play-with-coach");
                }}
                className="px-8 py-4 rounded-2xl bg-gradient-to-r from-cyan-400 via-cyan-500 to-blue-600 hover:from-cyan-300 hover:to-blue-500 text-slate-950 font-heading font-bold text-sm sm:text-base uppercase tracking-wider shadow-[0_0_25px_rgba(56,189,248,0.45)] hover:shadow-[0_0_35px_rgba(56,189,248,0.6)] inline-flex items-center gap-3 transition-all cursor-pointer"
              >
                <span>{hasGames ? "Review your games" : "Play with Coach"}</span>
                <ArrowRight className="h-5 w-5" strokeWidth={2.5} />
              </button>
            </motion.section>
          )}

          {/* The session card and the chances card used to sit here, below
              everything, each fetching /home/session for itself. Both are now
              inside the coaching session at the top of the page: the good move
              the session card celebrated is the board in movement one, and the
              chances reading is movement one's assessment slot.

              Their mounting note is kept because it is still the rule: both
              had been wired inside the `canonicalContext ? ... : pic ? ...`
              ternary, where 51 of 52 users take the other arm, so they rendered
              for almost nobody. Nothing on this page that does not depend on a
              player's focus shape may sit inside a test for one. */}

          {/* ─── NAVIGATION TILES ───
              Deliberately faded — utilities, not today's mission. Mohit,
              2026-07-31 §7: "Now I'm back inside software... I'd fade
              those into the background." */}
          <motion.section variants={fadeInUp} className="mt-20 pt-10 border-t border-border/30 opacity-70 hover:opacity-100 transition-opacity">
            <p className="text-[10px] uppercase tracking-[0.22em] text-muted-foreground/70 font-medium mb-4">
              Other ways to improve
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
              {NAV.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    onClick={() => {
                      track(ANALYTICS_EVENTS.FUNNEL_HOME_NAV_TILE_CLICKED, { tile: item.id });
                      navigate(item.href);
                    }}
                    className="group bg-gradient-to-b from-[#1b2633]/90 via-[#131d27]/95 to-[#0b1118] hover:from-[#223244] hover:via-[#192633] hover:to-[#0f1720] border border-white/15 hover:border-cyan-400/60 p-6 rounded-3xl backdrop-blur-xl shadow-lg hover:shadow-[0_15px_40px_rgba(56,189,248,0.2)] transition-all duration-300 text-left relative cursor-pointer"
                  >
                    <div className="w-12 h-12 rounded-2xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 group-hover:bg-cyan-400 group-hover:text-slate-950 group-hover:scale-110 transition-all shadow-sm mb-4">
                      <Icon className="w-5 h-5" strokeWidth={2} />
                    </div>
                    <p className="text-base sm:text-lg font-heading font-bold text-white group-hover:text-cyan-300 transition-colors tracking-tight">
                      {item.label}
                    </p>
                    <p className="text-xs sm:text-sm font-medium text-slate-400 group-hover:text-slate-200 mt-1 line-clamp-1">
                      {item.sub}
                    </p>
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
