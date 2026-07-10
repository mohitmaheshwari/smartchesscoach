/**
 * PrescriptionCard — Individual coaching plan with metrics and progress
 *
 * Displays:
 * - Plan name and cognitive gap
 * - Progress bar (puzzles completed / accuracy)
 * - Baseline vs current metric with improvement percentage
 * - Module completion status
 * - Expected completion date
 * - Action buttons (continue, complete, pause)
 *
 * Design: Shadcn/ui card with smooth animations
 */

import { useState } from "react";
import { motion } from "framer-motion";
import { API } from "@/App";
import { ChevronRight, CheckCircle2, Pause, BarChart3, Calendar } from "lucide-react";
import { cn } from "@/lib/utils";

const COLORS = {
  piece_safety: { bg: "#fef3c7", border: "#fbbf24", text: "#92400e" },
  missed_tactic: { bg: "#e0e7ff", border: "#a78bfa", text: "#3730a3" },
  tactical_oversight: { bg: "#f0fdfa", border: "#2dd4bf", text: "#0d3b35" },
  calculation_depth: { bg: "#fef2f2", border: "#f87171", text: "#7c2d12" },
  king_safety: { bg: "#dcfce7", border: "#4ade80", text: "#15803d" },
  pawn_structure: { bg: "#fef08a", border: "#eab308", text: "#713f12" },
  piece_activity: { bg: "#e9d5ff", border: "#d8b4fe", text: "#581c87" },
  opening_knowledge: { bg: "#cffafe", border: "#06b6d4", text: "#164e63" },
  endgame_technique: { bg: "#fecdd3", border: "#fb7185", text: "#831a27" },
};

const getGapColor = (gap) => {
  return COLORS[gap] || { bg: "#f3f4f6", border: "#d1d5db", text: "#374151" };
};

