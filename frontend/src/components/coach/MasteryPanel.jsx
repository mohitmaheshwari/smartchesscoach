/**
 * MasteryPanel — what the user has learned across the Engine 2 skill tree.
 *
 * Pairs with the "ledger" view (UnifiedProgress): that page tracks what
 * you're still working on (weakness patterns); this panel surfaces what
 * you've actually picked up (skills graduated by SkillProgress.is_learned()).
 *
 * Reads GET /api/engine2/mastery-summary which returns the four-state
 * roll-up: learned | learning | stale | unseen.
 */

import { useEffect, useState } from "react";
import { API } from "@/App";
import { Check, RotateCcw, Circle, Loader2 } from "lucide-react";

const KIND_TITLE = {
  endgame: "Endgames",
  mate_pattern: "Mate patterns",
  opening: "Openings",
  trap_set: "Traps",
  concept: "Concepts",
  coached_play: "Coached play",
};

// Render order: knowledge skills first, then craft skills.
const KIND_ORDER = [
  "concept",
  "endgame",
  "mate_pattern",
  "opening",
  "trap_set",
  "coached_play",
];

function StateIcon({ state }) {
  if (state === "learned") {
    return <Check className="h-3.5 w-3.5 text-emerald-500" strokeWidth={2.4} />;
  }
  if (state === "stale") {
    return <RotateCcw className="h-3.5 w-3.5 text-amber-500" strokeWidth={2.2} />;
  }
  if (state === "learning") {
    return <Circle className="h-3 w-3 text-violet-500 fill-violet-500/30" strokeWidth={2} />;
  }
  return <Circle className="h-3 w-3 text-muted-foreground/40" strokeWidth={1.5} />;
}

function meta(record) {
  if (record.state === "learned") {
    const d = record.days_since_learned;
    if (d == null) return "Just learned";
    if (d === 0) return "Learned today";
    if (d === 1) return "Learned yesterday";
    return `Learned ${d} days ago`;
  }
  if (record.state === "stale") {
    const d = record.days_since_learned;
    return d != null
      ? `Review recommended · ${d} days since last clean`
      : "Review recommended";
  }
  if (record.state === "learning") {
    return record.progress_hint || "In progress";
  }
  return "Not started";
}

function SkillRow({ record }) {
  const dimmed = record.state === "unseen";
  return (
    <div
      className={`grid grid-cols-[auto_1fr_auto] gap-3 items-center py-2.5 border-b border-border/30 last:border-b-0 ${
        dimmed ? "opacity-60" : ""
      }`}
    >
      <div className="w-4 flex items-center justify-center">
        <StateIcon state={record.state} />
      </div>
      <div className="min-w-0">
        <div className="font-serif text-[14.5px] text-foreground leading-snug truncate">
          {record.label}
        </div>
        <div className="text-[11px] text-muted-foreground mt-0.5 leading-snug">
          {meta(record)}
        </div>
      </div>
      {record.tier > 0 && (
        <span className="text-[10px] text-muted-foreground/60 font-mono tabular-nums">
          T{record.tier}
        </span>
      )}
    </div>
  );
}

function KindSection({ kind, records }) {
  if (!records || records.length === 0) return null;

  const counts = records.reduce(
    (acc, r) => {
      acc[r.state] = (acc[r.state] || 0) + 1;
      return acc;
    },
    { learned: 0, learning: 0, stale: 0, unseen: 0 }
  );

  const summary = [
    counts.learned && `${counts.learned} learned`,
    counts.learning && `${counts.learning} in progress`,
    counts.stale && `${counts.stale} to review`,
    counts.unseen && `${counts.unseen} to explore`,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="mb-8">
      <div className="flex items-baseline justify-between mb-3">
        <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold">
          {KIND_TITLE[kind] || kind}
        </div>
        <div className="text-[10.5px] text-muted-foreground/70 tabular-nums">
          {summary}
        </div>
      </div>
      <div>
        {records.map((r) => (
          <SkillRow key={r.skill_id} record={r} />
        ))}
      </div>
    </div>
  );
}

export default function MasteryPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API}/engine2/mastery-summary`, {
          credentials: "include",
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (!cancelled) setData(json);
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

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-[12px] text-muted-foreground py-6">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Loading what you've learned…
      </div>
    );
  }

  if (error || !data) {
    return null;
  }

  const { summary, by_kind } = data;
  const hasAnyActivity =
    summary.learned + summary.learning + summary.stale > 0;

  return (
    <section className="mb-16 md:mb-20" data-testid="mastery-panel">
      <div className="flex items-baseline justify-between mb-5 flex-wrap gap-2">
        <div className="text-[10.5px] uppercase tracking-[0.22em] text-emerald-600 dark:text-emerald-400 font-semibold">
          Skills · what you've learned
        </div>
        <div className="text-[11px] text-muted-foreground tabular-nums">
          {summary.learned} of {summary.total_skills} learned
          {summary.stale > 0 && ` · ${summary.stale} due for review`}
        </div>
      </div>

      {!hasAnyActivity ? (
        <div className="rounded-2xl border border-border/40 p-6 text-[13px] text-muted-foreground leading-relaxed">
          You haven't worked through any lessons yet. Open a trap, an
          endgame, or a coached game and the skills you pick up will show
          up here.
        </div>
      ) : (
        <div className="rounded-2xl border border-border/40 bg-gradient-to-b from-emerald-500/[0.02] to-transparent p-6 md:p-7">
          {KIND_ORDER.map((kind) => (
            <KindSection
              key={kind}
              kind={kind}
              records={by_kind[kind] || []}
            />
          ))}
        </div>
      )}
    </section>
  );
}
