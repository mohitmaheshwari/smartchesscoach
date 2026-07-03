/**
 * FocusResolutionBanner — the day-14 celebration or escalation card.
 *
 * Renders when the user's active focus has resolved. Reads focus.resolution
 * (set by the background focus_outcome_loop in server.py from
 * primary_weakness_picker.check_focus_outcome):
 *   - "improved"  → green celebration banner
 *   - "regressed" → red escalation card with CTA to /play-with-coach
 *   - "stuck"     → amber "extended" nudge
 *
 * Consumes GET /api/coach/active-focus. Renders nothing when no resolution
 * has fired yet.
 */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import { CheckCircle2, AlertTriangle, Clock, ArrowRight } from "lucide-react";

const FocusResolutionBanner = () => {
  const navigate = useNavigate();
  const [focus, setFocus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/coach/active-focus`, { credentials: "include" })
      .then(r => r.ok ? r.json() : {})
      .then(d => { if (!cancelled) setFocus(d); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  if (loading || !focus) return null;

  // The banner fires on the CURRENT metric vs baseline delta from focus_trend
  // (which is live and always fresh), NOT on a stale resolution field on the
  // focus doc. The focus_outcome_loop closes focuses at day 14; between
  // now and then, trend chip is the truth.
  const trend = focus?.focus_trend?.trend;
  const deltaPct = focus?.focus_trend?.delta_pct_vs_baseline;
  const events = focus?.focus_trend?.since_focus_events;
  const games = focus?.focus_trend?.since_focus_games;
  const daysIn = focus?.focus_trend?.days_since_focus_start ?? 0;

  // Only surface when we have real data and it's meaningful. Silence otherwise.
  if (!trend || games === 0 || daysIn < 2) return null;

  if (trend === "improving") {
    return (
      <motion.section
        initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}
        className="mb-6 rounded-xl border border-emerald-200 dark:border-emerald-800/40 p-4"
        style={{ background: "linear-gradient(135deg, #04785712 0%, #04785703 100%)" }}
      >
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg bg-emerald-500/15">
            <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
          </div>
          <div className="flex-1">
            <div className="text-[10.5px] uppercase tracking-[0.22em] font-semibold text-emerald-700 dark:text-emerald-400 mb-1">
              You're improving
            </div>
            <p className="text-[14px] text-foreground leading-relaxed">
              {Math.abs(deltaPct)}% fewer events per game since your focus started — {events} events across {games} games ({daysIn}d). Keep the discipline.
            </p>
          </div>
        </div>
      </motion.section>
    );
  }

  if (trend === "regressing") {
    return (
      <motion.section
        initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}
        className="mb-6 rounded-xl border border-rose-300 dark:border-rose-800/40 p-4"
        style={{ background: "linear-gradient(135deg, #b91c1c12 0%, #b91c1c03 100%)" }}
      >
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg bg-rose-500/15">
            <AlertTriangle className="w-5 h-5 text-rose-600 dark:text-rose-400" />
          </div>
          <div className="flex-1">
            <div className="text-[10.5px] uppercase tracking-[0.22em] font-semibold text-rose-700 dark:text-rose-400 mb-1">
              Going the wrong way
            </div>
            <p className="text-[14px] text-foreground leading-relaxed mb-2.5">
              You're at +{deltaPct}% events per game since your focus started ({events} events across {games} games). Time to slow it down.
            </p>
            <button
              onClick={() => navigate("/play-with-coach")}
              className="inline-flex items-center gap-1.5 text-[13px] font-medium text-rose-700 dark:text-rose-400 hover:underline"
            >
              Play a focus session <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </motion.section>
    );
  }

  // Steady — subtle "week in" nudge only after day 5
  if (trend === "steady" && daysIn >= 5) {
    return (
      <motion.section
        initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}
        className="mb-6 rounded-xl border border-amber-200 dark:border-amber-800/40 p-4"
        style={{ background: "linear-gradient(135deg, #d9770612 0%, #d9770603 100%)" }}
      >
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg bg-amber-500/15">
            <Clock className="w-5 h-5 text-amber-600 dark:text-amber-400" />
          </div>
          <div className="flex-1">
            <div className="text-[10.5px] uppercase tracking-[0.22em] font-semibold text-amber-700 dark:text-amber-400 mb-1">
              Holding steady
            </div>
            <p className="text-[14px] text-foreground leading-relaxed">
              Day {daysIn + 1} of your focus — rate hasn't moved much yet. Play a focused session to shift it.
            </p>
          </div>
        </div>
      </motion.section>
    );
  }

  return null;
};

export default FocusResolutionBanner;
