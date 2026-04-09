/**
 * CoachTimelinePanel — Historical coaching moments.
 *
 * NOT a live stream. NOT a chat.
 * Shows committed key moments only.
 *
 * Rules:
 *   - No auto-scroll during active hold
 *   - Collapse low-severity items by default
 *   - Highlight critical moments
 *   - Stable order (newest at bottom)
 */

import { useState } from "react";
import { AlertTriangle, TrendingDown, Check, ChevronDown, ChevronRight } from "lucide-react";

const SEVERITY_CONFIG = {
  high: { icon: AlertTriangle, color: "text-red-500", bg: "bg-red-50", border: "border-red-200" },
  medium: { icon: TrendingDown, color: "text-amber-500", bg: "bg-amber-50", border: "border-amber-200" },
  low: { icon: Check, color: "text-emerald-500", bg: "bg-emerald-50", border: "border-emerald-200" },
};

const CoachTimelinePanel = ({ timeline = [] }) => {
  const [expanded, setExpanded] = useState(false);

  if (timeline.length === 0) return null;

  // Split: critical/medium vs low
  const important = timeline.filter(t => t.severity !== "low");
  const minor = timeline.filter(t => t.severity === "low");

  return (
    <div className="space-y-2">
      <p className="text-[10px] uppercase tracking-widest font-bold text-muted-foreground/40 px-1">
        This game
      </p>

      {/* Important moments — always visible */}
      {important.map((item) => (
        <TimelineItem key={item.id} item={item} />
      ))}

      {/* Minor moments — collapsed */}
      {minor.length > 0 && (
        <div>
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1 text-[10px] text-muted-foreground/40 hover:text-muted-foreground transition-colors px-1"
          >
            {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            {minor.length} quiet moment{minor.length !== 1 ? "s" : ""}
          </button>
          {expanded && (
            <div className="space-y-1 mt-1">
              {minor.map((item) => (
                <TimelineItem key={item.id} item={item} compact />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const TimelineItem = ({ item, compact = false }) => {
  const config = SEVERITY_CONFIG[item.severity] || SEVERITY_CONFIG.medium;
  const Icon = config.icon;

  if (compact) {
    return (
      <div className="flex items-center gap-2 px-2 py-1 text-[11px] text-muted-foreground">
        <Icon className={`w-3 h-3 ${config.color} opacity-50`} />
        <span className="font-mono text-muted-foreground/50">{item.moveSan}</span>
        <span className="truncate">{item.text}</span>
      </div>
    );
  }

  return (
    <div className={`px-3 py-2 rounded-lg border ${config.border} ${config.bg}`}>
      <div className="flex items-center gap-2 mb-0.5">
        <Icon className={`w-3 h-3 ${config.color}`} strokeWidth={2.5} />
        <span className="font-mono text-xs font-bold text-foreground">{item.moveSan}</span>
      </div>
      <p className="text-xs text-foreground/80 leading-snug">{item.text}</p>
    </div>
  );
};

export default CoachTimelinePanel;
