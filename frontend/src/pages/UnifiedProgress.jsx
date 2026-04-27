/**
 * PROGRESS — The ledger.
 *
 * Implements `redesign/07_Progress.html`:
 *   - Head: eyebrow + Fraunces serif headline + supporting paragraph
 *   - Sparkline (blunders/game over recent period, when data exists)
 *   - Active pattern card (violet, "Currently working on")
 *   - Tracked patterns list ("Also tracking")
 *   - Archived list ("You beat these" — when we have strengths data)
 *
 * All existing data fetches (/progress/real, /progress/narrative,
 * /progress/improvement-proof) are preserved. Navigation to
 * /training/prescribed and /play-with-coach is preserved.
 *
 * Dropped from the previous 1,070-line implementation:
 *   - Standalone "Openings" section (already dedicated /openings page)
 *   - Quick Actions bar (the active-pattern Drill CTA covers this)
 *   - "Next step" card (redundant with active pattern)
 *   - 9 unused sub-components (ThinkingHabits, PhaseAccuracy, AccuracyTrend,
 *     PatternLifecycle, PatternRow, OpeningMastery, FocusCard,
 *     OpeningRepertoire, OpeningColorSection) that were defined but never
 *     rendered in the active return path.
 */

import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import {
  ChevronRight,
  Swords,
  Target,
  Loader2,
  Check,
  ArrowRight,
} from "lucide-react";

// ─── Weakness → training-pattern key (same mapping Home uses) ───────────────

const PATTERN_MAP = {
  tactical_miss: "tactical_oversight",
  one_move_blunder: "piece_safety",
  calculation_error: "calculation_depth",
  threw_winning: "calculation_depth",
  king_safety: "piece_safety",
  opening_disaster: "piece_safety",
  endgame_collapse: "endgame_technique",
};

// Category → design-friendly human label
const CATEGORY_LABEL = {
  tactical_miss: "Tactical awareness",
  one_move_blunder: "Piece safety",
  piece_safety: "Piece safety",
  calculation_error: "Calculation depth",
  calculation_depth: "Calculation depth",
  threw_winning: "Conversion technique",
  king_safety: "King safety",
  opening_disaster: "Opening discipline",
  endgame_collapse: "Endgame technique",
  ignore_threat: "Threat awareness",
  missed_tactic: "Tactical awareness",
  time_collapse: "Time discipline",
  positional: "Positional play",
};

const humanize = (cat) =>
  CATEGORY_LABEL[cat] ||
  (cat || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

// ─── Visual components ──────────────────────────────────────────────────────

function Pips({ streak, target }) {
  return (
    <div className="flex items-center gap-1.5">
      {Array.from({ length: target }).map((_, i) => (
        <span
          key={i}
          className={`h-2 w-6 rounded-full ${
            i < streak
              ? "bg-emerald-500/80 dark:bg-emerald-400/70"
              : i === streak
                ? "bg-muted ring-1 ring-violet-400/40"
                : "bg-muted"
          }`}
        />
      ))}
    </div>
  );
}

function Sparkline({ data }) {
  if (!data || data.length < 3) return null;
  const width = 800;
  const height = 120;
  // Auto-fit range
  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;
  const goal = min + span * 0.15; // goal line: near the best
  const pts = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * width;
      const y = height - ((v - min) / span) * 85 - 20;
      return `${x},${y}`;
    })
    .join(" ");
  const goalY = height - ((goal - min) / span) * 85 - 20;
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      className="w-full h-24"
    >
      <line
        x1="0"
        y1={height - 20}
        x2={width}
        y2={height - 20}
        stroke="currentColor"
        className="text-border"
        strokeWidth="1"
      />
      <line
        x1="0"
        y1={goalY}
        x2={width}
        y2={goalY}
        className="text-muted-foreground/30"
        stroke="currentColor"
        strokeWidth="0.5"
        strokeDasharray="3 4"
      />
      <text
        x={width - 4}
        y={goalY - 3}
        className="fill-muted-foreground font-mono"
        fontSize="9"
        textAnchor="end"
      >
        goal · {goal.toFixed(1)}
      </text>
      <polyline
        points={pts}
        fill="none"
        className="text-emerald-500 dark:text-emerald-400"
        stroke="currentColor"
        strokeWidth="1.6"
      />
    </svg>
  );
}

