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

import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import LichessBoard from "@/components/LichessBoard";
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

const PATTERN_MAP = {
  threw_winning: "calculation_depth",
  tactical_miss: "tactical_oversight",
  one_move_blunder: "piece_safety",
  calculation_error: "calculation_depth",
  time_collapse: "calculation_depth",
  opening_disaster: "piece_safety",
  endgame_collapse: "endgame_technique",
};

// Short, human label for the pattern — used in the page header as the
// replacement for the "50 unreviewed" backlog counter. One focus, named.
const FOCUS_LABEL = {
  threw_winning:     "throwing winning positions",
  tactical_miss:     "missing tactics",
  one_move_blunder:  "piece safety",
  calculation_error: "calculation depth",
  time_collapse:     "time pressure",
  opening_disaster:  "opening fundamentals",
  endgame_collapse:  "endgame conversion",
  positional:        "positional drift",
};

// Drill-style CTA copy keyed by the same categories. Makes the button
// specific to the pattern instead of the generic "Practice this pattern".
const CTA_LABEL = {
  threw_winning:     "Drill: Hold winning positions",
  tactical_miss:     "Drill: Spot the tactic",
  one_move_blunder:  "Drill: Piece safety check",
  calculation_error: "Drill: One move deeper",
  time_collapse:     "Drill: Clock discipline",
  opening_disaster:  "Drill: Opening fundamentals",
  endgame_collapse:  "Drill: Endgame technique",
  positional:        "Drill: Quiet improvements",
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
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all"); // all | unreviewed | losses | coach | week
  // Intelligence cards — each shows only when the user has real data. Fetched
  // in parallel with the main Lab data so the page isn't blocked.
  const [trapIntel, setTrapIntel] = useState(null);
  const [openingReport, setOpeningReport] = useState(null);
  const [repeatMistakes, setRepeatMistakes] = useState(null);
  const [graduation, setGraduation] = useState(null);
  const [peerMoves, setPeerMoves] = useState(null);
  const [openingBenchmark, setOpeningBenchmark] = useState(null);

  useEffect(() => {
    fetchData();
    fetchTrapIntel();
    fetchOpeningReport();
    fetchRepeatMistakes();
    fetchGraduation();
    fetchPeerMoves();
    fetchOpeningBenchmark();
  }, []);

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

  const fetchPeerMoves = async () => {
    try {
      const res = await fetch(`${API}/coach/peer-moves`, { credentials: "include" });
      if (res.ok) setPeerMoves(await res.json());
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
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center h-[60vh]">
          <div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
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
              className="px-6 py-3 text-sm font-semibold rounded-xl bg-violet-500 hover:bg-violet-400 text-white transition-colors inline-flex items-center justify-center gap-2"
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
  // No cross-game aggregation claims until we build the aggregator (P3+).
  const reasoningLines = [];
  if (featuredGame?.was_winning) {
    reasoningLines.push({
      at: "Earlier",
      note: "You were winning this one.",
    });
  }
  if (featuredGame?.critical_move) {
    reasoningLines.push({
      at: `Move ${featuredGame.critical_move}`,
      note:
        featuredGame.critical_best
          ? `The crucial moment — best was ${featuredGame.critical_best}.`
          : "This is where the game turned.",
    });
  }
  if (featuredGame?.was_winning && !featuredGame?.coach_take) {
    reasoningLines.push({
      at: "Outcome",
      note: "And then it slipped.",
    });
  }
  if (featuredGame?.coach_take) {
    reasoningLines.push({
      at: "The lesson",
      note: featuredGame.coach_take,
    });
  }

  const practicePattern =
    activeFocus?.gap ||
    PATTERN_MAP[primaryProblem?.category] ||
    primaryProblem?.category ||
    "current";

  return (
    <Layout user={user}>
      <div
        className="min-h-screen text-foreground"
        data-testid="lab-page"
      >
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="max-w-[1040px] mx-auto px-6 md:px-10 py-10 md:py-16"
        >
          {/* ─── Page head ─── */}
          <div className="flex items-baseline justify-between mb-10 md:mb-14">
            <div>
              <p className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-3">
                The Lab
              </p>
              <h1 className="font-serif text-[28px] md:text-[40px] leading-[1.05] tracking-[-0.02em] font-medium text-foreground">
                Review room
              </h1>
            </div>
            <p className="text-[11px] md:text-[12px] text-muted-foreground shrink-0 text-right max-w-[220px]">
              {primaryProblem && FOCUS_LABEL[primaryProblem.category] ? (
                <>
                  <span className="uppercase tracking-[0.18em] text-[10px] text-muted-foreground/80">
                    One pattern costing you games
                  </span>
                  <br />
                  <span className="text-foreground/80">
                    {FOCUS_LABEL[primaryProblem.category]}
                  </span>
                </>
              ) : (
                <span className="tabular-nums">{games.length} games</span>
              )}
            </p>
          </div>

          {/* ━━━━━━━━━━ COACH'S PICK ━━━━━━━━━━ */}
          {featuredGame && (
            <section className="mb-16 md:mb-24">
              <div className="text-[10.5px] uppercase tracking-[0.22em] text-violet-500 dark:text-violet-300/80 font-semibold mb-5">
                Coach's Pick · most educational
              </div>

              <div className="grid grid-cols-1 md:grid-cols-[auto_1fr] gap-8 md:gap-12 items-start">
                {/* Mini board */}
                <div className="w-full md:w-[240px] shrink-0">
                  {featuredGame.critical_fen ? (
                    <div className="rounded-xl overflow-hidden ring-1 ring-border">
                      <LichessBoard
                        fen={featuredGame.critical_fen}
                        viewOnly={true}
                        width={240}
                      />
                    </div>
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
                          `/game/${featuredGame.game_id}${
                            featuredGame.critical_move
                              ? `?move=${featuredGame.critical_move}`
                              : ""
                          }`
                        )
                      }
                      className="h-11 px-6 rounded-xl bg-violet-500 hover:bg-violet-400 text-white font-medium text-[14px] transition-colors inline-flex items-center gap-2"
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
                    {primaryProblem && (
                      <button
                        onClick={() =>
                          navigate(
                            `/training/prescribed?weakness=${practicePattern}`
                          )
                        }
                        className="ml-auto text-[12.5px] text-muted-foreground hover:text-foreground transition-colors inline-flex items-center gap-1.5"
                      >
                        <Target
                          className="h-3.5 w-3.5"
                          strokeWidth={1.75}
                        />
                        {CTA_LABEL[primaryProblem.category] || "Drill: fix this"}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </section>
          )}

          {/* ━━━━━━━━━━ TRAP INTELLIGENCE ━━━━━━━━━━ */}
          {/* Shows only when the user has actually hit an opening trap in
              their games. Headline + specific move count + CTA to targeted
              training. Nothing fabricated — if has_data is false the card
              never mounts. */}
          {trapIntel?.has_data && trapIntel.top_insight && (
            <section className="mb-16 md:mb-24">
              <div className="text-[10.5px] uppercase tracking-[0.22em] text-amber-600 dark:text-amber-300/80 font-semibold mb-5">
                Trap intelligence
              </div>
              <div className="rounded-xl border border-amber-500/20 bg-amber-500/[0.04] p-6 md:p-7">
                <p className="font-serif text-[19px] md:text-[22px] leading-[1.3] tracking-[-0.01em] text-foreground/90 mb-3">
                  {trapIntel.top_insight.headline}
                </p>
                <p className="text-[13px] text-muted-foreground mb-5">
                  {trapIntel.top_insight.sprung > 0 ? (
                    <>
                      The trap line actually played out in{" "}
                      <span className="text-foreground/80 font-medium">
                        {trapIntel.top_insight.sprung} of {trapIntel.top_insight.encounters}
                      </span>
                      .
                    </>
                  ) : (
                    <>
                      The trap line didn't play out in any of them — but the setup came up{" "}
                      <span className="text-foreground/80 font-medium">
                        {trapIntel.top_insight.encounters}{" "}
                        {trapIntel.top_insight.encounters === 1 ? "time" : "times"}
                      </span>
                      .
                    </>
                  )}
                </p>
                {trapIntel.all_insights.length > 1 && (
                  <p className="text-[11.5px] text-muted-foreground/80 mb-5">
                    {trapIntel.all_insights.length - 1} other trap{trapIntel.all_insights.length - 1 === 1 ? "" : "s"} in your games too.
                  </p>
                )}
                <button
                  onClick={() =>
                    navigate(
                      `/training/prescribed?weakness=${trapIntel.top_insight.training_weakness}`
                    )
                  }
                  className="h-10 px-5 rounded-lg bg-amber-500/90 hover:bg-amber-500 text-white font-medium text-[13px] transition-colors inline-flex items-center gap-2"
                >
                  <Target className="h-3.5 w-3.5" strokeWidth={1.75} />
                  {trapIntel.top_insight.cta}
                </button>
              </div>
            </section>
          )}

          {/* ━━━━━━━━━━ OPENING REPORT CARD ━━━━━━━━━━ */}
          {/* Surfaces when the user has a losing track record in a
              specific opening. Headline names it; CTA routes to opening
              training. */}
          {openingReport?.has_data && openingReport.problem_opening && (
            <section className="mb-16 md:mb-24">
              <div className="text-[10.5px] uppercase tracking-[0.22em] text-rose-500 dark:text-rose-300/80 font-semibold mb-5">
                Opening report
              </div>
              <div className="rounded-xl border border-rose-500/20 bg-rose-500/[0.04] p-6 md:p-7">
                <p className="font-serif text-[19px] md:text-[22px] leading-[1.3] tracking-[-0.01em] text-foreground/90 mb-3">
                  {openingReport.problem_opening.headline}
                </p>
                <p className="text-[13px] text-muted-foreground mb-5">
                  {openingReport.problem_opening.subline}
                </p>
                <button
                  onClick={() =>
                    navigate(
                      `/training/prescribed?weakness=${openingReport.problem_opening.training_weakness}`
                    )
                  }
                  className="h-10 px-5 rounded-lg bg-rose-500/90 hover:bg-rose-500 text-white font-medium text-[13px] transition-colors inline-flex items-center gap-2"
                >
                  <Target className="h-3.5 w-3.5" strokeWidth={1.75} />
                  Study this opening
                </button>
              </div>
            </section>
          )}

          {/* ━━━━━━━━━━ REPEAT MISTAKE PATTERN ━━━━━━━━━━ */}
          {/* "You've done this in N different games" signal — cross-game
              pattern detection that mirrors what a human coach would
              notice over multiple sessions. */}
          {repeatMistakes?.has_data && repeatMistakes.top_pattern && (
            <section className="mb-16 md:mb-24">
              <div className="text-[10.5px] uppercase tracking-[0.22em] text-violet-500 dark:text-violet-300/80 font-semibold mb-5">
                Pattern across your games
              </div>
              <div className="rounded-xl border border-violet-500/20 bg-violet-500/[0.04] p-6 md:p-7">
                <p className="font-serif text-[19px] md:text-[22px] leading-[1.3] tracking-[-0.01em] text-foreground/90 mb-3">
                  {repeatMistakes.top_pattern.headline}
                </p>
                {repeatMistakes.top_pattern.example_games?.length > 0 && (
                  <p className="text-[13px] text-muted-foreground mb-5">
                    Most recent: Move {repeatMistakes.top_pattern.example_games[0].move_number}{" "}
                    {repeatMistakes.top_pattern.example_games[0].san}
                    {repeatMistakes.top_pattern.example_games.length > 1 && (
                      <> · {repeatMistakes.top_pattern.example_games.length} examples on record</>
                    )}
                  </p>
                )}
                <button
                  onClick={() =>
                    navigate(
                      `/training/prescribed?weakness=${repeatMistakes.top_pattern.training_weakness}`
                    )
                  }
                  className="h-10 px-5 rounded-lg bg-violet-500/90 hover:bg-violet-500 text-white font-medium text-[13px] transition-colors inline-flex items-center gap-2"
                >
                  <Target className="h-3.5 w-3.5" strokeWidth={1.75} />
                  Train this pattern
                </button>
              </div>
            </section>
          )}

          {/* ━━━━━━━━━━ GRADUATION / IMPROVEMENT TRAJECTORY ━━━━━━━━━━ */}
          {/* Celebration (graduate) OR roadmap (struggler). Silent for users
              with <20 games or no improvement data. */}
          {graduation?.has_data && graduation.status === "graduate" && (
            <section className="mb-16 md:mb-24">
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
            </section>
          )}
          {graduation?.has_data && graduation.status === "struggler" && (
            <section className="mb-16 md:mb-24">
              <div className="text-[10.5px] uppercase tracking-[0.22em] text-sky-600 dark:text-sky-300/80 font-semibold mb-5">
                Players who improved
              </div>
              <div className="rounded-xl border border-sky-500/20 bg-sky-500/[0.04] p-6 md:p-7">
                <p className="font-serif text-[19px] md:text-[22px] leading-[1.3] tracking-[-0.01em] text-foreground/90 mb-3">
                  {graduation.headline}
                </p>
                <p className="text-[13px] text-muted-foreground mb-5">
                  {graduation.subline}
                </p>
                {graduation.training_weakness && (
                  <button
                    onClick={() =>
                      navigate(`/training/prescribed?weakness=${graduation.training_weakness}`)
                    }
                    className="h-10 px-5 rounded-lg bg-sky-500/90 hover:bg-sky-500 text-white font-medium text-[13px] transition-colors inline-flex items-center gap-2"
                  >
                    <Target className="h-3.5 w-3.5" strokeWidth={1.75} />
                    Work on {graduation.training_weakness.replace(/_/g, " ")}
                  </button>
                )}
              </div>
            </section>
          )}

          {/* ━━━━━━━━━━ PEER MOVES IN YOUR TOP OPENING ━━━━━━━━━━ */}
          {/* At each move number in your most-played opening, what other
              users tend to play. Teaches by aggregate example. */}
          {peerMoves?.has_data && peerMoves.move_distribution?.length > 0 && (
            <section className="mb-16 md:mb-24">
              <div className="text-[10.5px] uppercase tracking-[0.22em] text-indigo-600 dark:text-indigo-300/80 font-semibold mb-5">
                Peer moves in your top opening
              </div>
              <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/[0.04] p-6 md:p-7">
                <p className="font-serif text-[17px] md:text-[19px] leading-[1.3] tracking-[-0.01em] text-foreground/90 mb-4">
                  {peerMoves.headline}
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-2 font-mono text-[12.5px]">
                  {peerMoves.move_distribution.slice(0, 6).map((m) => (
                    <div key={m.move_number} className="flex items-baseline gap-3">
                      <span className="text-muted-foreground tabular-nums w-[32px]">
                        {m.move_number}.
                      </span>
                      <span className="text-foreground/80">
                        {m.choices
                          .map((c) => `${c.san} (${c.pct}%)`)
                          .join(" · ")}
                      </span>
                    </div>
                  ))}
                </div>
                <p className="text-[11px] text-muted-foreground mt-4">
                  Across {peerMoves.peer_count} other users who played this setup.
                </p>
              </div>
            </section>
          )}

          {/* ━━━━━━━━━━ OPENING-KNOWLEDGE BAND BENCHMARK ━━━━━━━━━━ */}
          {/* The only cognitive_gap with a real cross-band signal. Only shows
              when the user is meaningfully above their band's average. */}
          {openingBenchmark?.has_data && (
            <section className="mb-16 md:mb-24">
              <div className="text-[10.5px] uppercase tracking-[0.22em] text-orange-600 dark:text-orange-300/80 font-semibold mb-5">
                Benchmark vs your rating band
              </div>
              <div className="rounded-xl border border-orange-500/20 bg-orange-500/[0.04] p-6 md:p-7">
                <p className="font-serif text-[19px] md:text-[22px] leading-[1.3] tracking-[-0.01em] text-foreground/90 mb-3">
                  {openingBenchmark.headline}
                </p>
                <p className="text-[13px] text-muted-foreground mb-5">
                  {openingBenchmark.subline}
                </p>
                <button
                  onClick={() =>
                    navigate(`/training/prescribed?weakness=${openingBenchmark.training_weakness}`)
                  }
                  className="h-10 px-5 rounded-lg bg-orange-500/90 hover:bg-orange-500 text-white font-medium text-[13px] transition-colors inline-flex items-center gap-2"
                >
                  <Target className="h-3.5 w-3.5" strokeWidth={1.75} />
                  Study your openings
                </button>
              </div>
            </section>
          )}

          {/* ━━━━━━━━━━ ARCHIVE ━━━━━━━━━━ */}
          <section id="lab-archive">
            <div className="flex items-baseline justify-between mb-5">
              <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold">
                Archive
              </div>
              <button
                onClick={() => navigate("/games")}
                className="flex items-center gap-2 text-[12px] text-muted-foreground/70 hover:text-foreground transition-colors"
              >
                <Search className="h-3.5 w-3.5" strokeWidth={1.75} />
                <span>All games</span>
              </button>
            </div>

            {/* Filters */}
            <div className="flex items-center gap-5 md:gap-6 mb-6 pb-4 border-b border-border/60 overflow-x-auto">
              {FILTERS.map((f) => (
                <button
                  key={f.key}
                  onClick={() => setFilter(f.key)}
                  className={`text-[12.5px] transition-colors whitespace-nowrap ${
                    filter === f.key
                      ? "text-foreground font-medium"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>

            {/* Table */}
            <div className="space-y-0">
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
                    <div
                      key={g.game_id || g._id}
                      onClick={() => navigate(`/game/${g.game_id}`)}
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
                    </div>
                  );
                })
              )}
            </div>

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
        </motion.div>
      </div>
    </Layout>
  );
};

export default Dashboard;
