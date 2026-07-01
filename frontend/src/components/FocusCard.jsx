/**
 * FocusCard — the "Your focus this week" card on HomePage.
 *
 * Consumes GET /api/coach/active-focus. Renders nothing if no focus is
 * assigned to the user (either they haven't hit the 10-game minimum yet
 * or the picker didn't find enough signal).
 *
 * Design principles:
 *   - ONE thing. Not a list. The whole point of the Primary Weakness Picker
 *     is to remove decision fatigue — surface the one locked pattern.
 *   - Days-remaining counter creates a soft commitment / urgency.
 *   - Baseline metric grounds the coaching in real numbers from the user's data.
 *   - CTA leads to /coach/moments/<topic> — the guaranteed backing page.
 */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import { ArrowRight, Target } from "lucide-react";

const WINE = "#722F37";

const FocusCard = () => {
  const navigate = useNavigate();
  const [focus, setFocus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/coach/active-focus`, { credentials: "include" })
      .then(r => r.ok ? r.json() : { has_focus: false })
      .then(d => { if (!cancelled) setFocus(d); })
      .catch(() => { if (!cancelled) setFocus({ has_focus: false }); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  // Silent if no focus (new user, not enough games, or picker found nothing)
  if (loading || !focus || !focus.has_focus) return null;

  const daysLeft = focus.days_remaining ?? 14;
  const baseline = focus.baseline_metric?.value;
  const currentMetric = focus.current_metric?.value;
  const evidence = focus.picker_evidence_count;

  return (
    <motion.section
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="mb-14 md:mb-16"
    >
      <div className="text-[10.5px] uppercase tracking-[0.22em] font-semibold mb-5" style={{ color: WINE }}>
        Your focus · {daysLeft} day{daysLeft === 1 ? "" : "s"} left
      </div>

      <div
        className="rounded-xl overflow-hidden border border-amber-100 dark:border-amber-900/40"
        style={{ background: `linear-gradient(135deg, ${WINE}12 0%, ${WINE}05 100%)` }}
      >
        <div className="p-6 md:p-7">
          <div className="flex items-start gap-4 mb-4">
            <div
              className="p-2.5 rounded-lg flex-shrink-0"
              style={{ background: `${WINE}20`, color: WINE }}
            >
              <Target className="w-5 h-5" />
            </div>
            <div className="flex-1">
              <h2 className="font-serif text-[24px] md:text-[28px] leading-tight tracking-[-0.01em] font-medium text-foreground mb-1.5">
                {focus.topic_label}
              </h2>
              <p className="text-[13.5px] text-muted-foreground leading-relaxed">
                Locked as your focus for the next {daysLeft} day{daysLeft === 1 ? "" : "s"}.
                One habit. One thing. Everything else fades.
              </p>
            </div>
          </div>

          {/* Baseline / current metric */}
          {baseline !== undefined && baseline !== null && (
            <div className="grid grid-cols-2 gap-6 py-4 my-4 border-y border-amber-100/70 dark:border-amber-900/40">
              <div>
                <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground mb-1">
                  Baseline
                </div>
                <div className="font-serif text-[22px] font-medium text-foreground">
                  {baseline.toFixed(2)}
                  <span className="text-[12px] text-muted-foreground font-sans ml-1.5">/ game</span>
                </div>
                {evidence && (
                  <div className="text-[11px] text-muted-foreground mt-1">
                    {evidence.toLocaleString()} moments observed
                  </div>
                )}
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground mb-1">
                  Now
                </div>
                {currentMetric !== undefined && currentMetric !== null ? (
                  <>
                    <div className="font-serif text-[22px] font-medium text-foreground">
                      {currentMetric.toFixed(2)}
                      <span className="text-[12px] text-muted-foreground font-sans ml-1.5">/ game</span>
                    </div>
                    <div className={"text-[11px] mt-1 " + (currentMetric < baseline ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground")}>
                      {currentMetric < baseline
                        ? `${Math.round(100 * (1 - currentMetric / baseline))}% improved`
                        : "checking back later"}
                    </div>
                  </>
                ) : (
                  <>
                    <div className="font-serif text-[22px] font-medium text-muted-foreground">—</div>
                    <div className="text-[11px] text-muted-foreground mt-1">
                      measured at day 14
                    </div>
                  </>
                )}
              </div>
            </div>
          )}

          <motion.button
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.99 }}
            onClick={() => navigate(`/coach/moments/${focus.moments_page_topic || "piece_safety"}`)}
            className="w-full mt-2 rounded-lg py-3 px-4 flex items-center justify-center gap-2 text-white text-[14px] font-medium transition-all"
            style={{ background: WINE }}
          >
            See 3 specific moments from your games
            <ArrowRight className="w-4 h-4" />
          </motion.button>

          {/* Runners-up (softly surfaced) */}
          {focus.runners_up && focus.runners_up.length > 0 && (
            <div className="mt-5 pt-4 border-t border-amber-100/50 dark:border-amber-900/30">
              <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground mb-2">
                Also in your play (not the focus this week)
              </div>
              <div className="flex flex-wrap gap-2">
                {focus.runners_up.slice(0, 3).map((r) => (
                  <span
                    key={r.topic}
                    className="text-[11px] px-2.5 py-1 rounded-full bg-muted/50 text-muted-foreground"
                    title={`${r.evidence_count} occurrences`}
                  >
                    {r.topic.replace(/_/g, " ")}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </motion.section>
  );
};

export default FocusCard;
