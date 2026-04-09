/**
 * ActiveCoachingCard — Board-adjacent coaching moment.
 *
 * One card. One message. Optional question.
 * Shows during thinking_hold / critical_hold / awaiting_clock_commit.
 *
 * Design:
 *   - Critical: strong border, prominent
 *   - Medium: compact, clear
 *   - Low: subtle banner
 *
 * Message length target: 6-14 words.
 */

import { CLOCK_STATES } from "@/coachFlow/types";
import { Clock, AlertTriangle, TrendingDown, Check, BookOpen } from "lucide-react";

const SEVERITY_STYLES = {
  high: {
    card: "border-red-400 bg-red-50",
    icon: AlertTriangle,
    iconClass: "text-red-500",
    textClass: "text-red-900",
    label: "text-red-500",
  },
  medium: {
    card: "border-amber-300 bg-amber-50",
    icon: TrendingDown,
    iconClass: "text-amber-600",
    textClass: "text-amber-900",
    label: "text-amber-600",
  },
  low: {
    card: "border-emerald-300 bg-emerald-50",
    icon: Check,
    iconClass: "text-emerald-600",
    textClass: "text-emerald-900",
    label: "text-emerald-600",
  },
};

const TYPE_LABELS = {
  critical_interrupt: "Hold",
  pattern_repeat: "Pattern",
  turning_point: "Turning Point",
  reinforcement: "Good",
  opening_principle: "Opening",
  consequence_warning: "Warning",
};

const ActiveCoachingCard = ({ moment, clockState, onClockTap }) => {
  if (!moment) return null;

  const style = SEVERITY_STYLES[moment.severity] || SEVERITY_STYLES.medium;
  const Icon = style.icon;
  const typeLabel = TYPE_LABELS[moment.messageType] || "";

  const isLocked = clockState === CLOCK_STATES.HOLD_LOCKED;
  const isReady = clockState === CLOCK_STATES.HOLD_READY;

  return (
    <div className={`rounded-xl border-2 ${style.card} p-4 shadow-sm`}>
      {/* Header */}
      <div className="flex items-center gap-2 mb-2">
        <Icon className={`w-4 h-4 ${style.iconClass}`} strokeWidth={2.5} />
        <span className={`text-[10px] uppercase tracking-widest font-bold ${style.label}`}>
          {typeLabel}
        </span>
      </div>

      {/* Message */}
      <p className={`text-sm font-medium ${style.textClass} leading-snug`}>
        {moment.text}
      </p>

      {/* Question */}
      {moment.question?.prompt && (
        <p className={`text-xs ${style.textClass} opacity-70 mt-2 italic`}>
          {moment.question.prompt}
        </p>
      )}

      {/* Clock commit indicator */}
      <div className="mt-3 pt-2 border-t border-black/5">
        {isLocked && (
          <p className="text-[11px] text-muted-foreground flex items-center gap-1.5">
            <Clock className="w-3 h-3 animate-pulse" />
            Read the position
          </p>
        )}
        {isReady && (
          <button
            onClick={onClockTap}
            className="w-full py-2 text-xs font-semibold rounded-lg bg-foreground text-background hover:opacity-90 transition-all flex items-center justify-center gap-1.5"
          >
            <Clock className="w-3 h-3" />
            Tap clock to commit
          </button>
        )}
      </div>
    </div>
  );
};

export default ActiveCoachingCard;
