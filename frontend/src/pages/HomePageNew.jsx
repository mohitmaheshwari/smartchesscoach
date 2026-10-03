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
import { useNavigate } from "react-router-dom";
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
            <div className="flex flex-col sm:flex-row sm:items-baseline justify-between pb-4 border-b border-slate-200/80 dark:border-white/10 gap-2">
              <div>
                <span className="text-[10px] font-mono uppercase tracking-[0.22em] text-cyan-800 dark:text-cyan-400 font-bold bg-cyan-50 dark:bg-cyan-950/60 border border-cyan-200 dark:border-cyan-500/30 px-3 py-0.5 rounded-full inline-block mb-1.5 shadow-sm">
                  Studio Onboarding
                </span>
                <h1 className="font-serif text-2xl sm:text-3xl text-slate-900 dark:text-white tracking-tight">
                  {displayName ? `${timeOfDayGreeting()}, ${displayName}.` : `${timeOfDayGreeting()}.`}
                </h1>
              </div>
              <p className="text-slate-500 dark:text-slate-400 font-mono text-xs uppercase tracking-widest">{formatWhen()}</p>
            </div>

            {/* Diagnostic CTA */}
            {(() => {
              const shouldShow = diagnosticStatus && diagnosticStatus.status !== "complete" && diagnosticStatus.status !== "superseded";
              return shouldShow;
            })() && (
              <section>
                <div className="bg-white/95 dark:bg-gradient-to-b dark:from-[#24313d]/85 dark:to-[#19222a]/85 border border-violet-200 dark:border-violet-500/30 rounded-3xl p-6 sm:p-7 shadow-[0_20px_50px_rgba(0,0,0,0.06)] dark:shadow-[0_20px_50px_rgba(0,0,0,0.4)] backdrop-blur-xl relative overflow-hidden">
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="font-serif text-xl sm:text-2xl text-slate-900 dark:text-white font-normal mb-2">
                        Let me learn how you see the board.
                      </h3>
                      <p className="text-slate-600 dark:text-slate-200/85 text-xs sm:text-sm mb-5 max-w-[540px] leading-relaxed">
                        {diagnosticStatus.status === "in_progress"
                          ? "We have already started. Let’s pick up where you left off."
                          : "A short set of positions will help me choose the right first lesson for you."}
                      </p>
                      <button
                        onClick={() => navigate("/diagnostic")}
                        className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-mono text-xs font-bold tracking-wider uppercase shadow-[0_0_20px_rgba(168,85,247,0.4)] inline-flex items-center gap-2 transition-all"
                      >
                        <span>{diagnosticStatus.status === "in_progress" ? "Continue with me" : "Show me how I think"}</span>
                        <ArrowRight className="h-3.5 w-3.5" strokeWidth={2} />
                      </button>
                    </div>
                    <Zap className="h-5 w-5 text-violet-500 dark:text-violet-400 flex-shrink-0 mt-1" />
                  </div>
                </div>
              </section>
            )}

            {/* Hero Session Card */}
            <section>
              <div className="bg-white/95 dark:bg-gradient-to-b dark:from-[#25323d]/85 dark:to-[#1a232b]/85 border border-slate-200/90 dark:border-white/15 rounded-3xl p-7 sm:p-9 shadow-[0_20px_50px_rgba(0,0,0,0.06)] dark:shadow-[0_25px_60px_rgba(0,0,0,0.45)] backdrop-blur-xl relative overflow-hidden">
                <span className="text-[10px] font-mono uppercase tracking-[0.22em] text-cyan-800 dark:text-cyan-300 font-bold bg-cyan-50 dark:bg-cyan-950/60 border border-cyan-200 dark:border-cyan-500/30 px-3 py-1 rounded-full inline-block mb-3 shadow-sm">
                  Our first session
                </span>
                
                <h2 className="font-serif text-3xl sm:text-4xl text-slate-900 dark:text-white font-normal tracking-tight mt-1">
                  Let’s begin with your chess—not a generic course.
                </h2>
                
                <p className="text-slate-600 dark:text-slate-200/90 text-sm sm:text-base mt-3 max-w-[620px] leading-relaxed">
                  Play naturally. I’ll watch how you make decisions and choose the first idea worth working on together.
                </p>

                <div className="mt-8 flex flex-wrap items-center gap-4">
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => navigate("/play-with-coach")}
                    className="px-6 py-3 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 font-mono text-xs font-bold uppercase tracking-wider shadow-[0_0_20px_rgba(56,189,248,0.4)] inline-flex items-center gap-2.5 transition-all"
                  >
                    <Swords className="h-4 w-4" strokeWidth={2} />
                    <span>Play my first game</span>
                    <ArrowRight className="h-4 w-4" strokeWidth={2} />
                  </motion.button>
                </div>
              </div>
            </section>

            {/* External Accounts Card */}
            <section className="bg-slate-50/90 dark:bg-gradient-to-b dark:from-[#1e2730]/75 dark:to-[#161d24]/75 border border-slate-200/90 dark:border-white/10 rounded-2xl p-6 backdrop-blur-xl flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-sm">
              <div>
                <p className="text-[10px] font-mono uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400 font-semibold mb-1">
                  Already play elsewhere?
                </p>
                <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed max-w-[480px]">
                  Connect your Chess.com or Lichess account and I'll analyze your existing games.
                </p>
              </div>
              <button
                onClick={() => navigate("/import")}
                className="px-4 py-2.5 rounded-xl bg-white dark:bg-white/10 hover:bg-slate-100 dark:hover:bg-white/15 border border-slate-200 dark:border-white/15 text-slate-700 dark:text-slate-200 font-mono text-xs font-medium uppercase tracking-wider inline-flex items-center gap-2 transition-all self-start sm:self-auto shrink-0 shadow-sm"
              >
                <Import className="h-3.5 w-3.5" strokeWidth={1.75} />
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
                  <span className="text-[10px] font-mono uppercase tracking-[0.22em] text-cyan-800 dark:text-cyan-400 font-bold bg-cyan-50 dark:bg-cyan-950/60 border border-cyan-200 dark:border-cyan-500/30 px-3 py-0.5 rounded-full inline-block mb-1.5 shadow-sm">
                    Core Curriculum
                  </span>
                  <h3 className="font-serif text-2xl text-slate-900 dark:text-white font-normal">
                    The 4 Foundations of 1500+ Chess
                  </h3>
                </div>
                <p className="text-xs font-mono text-slate-500 dark:text-slate-400 hidden sm:block">Proven Plateau Breakers</p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div 
                  onClick={() => navigate("/training/pattern/piece_safety")}
                  className="group bg-white/95 dark:bg-gradient-to-b dark:from-[#202c38]/80 dark:to-[#161f27]/80 hover:bg-slate-50 dark:hover:from-[#273644]/90 dark:hover:to-[#1b2630]/90 border border-slate-200/90 dark:border-white/10 hover:border-cyan-400 dark:hover:border-cyan-500/40 p-5 rounded-2xl backdrop-blur-xl shadow-sm hover:shadow-md transition-all cursor-pointer text-left relative overflow-hidden"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="w-10 h-10 rounded-xl bg-cyan-50 dark:bg-cyan-950/60 border border-cyan-200 dark:border-cyan-500/30 flex items-center justify-center text-cyan-700 dark:text-cyan-400 group-hover:scale-105 transition-transform">
                      <Shield className="w-5 h-5" strokeWidth={1.75} />
                    </div>
                    <span className="text-[10.5px] font-mono font-bold text-cyan-800 dark:text-cyan-300 bg-cyan-50 dark:bg-cyan-950/70 border border-cyan-200 dark:border-cyan-500/30 px-2.5 py-0.5 rounded-full">
                      600–1200 ELO
                    </span>
                  </div>
                  <h4 className="font-serif text-lg text-slate-900 dark:text-white font-medium mb-1.5 group-hover:text-cyan-700 dark:group-hover:text-cyan-300 transition-colors">
                    Piece Safety & Hanging Radar
                  </h4>
                  <p className="text-xs text-slate-600 dark:text-slate-300/90 leading-relaxed mb-4">
                    The #1 blunder for club players: moving a piece to an attacked square or leaving an unprotected defender behind.
                  </p>
                  <div className="flex items-center text-xs font-mono font-medium text-cyan-700 dark:text-cyan-400 gap-1.5">
                    <span>Drill safety positions</span>
                    <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
                  </div>
                </div>

                <div 
                  onClick={() => navigate("/play-with-coach")}
                  className="group bg-white/95 dark:bg-gradient-to-b dark:from-[#202c38]/80 dark:to-[#161f27]/80 hover:bg-slate-50 dark:hover:from-[#273644]/90 dark:hover:to-[#1b2630]/90 border border-slate-200/90 dark:border-white/10 hover:border-cyan-400 dark:hover:border-cyan-500/40 p-5 rounded-2xl backdrop-blur-xl shadow-sm hover:shadow-md transition-all cursor-pointer text-left relative overflow-hidden"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="w-10 h-10 rounded-xl bg-violet-50 dark:bg-violet-950/60 border border-violet-200 dark:border-violet-500/30 flex items-center justify-center text-violet-700 dark:text-violet-400 group-hover:scale-105 transition-transform">
                      <Target className="w-5 h-5" strokeWidth={1.75} />
                    </div>
                    <span className="text-[10.5px] font-mono font-bold text-violet-800 dark:text-violet-300 bg-violet-50 dark:bg-violet-950/70 border border-violet-200 dark:border-violet-500/30 px-2.5 py-0.5 rounded-full">
                      800–1400 ELO
                    </span>
                  </div>
                  <h4 className="font-serif text-lg text-slate-900 dark:text-white font-medium mb-1.5 group-hover:text-violet-700 dark:group-hover:text-violet-300 transition-colors">
                    King Escape Squares & Back-Rank
                  </h4>
                  <p className="text-xs text-slate-600 dark:text-slate-300/90 leading-relaxed mb-4">
                    Count king flight squares under attack, recognize corridor mates early, and secure king safety during tactical storms.
                  </p>
                  <div className="flex items-center text-xs font-mono font-medium text-violet-700 dark:text-violet-400 gap-1.5">
                    <span>Try Escape Quiz in Coach Play</span>
                    <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
                  </div>
                </div>

                <div 
                  onClick={() => navigate("/training")}
                  className="group bg-white/95 dark:bg-gradient-to-b dark:from-[#202c38]/80 dark:to-[#161f27]/80 hover:bg-slate-50 dark:hover:from-[#273644]/90 dark:hover:to-[#1b2630]/90 border border-slate-200/90 dark:border-white/10 hover:border-cyan-400 dark:hover:border-cyan-500/40 p-5 rounded-2xl backdrop-blur-xl shadow-sm hover:shadow-md transition-all cursor-pointer text-left relative overflow-hidden"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="w-10 h-10 rounded-xl bg-amber-50 dark:bg-amber-950/60 border border-amber-200 dark:border-amber-500/30 flex items-center justify-center text-amber-700 dark:text-amber-400 group-hover:scale-105 transition-transform">
                      <Zap className="w-5 h-5" strokeWidth={1.75} />
                    </div>
                    <span className="text-[10.5px] font-mono font-bold text-amber-800 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/70 border border-amber-200 dark:border-amber-500/30 px-2.5 py-0.5 rounded-full">
                      1000–1500 ELO
                    </span>
                  </div>
                  <h4 className="font-serif text-lg text-slate-900 dark:text-white font-medium mb-1.5 group-hover:text-amber-700 dark:group-hover:text-amber-300 transition-colors">
                    Tactical Motifs & Double Attacks
                  </h4>
                  <p className="text-xs text-slate-600 dark:text-slate-300/90 leading-relaxed mb-4">
                    Master the foundational geometry of victory: knight forks, absolute pins, skewers, and deadly discovered checks.
                  </p>
                  <div className="flex items-center text-xs font-mono font-medium text-amber-700 dark:text-amber-400 gap-1.5">
                    <span>Solve pattern puzzles</span>
                    <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
                  </div>
                </div>

                <div 
                  onClick={() => navigate("/openings")}
                  className="group bg-white/95 dark:bg-gradient-to-b dark:from-[#202c38]/80 dark:to-[#161f27]/80 hover:bg-slate-50 dark:hover:from-[#273644]/90 dark:hover:to-[#1b2630]/90 border border-slate-200/90 dark:border-white/10 hover:border-cyan-400 dark:hover:border-cyan-500/40 p-5 rounded-2xl backdrop-blur-xl shadow-sm hover:shadow-md transition-all cursor-pointer text-left relative overflow-hidden"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="w-10 h-10 rounded-xl bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-500/30 flex items-center justify-center text-emerald-700 dark:text-emerald-400 group-hover:scale-105 transition-transform">
                      <BookOpen className="w-5 h-5" strokeWidth={1.75} />
                    </div>
                    <span className="text-[10.5px] font-mono font-bold text-emerald-800 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/70 border border-emerald-200 dark:border-emerald-500/30 px-2.5 py-0.5 rounded-full">
                      1200+ ELO
                    </span>
                  </div>
                  <h4 className="font-serif text-lg text-slate-900 dark:text-white font-medium mb-1.5 group-hover:text-emerald-700 dark:group-hover:text-emerald-300 transition-colors">
                    Repertoire & Endgame Conversion
                  </h4>
                  <p className="text-xs text-slate-600 dark:text-slate-300/90 leading-relaxed mb-4">
                    Build opening confidence that leads to comfortable middlegames, and convert advantages into decisive wins.
                  </p>
                  <div className="flex items-center text-xs font-mono font-medium text-emerald-700 dark:text-emerald-400 gap-1.5">
                    <span>Explore openings & endgames</span>
                    <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
                  </div>
                </div>
              </div>
            </section>

            {/* ─── STUDIO SPOTLIGHT: 18 TRAPS & 10 ENDGAMES ─── */}
            <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-white/95 dark:bg-gradient-to-b dark:from-[#222e3a]/85 dark:to-[#172028]/85 border border-slate-200/90 dark:border-white/10 rounded-3xl p-6 sm:p-7 shadow-[0_20px_50px_rgba(0,0,0,0.06)] dark:shadow-[0_20px_50px_rgba(0,0,0,0.4)] backdrop-blur-xl flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-[10px] font-mono uppercase tracking-[0.22em] text-cyan-800 dark:text-cyan-400 font-bold bg-cyan-50 dark:bg-cyan-950/60 border border-cyan-200 dark:border-cyan-500/30 px-2.5 py-0.5 rounded-full">
                      Teaching Engine
                    </span>
                    <span className="text-xs font-mono text-slate-500 dark:text-slate-400">18 Verified Traps</span>
                  </div>
                  <h4 className="font-serif text-xl text-slate-900 dark:text-white font-medium mb-2">
                    Famous Opening Traps & Defenses
                  </h4>
                  <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300/90 leading-relaxed mb-5">
                    Learn to recognize and punish Scholar's Mate, the Fried Liver, Legal's Mate, and the Blackburne Shilling before your opponents catch you.
                  </p>
                </div>
                <button
                  onClick={() => navigate("/play-with-coach")}
                  className="px-4 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-white/10 dark:hover:bg-white/15 border border-slate-200 dark:border-white/15 text-slate-800 dark:text-slate-200 font-mono text-xs font-semibold uppercase tracking-wider inline-flex items-center justify-between transition-all"
                >
                  <span>Practice Trap Lessons</span>
                  <ChevronRight className="w-4 h-4 text-cyan-600 dark:text-cyan-400" />
                </button>
              </div>

              <div className="bg-white/95 dark:bg-gradient-to-b dark:from-[#222e3a]/85 dark:to-[#172028]/85 border border-slate-200/90 dark:border-white/10 rounded-3xl p-6 sm:p-7 shadow-[0_20px_50px_rgba(0,0,0,0.06)] dark:shadow-[0_20px_50px_rgba(0,0,0,0.4)] backdrop-blur-xl flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-[10px] font-mono uppercase tracking-[0.22em] text-violet-800 dark:text-violet-400 font-bold bg-violet-50 dark:bg-violet-950/60 border border-violet-200 dark:border-violet-500/30 px-2.5 py-0.5 rounded-full">
                      Endgame Mastery
                    </span>
                    <span className="text-xs font-mono text-slate-500 dark:text-slate-400">10 Scenarios</span>
                  </div>
                  <h4 className="font-serif text-xl text-slate-900 dark:text-white font-medium mb-2">
                    Endgame Conversions & Techniques
                  </h4>
                  <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300/90 leading-relaxed mb-5">
                    Step-by-step interactive exercises: Lucena bridge technique, Philidor passive defense, King & Pawn opposition, and rook cutoffs.
                  </p>
                </div>
                <button
                  onClick={() => navigate("/play-with-coach")}
                  className="px-4 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-white/10 dark:hover:bg-white/15 border border-slate-200 dark:border-white/15 text-slate-800 dark:text-slate-200 font-mono text-xs font-semibold uppercase tracking-wider inline-flex items-center justify-between transition-all"
                >
                  <span>Practice Endgame Lessons</span>
                  <ChevronRight className="w-4 h-4 text-violet-600 dark:text-violet-400" />
                </button>
              </div>
            </section>

            {/* ─── EXPLORE STUDIO TOOLS ─── */}
            <section className="pt-2">
              <p className="text-[10px] font-mono uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400 font-semibold mb-4">
                Explore Studio Tools
              </p>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3.5">
                {NAV.map((item) => {
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.id}
                      onClick={() => {
                        track(ANALYTICS_EVENTS.FUNNEL_HOME_NAV_TILE_CLICKED, { tile: item.id });
                        navigate(item.href);
                      }}
                      className="group bg-white/95 dark:bg-gradient-to-b dark:from-[#202c38]/80 dark:to-[#161f27]/80 hover:bg-slate-50 dark:hover:from-[#293846]/90 dark:hover:to-[#1c2731]/90 border border-slate-200/90 dark:border-white/10 hover:border-cyan-400 dark:hover:border-cyan-500/40 p-4 rounded-2xl backdrop-blur-xl shadow-sm hover:shadow-md transition-all text-left"
                    >
                      <div className="w-8 h-8 rounded-xl bg-slate-100 dark:bg-black/40 border border-slate-200 dark:border-white/10 flex items-center justify-center text-slate-600 dark:text-slate-400 group-hover:text-cyan-600 dark:group-hover:text-cyan-300 group-hover:border-cyan-400 dark:group-hover:border-cyan-500/40 transition-colors mb-3">
                        <Icon className="w-4 h-4" strokeWidth={1.75} />
                      </div>
                      <p className="text-xs font-serif font-medium text-slate-900 dark:text-white tracking-wide group-hover:text-cyan-700 dark:group-hover:text-cyan-200 transition-colors">
                        {item.label}
                      </p>
                      <p className="text-[10px] font-mono text-slate-500 dark:text-slate-400 mt-0.5 line-clamp-1">
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
        className="min-h-full py-6 px-4 sm:px-6 relative"
        data-testid="home-page"
      >
        {/* Soft Ambient Studio Lighting */}
        <div className="absolute top-0 right-1/4 w-96 h-96 bg-cyan-500/10 rounded-full blur-[140px] pointer-events-none" />
        <div className="absolute top-1/2 left-10 w-80 h-80 bg-blue-600/5 dark:bg-violet-600/10 rounded-full blur-[140px] pointer-events-none" />

        <motion.div variants={staggerContainer} initial="initial" animate="animate" className="max-w-4xl mx-auto space-y-8 relative z-10">
          
          {/* ─── GREETING ─── */}
          <motion.div variants={fadeInUp} className="flex flex-col sm:flex-row sm:items-baseline justify-between pb-4 border-b border-slate-200/80 dark:border-white/10 gap-2">
            <div>
              <span className="text-[10px] font-mono uppercase tracking-[0.22em] text-cyan-800 dark:text-cyan-400 font-bold bg-cyan-50 dark:bg-cyan-950/60 border border-cyan-200 dark:border-cyan-500/30 px-3 py-0.5 rounded-full inline-block mb-1.5 shadow-sm">
                Active Session
              </span>
              <h1 className="font-serif text-2xl sm:text-3xl text-slate-900 dark:text-white tracking-tight">
                {displayName ? `${timeOfDayGreeting()}, ${displayName}.` : `${timeOfDayGreeting()}.`}
              </h1>
            </div>
            <p className="text-slate-500 dark:text-slate-400 font-mono text-xs uppercase tracking-widest">{formatWhen()}</p>
          </motion.div>

          {/* ─── SINCE YOU LAST PLAYED (the Mirror) ─── */}
          {lastSession?.story && (
            <motion.section ref={mirrorRef} variants={fadeInUp}>
              <div className="bg-white/95 dark:bg-gradient-to-b dark:from-[#24313d]/85 dark:to-[#19222a]/85 border border-slate-200/90 dark:border-white/15 rounded-3xl p-6 sm:p-7 shadow-[0_20px_50px_rgba(0,0,0,0.06)] dark:shadow-[0_20px_50px_rgba(0,0,0,0.4)] backdrop-blur-xl relative overflow-hidden">
                <div className="flex items-center space-x-2 text-[10px] font-mono uppercase tracking-[0.22em] text-cyan-800 dark:text-cyan-300 font-bold mb-3">
                  <Activity className="w-3.5 h-3.5 text-cyan-600 dark:text-cyan-400" />
                  <span>Since you last played</span>
                </div>
                
                <p className="text-sm sm:text-[15px] leading-relaxed text-slate-700 dark:text-slate-200">
                  {lastSession.story}
                </p>
                
                {(lastSession.game_id || lastSession.game_ids?.[0]) && (
                  <div className="mt-4 pt-3 border-t border-slate-200/80 dark:border-white/10">
                    <button
                      onClick={() => {
                        track(ANALYTICS_EVENTS.FUNNEL_HOME_CTA_CLICKED, { cta: "review_this_game" });
                        navigate(`/game/${lastSession.game_id || lastSession.game_ids[0]}`);
                      }}
                      className="px-4 py-2 rounded-xl bg-cyan-50 hover:bg-cyan-100 border border-cyan-200 text-cyan-800 dark:bg-cyan-950/60 dark:hover:bg-cyan-900/60 dark:border-cyan-500/40 dark:text-cyan-300 font-mono text-xs font-semibold tracking-wider inline-flex items-center gap-1.5 transition-all shadow-sm"
                    >
                      <span>Review this game</span>
                      <ChevronRight className="h-3.5 w-3.5 text-cyan-600 dark:text-cyan-400" strokeWidth={2} />
                    </button>
                  </div>
                )}
              </div>
            </motion.section>
          )}

          {/* ─── THE COACH CONVERSATION ─── */}
          {coachConversation?.has_conversation || canonicalContext ? (
            <motion.section 
              variants={fadeInUp} 
              className="bg-white/95 dark:bg-gradient-to-b dark:from-[#25323d]/85 dark:to-[#19222b]/85 border border-slate-200/90 dark:border-white/15 rounded-3xl p-7 sm:p-9 shadow-[0_20px_50px_rgba(0,0,0,0.06)] dark:shadow-[0_25px_60px_rgba(0,0,0,0.45)] backdrop-blur-2xl relative overflow-hidden"
            >
              {coachConversation?.thinking_signature && (
                <div className="bg-slate-100/90 dark:bg-black/25 border-l-2 border-cyan-500 dark:border-cyan-400/80 p-3.5 rounded-r-xl mb-5 text-xs font-mono text-slate-800 dark:text-cyan-200/90 leading-relaxed">
                  {coachConversation.thinking_signature}
                </div>
              )}

              {coachConversation?.narrative && (
                <div className="space-y-3 mb-6">
                  <p className="text-[15px] leading-relaxed text-slate-700 dark:text-slate-200">
                    {coachConversation.narrative.stage_opener}
                  </p>
                  <p className="text-[15px] leading-relaxed text-slate-600 dark:text-slate-300">
                    {coachConversation.narrative.continuity}{" "}
                    <span className="text-slate-900 dark:text-white font-medium">
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
                  className="bg-slate-50 dark:bg-black/30 border border-slate-200 dark:border-0 border-l-2 border-l-cyan-500 dark:border-l-cyan-400/80 rounded-r-2xl p-5 mb-7 shadow-sm"
                >
                  <p className="text-[10px] uppercase tracking-[0.2em] text-cyan-700 dark:text-cyan-400 font-mono font-semibold mb-2 flex items-center gap-1.5">
                    <Shield className="w-3.5 h-3.5 text-cyan-600 dark:text-cyan-400" />
                    <span>
                      {pic.learner_state?.label || "Learning"}
                      {pic.learner_state?.refresh_needed ? " · Refresh needed" : ""}
                    </span>
                  </p>
                  <p className="font-serif text-lg font-medium text-slate-900 dark:text-white mb-2">
                    {pic.focus_label}
                  </p>
                  <p className="text-[14px] leading-relaxed text-slate-600 dark:text-slate-200 mb-2">
                    {pic.instruction_text || "Before you move, check whether the piece will be safe on its new square."}
                  </p>
                  <p className="text-[12.5px] leading-relaxed text-slate-500 dark:text-slate-400 italic">
                    I have seen this same decision in more than one of your games. We’ll stay with it until your response begins to change over the board.
                  </p>
                  <div className="flex flex-wrap gap-3 mt-4 pt-3 border-t border-slate-200/80 dark:border-white/10">
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
                      className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 font-mono text-xs font-bold uppercase tracking-wider shadow-[0_0_15px_rgba(56,189,248,0.4)] transition-all"
                    >
                      Practise this
                    </button>
                    {!pic.focus_game || ["cancelled", "completed"].includes(pic.focus_game.status) ? (
                      <button
                        disabled={focusGameBusy}
                        onClick={() => updateFocusGame("commit")}
                        className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 border border-slate-200 text-slate-700 dark:bg-white/10 dark:hover:bg-white/15 dark:border-white/15 dark:text-slate-200 text-xs font-mono font-medium tracking-wide transition-all disabled:opacity-50"
                      >
                        Make my next game a Focus Game
                      </button>
                    ) : pic.focus_game.status === "waiting" ? (
                      <div className="flex items-center space-x-2 text-xs font-mono text-cyan-700 dark:text-cyan-300">
                        <span>Committed — play on Chess.com or Lichess, then sync.</span>
                        <button
                          disabled={focusGameBusy}
                          onClick={() => updateFocusGame("cancel")}
                          className="text-[11px] underline text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : pic.focus_game.status === "claimed" ? (
                      <div className="flex items-center space-x-2 text-xs font-mono text-emerald-700 dark:text-emerald-300">
                        <span>I found the game. I’ll use it to see whether the new habit appeared.</span>
                        <button
                          disabled={focusGameBusy}
                          onClick={() => updateFocusGame("correct", { game_id: pic.focus_game.game_id })}
                          className="text-[11px] underline text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
                        >
                          That was not my Focus Game
                        </button>
                      </div>
                    ) : null}
                  </div>
                </div>
              ) : (
                <p className="text-[15px] leading-relaxed text-slate-900 dark:text-white font-medium mb-6">
                  {coachConversation.one_action}
                </p>
              )}

              {coachConversation?.punish_line?.text && (
                <div className="bg-slate-100/80 dark:bg-white/5 border border-slate-200 dark:border-white/10 rounded-xl p-3.5 mb-4 flex items-center space-x-2 text-xs text-slate-700 dark:text-slate-300">
                  <Sparkles className="w-4 h-4 text-cyan-600 dark:text-cyan-400 shrink-0" />
                  <div>
                    <span className="font-semibold text-slate-900 dark:text-white">{coachConversation.punish_line.headline}</span>{" "}
                    <span>{coachConversation.punish_line.habit}</span>
                  </div>
                </div>
              )}

              {coachConversation?.encouragement && (
                <p className="text-[13px] text-slate-600 dark:text-slate-300/80 mb-2 italic">
                  "{coachConversation.encouragement}"
                </p>
              )}

              {coachConversation?.closing_line && (
                <p className="text-[13px] text-slate-500 dark:text-slate-400 mb-8 font-mono">
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
                  className="px-6 py-3 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 font-mono text-xs font-bold uppercase tracking-wider shadow-[0_0_20px_rgba(56,189,248,0.4)] inline-flex items-center gap-2 transition-all"
                >
                  <Swords className="h-4 w-4" strokeWidth={2} />
                  <span>Play with Coach</span>
                  <ArrowRight className="h-4 w-4" strokeWidth={2} />
                </button>
              )}
            </motion.section>
          ) : (
            <motion.section 
              variants={fadeInUp} 
              className="bg-white/95 dark:bg-gradient-to-b dark:from-[#24313d]/85 dark:to-[#19222a]/85 border border-slate-200/90 dark:border-white/15 rounded-3xl p-7 sm:p-9 shadow-[0_20px_50px_rgba(0,0,0,0.06)] dark:shadow-[0_20px_50px_rgba(0,0,0,0.4)] backdrop-blur-xl relative"
            >
              <p className="text-[15px] leading-relaxed text-slate-700 dark:text-slate-200 mb-6">
                {hasGames
                  ? "I have been through your games. I have not settled on the one pattern to work on with you yet — in the meantime, your last game is worth a look."
                  : "I'm still learning how you play. Play a game or two and I'll start noticing your habits."}
              </p>
              <button
                onClick={() => {
                  track(ANALYTICS_EVENTS.FUNNEL_HOME_CTA_CLICKED, {
                    cta: hasGames ? "review_games" : "play_with_coach",
                    has_conversation: false,
                  });
                  navigate(hasGames ? "/lab" : "/play-with-coach");
                }}
                className="px-6 py-3 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 font-mono text-xs font-bold uppercase tracking-wider shadow-[0_0_15px_rgba(56,189,248,0.4)] inline-flex items-center gap-2 transition-all"
              >
                {hasGames ? "Review your games" : "Play with Coach"}
                <ArrowRight className="h-4 w-4" strokeWidth={2} />
              </button>
            </motion.section>
          )}

          {/* ─── NAVIGATION TILES ─── */}
          <motion.section variants={fadeInUp} className="pt-6">
            <p className="text-[10px] font-mono uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400 font-semibold mb-4">
              Other ways to improve
            </p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3.5">
              {NAV.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    onClick={() => {
                      track(ANALYTICS_EVENTS.FUNNEL_HOME_NAV_TILE_CLICKED, { tile: item.id });
                      navigate(item.href);
                    }}
                    className="group bg-white/95 dark:bg-gradient-to-b dark:from-[#202c38]/80 dark:to-[#161f27]/80 hover:bg-slate-50 dark:hover:from-[#293846]/90 dark:hover:to-[#1c2731]/90 border border-slate-200/90 dark:border-white/10 hover:border-cyan-400 dark:hover:border-cyan-500/40 p-4 rounded-2xl backdrop-blur-xl shadow-sm hover:shadow-md transition-all text-left"
                  >
                    <div className="w-8 h-8 rounded-xl bg-slate-100 dark:bg-black/40 border border-slate-200 dark:border-white/10 flex items-center justify-center text-slate-600 dark:text-slate-400 group-hover:text-cyan-600 dark:group-hover:text-cyan-300 group-hover:border-cyan-400 dark:group-hover:border-cyan-500/40 transition-colors mb-3">
                      <Icon className="w-4 h-4" strokeWidth={1.75} />
                    </div>
                    <p className="text-xs font-serif font-medium text-slate-900 dark:text-white tracking-wide group-hover:text-cyan-700 dark:group-hover:text-cyan-200 transition-colors">
                      {item.label}
                    </p>
                    <p className="text-[10px] font-mono text-slate-500 dark:text-slate-400 mt-0.5 line-clamp-1">
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
