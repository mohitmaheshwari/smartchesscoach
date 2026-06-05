/**
 * InGameMasteryPanel — what the PWC Mastery Gate considers mastered.
 *
 * Built 2026-06-05 per docs/mastery_panel_data_source_swap_scope.md.
 *
 * Sibling to MasteryPanel.jsx. Renders /coach/concepts/mastery-detail
 * (user_concept_understanding + gate verdict) in three tiers:
 *
 *   - MASTERED    coach stays quiet on these  (emerald, like
 *                                              MasteryPanel's "studied")
 *   - SLIPPING    coach gives a quick reminder (amber, like "stale")
 *   - LEARNING    coach gives full guidance    (violet, like "learning")
 *
 * Per-tier collapse: top 5 by clean_games_total desc, "Show all" expands.
 * Hides entirely when total rows == 0 (Q2 LOCKED 2026-06-05).
 * No hard row cap in V1 (Q3 LOCKED).
 * No /concepts/all linkout (Q4 LOCKED).
 *
 * Concept-id → human label via /coach/principles-catalog. Unknown IDs
 * (anything not in the catalog) fall back to a title-cased version of
 * the ID, so the panel never renders raw `TAC_*` strings.
 */

import { useEffect, useMemo, useState } from "react";
import { API } from "@/App";
import { Check, RotateCcw, Circle, Loader2 } from "lucide-react";

const TIER_ORDER = ["mastered", "slipping", "learning"];

const TIER_META = {
  mastered: {
    title: "Mastered",
    subtitle: "Coach stays quiet on these",
    color: "text-emerald-600 dark:text-emerald-400",
    icon: (
      <Check className="h-3.5 w-3.5 text-emerald-500" strokeWidth={2.4} />
    ),
  },
  slipping: {
    title: "Slipping",
    subtitle: "Coach gives a quick reminder",
    color: "text-amber-600 dark:text-amber-400",
    icon: (
      <RotateCcw className="h-3.5 w-3.5 text-amber-500" strokeWidth={2.2} />
    ),
  },
  learning: {
    title: "Still learning",
    subtitle: "Coach gives full guidance",
    color: "text-violet-500 dark:text-violet-300",
    icon: (
      <Circle
        className="h-3 w-3 text-violet-500 fill-violet-500/30"
        strokeWidth={2}
      />
    ),
  },
};

const TIER_COLLAPSE_LIMIT = 5;

