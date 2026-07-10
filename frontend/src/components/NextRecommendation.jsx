/**
 * NextRecommendation — Coach's recommendation for next focus area
 *
 * Displays:
 * - Recommended plan with reasoning
 * - Issue severity and occurrence count
 * - Up to 3 alternative plans
 * - Action buttons: Accept, Choose Alternative, Add as Parallel
 * - Evidence and trend information
 *
 * Design: Shadcn/ui card with interactive elements
 */

import { useState } from "react";
import { motion } from "framer-motion";
import { API } from "@/App";
import {
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Zap,
  ChevronRight,
  CheckCircle2,
  Plus,
} from "lucide-react";
import { cn } from "@/lib/utils";

const URGENCY_STYLES = {
  critical: {
    icon: AlertTriangle,
    color: "text-red-600 dark:text-red-400",
    bg: "bg-red-50 dark:bg-red-950/20",
    badge: "bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-300",
  },
  high: {
    icon: Zap,
    color: "text-orange-600 dark:text-orange-400",
    bg: "bg-orange-50 dark:bg-orange-950/20",
    badge: "bg-orange-100 dark:bg-orange-900/40 text-orange-800 dark:text-orange-300",
  },
  medium: {
    icon: TrendingUp,
    color: "text-amber-600 dark:text-amber-400",
    bg: "bg-amber-50 dark:bg-amber-950/20",
    badge: "bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300",
  },
  low: {
    icon: TrendingDown,
    color: "text-muted-foreground",
    bg: "bg-muted/50",
    badge: "bg-muted text-muted-foreground",
  },
};

