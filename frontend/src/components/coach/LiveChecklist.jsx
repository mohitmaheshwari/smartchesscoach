/**
 * LiveChecklist — Behavioral Coaching Panel
 *
 * Shows:
 *   1. ROOT PROBLEM (one dominant, red, prominent)
 *   2. Fundamentals grouped by phase (with progress)
 *   3. Secondary focus areas
 *
 * Root problem = collapsed behavioral cluster, not individual signals.
 * Fundamentals = derived from position + history each move.
 */

import { AlertTriangle, ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";

const STATUS_CONFIG = {
  NOT_STARTED: { color: "text-muted-foreground/50", bg: "bg-muted/20", border: "border-border/20", barColor: "bg-muted-foreground/15" },
  IN_PROGRESS: { color: "text-amber-600", bg: "bg-amber-500/5", border: "border-amber-500/15", barColor: "bg-amber-500" },
  COMPLETED: { color: "text-emerald-600", bg: "bg-emerald-500/5", border: "border-emerald-500/15", barColor: "bg-emerald-500" },
  FAILED: { color: "text-red-500", bg: "bg-red-500/5", border: "border-red-500/15", barColor: "bg-red-500" },
};

const CATEGORY_ICONS = { Opening: "♟", Tactical: "⚔", Positional: "🧠", Endgame: "👑" };

const LiveChecklist = ({ checklist, weaknesses, playerProfile, rootProblem, gamePhase, coachNote }) => {
  const [showMinor, setShowMinor] = useState(false);
  const fundamentals = checklist?.fundamentals || [];
  const phase = checklist?.phase || gamePhase;

  // Group fundamentals by category
  const categories = {};
  for (const f of fundamentals) {
    const cat = f.category || "Other";
    if (!categories[cat]) categories[cat] = [];
    categories[cat].push(f);
  }

  const primary = rootProblem?.primary;
  const secondary = rootProblem?.secondary || [];

  return (
    <div className="space-y-3">

      {/* ─── ROOT PROBLEM (dominant, one only) ─── */}
      {primary && (
        <div className="rounded-xl border-2 border-red-400/30 bg-red-500/[0.04] p-3.5">
          <div className="flex items-center gap-2 mb-1.5">
            <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            <span className="text-[10px] uppercase tracking-widest font-bold text-red-500">
              Main Problem
            </span>
          </div>
          <p className="text-sm font-semibold text-foreground mb-1">
            {primary.label}
          </p>
          <p className="text-xs text-foreground/70 leading-snug">
            {primary.description}
          </p>
          <p className="text-[11px] text-red-500/70 mt-2 italic">
            {primary.coaching}
          </p>
        </div>
      )}

      {/* ─── SECONDARY CLUSTERS ─── */}
      {secondary.length > 0 && (
        <div className="space-y-1">
          {secondary.map((s) => (
            <div key={s.key} className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-amber-500/5 border border-amber-500/10">
              <div className="w-1.5 h-1.5 rounded-full bg-amber-500" />
              <span className="text-xs text-foreground flex-1">{s.label}</span>
              <span className="text-[9px] text-amber-600">{s.description.split(" ").slice(0, 5).join(" ")}...</span>
            </div>
          ))}
        </div>
      )}

      {/* ─── COACH NOTE ─── */}
      {coachNote && (
        <div className="rounded-lg px-3 py-2.5 border bg-muted/40 border-border/40">
          <p className="text-sm text-foreground leading-snug">{coachNote}</p>
        </div>
      )}

      {/* ─── FUNDAMENTALS BY CATEGORY ─── */}
      {Object.entries(categories).map(([cat, items]) => {
        // Separate completed vs in-progress/failed
        const active = items.filter(f => f.status !== "COMPLETED");
        const completed = items.filter(f => f.status === "COMPLETED");

        return (
          <div key={cat}>
            <p className="text-[10px] uppercase tracking-widest font-bold text-muted-foreground/50 mb-1.5">
              {CATEGORY_ICONS[cat] || "📋"} {cat}
            </p>
            <div className="space-y-0.5">
              {/* Show failed/in-progress first (important) */}
              {active.map((f, i) => (
                <FundamentalRow key={i} f={f} />
              ))}
              {/* Completed items — compact */}
              {completed.map((f, i) => (
                <CompletedRow key={i} f={f} />
              ))}
            </div>
          </div>
        );
      })}

      {/* ─── PHASE ─── */}
      {phase && (
        <p className="text-[9px] uppercase tracking-widest text-muted-foreground/30 text-right">
          {phase}
        </p>
      )}
    </div>
  );
};

const FundamentalRow = ({ f }) => {
  const config = STATUS_CONFIG[f.status] || STATUS_CONFIG.NOT_STARTED;

  return (
    <div className={`rounded-lg border ${config.bg} ${config.border} px-2.5 py-2`}>
      <div className="flex items-center justify-between mb-0.5">
        <span className={`text-xs font-medium ${config.color}`}>{f.name}</span>
        <span className={`text-[9px] font-mono ${config.color} opacity-60`}>{f.progress}%</span>
      </div>
      <div className="h-1 bg-muted/40 rounded-full overflow-hidden mb-1">
        <div
          className={`h-full rounded-full transition-all duration-500 ${config.barColor}`}
          style={{ width: `${f.progress}%` }}
        />
      </div>
      <p className="text-[11px] text-muted-foreground leading-snug">{f.reason}</p>
    </div>
  );
};

const CompletedRow = ({ f }) => (
  <div className="flex items-center gap-2 px-2.5 py-1 rounded-lg bg-emerald-500/[0.03]">
    <span className="text-emerald-500 text-[10px]">✓</span>
    <span className="text-xs text-foreground/50">{f.name}</span>
    <span className="text-[9px] text-emerald-500/50 ml-auto">Done</span>
  </div>
);

export default LiveChecklist;
