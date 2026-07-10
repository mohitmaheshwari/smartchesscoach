/**
 * CoachingPrescriptions — Main component for prescription management
 *
 * Displays:
 * 1. Active prescriptions with progress tracking
 * 2. Next coach recommendation (if no active plans or space for parallel)
 * 3. Loading/error/empty states
 *
 * Design: Mobile-first responsive, uses shadcn/ui components
 */

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { API } from "@/App";
import { fadeInUp, staggerContainer, staggerItem, MOTION_TIMING } from "@/lib/motion";
import PrescriptionCard from "./PrescriptionCard";
import NextRecommendation from "./NextRecommendation";
import { AlertCircle, Zap } from "lucide-react";

const CoachingPrescriptions = () => {
  const [prescriptions, setPrescriptions] = useState([]);
  const [nextRec, setNextRec] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeCount, setActiveCount] = useState(0);

  useEffect(() => {
    let cancelled = false;

    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);

        // Fetch current prescriptions
        const presRes = await fetch(`${API}/coaching/current-prescriptions`, {
          credentials: "include",
        });

        let presData = { current_prescriptions: [] };
        if (presRes.ok) {
          presData = await presRes.json();
        }

        // Fetch next recommendation
        const recRes = await fetch(`${API}/coaching/next-prescription`, {
          credentials: "include",
        });

        let recData = null;
        if (recRes.ok) {
          recData = await recRes.json();
        }

        if (!cancelled) {
          setPrescriptions(presData.current_prescriptions || []);
          setNextRec(recData);
          setActiveCount(presData.total_active || 0);
        }
      } catch (e) {
        console.error("Error fetching coaching prescriptions:", e);
        if (!cancelled) {
          setError("Unable to load coaching prescriptions. Please try again.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    fetchData();
    return () => {
      cancelled = true;
    };
  }, []);

  // ─── Loading State ───────────────────────────────────────────────────
  if (loading) {
    return (
      <motion.section
        variants={fadeInUp}
        className="mb-16 md:mb-20"
      >
        <div className="space-y-4">
          <div className="h-8 bg-muted rounded-lg w-32 animate-pulse" />
          <div className="h-24 bg-muted rounded-lg animate-pulse" />
          <div className="h-24 bg-muted rounded-lg animate-pulse" />
        </div>
      </motion.section>
    );
  }

  // ─── Error State ─────────────────────────────────────────────────────
  if (error) {
    return (
      <motion.section
        variants={fadeInUp}
        className="mb-16 md:mb-20"
      >
        <div className="rounded-lg border border-red-200 dark:border-red-900/40 bg-red-50 dark:bg-red-950/20 p-4 md:p-5">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="font-medium text-red-900 dark:text-red-200 text-sm">
                Error loading prescriptions
              </h3>
              <p className="text-[12.5px] text-red-800 dark:text-red-300 mt-1">
                {error}
              </p>
            </div>
          </div>
        </div>
      </motion.section>
    );
  }

  // ─── Empty State ─────────────────────────────────────────────────────
  if (prescriptions.length === 0 && !nextRec) {
    return (
      <motion.section
        variants={fadeInUp}
        className="mb-16 md:mb-20"
      >
        <div className="rounded-lg border border-border/60 bg-muted/30 p-8 md:p-10 text-center">
          <Zap className="h-8 w-8 text-muted-foreground/50 mx-auto mb-3" />
          <p className="text-[14px] text-muted-foreground mb-1">
            No active coaching plans yet
          </p>
          <p className="text-[13px] text-muted-foreground/70">
            Play more games and the coach will recommend a personalized training plan
          </p>
        </div>
      </motion.section>
    );
  }

  // ─── Main Render ─────────────────────────────────────────────────────
  return (
    <motion.section
      variants={staggerContainer}
      initial="initial"
      animate="animate"
      className="mb-16 md:mb-20"
    >
      {/* Active Prescriptions */}
      {prescriptions.length > 0 && (
        <div className="mb-12">
          <motion.div variants={fadeInUp}>
            <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-5">
              Active coaching plan{prescriptions.length > 1 ? "s" : ""}
            </div>
          </motion.div>

          <motion.div
            variants={staggerContainer}
            className="space-y-4"
          >
            {prescriptions.map((prescription) => (
              <motion.div key={prescription.prescription_id} variants={staggerItem}>
                <PrescriptionCard
                  prescription={prescription}
                  onUpdate={() => {
                    // Trigger refresh of prescriptions
                    window.location.href = window.location.href;
                  }}
                />
              </motion.div>
            ))}
          </motion.div>
        </div>
      )}

      {/* Next Recommendation */}
      {nextRec && (
        <motion.div variants={fadeInUp}>
          <NextRecommendation
            recommendation={nextRec}
            hasActivePlans={prescriptions.length > 0}
            onAccept={() => {
              // Trigger refresh
              window.location.href = window.location.href;
            }}
          />
        </motion.div>
      )}
    </motion.section>
  );
};

export default CoachingPrescriptions;