const NextRecommendation = ({
  recommendation,
  hasActivePlans = false,
  onAccept = () => {},
}) => {
  const [accepting, setAccepting] = useState(false);
  const [choosingAlt, setChoosingAlt] = useState(false);
  const [addingParallel, setAddingParallel] = useState(false);
  const [selectedAlt, setSelectedAlt] = useState(null);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const urgency = recommendation.urgency || "medium";
  const urgencyStyle = URGENCY_STYLES[urgency];
  const UrgencyIcon = urgencyStyle.icon;

  // Handle accept recommendation
  const handleAccept = async () => {
    try {
      setAccepting(true);
      setError(null);

      // First create prescription from recommendation
      const prescRes = await fetch(
        `${API}/coaching/accept-prescription`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            prescription_id: `rec-${recommendation.recommended_plan_id}`,
            start_immediately: true,
          }),
        }
      );

      if (!prescRes.ok) {
        throw new Error("Failed to accept prescription");
      }

      setSuccess("Prescription activated! Starting your training plan.");
      setTimeout(() => {
        onAccept?.();
      }, 1500);
    } catch (e) {
      setError(e.message);
    } finally {
      setAccepting(false);
    }
  };

  // Handle choose alternative
  const handleChooseAlt = async (altPlan) => {
    try {
      setChoosingAlt(true);
      setError(null);

      const res = await fetch(
        `${API}/coaching/choose-alternative`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            plan_id: altPlan.plan_id,
            reason: "User chose alternative plan",
          }),
        }
      );

      if (!res.ok) {
        throw new Error("Failed to select alternative plan");
      }

      setSuccess(
        `Great choice! "${altPlan.name}" added to your coaching plan.`
      );
      setTimeout(() => {
        onAccept?.();
      }, 1500);
    } catch (e) {
      setError(e.message);
    } finally {
      setChoosingAlt(false);
    }
  };

  // Handle add parallel plan
  const handleAddParallel = async () => {
    try {
      setAddingParallel(true);
      setError(null);

      const res = await fetch(
        `${API}/coaching/add-parallel-plan`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            plan_id: recommendation.recommended_plan_id,
            reason: "Added as parallel training focus",
            max_concurrent_plans: 2,
          }),
        }
      );

      if (!res.ok) {
        throw new Error("Failed to add parallel plan");
      }

      setSuccess(
        `"${recommendation.plan_name}" added as secondary focus. Balance your training.`
      );
      setTimeout(() => {
        onAccept?.();
      }, 1500);
    } catch (e) {
      setError(e.message);
    } finally {
      setAddingParallel(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={cn(
        "rounded-lg border overflow-hidden transition-colors",
        success
          ? "border-emerald-200 dark:border-emerald-900/40 bg-emerald-50 dark:bg-emerald-950/20"
          : `border-border/60 ${urgencyStyle.bg}`
      )}
    >
      {/* Header */}
      <div className="p-5 md:p-6 border-b border-border/60">
        <div className="flex items-start gap-3 mb-3">
          <div className={cn("p-2 rounded-lg flex-shrink-0", urgencyStyle.bg)}>
            <UrgencyIcon className={cn("w-5 h-5", urgencyStyle.color)} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-baseline gap-2 mb-1 flex-wrap">
              <h3 className="text-[14px] font-semibold uppercase tracking-[0.15em] text-muted-foreground">
                Coach's recommendation
              </h3>
              <span
                className={cn(
                  "px-2 py-0.5 rounded text-[10px] font-medium uppercase tracking-wider",
                  urgencyStyle.badge
                )}
              >
                {urgency} priority
              </span>
            </div>

            {success && (
              <p className="text-[14px] text-emerald-700 dark:text-emerald-300 leading-relaxed">
                {success}
              </p>
            )}

            {!success && (
              <>
                <p className="font-serif text-[22px] md:text-[26px] leading-tight text-foreground font-medium mb-2">
                  {recommendation.plan_name}
                </p>
                <p className="text-[13.5px] text-foreground/80 leading-relaxed max-w-[500px]">
                  {recommendation.reasoning}
                </p>
              </>
            )}
          </div>
        </div>

        {/* Evidence row */}
        {!success && (
          <div className="flex flex-wrap items-center gap-4 text-[12px] text-muted-foreground">
            <div className="flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5" />
              <span>
                {recommendation.occurrence_count || 0} occurrence
                {recommendation.occurrence_count !== 1 ? "s" : ""}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              {recommendation.trend === "increasing" ? (
                <>
                  <TrendingUp className="w-3.5 h-3.5 text-orange-500" />
                  <span>Trending up</span>
                </>
              ) : (
                <>
                  <TrendingDown className="w-3.5 h-3.5 text-emerald-500" />
                  <span>Stable</span>
                </>
              )}
            </div>
            <div className="hidden sm:flex items-center gap-1.5">
              <span>
                {recommendation.duration_weeks} week
                {recommendation.duration_weeks !== 1 ? "s" : ""}
              </span>
            </div>
          </div>
        )}
      </div>

      {!success && (
        <>
          {/* Alternatives section */}
          {recommendation.alternatives &&
            recommendation.alternatives.length > 0 && (
              <div className="px-5 md:px-6 py-4 border-b border-border/60">
                <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground font-medium mb-3">
                  Or choose one of these
                </p>
                <div className="space-y-2">
                  {recommendation.alternatives.map((alt) => (
                    <motion.button
                      key={alt.plan_id}
                      whileHover={{ x: 2 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={() => handleChooseAlt(alt)}
                      disabled={choosingAlt}
                      className="w-full text-left p-3 rounded-lg border border-border/40 hover:border-border hover:bg-muted/50 transition-colors disabled:opacity-50"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-[13px] text-foreground mb-0.5">
                            {alt.name}
                          </p>
                          <p className="text-[11px] text-muted-foreground">
                            Focus: {alt.cognitive_gap.replace(/_/g, " ")}
                          </p>
                        </div>
                        <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0 mt-0.5" />
                      </div>
                    </motion.button>
                  ))}
                </div>
              </div>
            )}

          {/* Action buttons */}
          <div className="p-5 md:p-6 flex flex-col sm:flex-row gap-3">
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={handleAccept}
              disabled={accepting}
              className="flex-1 h-10 px-4 rounded-lg bg-violet-500 hover:bg-violet-400 text-white font-medium text-[13px] transition-colors disabled:opacity-50 inline-flex items-center justify-center gap-2"
            >
              <CheckCircle2 className="w-4 h-4" />
              Accept This Plan
            </motion.button>

            {/* Show parallel option only if user can add more plans */}
            {hasActivePlans && recommendation.can_add_parallel && (
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={handleAddParallel}
                disabled={addingParallel}
                className="flex-1 h-10 px-4 rounded-lg border border-border/60 hover:border-border hover:bg-muted text-foreground font-medium text-[13px] transition-colors disabled:opacity-50 inline-flex items-center justify-center gap-2"
              >
                <Plus className="w-4 h-4" />
                Add as Parallel
              </motion.button>
            )}

            {!hasActivePlans && (
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="flex-1 h-10 px-4 rounded-lg border border-border/60 text-muted-foreground font-medium text-[13px] cursor-not-allowed opacity-50"
                disabled
              >
                <Plus className="w-4 h-4 inline mr-2" />
                Add as Parallel (need active plan first)
              </motion.button>
            )}
          </div>

          {/* Error state */}
          {error && (
            <div className="px-5 md:px-6 py-3 bg-red-50 dark:bg-red-950/20 border-t border-red-200 dark:border-red-900/40">
              <p className="text-[12px] text-red-700 dark:text-red-300">
                {error}
              </p>
            </div>
          )}
        </>
      )}
    </motion.div>
  );
};

export default NextRecommendation;