const PrescriptionCard = ({ prescription, onUpdate }) => {
  const [completing, setCompleting] = useState(false);
  const [pausing, setPausing] = useState(false);
  const [error, setError] = useState(null);

  const gap = prescription.issue_detected || "piece_safety";
  const color = getGapColor(gap);

  // Format dates
  const formatDate = (dateStr) => {
    if (!dateStr) return "";
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
      });
    } catch {
      return "";
    }
  };

  // Calculate progress percentage
  const puzzlesTotal = prescription.puzzles_completed + 50; // Assume ~50 puzzles per module
  const progressPct = Math.min(
    Math.round((prescription.puzzles_completed / puzzlesTotal) * 100),
    100
  );

  // Handle completion
  const handleComplete = async () => {
    try {
      setCompleting(true);
      setError(null);

      const res = await fetch(
        `${API}/coaching/complete-prescription`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            prescription_id: prescription.prescription_id,
          }),
        }
      );

      if (!res.ok) {
        throw new Error("Failed to complete prescription");
      }

      onUpdate?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setCompleting(false);
    }
  };

  // Handle pause
  const handlePause = async () => {
    try {
      setPausing(true);
      setError(null);

      const res = await fetch(
        `${API}/coaching/pause-prescription`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            prescription_id: prescription.prescription_id,
          }),
        }
      );

      if (!res.ok) {
        throw new Error("Failed to pause prescription");
      }

      onUpdate?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setPausing(false);
    }
  };

  // Gap label
  const gapLabel = gap.replace(/_/g, " ");

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="rounded-lg border border-border/60 bg-card overflow-hidden hover:border-border transition-colors"
    >
      {/* Header with plan name and gap badge */}
      <div className="p-5 md:p-6 border-b border-border/60">
        <div className="flex items-start justify-between gap-4 mb-3">
          <div className="flex-1 min-w-0">
            <h3 className="font-serif text-[18px] md:text-[20px] leading-tight text-foreground font-medium truncate">
              {prescription.plan_name}
            </h3>
          </div>
          <div
            className="px-2.5 py-1.5 rounded-md text-[11px] font-medium uppercase tracking-wider whitespace-nowrap flex-shrink-0"
            style={{
              backgroundColor: color.bg,
              color: color.text,
              borderLeft: `3px solid ${color.border}`,
            }}
          >
            {gapLabel}
          </div>
        </div>

        {prescription.reasoning && (
          <p className="text-[13px] text-muted-foreground leading-relaxed">
            {prescription.reasoning}
          </p>
        )}
      </div>

      {/* Progress section */}
      <div className="p-5 md:p-6 border-b border-border/60">
        <div className="mb-4">
          <div className="flex items-baseline justify-between mb-2">
            <span className="text-[12px] uppercase tracking-[0.18em] font-medium text-muted-foreground">
              Progress
            </span>
            <span className="text-[13px] font-medium text-foreground">
              {progressPct}%
            </span>
          </div>
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${progressPct}%` }}
              transition={{ duration: 0.6, ease: "easeOut" }}
              className="h-full bg-violet-500 rounded-full"
            />
          </div>
          <p className="text-[12px] text-muted-foreground mt-2">
            {prescription.puzzles_completed} puzzle{prescription.puzzles_completed !== 1 ? "s" : ""} completed
            {prescription.puzzle_accuracy > 0 && (
              <>
                {" "}
                · {Math.round(prescription.puzzle_accuracy)}% accuracy
              </>
            )}
          </p>
        </div>

        {/* Metrics grid */}
        <div className="grid grid-cols-2 gap-4">
          {prescription.baseline_metric !== undefined &&
            prescription.baseline_metric !== null && (
              <div>
                <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground font-medium mb-1">
                  Baseline
                </div>
                <div className="font-serif text-[18px] font-medium text-foreground">
                  {prescription.baseline_metric.toFixed(2)}
                  <span className="text-[12px] text-muted-foreground font-sans ml-1">
                    /game
                  </span>
                </div>
              </div>
            )}

          {prescription.current_metric !== undefined &&
            prescription.current_metric !== null && (
              <div>
                <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground font-medium mb-1">
                  Current
                </div>
                <div className="font-serif text-[18px] font-medium text-foreground">
                  {prescription.current_metric.toFixed(2)}
                  <span className="text-[12px] text-muted-foreground font-sans ml-1">
                    /game
                  </span>
                </div>

                {prescription.improvement_pct > 0 && (
                  <div className="text-[11px] text-emerald-600 dark:text-emerald-400 mt-1 font-medium">
                    ↓ {prescription.improvement_pct.toFixed(0)}%
                  </div>
                )}
              </div>
            )}
        </div>
      </div>

      {/* Module status and completion date */}
      <div className="p-5 md:p-6 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          {prescription.modules_completed &&
            prescription.modules_completed.length > 0 && (
              <div className="flex items-center gap-2 flex-shrink-0">
                <div className="flex -space-x-1">
                  {[...Array(Math.min(prescription.modules_completed.length, 3))].map(
                    (_, i) => (
                      <div
                        key={i}
                        className="w-5 h-5 rounded-full bg-violet-500/20 border border-violet-500/50 flex items-center justify-center flex-shrink-0"
                      >
                        <CheckCircle2 className="w-3 h-3 text-violet-600 dark:text-violet-400" />
                      </div>
                    )
                  )}
                </div>
                <span className="text-[12px] text-muted-foreground">
                  {prescription.modules_completed.length} module{prescription.modules_completed.length !== 1 ? "s" : ""} done
                </span>
              </div>
            )}

          {prescription.expected_completion_date && (
            <div className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
              <Calendar className="w-3.5 h-3.5 flex-shrink-0" />
              <span>
                Due {formatDate(prescription.expected_completion_date)}
              </span>
            </div>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            disabled={pausing}
            onClick={handlePause}
            className="h-8 px-3 rounded-lg text-[12px] font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-50"
          >
            <Pause className="w-3.5 h-3.5" />
          </button>
          <button
            disabled={completing}
            onClick={handleComplete}
            className="h-8 px-3.5 rounded-lg bg-violet-500 hover:bg-violet-400 text-white text-[12px] font-medium transition-colors disabled:opacity-50 inline-flex items-center gap-1.5"
          >
            Complete
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="px-5 md:px-6 py-3 bg-red-50 dark:bg-red-950/20 border-t border-red-200 dark:border-red-900/40">
          <p className="text-[12px] text-red-700 dark:text-red-300">{error}</p>
        </div>
      )}
    </motion.div>
  );
};

export default PrescriptionCard;