// ─── Page ───────────────────────────────────────────────────────────────────

const UnifiedProgress = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [progress, setProgress] = useState(null);
  const [narrative, setNarrative] = useState(null);
  const [proof, setProof] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const [progressRes, narrativeRes, proofRes] = await Promise.all([
          fetch(`${API}/progress/real`, { credentials: "include" }),
          fetch(`${API}/progress/narrative`, { credentials: "include" }),
          fetch(`${API}/progress/improvement-proof`, {
            credentials: "include",
          }),
        ]);
        if (progressRes.ok) setProgress(await progressRes.json());
        if (narrativeRes.ok) setNarrative(await narrativeRes.json());
        if (proofRes.ok) setProof(await proofRes.json());
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // ─── Derive the ledger data from existing endpoints ─────────────────
  const derived = useMemo(() => {
    const weaknesses = narrative?.weaknesses || [];
    const strengths = narrative?.strengths || [];
    const primary = proof?.primary_pattern;
    const streaks = proof?.streaks || {};
    const reductionPct = primary?.reduction_pct || 0;

    // Active pattern — the coach's current focus
    const activeWeakness = weaknesses[0];
    const active = activeWeakness
      ? {
          name: humanize(activeWeakness.category),
          desc: activeWeakness.description || "",
          category: activeWeakness.category,
          pattern:
            PATTERN_MAP[activeWeakness.category] ||
            activeWeakness.category ||
            "current",
          streak: Math.min(
            streaks.no_big_mistake_games || streaks.no_blunder_games || 0,
            5
          ),
          target: 5,
          // Decay % — render the improvement-proof reduction_pct when present,
          // otherwise a conservative fallback tied to the clean streak.
          decay:
            reductionPct > 0
              ? Math.min(reductionPct, 95) / 100
              : Math.min(
                  (streaks.no_big_mistake_games || 0) * 0.15,
                  0.6
                ),
          coachLine:
            streaks.no_big_mistake_games >= 3
              ? `${streaks.no_big_mistake_games} clean games — one more and we move on.`
              : primary?.message ||
                "We'll close this chapter once the pattern stays quiet for 5 games.",
        }
      : null;

    // Map a narrative category to the root bucket the backend's
    // improvement_proof_engine groups it under. ONLY entries that map
    // to a real bucket on the backend (see ROOT_PATTERNS in
    // improvement_proof_engine.py). Categories without a real backend
    // home — time_collapse, positional, opening_disaster — are
    // intentionally absent so the row shows "no signal yet" instead
    // of borrowing an unrelated bucket's reduction_pct.
    const CATEGORY_TO_ROOT = {
      // calculation bucket — gaps backend lists explicitly
      tactical_miss: "calculation",
      missed_tactic: "calculation",       // alias of tactical_miss
      calculation_error: "calculation",   // alias of calculation_depth
      calculation_depth: "calculation",
      tactical_oversight: "calculation",
      one_move_blunder: "calculation",
      // threat_awareness bucket
      ignore_threat: "threat_awareness",
      hung_pieces: "threat_awareness",
      piece_safety: "threat_awareness",
      king_safety: "threat_awareness",
      // coordination bucket
      piece_activity: "coordination",
      // endgame bucket
      endgame_collapse: "endgame",
      endgame_technique: "endgame",
      threw_winning: "endgame",
      conversion: "endgame",
    };

    // Build root → reduction_pct lookup from proof.all_patterns.
    const allPatterns = proof?.all_patterns || [];
    const reductionByRoot = {};
    for (const p of allPatterns) {
      if (p.pattern && typeof p.reduction_pct === "number") {
        reductionByRoot[p.pattern] = p.reduction_pct;
      }
    }

    // Tracked patterns — remaining weaknesses. Each one gets a real
    // decay value from the matching root pattern's reduction_pct, OR
    // null when we have nothing meaningful to show (no match, or
    // non-positive reduction). Showing "0%" implied no progress —
    // we'd rather hide the field than mislead.
    const tracked = weaknesses.slice(1).map((w) => {
      const root = CATEGORY_TO_ROOT[w.category];
      const rPct = root ? reductionByRoot[root] : undefined;
      const decayValue =
        typeof rPct === "number" && rPct > 0
          ? Math.min(rPct, 95) / 100
          : null;
      return {
        name: humanize(w.category),
        desc: w.description || "",
        category: w.category,
        pattern: PATTERN_MAP[w.category] || w.category || "current",
        // We don't have per-pattern streaks for non-primary — leave at 0.
        streak: 0,
        target: 5,
        decay: decayValue,
        last: w.last_seen || null,
      };
    });

    // Archived — strengths read as patterns the user has beaten
    const archived = strengths.slice(0, 4).map((s, i) => ({
      name:
        typeof s === "string"
          ? s
          : s.label || humanize(s.category) || "Consistent",
      meta:
        typeof s === "string"
          ? "Clean — keep it that way"
          : s.detail || s.record || "Clean — keep it that way",
      stale: 0.9 - i * 0.08,
    }));

    // Headline — synthesize from active state
    let headline = "You're building your pattern library.";
    let subhead =
      "The coach is watching for consistency. When a weakness stays quiet for 5 games, we archive it and move on.";
    if (active && active.streak >= 3) {
      headline = `You've had ${active.streak} clean games of ${active.name.toLowerCase()} — ${5 - active.streak} more and we close the chapter.`;
      if (reductionPct > 0) {
        subhead = `Your ${active.name.toLowerCase()} mistakes are down ${reductionPct}% from 90 days ago. The coach is watching for a 5-game streak before archiving this weakness and moving to the next.`;
      }
    } else if (active) {
      headline = `${active.name} is the pattern we're breaking right now.`;
      if (reductionPct > 0) {
        subhead = `Already ${reductionPct}% fewer mistakes than 90 days ago. Stay on it — consistency is what closes the chapter.`;
      } else {
        subhead = active.desc || subhead;
      }
    } else if (archived.length > 0) {
      headline = "Clean sheet. The coach has nothing urgent to flag.";
      subhead =
        "Keep playing — the next weakness will surface when it's ready.";
    }

    // Sparkline — use any time-series on proof if it exists
    const spark =
      proof?.by_week ||
      proof?.blunder_trend ||
      proof?.trend ||
      null;

    return { active, tracked, archived, headline, subhead, spark };
  }, [narrative, proof]);

  // ─── Loading ─────────────────────────────────────────────────────────
  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center h-[60vh]">
          <Loader2 className="w-6 h-6 text-violet-500 animate-spin" />
        </div>
      </Layout>
    );
  }

  const state = progress?.state || "not_started";

  // New user — no data at all
  if (state === "not_started" && !derived.active && derived.tracked.length === 0) {
    return (
      <Layout user={user}>
        <div
          className="max-w-[640px] mx-auto px-6 md:px-10 py-16 md:py-24"
          data-testid="progress-page"
        >
          <p className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-4">
            Progress · the ledger
          </p>
          <h1 className="font-serif text-[32px] md:text-[40px] leading-[1.06] tracking-[-0.02em] font-medium text-foreground mb-4">
            Nothing to track yet.
          </h1>
          <p className="text-[13.5px] text-muted-foreground mb-10 max-w-[480px] leading-relaxed">
            Play a few games with the coach — once we've seen enough, your
            weaknesses and the pattern-decay ledger start filling in.
          </p>
          <button
            onClick={() => navigate("/play-with-coach")}
            className="h-11 px-6 rounded-xl bg-violet-500 hover:bg-violet-400 text-white font-medium text-[14px] transition-colors inline-flex items-center gap-2"
          >
            <Swords className="h-4 w-4" strokeWidth={2} />
            Play with Coach
            <ArrowRight className="h-4 w-4" strokeWidth={2} />
          </button>
        </div>
      </Layout>
    );
  }

  // ─── Main render ─────────────────────────────────────────────────────
  return (
    <Layout user={user}>
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="max-w-[920px] mx-auto px-6 md:px-10 py-10 md:py-16"
        data-testid="progress-page"
      >
        {/* ─── Page head ─── */}
        <div className="mb-12 md:mb-16">
          <p className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-4">
            Progress · the ledger
          </p>
          <h1 className="font-serif text-[28px] md:text-[44px] leading-[1.06] tracking-[-0.02em] font-medium text-foreground max-w-[640px]">
            {derived.headline}
          </h1>
          <p className="mt-5 text-[13.5px] text-muted-foreground leading-relaxed max-w-[520px]">
            {derived.subhead}
          </p>
        </div>

        {/* ─── Sparkline — only when we have real data ─── */}
        {derived.spark && derived.spark.length >= 3 && (
          <section className="mb-16 md:mb-20">
            <div className="flex items-baseline justify-between mb-4">
              <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold">
                Blunders per game · recent window
              </div>
              <div className="text-[11px] text-muted-foreground tabular-nums">
                {derived.spark[0]?.toFixed(1)} →{" "}
                {derived.spark[derived.spark.length - 1]?.toFixed(1)}
              </div>
            </div>
            <Sparkline data={derived.spark} />
            <div className="mt-3 flex justify-between text-[10px] text-muted-foreground font-mono">
              <span>start</span>
              <span>·</span>
              <span>today</span>
            </div>
          </section>
        )}

        {/* ─── Active pattern ─── */}
        {derived.active && (
          <section className="mb-12">
            <div className="text-[10.5px] uppercase tracking-[0.22em] text-violet-500 dark:text-violet-300 font-semibold mb-5">
              Currently working on
            </div>
            <div className="rounded-2xl border border-violet-400/25 bg-gradient-to-b from-violet-500/[0.04] to-transparent p-6 md:p-7">
              <div className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-6 md:gap-8 items-start">
                <div>
                  <h2 className="font-serif text-[22px] md:text-[26px] leading-[1.2] tracking-[-0.015em] font-medium text-foreground mb-2">
                    {derived.active.name}
                  </h2>
                  {derived.active.desc && (
                    <p className="text-[13px] text-muted-foreground leading-relaxed max-w-[440px]">
                      {derived.active.desc}
                    </p>
                  )}
                  <div className="mt-6 flex items-center gap-3 flex-wrap">
                    <Pips
                      streak={derived.active.streak}
                      target={derived.active.target}
                    />
                    <span className="text-[11.5px] text-muted-foreground tabular-nums">
                      {derived.active.streak} / {derived.active.target} clean games
                    </span>
                  </div>
                  {derived.active.coachLine && (
                    <p className="mt-5 font-serif italic text-[14px] text-foreground/80 leading-snug max-w-[420px]">
                      "{derived.active.coachLine}"
                    </p>
                  )}
                </div>
                <div className="flex md:flex-col items-start md:items-end gap-4 justify-between md:justify-start">
                  <button
                    onClick={() =>
                      navigate(
                        `/training/prescribed?weakness=${derived.active.pattern}`
                      )
                    }
                    className="h-10 px-5 rounded-xl bg-violet-500 hover:bg-violet-400 text-white font-medium text-[13px] transition-colors inline-flex items-center gap-2"
                  >
                    <Target className="h-3.5 w-3.5" strokeWidth={2} />
                    Drill this pattern
                  </button>
                  {derived.active.decay > 0 && (
                    <div className="md:text-right">
                      <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold">
                        Decay
                      </div>
                      <div className="font-serif text-[20px] md:text-[22px] tabular-nums text-foreground leading-none mt-1.5">
                        {Math.round(derived.active.decay * 100)}%
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </section>
        )}

        {/* ─── Tracked patterns ─── */}
        {derived.tracked.length > 0 && (
          <section className="mb-16 md:mb-20">
            <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-5">
              Also tracking
            </div>
            <div>
              {derived.tracked.map((p, i) => (
                <div
                  key={i}
                  className="group grid grid-cols-[1fr_auto] md:grid-cols-[1fr_180px_110px_80px] gap-4 md:gap-8 items-center py-4 md:py-5 border-b border-border/50 hover:bg-muted/20 -mx-3 px-3 transition-colors"
                >
                  {/* Name + desc */}
                  <div className="min-w-0">
                    <div className="flex items-baseline gap-3 flex-wrap">
                      <span className="font-serif text-[16px] md:text-[18px] text-foreground leading-snug">
                        {p.name}
                      </span>
                      {p.last && (
                        <span className="text-[10.5px] text-muted-foreground tabular-nums">
                          last miss · {p.last}
                        </span>
                      )}
                    </div>
                    {p.desc && (
                      <div className="text-[12px] text-muted-foreground mt-1 leading-relaxed">
                        {p.desc}
                      </div>
                    )}
                  </div>

                  {/* Pips (desktop) */}
                  <div className="hidden md:block">
                    <Pips streak={p.streak} target={p.target} />
                    <div className="text-[10.5px] text-muted-foreground mt-1.5 tabular-nums">
                      {p.streak} / {p.target} clean
                    </div>
                  </div>

                  {/* Decay % (desktop) — only render when we have a
                      real positive reduction from improvement_proof for
                      this pattern's root bucket. Showing "0%" was
                      misleading: it implied no progress when really we
                      just hadn't computed it for tracked patterns. */}
                  <div className="hidden md:block text-right">
                    {p.decay != null ? (
                      <>
                        <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold">
                          decay
                        </div>
                        <div className="font-serif text-[17px] tabular-nums text-muted-foreground leading-none mt-1">
                          {Math.round(p.decay * 100)}%
                        </div>
                      </>
                    ) : (
                      <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground/50">
                        no signal yet
                      </div>
                    )}
                  </div>

                  {/* Drill action */}
                  <button
                    onClick={() =>
                      navigate(`/training/prescribed?weakness=${p.pattern}`)
                    }
                    className="text-[11.5px] text-muted-foreground hover:text-violet-500 dark:hover:text-violet-300 transition-colors text-right"
                  >
                    Drill →
                  </button>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* ─── Archived — you beat these ─── */}
        {derived.archived.length > 0 && (
          <section>
            <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground/70 font-semibold mb-5">
              Archived · you've been consistent at
            </div>
            <div className="opacity-70">
              {derived.archived.map((a, i) => (
                <div
                  key={i}
                  className="py-3 md:py-4 border-b border-border/40 grid grid-cols-[auto_1fr_auto] gap-4 md:gap-6 items-center"
                >
                  <Check
                    className="h-3.5 w-3.5 text-emerald-500/80"
                    strokeWidth={2}
                  />
                  <div>
                    <div className="font-serif text-[15px] md:text-[16px] text-foreground/80">
                      {a.name}
                    </div>
                    <div className="text-[11px] text-muted-foreground/70 mt-0.5">
                      {a.meta}
                    </div>
                  </div>
                  <span className="text-[10.5px] text-muted-foreground/60 font-mono tabular-nums">
                    stable
                  </span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* ─── Empty-patterns fallback ─── */}
        {!derived.active && derived.tracked.length === 0 && (
          <div className="py-12 text-[13.5px] text-muted-foreground">
            The coach is still building your profile. Keep playing — the
            ledger fills in as patterns stabilize.
          </div>
        )}
      </motion.div>
    </Layout>
  );
};

export default UnifiedProgress;
