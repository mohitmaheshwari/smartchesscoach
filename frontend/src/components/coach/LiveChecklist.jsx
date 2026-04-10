/**
 * LiveChecklist — Chess Fundamentals Progress Tracker
 *
 * Renders progress-based fundamentals:
 *   NOT_STARTED → grey
 *   IN_PROGRESS → yellow/amber
 *   COMPLETED → green
 *   FAILED → red
 *
 * Shows phase-filtered fundamentals with progress bars and coach reasons.
 * Plus player profile (strengths/weaknesses/domains).
 */

import { AlertTriangle } from "lucide-react";

const STATUS_CONFIG = {
  NOT_STARTED: {
    color: "text-muted-foreground/50",
    bg: "bg-muted/30",
    border: "border-border/30",
    barColor: "bg-muted-foreground/20",
    label: "Not Started",
  },
  IN_PROGRESS: {
    color: "text-amber-600",
    bg: "bg-amber-500/5",
    border: "border-amber-500/15",
    barColor: "bg-amber-500",
    label: "In Progress",
  },
  COMPLETED: {
    color: "text-emerald-600",
    bg: "bg-emerald-500/5",
    border: "border-emerald-500/15",
    barColor: "bg-emerald-500",
    label: "Complete",
  },
  FAILED: {
    color: "text-red-500",
    bg: "bg-red-500/5",
    border: "border-red-500/15",
    barColor: "bg-red-500",
    label: "Failed",
  },
};

const CATEGORY_ICONS = {
  Opening: "♟",
  Tactical: "⚔",
  Positional: "🧠",
  Endgame: "👑",
};

const DOMAIN_LABELS = {
  tactical_vision: "Tactical Vision",
  calculation_depth: "Calculation",
  positional_sense: "Positional Sense",
  endgame_technique: "Endgame",
  opening_knowledge: "Opening Knowledge",
  pressure_handling: "Under Pressure",
};

const LiveChecklist = ({ checklist, weaknesses, playerProfile, gamePhase, coachNote }) => {
  // checklist is now { phase, fundamentals: [...] }
  const fundamentals = checklist?.fundamentals || [];
  const phase = checklist?.phase || gamePhase;

  // Group by category
  const categories = {};
  for (const f of fundamentals) {
    const cat = f.category || "Other";
    if (!categories[cat]) categories[cat] = [];
    categories[cat].push(f);
  }

  return (
    <div className="space-y-4">
      {/* Phase badge */}
      {phase && (
        <div className="flex items-center gap-2">
          <span className="text-[9px] uppercase tracking-widest font-bold text-muted-foreground/40">
            {phase}
          </span>
        </div>
      )}

      {/* Coach note */}
      {coachNote && (
        <div className="rounded-lg px-3 py-2.5 border bg-muted/40 border-border/40">
          <p className="text-sm text-foreground leading-snug">{coachNote}</p>
        </div>
      )}

      {/* Fundamentals by category */}
      {Object.entries(categories).map(([cat, items]) => (
        <div key={cat}>
          <p className="text-[10px] uppercase tracking-widest font-bold text-muted-foreground/50 mb-2">
            {CATEGORY_ICONS[cat] || "📋"} {cat}
          </p>
          <div className="space-y-1">
            {items.map((f, i) => (
              <FundamentalRow key={i} fundamental={f} />
            ))}
          </div>
        </div>
      ))}

      {/* Player Weaknesses */}
      {weaknesses && weaknesses.length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-widest font-bold text-muted-foreground/50 mb-2">
            Focus Areas
          </p>
          <div className="space-y-1">
            {weaknesses.map((w, i) => (
              <div
                key={i}
                className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-red-500/5 border border-red-500/10"
              >
                <AlertTriangle className="w-3 h-3 text-amber-400 flex-shrink-0" strokeWidth={2} />
                <span className="text-xs text-foreground flex-1">{w.label}</span>
                <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-medium ${
                  w.severity === "high" ? "bg-red-500/10 text-red-500" : "bg-amber-500/10 text-amber-600"
                }`}>
                  {w.severity}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Player Profile moved to Progress page */}
    </div>
  );
};

const FundamentalRow = ({ fundamental }) => {
  const { name, status, progress, reason } = fundamental;
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.NOT_STARTED;

  return (
    <div className={`rounded-lg border ${config.bg} ${config.border} px-2.5 py-2 transition-all duration-200`}>
      <div className="flex items-center justify-between mb-1">
        <span className={`text-xs font-medium ${config.color}`}>{name}</span>
        <span className={`text-[9px] ${config.color} opacity-70`}>{progress}%</span>
      </div>
      {/* Progress bar */}
      <div className="h-1 bg-muted/50 rounded-full overflow-hidden mb-1.5">
        <div
          className={`h-full rounded-full transition-all duration-500 ${config.barColor}`}
          style={{ width: `${progress}%` }}
        />
      </div>
      {/* Coach reason */}
      <p className="text-[11px] text-muted-foreground leading-snug">{reason}</p>
    </div>
  );
};

export default LiveChecklist;
