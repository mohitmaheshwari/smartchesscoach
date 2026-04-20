/**
 * TodayHero — the coach's two-part prescription:
 *   1. PRIMARY hero (what to fix OR, if nothing's broken, what to learn)
 *   2. Optional SECONDARY "Learn next" card (Engine 2, when Engine 1 is primary)
 *
 * Self-contained: fetches /api/today, renders both sections, handles the
 * "not feeling this today" dialogue.
 *
 * Design principles:
 *   - The coach speaks in sentences, not labels.
 *   - Evidence is always visible when we have it.
 *   - Primary action button dominates. Secondary card is smaller.
 *   - "not feeling this today" is a conversation, not a library.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { API } from "@/App";
import LichessBoard from "@/components/LichessBoard";
import { ChevronRight, ArrowRight, Sparkles } from "lucide-react";


export default function TodayHero() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showInterrupt, setShowInterrupt] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API}/today`, { credentials: "include" });
        if (res.ok) setData(await res.json());
      } catch (e) { console.error(e); }
      finally { setLoading(false); }
    })();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="py-16 text-center">
        <p className="text-sm text-muted-foreground">Coach is thinking.</p>
      </div>
    );
  }

  const primary = data.primary || {};
  const secondary = data.secondary;

  const handlePrimary = () => {
    if (primary.action?.href) navigate(primary.action.href);
  };
  const handleSecondary = () => {
    if (secondary?.action?.href) navigate(secondary.action.href);
  };
  const handleAlternate = (alt) => {
    setShowInterrupt(false);
    if (alt.action === "dismiss") return;
    if (alt.href) navigate(alt.href);
  };

  return (
    <>
      {/* ─────────── PRIMARY HERO (Engine 1, or promoted Engine 2) ─────────── */}
      <motion.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="space-y-8"
        data-testid="today-hero"
      >
        <div className="flex items-center gap-2">
          <span className="text-[10px] uppercase tracking-[0.2em] font-bold text-primary/60">
            Today's focus
          </span>
        </div>

        <p className="text-sm text-muted-foreground font-light -mt-6">{data.greeting}</p>

        <h1 className="text-[26px] leading-[1.25] font-heading font-medium text-foreground tracking-tight">
          {primary.headline}
        </h1>

        {primary.evidence?.length > 0 && (
          <div className="space-y-1.5">
            {primary.evidence.map((line, i) => (
              <p key={i} className="text-[13px] text-muted-foreground leading-relaxed">
                {line}
              </p>
            ))}
          </div>
        )}

        {primary.board?.fen && (
          <motion.div
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.15 }}
            className="rounded-xl overflow-hidden border border-border"
          >
            <LichessBoard fen={primary.board.fen} viewOnly={true} width={360} />
          </motion.div>
        )}

        {primary.rule && (
          <div className="py-3.5 px-4 rounded-xl bg-amber-500/[0.04] border border-amber-500/10">
            <p className="text-[13px] text-foreground font-medium leading-snug">{primary.rule}</p>
          </div>
        )}

        {primary.streak && primary.streak.results?.length > 0 && (
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              {Array.from({ length: primary.streak.total || 5 }).map((_, i) => {
                const r = primary.streak.results[i];
                return (
                  <div
                    key={i}
                    className={`w-2.5 h-2.5 rounded-full border ${
                      r === undefined
                        ? "border-border"
                        : r ? "border-emerald-500 bg-emerald-500"
                            : "border-red-400 bg-red-400"
                    }`}
                  />
                );
              })}
            </div>
            <span className="text-[11px] text-muted-foreground font-light">
              {primary.streak.clean}/{primary.streak.target} clean games so far
            </span>
          </div>
        )}

        {primary.action && (
          <motion.button
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25 }}
            onClick={handlePrimary}
            className="w-full py-4 px-6 text-[15px] font-semibold rounded-xl bg-foreground text-background hover:opacity-90 transition-all flex items-center justify-center gap-2.5 shadow-sm"
            data-testid="today-primary-action"
          >
            {primary.action.cta}
            <ArrowRight className="w-4 h-4" strokeWidth={2.25} />
          </motion.button>
        )}
      </motion.section>

      {/* ─────────── SECONDARY: LEARN NEXT (Engine 2, when both engines have picks) ─────────── */}
      {secondary && (
        <motion.section
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.3 }}
          className="mt-8 pt-6 border-t border-border/50"
          data-testid="today-secondary"
        >
          <div className="flex items-center gap-2 mb-3">
            <Sparkles className="w-3.5 h-3.5 text-emerald-500/70" strokeWidth={2} />
            <span className="text-[10px] uppercase tracking-[0.2em] font-bold text-emerald-500/70">
              Learn next
            </span>
            {secondary.tier !== undefined && (
              <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                Tier {secondary.tier}
              </span>
            )}
          </div>

          <p className="text-[15px] font-medium text-foreground mb-1 leading-snug">
            {secondary.label}
          </p>

          {secondary.reason && (
            <p className="text-[12px] text-muted-foreground leading-relaxed mb-3">
              {secondary.reason}
            </p>
          )}

          {secondary.action && (
            <button
              onClick={handleSecondary}
              className="w-full py-3 px-5 text-[13px] font-medium rounded-xl border border-emerald-500/30 bg-emerald-500/[0.03] hover:bg-emerald-500/[0.06] hover:border-emerald-500/50 text-emerald-700 dark:text-emerald-400 transition-all flex items-center justify-center gap-2"
              data-testid="today-secondary-action"
            >
              {secondary.action.cta}
              <ChevronRight className="w-3.5 h-3.5" strokeWidth={2} />
            </button>
          )}
        </motion.section>
      )}

      {/* "Not feeling this" — applies to the primary, always last */}
      {data.alternates?.length > 0 && (
        <div className="text-center pt-6">
          <button
            onClick={() => setShowInterrupt(true)}
            className="text-[12px] text-muted-foreground/60 hover:text-muted-foreground transition-colors"
          >
            not feeling this today
          </button>
        </div>
      )}

      {/* Interrupt dialogue */}
      <AnimatePresence>
        {showInterrupt && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setShowInterrupt(false)}
            className="fixed inset-0 bg-black/30 z-50 flex items-end sm:items-center justify-center"
          >
            <motion.div
              initial={{ y: 40, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: 40, opacity: 0 }}
              transition={{ duration: 0.22 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full sm:max-w-sm bg-card border border-border rounded-t-2xl sm:rounded-2xl p-6 space-y-4"
            >
              <div className="space-y-1.5">
                <p className="text-[15px] text-foreground font-medium leading-snug">
                  Fair enough. What's on your mind?
                </p>
                <p className="text-[12px] text-muted-foreground font-light">
                  I'll pick up where we left off tomorrow.
                </p>
              </div>

              <div className="space-y-2">
                {data.alternates.map((alt, i) => (
                  <button
                    key={i}
                    onClick={() => handleAlternate(alt)}
                    className="w-full text-left py-3 px-4 rounded-xl border border-border hover:border-foreground/20 hover:bg-muted/40 transition-all flex items-center justify-between"
                  >
                    <span className="text-[13px] text-foreground font-light">{alt.label}</span>
                    {alt.action !== "dismiss" && (
                      <ChevronRight className="w-3.5 h-3.5 text-muted-foreground/40" />
                    )}
                  </button>
                ))}
              </div>

              <button
                onClick={() => setShowInterrupt(false)}
                className="w-full text-[12px] text-muted-foreground/60 hover:text-muted-foreground transition-colors pt-1"
              >
                actually, let's keep going
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
