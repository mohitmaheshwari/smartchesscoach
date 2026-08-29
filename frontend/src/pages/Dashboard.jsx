/**
 * LAB — Review room.
 *
 * Implements the redesign spec at
 *   chessguru-design-system/project/redesign/02_Lab.{html,jsx}
 *
 * One promoted game (Coach's Pick) gets the hero slot — mini board + a
 * Fraunces-serif verdict sentence + move-by-move reasoning + tags + single
 * CTA. The rest of the games collapse into a quiet filterable archive
 * table. No cards on the hero, no accuracy progress chrome, no emoji.
 *
 * All existing data fetching (/api/lab-coach-pick), navigation to
 * /game/:id, /play-with-coach, /import, /training/prescribed, and the
 * empty-state flow are preserved.
 */

import { useState, useEffect, useMemo, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { API } from "@/App";
import { ANALYTICS_EVENTS, trackCurriculum } from "@/lib/analytics";
import { CURRICULUM_ROUTES } from "@/lib/personalCurriculum";
import {
  fadeInUp,
  glowPulseAmber,
  revealOnScroll,
  pageEnter,
  staggerContainer,
  staggerItem,
  scaleIn,
  MOTION_TIMING,
} from "@/lib/motion";
import Layout from "@/components/Layout";
import LichessBoard from "@/components/LichessBoard";
// Engine-2 skill curriculum — the Lab's new identity (moved off Progress).
import MasteryPanel from "@/components/coach/MasteryPanel";
import InGameMasteryPanel from "@/components/coach/InGameMasteryPanel";
import TacticsMasteryPanel from "@/components/coach/TacticsMasteryPanel";
import CoachingPatternsPanel from "@/components/Lab/CoachingPatternsPanel";
import {
  Import,
  ChevronRight,
  Swords,
  Target,
  ArrowRight,
  Search,
} from "lucide-react";

// ─── Copy fallbacks ──────────────────────────────────────────────────────────

const BEHAVIOR_DESCRIPTIONS = {
  threw_winning:
    "You were winning. Then you stopped defending — and never noticed.",
  tactical_miss: "You're missing tactics that are right in front of you.",
  one_move_blunder:
    "You're moving without checking if your pieces are still safe.",
  calculation_error:
    "You stop thinking too early. One move deeper would save you.",
  time_collapse:
    "You run out of time and panic. The mistakes come from rushing.",
  opening_disaster: "Your games go wrong in the first ten moves.",
  endgame_collapse:
    "You reach winning endgames, but can't close them.",
  positional:
    "Your opponent outplays you in small ways. The position gradually slips.",
};

// ─── Utilities ──────────────────────────────────────────────────────────────

const resultLetter = (g) => {
  const r = String(g?.result || "").toLowerCase().trim();
  if (r === "win" || r === "w") return "W";
  if (r === "loss" || r === "l") return "L";
  if (r === "draw" || r === "d" || r === "1/2-1/2" || r === "½-½") return "D";
  const color = String(g?.user_color || "").toLowerCase();
  if (r === "1-0") return color === "white" ? "W" : "L";
  if (r === "0-1") return color === "black" ? "W" : "L";
  return null;
};

const fmtDate = (g) => {
  const d = g?.analyzed_at || g?.created_at || g?.date;
  if (!d) return "";
  const ts = new Date(d);
  const diffH = (Date.now() - ts.getTime()) / 3600000;
  if (diffH < 1) return `${Math.floor(diffH * 60)}m`;
  if (diffH < 24) return `${Math.floor(diffH)}h`;
  const days = Math.floor(diffH / 24);
  if (days < 7) return `${days}d`;
  return ts.toLocaleDateString();
};


// ─── Components ─────────────────────────────────────────────────────────────

function ResultGlyph({ r }) {
  if (!r) return <span className="text-muted-foreground/40">—</span>;
  const map = {
    W: { label: "W", cls: "text-emerald-500 dark:text-emerald-400" },
    L: { label: "L", cls: "text-rose-500 dark:text-rose-400" },
    D: { label: "½", cls: "text-muted-foreground" },
  };
  const { label, cls } = map[r];
  return (
    <span className={`font-serif text-[15px] tabular-nums ${cls}`}>{label}</span>
  );
}

// ─── Page ───────────────────────────────────────────────────────────────────

const Dashboard = ({ user }) => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const sessionParam = searchParams.get("session");

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all"); // all | unreviewed | losses | coach | week
  // Intelligence cards — each shows only when the user has real data. Fetched
  // in parallel with the main Lab data so the page isn't blocked.
  const [learnNext, setLearnNext] = useState(null);  // Engine-2 next skill to learn
  const [trapIntel, setTrapIntel] = useState(null);
  const [openingReport, setOpeningReport] = useState(null);
  const [repeatMistakes, setRepeatMistakes] = useState(null);
  const [graduation, setGraduation] = useState(null);
  const [openingBenchmark, setOpeningBenchmark] = useState(null);
  const [openingFit, setOpeningFit] = useState(null);
  // Session panel (Mirror window) — only loaded when ?session=... is in URL.
  const [mirrorSession, setMirrorSession] = useState(null);
  const recommendationShownRef = useRef(null);
  const recommendationElementRef = useRef(null);

  useEffect(() => {
    trackCurriculum(ANALYTICS_EVENTS.LEARN_VIEWED, {
      surface: "legacy_lab",
    });
  }, []);

  useEffect(() => {
    fetchData();
    fetchLearnNext();
    fetchTrapIntel();
    fetchOpeningReport();
    fetchRepeatMistakes();
    fetchGraduation();
    fetchOpeningBenchmark();
    fetchOpeningFit();
    if (sessionParam) {
      fetchMirrorSession();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchOpeningFit = async () => {
    try {
      const res = await fetch(`${API}/coach/opening-fit`, {
        credentials: "include",
      });
      if (res.ok) setOpeningFit(await res.json());
    } catch (_e) { /* silent — card hides when no data */ }
  };

  const fetchData = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API}/lab-coach-pick`, {
        credentials: "include",
      });
      if (res.ok) setData(await res.json());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const fetchMirrorSession = async () => {
    try {
      const res = await fetch(`${API}/coach/mirror-session`, {
        credentials: "include",
      });
      if (!res.ok) return;
      const payload = await res.json();
      // Empty window — server says nothing to mirror; render nothing.
      if (!payload || !payload.window_size) return;
      setMirrorSession(payload);
      // Now that the panel has rendered, close the window — this is
      // the engagement signal. The next Home visit will see a fresh
      // empty window until the user plays more games.
      try {
        await fetch(`${API}/coach/mirror-engaged`, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reason: "lab_open" }),
        });
      } catch (_e) {
        /* engagement is best-effort — don't break the panel */
      }
    } catch (_e) { /* silent */ }
  };

  const fetchLearnNext = async () => {
    try {
      const res = await fetch(`${API}/engine2/learn-next`, {
        credentials: "include",
      });
      if (res.ok) {
        const d = await res.json();
        setLearnNext(d.learn_next || null);
      }
    } catch (_e) {
      // Silent — hero just stays hidden.
    }
  };

  useEffect(() => {
    if (!learnNext?.skill_id) return;
    const decisionId = `legacy_engine2:${learnNext.skill_id}`;
    const element = recommendationElementRef.current;
    if (!element) return;
    const observer = new IntersectionObserver((entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return;
      if (recommendationShownRef.current === decisionId) return;
      recommendationShownRef.current = decisionId;
      trackCurriculum(ANALYTICS_EVENTS.CURRICULUM_DECISION_SHOWN, {
        surface: "legacy_lab",
        decision_id: decisionId,
        decision_source: "engine2_learn_next",
        recommendation_kind: "expand",
        content_type: "skill",
        content_id: learnNext.skill_id,
        origin: "recommendation",
        is_recommended: true,
      });
      observer.disconnect();
    }, { threshold: 0.6 });
    observer.observe(element);
    return () => observer.disconnect();
  }, [learnNext]);

  const fetchTrapIntel = async () => {
    try {
      const res = await fetch(`${API}/coach/trap-intelligence`, {
        credentials: "include",
      });
      if (res.ok) setTrapIntel(await res.json());
    } catch (_e) {
      // Silent — card just stays hidden.
    }
  };

  const fetchOpeningReport = async () => {
    try {
      const res = await fetch(`${API}/coach/opening-report`, {
        credentials: "include",
      });
      if (res.ok) setOpeningReport(await res.json());
    } catch (_e) {
      /* card hidden on error */
    }
  };

  const fetchRepeatMistakes = async () => {
    try {
      const res = await fetch(`${API}/coach/repeat-mistakes`, {
        credentials: "include",
      });
      if (res.ok) setRepeatMistakes(await res.json());
    } catch (_e) {
      /* card hidden on error */
    }
  };

  const fetchGraduation = async () => {
    try {
      const res = await fetch(`${API}/coach/graduation-insight`, { credentials: "include" });
      if (res.ok) setGraduation(await res.json());
    } catch (_e) { /* silent */ }
  };

  const fetchOpeningBenchmark = async () => {
    try {
      const res = await fetch(`${API}/coach/opening-benchmark`, { credentials: "include" });
      if (res.ok) setOpeningBenchmark(await res.json());
    } catch (_e) { /* silent */ }
  };

  // ─── Derived state (same semantics as before, just better-named) ─────
  const coaching = data?.coaching;
  const games = useMemo(() => data?.games || [], [data]);
  const topProblems = coaching?.top_problems || [];
  const groupedGames = coaching?.grouped_games || {};
  const priorityGame = coaching?.priority_game;
  const activeFocus = coaching?.active_focus || null;
  const primaryProblem = topProblems[0] || null;
  const primaryGames = primaryProblem
    ? groupedGames[primaryProblem.category]?.games || []
    : [];
  const unreviewed = primaryGames.filter((g) => !g.reviewed);

  // Featured game for Coach's Pick hero — same logic as before
  let featuredGame = null;
  try {
    if (priorityGame) {
      featuredGame = {
        ...priorityGame,
        critical_fen:
          priorityGame.critical_fen ||
          priorityGame.replay?.mistake_fen ||
          null,
        critical_move:
          priorityGame.critical_move || priorityGame.move_number || null,
      };
    }
    if (!featuredGame?.critical_fen && unreviewed.length > 0) {
      featuredGame = unreviewed[0];
    }
    if (
      featuredGame?.critical_fen &&
      featuredGame.critical_fen.split(" ").length < 2
    ) {
      featuredGame.critical_fen = null;
    }
  } catch (e) {
    featuredGame = null;
  }

  const unreviewedCount = games.filter((g) => !g.reviewed).length;

  // Archive — apply filter
  const filteredGames = useMemo(() => {
    const all = [...games].sort((a, b) => {
      const da = new Date(a.analyzed_at || a.created_at || a.date || 0);
      const db = new Date(b.analyzed_at || b.created_at || b.date || 0);
      return db - da;
    });
    switch (filter) {
      case "unreviewed":
        return all.filter((g) => !g.reviewed);
      case "losses":
        return all.filter((g) => resultLetter(g) === "L");
      case "coach":
        return all.filter((g) => g.platform === "coach");
      case "week": {
        const cutoff = Date.now() - 7 * 24 * 3600 * 1000;
        return all.filter(
          (g) =>
            new Date(
              g.analyzed_at || g.created_at || g.date || 0
            ).getTime() >= cutoff
        );
      }
      default:
        return all;
    }
  }, [games, filter]);

  const FILTERS = [
    { key: "all", label: "All" },
    {
      key: "unreviewed",
      label: `Unreviewed · ${unreviewedCount}`,
    },
    { key: "losses", label: "Losses" },
    { key: "coach", label: "vs Coach" },
    { key: "week", label: "This week" },
  ];

  // ─── Loading / empty ─────────────────────────────────────────────────
  if (loading) {
    // Skeleton shimmer while loading (scope §Lab) — page-shaped rows
    // instead of a spinner so the layout doesn't jump when data lands.
    return (
      <Layout user={user}>
        <div
          className="max-w-[1040px] mx-auto px-6 md:px-10 py-10 md:py-16"
          data-testid="lab-skeleton"
        >
          {/* Head */}
          <div className="relative overflow-hidden rounded-lg bg-muted/40 h-4 w-40 mb-6">
            <div className="absolute inset-0 animate-shimmer" />
          </div>
          <div className="relative overflow-hidden rounded-lg bg-muted/40 h-10 w-[420px] max-w-full mb-12">
            <div className="absolute inset-0 animate-shimmer" />
          </div>
          {/* Coach's Pick block */}
          <div className="grid grid-cols-1 md:grid-cols-[auto_1fr] gap-8 md:gap-12 mb-16">
            <div className="relative overflow-hidden rounded-xl bg-muted/40 w-full md:w-[240px] aspect-square">
              <div className="absolute inset-0 animate-shimmer" />
            </div>
            <div className="space-y-4">
              <div className="relative overflow-hidden rounded-lg bg-muted/40 h-6 w-3/4">
                <div className="absolute inset-0 animate-shimmer" />
              </div>
              <div className="relative overflow-hidden rounded-lg bg-muted/40 h-4 w-1/2">
                <div className="absolute inset-0 animate-shimmer" />
              </div>
            </div>
          </div>
          {/* Archive rows */}
          <div className="space-y-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="relative overflow-hidden rounded-lg bg-muted/30 h-11"
              >
                <div className="absolute inset-0 animate-shimmer" />
              </div>
            ))}
          </div>
        </div>
      </Layout>
    );
  }

  if (games.length === 0) {
    return (
      <Layout user={user}>
        <div
          className="max-w-[520px] mx-auto px-6 py-24 text-center"
          data-testid="lab-page"
        >
          <p className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-4">
            The Lab
          </p>
          <h2 className="font-serif text-[32px] leading-[1.05] tracking-[-0.02em] font-medium text-foreground mb-4">
            Nothing to review yet.
          </h2>
          <p className="text-[13.5px] text-muted-foreground mb-10 leading-relaxed">
            Import your games or play the coach — the Lab fills up with
            moments worth studying.
          </p>
          <div className="flex flex-col gap-3 items-stretch">
            <button
              onClick={() => navigate("/play-with-coach")}
              className="experience-primary px-6 py-3 text-sm font-semibold rounded-xl bg-violet-500 hover:bg-violet-400 text-white transition-colors inline-flex items-center justify-center gap-2"
            >
              <Swords className="w-4 h-4" strokeWidth={2} />
              Play with Coach
            </button>
            <button
              onClick={() => navigate("/import")}
              className="px-6 py-3 text-sm border border-border text-foreground rounded-xl hover:bg-muted/40 transition-colors"
            >
              Import your games
            </button>
          </div>
        </div>
      </Layout>
    );
  }

  // ─── Main render ─────────────────────────────────────────────────────
  // Coach's Pick primary: prefer the featured game's own coach-voice
  // headline (e.g. "You were winning. You let it slip.") — that's the
  // specific-game truth. Fall back to the cross-game pattern label only if
  // no featured verdict is available yet.
  const verdict =
    featuredGame?.root_cause ||
    activeFocus?.label ||
    BEHAVIOR_DESCRIPTIONS[primaryProblem?.category] ||
    primaryProblem?.label ||
    "Let's find something to work on.";

  // Secondary line: the move-specific supporting sentence from the summary,
  // or (if missing) the cross-game count. Numbers only when they're real.
  const verdictSub =
    featuredGame?.subline ||
    activeFocus?.reason ||
    (primaryProblem && primaryProblem.count
      ? `Showing up in ${primaryProblem.count} of your recent games.`
      : null);

  const pickResult = resultLetter(featuredGame);

  // Construct "reasoning" bullet list when available. Per-game, factual.
  // Rule: only show a line when we have concrete data — the move you
  // played, the best move, the coach take. No italic filler like
  // "this is where the game turned" / "and then it slipped" — either
  // we have the specifics, or we say nothing.
  const reasoningLines = [];
  if (featuredGame?.was_winning) {
    reasoningLines.push({
      at: "Earlier",
      note: "You were winning this one.",
    });
  }
  // Coach Voice line replaces the engine arrow + cp output. Backend
  // computes coach_line per game (game_mirror.compute_card_coach_line).
  // Falls through silently when no decisive moment to surface.
  if (featuredGame?.coach_line) {
    reasoningLines.push({
      at: featuredGame.critical_move ? `Move ${featuredGame.critical_move}` : "The moment",
      note: featuredGame.coach_line.charAt(0).toUpperCase() + featuredGame.coach_line.slice(1) + ".",
    });
  }
  if (featuredGame?.coach_take) {
    reasoningLines.push({
      at: "The lesson",
      note: featuredGame.coach_take,
    });
  }

  return (
    <Layout user={user}>
      <motion.div
        variants={pageEnter}
        initial="initial"
        animate="animate"
        exit="exit"
        className="experience-page experience-lab-page min-h-screen text-foreground"
        data-testid="lab-page"
      >
        <motion.div
          variants={fadeInUp}
          initial="initial"
          animate="animate"
          className="max-w-[1040px] mx-auto px-6 md:px-10 py-10 md:py-16"
        >
          {/* ─── Page head ─── */}
          <div className="flex items-baseline justify-between mb-10 md:mb-14">
            <div>
              <p className="experience-eyebrow text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-3">
                Learn
              </p>
              <h1 className="experience-coach-copy font-serif text-[28px] md:text-[40px] leading-[1.05] tracking-[-0.02em] font-medium text-foreground">
                Your learning path
              </h1>
            </div>
          </div>

          {/* ━━━━━━━━━━ LEARN NEXT · Engine 2 curriculum ━━━━━━━━━━ */}
          {/* The Lab's identity: the forward-looking learning PATH. "Learn next"
              is the prerequisite-gated, rating-aware pick from Engine 2; the skill
              tree below shows what you've mastered / next / locked. (Progress is
              the report card — how you're doing; this is the syllabus — what to
              learn next.) 2026-07-07. */}
          {learnNext && (
            <motion.section ref={recommendationElementRef} {...revealOnScroll} className="mb-12 md:mb-16">
              <div className="experience-eyebrow text-[10.5px] uppercase tracking-[0.22em] text-violet-500 dark:text-violet-300/80 font-semibold mb-5">
                Learn next
              </div>
              <div className="experience-focus-card experience-surface rounded-2xl border border-violet-500/20 bg-violet-500/[0.04] p-6 md:p-7">
                <p className="font-serif text-[22px] md:text-[28px] leading-[1.15] tracking-[-0.015em] font-medium text-foreground mb-2">
                  {learnNext.label}
                </p>
                {learnNext.reason && (
                  <p className="text-[13.5px] text-muted-foreground mb-1">{learnNext.reason}</p>
                )}
                {learnNext.fixes && (
                  <p className="text-[13px] text-muted-foreground/80 mb-5">
                    Fixes: {learnNext.fixes}
                  </p>
                )}
                <button
                  onClick={() => {
                    trackCurriculum(ANALYTICS_EVENTS.CURRICULUM_PRIMARY_CLICKED, {
                      surface: "legacy_lab",
                      decision_id: `legacy_engine2:${learnNext.skill_id}`,
                      decision_source: "engine2_learn_next",
                      recommendation_kind: "expand",
                      content_type: "skill",
                      content_id: learnNext.skill_id,
                      origin: "recommendation",
                      is_recommended: true,
                    });
                    navigate(`/training/skill/${learnNext.skill_id}`);
                  }}
                  className="experience-primary h-11 px-6 rounded-xl bg-violet-500 hover:bg-violet-400 text-white font-medium text-[14px] transition-colors inline-flex items-center gap-2"
                >
                  Start this lesson
                  <ArrowRight className="h-4 w-4" strokeWidth={2} />
                </button>
              </div>
            </motion.section>
          )}

          {/* ━━━━━━━━━━ YOUR MASTERY · fundamentals + tactics ━━━━━━━━━━ */}
          {/* Fundamentals skill tree (openings/mates/concepts/endgames) AND the
              fork/pin/skewer tactics ladder — unified here 2026-07-08 so pins &
              forks show up in the mastery view, not a separate page. */}
          <section className="mb-16 md:mb-24 space-y-14">
            <MasteryPanel />
            <InGameMasteryPanel />
            <TacticsMasteryPanel />
          </section>

          {/* ━━━━━━━━━━ COACHING PATTERNS · motifs, phases, coordination ━━━━━━━━━━ */}
          {/* New: Display 5 coaching patterns (fork/pin/skewer, phase accuracy,
              coordination, prophylaxis, opening deviations) with cards + CTAs.
              Launched 2026-07-14 as part of complete pattern detector system. */}
          <CoachingPatternsPanel user={user} />

          {/* ━━━━━━━━━━ SESSION REVIEW ━━━━━━━━━━ */}
          {/* Renders only when user arrived from Home's "Open in Lab"
              with a Mirror window in URL. Scopes the top of Lab to
              just the games that window covered, with the same verdict
              the user saw on Home. Existing aggregate Lab cards still
              render below — they speak to longer-horizon patterns. */}
          {mirrorSession && mirrorSession.window_size > 0 && (
            <section className="mb-16 md:mb-24">
              <div className="text-[10.5px] uppercase tracking-[0.22em] text-amber-600 dark:text-amber-300/80 font-semibold mb-5">
                Recent session · {mirrorSession.window_size}{" "}
                {mirrorSession.window_size === 1 ? "game" : "games"}
                {mirrorSession.games_breakdown &&
                  mirrorSession.games_breakdown.length < mirrorSession.window_size && (
                    <span className="ml-3 normal-case tracking-normal text-muted-foreground/70">
                      · showing {mirrorSession.games_breakdown.length} most recent
                    </span>
                  )}
                {(!mirrorSession.games_breakdown ||
                  mirrorSession.games_breakdown.length === mirrorSession.window_size) && (
                  <span className="ml-3 normal-case tracking-normal text-muted-foreground/70">
                    · newest first
                  </span>
                )}
              </div>
              <div className="rounded-xl border border-amber-500/20 bg-amber-500/[0.04] p-6 md:p-7">
                {mirrorSession.story && (
                  <p className="font-serif italic text-[17px] md:text-[19px] leading-snug text-foreground/90 mb-5 max-w-[640px]">
                    "{mirrorSession.story}"
                  </p>
                )}
                {(mirrorSession.games_breakdown?.length > 0 ||
                  mirrorSession.game_ids?.length > 0) && (
                  <div className="space-y-1">
                    {(mirrorSession.games_breakdown ||
                      mirrorSession.game_ids?.map((gid) => ({ game_id: gid }))
                    ).map((g, i) => {
                      const outcomeLabel =
                        g.outcome === "won" ? "Win" :
                        g.outcome === "lost" ? "Loss" :
                        g.outcome === "drew" ? "Draw" : null;
                      const outcomeColor =
                        g.outcome === "won" ? "text-emerald-500 dark:text-emerald-300/80" :
                        g.outcome === "lost" ? "text-rose-500 dark:text-rose-300/80" :
                        g.outcome === "drew" ? "text-muted-foreground" : "";
                      const opening = g.opening
                        ? String(g.opening).split(":")[0].trim()
                        : null;
                      // Coach Voice line replaces the engine arrow.
                      // Backend produces coach_line per card; raw
                      // critical_* fields stay only for legacy callers.
                      const coachLine = g.coach_line || null;
                      const chips = g.pattern_chips || [];
                      const isUrgent = !!g.is_urgent;
                      return (
                        <button
                          key={g.game_id}
                          // 2026-05-19: redirect to /lab/game/:id (LabV2 — interactive
                          // review WITH V5 captions) instead of /game/:id (legacy
                          // GameAnalysis.jsx — missing interactive flow AND V5).
                          onClick={() => navigate(`/lab/game/${g.game_id}`)}
                          className={`w-full text-left flex items-baseline gap-3 text-[13px] py-2 px-2 rounded transition-colors ${
                            isUrgent
                              ? "border-l-2 border-rose-500/70 bg-rose-500/[0.03] hover:bg-rose-500/[0.06]"
                              : "hover:bg-amber-500/10"
                          }`}
                        >
                          <span className="text-muted-foreground tabular-nums w-[24px] shrink-0">
                            {i + 1}.
                          </span>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-baseline gap-2 flex-wrap">
                              {outcomeLabel && (
                                <span className={`font-medium ${outcomeColor}`}>
                                  {outcomeLabel}
                                </span>
                              )}
                              {g.opponent && (
                                <span className="text-foreground/70">
                                  vs {g.opponent}
                                </span>
                              )}
                              {opening && (
                                <span className="text-muted-foreground">
                                  · {opening}
                                </span>
                              )}
                              {chips.map((c) => (
                                <span
                                  key={c.key}
                                  className={
                                    c.urgent
                                      ? "text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-md bg-rose-500/15 border border-rose-500/30 text-rose-600 dark:text-rose-300 font-semibold"
                                      : "text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-md bg-muted/40 border border-border/50 text-muted-foreground/90"
                                  }
                                >
                                  {c.label}
                                </span>
                              ))}
                              {isUrgent && (
                                <span className="text-[10px] uppercase tracking-wider text-rose-500 font-semibold">
                                  · cost the game
                                </span>
                              )}
                            </div>
                            {coachLine && (
                              <div className="text-[11.5px] text-muted-foreground/80 mt-0.5">
                                {coachLine}
                              </div>
                            )}
                          </div>
                          <ChevronRight
                            className="w-3.5 h-3.5 text-muted-foreground shrink-0 self-center"
                            strokeWidth={1.75}
                          />
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            </section>
          )}

          {/* ━━━━━━━━━━ COACH'S PICK ━━━━━━━━━━ */}
          {featuredGame && (
            <motion.section
              variants={scaleIn}
              initial="initial"
              animate="animate"
              className="mb-16 md:mb-24"
            >
              <div className="experience-eyebrow text-[10.5px] uppercase tracking-[0.22em] text-violet-500 dark:text-violet-300/80 font-semibold mb-5">
                Coach's Pick · most educational
              </div>

              <div className="grid grid-cols-1 md:grid-cols-[auto_1fr] gap-8 md:gap-12 items-start">
                {/* Mini board — one-shot amber glow pulse on entrance */}
                <div className="w-full md:w-[240px] shrink-0">
                  {featuredGame.critical_fen ? (
                    <motion.div
                      variants={glowPulseAmber}
                      initial="initial"
                      animate="animate"
                      className="rounded-xl overflow-hidden ring-1 ring-border"
                    >
                      <LichessBoard
                        fen={featuredGame.critical_fen}
                        viewOnly={true}
                        width={240}
                      />
                    </motion.div>
                  ) : (
                    <div className="aspect-square rounded-xl bg-muted/40 ring-1 ring-border flex items-center justify-center">
                      <span className="text-[11px] text-muted-foreground">
                        No position
                      </span>
                    </div>
                  )}
                </div>

                {/* Content */}
                <div className="pt-1">
                  {/* Top line: opponent + metadata + result */}
                  <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 mb-5">
                    <span className="font-serif text-[15px] text-muted-foreground">
                      {featuredGame.platform === "coach"
                        ? "vs Coach"
                        : featuredGame.opponent
                          ? `vs ${featuredGame.opponent}`
                          : "Recent game"}
                    </span>
                    <span className="text-[12px] text-muted-foreground/60 tabular-nums">
                      {[
                        featuredGame.opponent_rating,
                        featuredGame.time_control,
                        fmtDate(featuredGame),
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                    {pickResult && (
                      <span
                        className={`ml-auto text-[12px] tabular-nums ${
                          pickResult === "L"
                            ? "text-rose-500 dark:text-rose-400"
                            : pickResult === "W"
                              ? "text-emerald-500 dark:text-emerald-400"
                              : "text-muted-foreground"
                        }`}
                      >
                        {pickResult === "L"
                          ? "Loss"
                          : pickResult === "W"
                            ? "Win"
                            : "Draw"}
                        {featuredGame.accuracy
                          ? ` · ${featuredGame.accuracy}% acc`
                          : ""}
                      </span>
                    )}
                  </div>

                  {/* Verdict — the serif hero */}
                  <p className="font-serif text-[22px] md:text-[28px] leading-[1.15] tracking-[-0.015em] font-medium text-foreground max-w-[540px]">
                    {verdict}
                  </p>

                  {verdictSub && (
                    <p className="mt-3 text-[13.5px] text-muted-foreground leading-relaxed max-w-[520px]">
                      {verdictSub}
                    </p>
                  )}

                  {/* Move-by-move reasoning */}
                  {reasoningLines.length > 0 && (
                    <ol className="mt-7 space-y-2.5 max-w-[540px]">
                      {reasoningLines.map((r, i) => (
                        <li key={i} className="flex gap-4 text-[13.5px]">
                          <span className="font-mono text-[12px] text-muted-foreground/70 tabular-nums w-[78px] shrink-0 pt-0.5">
                            {r.at}
                          </span>
                          <span className="text-foreground/80 leading-relaxed">
                            {r.note}
                          </span>
                        </li>
                      ))}
                    </ol>
                  )}

                  {/* CTA row */}
                  <div className="mt-8 md:mt-9 flex flex-wrap items-center gap-5">
                    <button
                      onClick={() =>
                        navigate(
                          // 2026-05-19: route to interactive LabV2 surface,
                          // not the static legacy GameAnalysis page.
                          `/lab/game/${featuredGame.game_id}${
                            featuredGame.critical_move
                              ? `?move=${featuredGame.critical_move}`
                              : ""
                          }`
                        )
                      }
                      className="experience-primary h-11 px-6 rounded-xl bg-violet-500 hover:bg-violet-400 text-white font-medium text-[14px] transition-colors inline-flex items-center gap-2"
                    >
                      Review this game
                      <ArrowRight className="h-4 w-4" strokeWidth={2} />
                    </button>
                    <button
                      onClick={() => {
                        const el = document.getElementById("lab-archive");
                        el?.scrollIntoView({ behavior: "smooth" });
                      }}
                      className="text-[12.5px] text-muted-foreground hover:text-foreground transition-colors"
                    >
                      Skip to archive
                    </button>
                  </div>
                </div>
              </div>
            </motion.section>
          )}

          {/* Trap intelligence removed from the Lab 2026-07-07 — "you've seen the
              Fried Liver 127 times" is a trivia stat, not something the player
              needs to work on. Noise, not coaching. (fetchTrapIntel left in place
              but its card no longer renders.) */}

          {/* Opening report moved OFF the Lab — it's a trend/stat (your losing
              openings), which is the /openings page's job (and Progress's). The
              Lab is the experiment bench, not a stats report. 2026-07-07. */}

          {/* ━━━━━━━━━━ OPENINGS THAT FIT YOU ━━━━━━━━━━ */}
          {/* Combines win rate + Mirror's weakness patterns + theory
              burden, scaled by user rating. Tells the user which
              openings reward what they already do, and which keep
              punishing the weakness they haven't fixed yet. */}
          {openingFit?.has_data && (openingFit.play_more?.length > 0 || openingFit.avoid?.length > 0) && (
            <motion.section {...revealOnScroll} className="mb-16 md:mb-24">
              <div className="text-[10.5px] uppercase tracking-[0.22em] text-teal-600 dark:text-teal-300/80 font-semibold mb-5">
                Openings that fit you
              </div>
              <div className="rounded-xl border border-teal-500/20 bg-teal-500/[0.04] p-6 md:p-7 space-y-5">
                {openingFit.play_more?.length > 0 && (
                  <div>
                    <div className="text-[11px] uppercase tracking-[0.18em] text-emerald-600 dark:text-emerald-300/80 font-semibold mb-3">
                      Play more
                    </div>
                    <div className="space-y-2.5">
                      {openingFit.play_more.map((o) => (
                        <button
                          key={`pm-${o.opening_key}-${o.color}`}
                          onClick={() => navigate(`/openings/${o.opening_key}`)}
                          className="w-full text-left flex items-baseline gap-3 py-1.5 px-2 rounded hover:bg-emerald-500/10 transition-colors"
                        >
                          <span className="text-emerald-500 dark:text-emerald-300/80 shrink-0">✓</span>
                          <span className="font-medium text-foreground/90">
                            {o.name}
                            <span className="text-muted-foreground font-normal">
                              {" "}({o.color})
                            </span>
                          </span>
                          <span className="text-xs text-muted-foreground ml-auto text-right">
                            {o.reason}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                {openingFit.avoid?.length > 0 && (
                  <div>
                    <div className="text-[11px] uppercase tracking-[0.18em] text-rose-600 dark:text-rose-300/80 font-semibold mb-3">
                      Avoid for now
                    </div>
                    <div className="space-y-2.5">
                      {openingFit.avoid.map((o) => (
                        <div
                          key={`av-${o.opening_key}-${o.color}`}
                          className="flex items-baseline gap-3 py-1.5 px-2"
                        >
                          <span className="text-rose-500 dark:text-rose-300/80 shrink-0">✗</span>
                          <span className="font-medium text-foreground/80">
                            {o.name}
                            <span className="text-muted-foreground font-normal">
                              {" "}({o.color})
                            </span>
                          </span>
                          <span className="text-xs text-muted-foreground ml-auto text-right">
                            {o.reason}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                <p className="text-[10.5px] uppercase tracking-[0.18em] text-muted-foreground/70 pt-2 border-t border-teal-500/10">
                  Based on your rating ({openingFit.rating_used}) and recent patterns
                </p>
              </div>
            </motion.section>
          )}

          {/* ━━━━━━━━━━ REPEAT MISTAKE PATTERN ━━━━━━━━━━ */}
          {/* "You've done this in N different games" signal — cross-game
              pattern detection that mirrors what a human coach would
              notice over multiple sessions. */}
          {repeatMistakes?.has_data && repeatMistakes.top_pattern && (
            <motion.section {...revealOnScroll} className="mb-16 md:mb-24">
              <div className="experience-eyebrow text-[10.5px] uppercase tracking-[0.22em] text-violet-500 dark:text-violet-300/80 font-semibold mb-5">
                Pattern across your games
              </div>
              <div className="experience-focus-card experience-surface rounded-2xl border border-violet-500/20 bg-violet-500/[0.04] p-6 md:p-7">
                <p className="font-serif text-[19px] md:text-[22px] leading-[1.3] tracking-[-0.01em] text-foreground/90 mb-3">
                  {repeatMistakes.top_pattern.headline}
                </p>
                {repeatMistakes.top_pattern.example_games?.length > 0 && (
                  <p className="text-[13px] text-muted-foreground mb-5">
                    Most recent: Move {repeatMistakes.top_pattern.example_games[0].move_number}{" "}
                    {repeatMistakes.top_pattern.example_games[0].san}
                    {repeatMistakes.top_pattern.cognitive_gap === "piece_safety" &&
                      repeatMistakes.top_pattern.piece_name && (
                        <> — left a {repeatMistakes.top_pattern.piece_name} undefended</>
                      )}
                    {repeatMistakes.top_pattern.example_games.length > 1 && (
                      <> · {repeatMistakes.top_pattern.example_games.length} examples</>
                    )}
                  </p>
                )}
                <button
                  onClick={() =>
                    navigate(
                      `/training/prescribed?weakness=${repeatMistakes.top_pattern.training_weakness}`
                    )
                  }
                  className="experience-primary h-10 px-5 rounded-lg bg-violet-500/90 hover:bg-violet-500 text-white font-medium text-[13px] transition-colors inline-flex items-center gap-2"
                >
                  <Target className="h-3.5 w-3.5" strokeWidth={1.75} />
                  Train this pattern
                </button>
              </div>
            </motion.section>
          )}

          {/* ━━━━━━━━━━ GRADUATION / IMPROVEMENT TRAJECTORY ━━━━━━━━━━ */}
          {/* Celebration (graduate) OR roadmap (struggler). Silent for users
              with <20 games or no improvement data. */}
          {graduation?.has_data && graduation.status === "graduate" && (
            <motion.section {...revealOnScroll} className="mb-16 md:mb-24">
              <div className="text-[10.5px] uppercase tracking-[0.22em] text-emerald-600 dark:text-emerald-300/80 font-semibold mb-5">
                You're improving
              </div>
              <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/[0.04] p-6 md:p-7">
                <p className="font-serif text-[19px] md:text-[22px] leading-[1.3] tracking-[-0.01em] text-foreground/90 mb-3">
                  {graduation.headline}
                </p>
                <p className="text-[13px] text-muted-foreground">
                  {graduation.subline}
                </p>
              </div>
            </motion.section>
          )}
          {/* ━━━━━━━━━━ BROWSE YOUR GAMES ━━━━━━━━━━ */}
          {/* The full 50-game archive moved OFF the Lab — the game LIST + review
              queue is /games (AllGames). The reviewer-only queue stays at
              /review. The Lab is the
              experiment bench (drills + the one curated Coach's Pick above), not a
              game log. This is just a way out to those pages. 2026-07-07. */}
          <section id="lab-archive">
            <div className="flex items-center justify-between gap-4 rounded-xl border border-border/60 bg-muted/20 px-6 py-5">
              <div className="text-[13px] text-muted-foreground">
                Looking for a specific game? Your game history is ready in Game Review.
              </div>
              <button
                onClick={() => navigate(CURRICULUM_ROUTES.gameReview)}
                className="shrink-0 flex items-center gap-2 text-[12.5px] text-foreground hover:text-violet-500 dark:hover:text-violet-300 font-medium transition-colors"
              >
                <Search className="h-3.5 w-3.5" strokeWidth={1.75} />
                <span>Browse games</span>
                <ArrowRight className="h-3.5 w-3.5" strokeWidth={2} />
              </button>
            </div>
          </section>

          {/* Legacy archive table removed 2026-07-07 (moved to /games).
              Kept the filter/row logic out of the Lab — it was the biggest source
              of noise. If a compact recent-games strip is wanted here later, build
              it fresh rather than restoring the 50-row scroll. */}
          {false && (
            <section>
              <div className="flex items-center gap-5 md:gap-6 mb-6 pb-4 border-b border-border/60 overflow-x-auto">
              {FILTERS.map((f) => (
                <motion.button
                  key={f.key}
                  whileHover={{ y: -2 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => setFilter(f.key)}
                  className={`relative pb-1 text-[12.5px] transition-colors whitespace-nowrap ${
                    filter === f.key
                      ? "text-foreground font-medium"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {f.label}
                  {filter === f.key && (
                    <motion.span
                      layoutId="lab-filter-active"
                      // Spring specified for the pill morph (scope §Lab) —
                      // the one place choreography uses spring, not tween.
                      transition={{ type: "spring", stiffness: 300, damping: 30 }}
                      className="absolute left-0 right-0 bottom-0 h-[2px] rounded-full bg-amber-400"
                    />
                  )}
                </motion.button>
              ))}
            </div>

            {/* Table — keyed by filter so AnimatePresence fades the old
                rows out (150ms) and staggers the new rows in (40ms/row). */}
            <AnimatePresence mode="wait">
            <motion.div
              key={filter}
              variants={staggerContainer}
              initial="initial"
              animate="animate"
              exit={{
                opacity: 0,
                transition: { duration: MOTION_TIMING.micro.duration / 1000 },
              }}
              className="space-y-0"
            >
              {filteredGames.length === 0 ? (
                <div className="py-12 text-center text-[12.5px] text-muted-foreground">
                  No games match this filter.
                </div>
              ) : (
                filteredGames.slice(0, 24).map((g) => {
                  const r = resultLetter(g);
                  // Quality filter: only render the diagnosis line when it
                  // adds signal. Bland fallbacks from compute_game_summary
                  // (empty / "No move data" / a plain draw sentence) are
                  // suppressed — the result glyph already carries the story.
                  const raw = (g.root_cause || "").trim();
                  const isWeak =
                    !raw ||
                    raw === "No move data available" ||
                    raw === "No user moves found" ||
                    raw === "Game ended in a draw.";
                  const diagnosis = isWeak ? "" : raw;
                  return (
                    <motion.div
                      key={g.game_id || g._id}
                      variants={staggerItem}
                      // 2026-05-19: route to interactive LabV2 surface (has V5 + guided-review quiz).
                      onClick={() => navigate(`/lab/game/${g.game_id}`)}
                      className="group grid grid-cols-[12px_1fr_40px_60px_14px] md:grid-cols-[12px_1fr_48px_80px_14px] gap-4 md:gap-5 items-center py-3.5 border-b border-border/40 hover:bg-muted/30 -mx-3 px-3 transition-colors cursor-pointer"
                    >
                      {/* Reviewed dot */}
                      <span
                        className={`h-1.5 w-1.5 rounded-full ${
                          g.reviewed
                            ? "bg-muted-foreground/30"
                            : "bg-violet-400 dark:bg-violet-400"
                        }`}
                      />

                      {/* Opponent + move-grounded diagnosis */}
                      <div className="min-w-0">
                        <div className="flex items-baseline gap-2">
                          <span className="text-[13.5px] md:text-[14px] text-foreground font-medium truncate">
                            {g.platform === "coach"
                              ? "Coach"
                              : g.opponent || "Opponent"}
                          </span>
                          {g.platform === "coach" && (
                            <span className="text-[9.5px] uppercase tracking-[0.18em] text-violet-600 dark:text-violet-300/70 font-semibold">
                              Coach
                            </span>
                          )}
                        </div>
                        {diagnosis && (
                          <div className="text-[11.5px] text-muted-foreground truncate">
                            {diagnosis}
                          </div>
                        )}
                      </div>

                      {/* Result */}
                      <div>
                        <ResultGlyph r={r} />
                      </div>

                      {/* Age */}
                      <div className="text-[11.5px] text-muted-foreground tabular-nums text-right">
                        {fmtDate(g)}
                      </div>

                      {/* Chevron */}
                      <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/20 group-hover:text-muted-foreground transition-colors" />
                    </motion.div>
                  );
                })
              )}
            </motion.div>
            </AnimatePresence>

            {/* Load more */}
            {filteredGames.length > 24 && (
              <div className="mt-10 text-center">
                <button
                  onClick={() => navigate("/games")}
                  className="text-[12.5px] text-muted-foreground hover:text-foreground transition-colors"
                >
                  Load {filteredGames.length - 24} more
                </button>
              </div>
            )}
            </section>
          )}
        </motion.div>
      </motion.div>
    </Layout>
  );
};

export default Dashboard;