function titleCase(id) {
  return (id || "")
    .replace(/^(TAC|OP|MID|END|DEF|STR)_/, "")
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function metaLine(row) {
  const clean = row.clean_games_total ?? 0;
  const violations = row.violations_total ?? 0;
  if (row.mastery_state === "mastered") {
    return `${clean} clean game${clean === 1 ? "" : "s"} · ${violations} slip${violations === 1 ? "" : "s"}`;
  }
  if (row.mastery_state === "slipping") {
    return `Was mastered · slipped recently`;
  }
  return `${violations} violation${violations === 1 ? "" : "s"} in your games`;
}

function ConceptRow({ row, label }) {
  const tier = TIER_META[row.mastery_state] || TIER_META.learning;
  return (
    <div className="flex items-center gap-3 py-2.5 border-b border-border/30 last:border-b-0">
      <span className="shrink-0">{tier.icon}</span>
      <div className="flex-1 min-w-0">
        <div className="text-[13.5px] text-foreground/90 truncate">{label}</div>
        <div className="text-[11px] text-muted-foreground tabular-nums mt-0.5">
          {metaLine(row)}
        </div>
      </div>
    </div>
  );
}

function TierGroup({ tier, rows, labelFor }) {
  const [expanded, setExpanded] = useState(false);
  if (!rows.length) return null;
  const meta = TIER_META[tier];
  const hidden = Math.max(0, rows.length - TIER_COLLAPSE_LIMIT);
  const visible = expanded ? rows : rows.slice(0, TIER_COLLAPSE_LIMIT);
  return (
    <div className="mb-6 last:mb-0">
      <div className="flex items-baseline justify-between mb-2">
        <div
          className={`text-[10.5px] uppercase tracking-[0.22em] font-semibold ${meta.color}`}
        >
          {meta.title} — {meta.subtitle.toLowerCase()}
        </div>
        <div className="text-[11px] text-muted-foreground tabular-nums">
          {rows.length}
        </div>
      </div>
      <div>
        {visible.map((row) => (
          <ConceptRow key={row.concept_id} row={row} label={labelFor(row)} />
        ))}
      </div>
      {hidden > 0 && (
        <button
          onClick={() => setExpanded((v) => !v)}
          className="mt-2 text-[11.5px] text-muted-foreground hover:text-foreground transition-colors"
          data-testid={`mastery-tier-toggle-${tier}`}
        >
          {expanded ? "Show fewer" : `Show all ${rows.length}`}
        </button>
      )}
    </div>
  );
}

export default function InGameMasteryPanel() {
  const [data, setData] = useState(null);
  const [catalog, setCatalog] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [detailRes, catalogRes] = await Promise.all([
          fetch(`${API}/coach/concepts/mastery-detail`, {
            credentials: "include",
          }),
          fetch(`${API}/coach/principles-catalog`),
        ]);
        if (!detailRes.ok) throw new Error(`HTTP ${detailRes.status}`);
        const detailJson = await detailRes.json();
        const catalogJson = catalogRes.ok ? await catalogRes.json() : { principles: [] };
        if (cancelled) return;
        setData(detailJson);
        const map = {};
        for (const p of catalogJson.principles || []) {
          map[p.id] = p.name;
        }
        setCatalog(map);
      } catch (e) {
        if (!cancelled) setError(e.message || "Failed to load");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const rowsByTier = useMemo(() => {
    const out = { mastered: [], slipping: [], learning: [] };
    for (const row of data?.concepts || []) {
      // Drop unseen — would be noise in V1
      if (!TIER_ORDER.includes(row.mastery_state)) continue;
      out[row.mastery_state].push(row);
    }
    for (const tier of TIER_ORDER) {
      out[tier].sort(
        (a, b) => (b.clean_games_total || 0) - (a.clean_games_total || 0),
      );
    }
    return out;
  }, [data]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-[12px] text-muted-foreground py-6">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Loading what the coach knows…
      </div>
    );
  }

  if (error || !data) return null;

  // Q2 LOCKED: HIDE the section entirely when there are no rows.
  const total = (rowsByTier.mastered.length
    + rowsByTier.slipping.length
    + rowsByTier.learning.length);
  if (total === 0) return null;

  const labelFor = (row) => catalog[row.concept_id] || titleCase(row.concept_id);

  const summary = data.summary || {};

  return (
    <section
      className="mb-16 md:mb-20"
      data-testid="in-game-mastery-panel"
    >
      <div className="flex items-baseline justify-between mb-5 flex-wrap gap-2">
        <div className="text-[10.5px] uppercase tracking-[0.22em] text-emerald-600 dark:text-emerald-400 font-semibold">
          In-game concept mastery
        </div>
        <div className="text-[11px] text-muted-foreground tabular-nums">
          {summary.mastered ?? rowsByTier.mastered.length} mastered
          {(summary.slipping ?? rowsByTier.slipping.length) > 0
            && ` · ${summary.slipping ?? rowsByTier.slipping.length} slipping`}
        </div>
      </div>

      <div className="rounded-2xl border border-border/40 bg-gradient-to-b from-emerald-500/[0.02] to-transparent p-6 md:p-7">
        {TIER_ORDER.map((tier) => (
          <TierGroup
            key={tier}
            tier={tier}
            rows={rowsByTier[tier]}
            labelFor={labelFor}
          />
        ))}
      </div>
    </section>
  );
}
