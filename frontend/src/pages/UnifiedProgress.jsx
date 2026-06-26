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
import {
  AnimatedNumber,
  staggerContainer,
  fadeInUp,
  scaleIn,
  rowStaggerContainer,
  rowStaggerItem,
  revealOnScroll,
  ROW_STAGGER_STEP,
  chartDrawTransition,
  GLOW,
  MOTION_TIMING,
} from "@/lib/motion";
import Layout from "@/components/Layout";
import {
  ChevronRight,
  Swords,
  Target,
  Loader2,
  Check,
  ArrowRight,
} from "lucide-react";
import MasteryPanel from "@/components/coach/MasteryPanel";
import InGameMasteryPanel from "@/components/coach/InGameMasteryPanel";

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
  // Progress pips fill left-to-right on viewport entry (scope §Charts:
  // "pattern-card progress bars fill") — 40ms/pip, scaleX from the left.
  return (
    <div className="flex items-center gap-1.5">
      {Array.from({ length: target }).map((_, i) => (
        <motion.span
          key={i}
          initial={{ scaleX: 0, opacity: 0 }}
          whileInView={{ scaleX: 1, opacity: 1 }}
          viewport={{ once: true }}
          transition={{
            duration: MOTION_TIMING.standard.duration / 1000,
            ease: MOTION_TIMING.standard.easing,
            delay: (i * ROW_STAGGER_STEP) / 1000,
          }}
          style={{ originX: 0 }}
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
  const coords = data.map((v, i) => ({
    x: (i / (data.length - 1)) * width,
    y: height - ((v - min) / span) * 85 - 20,
  }));
  const pts = coords.map((c) => `${c.x},${c.y}`).join(" ");
  const last = coords[coords.length - 1];
  const goalY = height - ((goal - min) / span) * 85 - 20;
  // Draw-in: pathLength 0 → 1 over the chart timing (800ms), then the
  // endpoint dot pops in. Timing from motion.js, no inline numbers.
  const drawSeconds = MOTION_TIMING.chart.duration / 1000;
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
      <motion.polyline
        points={pts}
        fill="none"
        className="text-emerald-500 dark:text-emerald-400"
        stroke="currentColor"
        strokeWidth="1.6"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={chartDrawTransition}
      />
      {/* Endpoint dot pops in once the line finishes drawing */}
      <motion.circle
        cx={Math.min(last.x, width - 4)}
        cy={last.y}
        r="3.5"
        className="fill-emerald-500 dark:fill-emerald-400"
        initial={{ opacity: 0, scale: 0 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{
          delay: drawSeconds,
          duration: MOTION_TIMING.micro.duration / 1000,
          ease: MOTION_TIMING.micro.easing,
        }}
        style={{ transformBox: "fill-box", transformOrigin: "center" }}
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
  const [motif, setMotif] = useState(null);
  const [reco, setReco] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const [progressRes, narrativeRes, proofRes, motifRes, recoRes] = await Promise.all([
          fetch(`${API}/progress/real`, { credentials: "include" }),
          fetch(`${API}/progress/narrative`, { credentials: "include" }),
          fetch(`${API}/progress/improvement-proof`, {
            credentials: "include",
          }),
          fetch(`${API}/motif-profile`, { credentials: "include" }),
          fetch(`${API}/motif-recognition`, { credentials: "include" }),
        ]);
        if (progressRes.ok) setProgress(await progressRes.json());
        if (narrativeRes.ok) setNarrative(await narrativeRes.json());
        if (proofRes.ok) setProof(await proofRes.json());
        if (motifRes.ok) setMotif(await motifRes.json());
        if (recoRes.ok) setReco(await recoRes.json());
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

    // Map a narrative category to the root bucket the backend's
    // improvement_proof_engine groups it under. ONLY entries that map
    // to a real bucket on the backend (see ROOT_PATTERNS in
    // improvement_proof_engine.py). Categories without a real backend
    // home are intentionally absent so the row shows "no signal yet"
    // instead of borrowing an unrelated bucket's reduction_pct.
    //
    // Mohit 2026-05-28: time_collapse, threw_winning, tactical_miss
    // had no matching backend bucket — fixed by extending
    // improvement_proof_engine ROOT_PATTERNS with conversion +
    // time_management buckets and rerouting tactical_miss to a real
    // bucket. Mappings below mirror that backend change.
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
      // conversion bucket (new — backed by improvement_proof_engine)
      threw_winning: "conversion",
      conversion: "conversion",
      // time_management bucket (new)
      time_collapse: "time_management",
    };

    // Build root → reduction_pct lookup from proof.all_patterns.
    const allPatterns = proof?.all_patterns || [];
    const reductionByRoot = {};
    for (const p of allPatterns) {
      if (p.pattern && typeof p.reduction_pct === "number") {
        reductionByRoot[p.pattern] = p.reduction_pct;
      }
    }

    // Active pattern — the coach's current focus.
    //
    // Bug fix Mohit 2026-05-28: the active card used to render
    // `proof.primary_pattern.reduction_pct` regardless of whether the
    // active weakness's category matched primary_pattern.pattern. On
    // Mohit's data, active=threw_winning (Conversion technique) but
    // primary=threat_awareness — so the card showed "Decay 44%" for
    // Conversion when 44% belonged to a category that wasn't even in
    // the visible weakness list. Same misattribution drove the
    // subhead "Already 44% fewer mistakes" text.
    //
    // Fix: look up the active weakness's OWN root bucket via
    // CATEGORY_TO_ROOT (same lookup the Tracked rows already use).
    // When no match, fall back to the clean-streak heuristic.
    const activeWeakness = weaknesses[0];
    const activeRoot = activeWeakness
      ? CATEGORY_TO_ROOT[activeWeakness.category]
      : undefined;
    const activeReductionPct =
      activeRoot && typeof reductionByRoot[activeRoot] === "number"
        ? reductionByRoot[activeRoot]
        : 0;

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
          // Decay % — render the category-matched reduction_pct when
          // present, otherwise a conservative fallback tied to the
          // clean streak.
          decay:
            activeReductionPct > 0
              ? Math.min(activeReductionPct, 95) / 100
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

    // Tracked patterns — remaining weaknesses. Each one gets a real
    // decay value from the matching root pattern's reduction_pct, OR
    // null when we have nothing meaningful to show (no match, or
    // non-positive reduction). Showing "0%" implied no progress —
    // we'd rather hide the field than mislead.
    // Mohit 2026-05-29: when improvement_proof has no reduction% for
    // a tracked weakness's bucket, fall back to the recency signal
    // from problem_lifecycle.updated_at (days_since_last_seen). The
    // old behaviour rendered "no signal yet" right next to the
    // description "It's happened 13 times in recent games" — a flat
    // contradiction. The recency label answers a real question users
    // are actually asking ("when did this last bite me?") instead of
    // confessing absence of a metric.
    const recencyLabel = (daysSince) => {
      if (typeof daysSince !== "number") return null;
      if (daysSince <= 1) return "active today";
      if (daysSince <= 3) return `${daysSince}d since last`;
      if (daysSince <= 13) return `quiet · ${daysSince}d`;
      if (daysSince <= 30) return `quiet · ${daysSince}d since last`;
      return `dormant · ${daysSince}d`;
    };

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
        // Per-pattern clean streak — count of analyzed games imported
        // since the pattern last fired (capped at 5 by the backend).
        // Falls back to 0 when the backend can't compute it (no
        // updated_at on the underlying problem_lifecycle doc). Mohit
        // 2026-05-29: time_collapse showed '0 / 5 clean' alongside
        // 'quiet · 24d since last' — flat contradiction. The clean
        // streak is now per-pattern instead of a single global value.
        streak: typeof w.clean_games_since === "number"
          ? Math.min(w.clean_games_since, 5)
          : 0,
        target: 5,
        decay: decayValue,
        // Recency / activity signal used when decay is null.
        recency: recencyLabel(w.days_since_last_seen),
        count: typeof w.count === "number" ? w.count : null,
        last: w.last_seen || null,
      };
    });

    // Archived — strengths read as patterns the user has beaten,
    // PLUS weaknesses that hit the graduation contract (5 clean
    // games or 21+ days quiet). Mohit 2026-05-30: Time discipline
    // was still on "Also tracking" at 5/5 clean + 25d quiet, which
    // contradicted the active card's "we'll close this chapter once
    // it stays quiet for 5 games" copy.
    const archivedWeaknesses = (narrative?.archived_weaknesses || []).map((w) => {
      const days = w.days_since_last_seen;
      const recency = typeof days === "number"
        ? (days <= 1
            ? "quiet — looking solid"
            : days <= 13
              ? `clean for ${days} days`
              : `clean for ${days} days`)
        : "clean streak";
      return {
        name: humanize(w.category),
        meta: `${recency} · was ${w.count} misses before you beat it`,
        stale: 0.95,
        beaten: true,
      };
    });
    const strengthCards = strengths.slice(0, 4).map((s, i) => ({
      name:
        typeof s === "string"
          ? s
          : s.label || humanize(s.category) || "Consistent",
      meta:
        typeof s === "string"
          ? "Clean — keep it that way"
          : s.detail || s.record || "Clean — keep it that way",
      stale: 0.9 - i * 0.08,
      beaten: false,
    }));
    // Beaten weaknesses lead — they're the more recent victories.
    const archived = [...archivedWeaknesses, ...strengthCards];

    // Headline — synthesize from active state.
    // Reads the category-matched activeReductionPct so the message
    // text tracks the actual bucket, not whichever bucket happens to
    // be the global primary.
    let headline = "You're building your pattern library.";
    let subhead =
      "The coach is watching for consistency. When a weakness stays quiet for 5 games, we archive it and move on.";
    if (active && active.streak >= 3) {
      headline = `You've had ${active.streak} clean games of ${active.name.toLowerCase()} — ${5 - active.streak} more and we close the chapter.`;
      if (activeReductionPct > 0) {
        subhead = `Your ${active.name.toLowerCase()} mistakes are down ${activeReductionPct}% from 90 days ago. The coach is watching for a 5-game streak before archiving this weakness and moving to the next.`;
      }
    } else if (active) {
      headline = `${active.name} is the pattern we're breaking right now.`;
      if (activeReductionPct > 0) {
        subhead = `Already ${activeReductionPct}% fewer mistakes than 90 days ago. Stay on it — consistency is what closes the chapter.`;
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

    // Concept shelf — UnifiedProgress v2 enrichment (Formula C locked 2026-06-05).
    // Top concept across all families with most-recent-game metadata so
    // the Active card can show "What you keep doing" + Review-game CTA.
    const conceptShelf = narrative?.concept_shelf || [];
    const topConcept = conceptShelf[0] || null;

    return { active, tracked, archived, headline, subhead, spark, topConcept };
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
        variants={staggerContainer}
        initial="initial"
        animate="animate"
        className="max-w-[920px] mx-auto px-6 md:px-10 py-10 md:py-16"
        data-testid="progress-page"
      >
        {/* ─── Page head ─── */}
        <motion.div variants={fadeInUp} className="mb-12 md:mb-16">
          <p className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-4">
            Progress · the ledger
          </p>
          <h1 className="font-serif text-[28px] md:text-[44px] leading-[1.06] tracking-[-0.02em] font-medium text-foreground max-w-[640px]">
            {derived.headline}
          </h1>
          <p className="mt-5 text-[13.5px] text-muted-foreground leading-relaxed max-w-[520px]">
            {derived.subhead}
          </p>
        </motion.div>

        {/* ─── Tactics mastery ladder: your level + which way you're moving (you vs your past) ─── */}
        {reco && (reco.rows || []).length > 0 && (
          <motion.section variants={fadeInUp} className="mb-14">
            <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-2">
              Your tactics · where you are, where you're heading
            </div>
            <div className="text-[12px] text-muted-foreground mb-5">
              Your level on the path to mastering each tactic — and whether you're climbing.
            </div>
            <div className="space-y-5">
              {(reco.rows || []).map((r) => {
                const t = r.trend || {};
                const trend = {
                  up:     { dot: "bg-emerald-500", label: "Improving lately", icon: "↗", cls: "text-emerald-600 dark:text-emerald-400" },
                  down:   { dot: "bg-amber-500",   label: "Slipped a little",  icon: "↘", cls: "text-amber-600 dark:text-amber-400" },
                  steady: { dot: "bg-sky-500",     label: "Holding steady",    icon: "→", cls: "text-sky-600 dark:text-sky-400" },
                  new:    { dot: "bg-muted-foreground/40", label: "Just getting going", icon: "·", cls: "text-muted-foreground" },
                }[t.dir] || {};
                return (
                  <div key={r.motif} className="rounded-xl border border-border p-5">
                    <div className="flex items-baseline justify-between mb-3">
                      <div className="text-[15px] font-semibold text-foreground">{r.label}</div>
                      <div className={`text-[12px] font-medium inline-flex items-center gap-1 ${trend.cls}`}>
                        <span className="text-[14px] leading-none">{trend.icon}</span> {trend.label}
                      </div>
                    </div>
                    {/* tier ladder */}
                    <div className="flex items-center justify-between mb-1.5">
                      {(r.tiers || []).map((name, i) => (
                        <div
                          key={name}
                          className={`text-[10px] tracking-wide ${
                            i === r.tier_index
                              ? "text-foreground font-semibold"
                              : "text-muted-foreground/50"
                          }`}
                        >
                          {name}
                        </div>
                      ))}
                    </div>
                    <div className="relative h-2.5 rounded-full bg-muted overflow-hidden">
                      <div className={`h-full rounded-full ${trend.dot}`} style={{ width: `${r.fill_pct}%` }} />
                      {/* tier dividers at 20/40/60/80 */}
                      {[20, 40, 60, 80].map((x) => (
                        <div key={x} className="absolute top-0 h-full w-px bg-background/70" style={{ left: `${x}%` }} />
                      ))}
                    </div>
                    <div className="flex items-center justify-between gap-3 mt-2.5">
                      <div className="text-[12.5px] text-muted-foreground">
                        You're at <span className="text-foreground font-medium">{r.tier}</span>
                        {r.next_tier ? <> · next rung: {r.next_tier}</> : <> — top of the ladder.</>}
                        {r.trust === "rough" && <span className="text-[11px] opacity-60"> · rough read</span>}
                        {/* Two-sided truth: overall = weaker of attack/defense, so a motif
                            that keeps catching you can't read "Mastered". */}
                        {r.two_sided_note && (
                          <div className="mt-1.5 text-[12px]">
                            <span className="text-emerald-600 dark:text-emerald-400">Attack: {r.attack?.tier}</span>
                            <span className="opacity-40"> · </span>
                            <span className="text-amber-600 dark:text-amber-400">
                              Defense: {r.defense?.tier ?? "—"}
                              {r.defense?.rate != null ? ` (${r.defense.rate}% seen coming)` : ""}
                            </span>
                            <div className="text-foreground/70 mt-0.5">{r.two_sided_note}</div>
                          </div>
                        )}
                      </div>
                      {r.drill && (
                        <button
                          onClick={() => navigate(`/training/pattern/${r.motif}`)}
                          className="h-8 px-3 rounded-lg bg-violet-500 hover:bg-violet-400 text-white font-medium text-[12px] inline-flex items-center gap-1.5 transition-colors shrink-0"
                        >
                          Drill {r.label.toLowerCase()}
                          <ArrowRight className="h-3 w-3" strokeWidth={2} />
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </motion.section>
        )}

        {/* ─── Tactics profile: patterns you find vs patterns that catch you ─── */}
        {motif && ((motif.strengths || []).length > 0 || (motif.weaknesses || []).length > 0) && (
          <motion.section variants={fadeInUp} className="mb-14">
            <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-5">
              Your tactics · patterns you find vs patterns that catch you
            </div>
            <div className="grid md:grid-cols-2 gap-4">
              <div className="rounded-xl border border-border p-5">
                <div className="text-[11px] uppercase tracking-wide text-emerald-500 dark:text-emerald-400 font-semibold mb-3">
                  You identify easily
                </div>
                {(motif.strengths || []).length ? (
                  (motif.strengths || []).map((s) => (
                    <div key={s.motif} className="mb-3 last:mb-0">
                      <div className="text-[14px] font-medium text-foreground">{s.label} ✓</div>
                      <div className="text-[12.5px] text-muted-foreground leading-relaxed">{s.lesson}</div>
                    </div>
                  ))
                ) : (
                  <div className="text-[12.5px] text-muted-foreground">Keep playing — your strengths will surface here.</div>
                )}
              </div>
              <div className="rounded-xl border border-border p-5">
                <div className="text-[11px] uppercase tracking-wide text-rose-500 dark:text-rose-400 font-semibold mb-3">
                  Patterns giving you trouble
                </div>
                {(motif.weaknesses || []).length ? (
                  (motif.weaknesses || []).map((w) => (
                    <div key={w.motif} className="mb-4 last:mb-0">
                      <div className="text-[14px] font-medium text-foreground">{w.label} — caught {w.got}×</div>
                      <div className="text-[12.5px] text-muted-foreground leading-relaxed mb-2">💡 {w.lesson}</div>
                      {(w.drill_positions?.length || 0) > 0 && (
                        <button
                          onClick={() => navigate(`/training/motif/${w.motif}`)}
                          className="h-9 px-4 rounded-lg bg-rose-500 hover:bg-rose-400 text-white font-medium text-[13px] inline-flex items-center gap-2 transition-colors"
                        >
                          Drill {w.drill_positions?.length || 0} from your games
                          <ArrowRight className="h-3.5 w-3.5" strokeWidth={2} />
                        </button>
                      )}
                    </div>
                  ))
                ) : (
                  <div className="text-[12.5px] text-muted-foreground">No recurring tactical weakness yet — nice.</div>
                )}
              </div>
            </div>
          </motion.section>
        )}

        {/* ─── Sparkline — only when we have real data ─── */}
        {derived.spark && derived.spark.length >= 3 && (
          <motion.section variants={fadeInUp} className="mb-16 md:mb-20">
            <div className="flex items-baseline justify-between mb-4">
              <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold">
                Blunders per game · recent window
              </div>
              <div className="text-[11px] text-muted-foreground tabular-nums">
                {/* Headline numbers count up over the chart timing */}
                <AnimatedNumber value={derived.spark[0]} decimals={1} /> →{" "}
                <AnimatedNumber
                  value={derived.spark[derived.spark.length - 1]}
                  decimals={1}
                />
              </div>
            </div>
            <Sparkline data={derived.spark} />
            <div className="mt-3 flex justify-between text-[10px] text-muted-foreground font-mono">
              <span>start</span>
              <span>·</span>
              <span>today</span>
            </div>
          </motion.section>
        )}

        {/* ─── Active pattern ─── */}
        {derived.active && (
          <motion.section variants={fadeInUp} className="mb-12">
            <div className="text-[10.5px] uppercase tracking-[0.22em] text-violet-500 dark:text-violet-300 font-semibold mb-5">
              Currently working on
            </div>
            {/* Card scales in; hover lifts with a teal data-accent glow */}
            <motion.div
              variants={scaleIn}
              whileHover={{ y: -4, boxShadow: GLOW.teal }}
              transition={{
                duration: MOTION_TIMING.micro.duration / 1000,
                ease: MOTION_TIMING.micro.easing,
              }}
              className="rounded-2xl border border-violet-400/25 bg-gradient-to-b from-violet-500/[0.04] to-transparent p-6 md:p-7"
            >
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

                  {/* ─── V2: What you keep doing (Formula C top concept) ─── */}
                  {derived.topConcept && (
                    <div className="mt-6 pt-5 border-t border-violet-400/15">
                      <div className="text-[10.5px] uppercase tracking-[0.22em] text-violet-500/80 dark:text-violet-300/80 font-semibold mb-2">
                        What you keep doing
                      </div>
                      <p className="text-[14px] text-foreground/90 leading-snug mb-2">
                        {derived.topConcept.headline}
                      </p>
                      <p className="text-[12px] text-muted-foreground">
                        Seen {derived.topConcept.recurrence} times across your recent games
                        {derived.topConcept.most_recent_opponent
                          ? ` — last time vs ${derived.topConcept.most_recent_opponent}`
                          : ""}.
                      </p>
                      {derived.topConcept.most_recent_game_id && (
                        <button
                          onClick={() =>
                            navigate(`/game/${derived.topConcept.most_recent_game_id}`)
                          }
                          data-testid="review-game-cta"
                          className="mt-3 h-9 px-4 rounded-lg bg-violet-500/10 hover:bg-violet-500/20 text-violet-600 dark:text-violet-300 font-medium text-[12.5px] transition-colors inline-flex items-center gap-1.5"
                        >
                          Review the game
                          <ArrowRight className="h-3.5 w-3.5" strokeWidth={2} />
                        </button>
                      )}
                    </div>
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
                        <AnimatedNumber
                          value={Math.round(derived.active.decay * 100)}
                        />
                        %
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          </motion.section>
        )}

        {/* ─── Tracked patterns ─── */}
        {derived.tracked.length > 0 && (
          <motion.section variants={fadeInUp} className="mb-16 md:mb-20">
            <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-5">
              Also tracking
            </div>
            {/* Rows stagger in at the dense-list step (40ms/row) */}
            <motion.div
              variants={rowStaggerContainer}
              initial="initial"
              animate="animate"
            >
              {derived.tracked.map((p, i) => (
                <motion.div
                  key={i}
                  variants={rowStaggerItem}
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
                    ) : p.recency ? (
                      <>
                        <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground/70 font-semibold">
                          recency
                        </div>
                        <div className="text-[12px] tabular-nums text-muted-foreground leading-snug mt-1">
                          {p.recency}
                        </div>
                      </>
                    ) : (
                      <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground/50">
                        tracking
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
                </motion.div>
              ))}
            </motion.div>
          </motion.section>
        )}

        {/* ─── Archived — you beat these (below fold → reveal on scroll) ─── */}
        {derived.archived.length > 0 && (
          <motion.section {...revealOnScroll}>
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
                    {a.beaten ? "beaten" : "stable"}
                  </span>
                </div>
              ))}
            </div>
          </motion.section>
        )}

        {/* ─── Mastery — what you've learned ─── */}
        <MasteryPanel />

        {/* ─── In-game concept mastery — what the PWC gate considers
             mastered, sourced from user_concept_understanding. Sibling
             to MasteryPanel; auto-hides when the user has no rows.
             See docs/mastery_panel_data_source_swap_scope.md. ─── */}
        <InGameMasteryPanel />

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
