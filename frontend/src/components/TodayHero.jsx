/**
 * TodayHero — the coach's two-part prescription, editorial variant.
 *
 *   1. PRIMARY hero (what to fix OR, if nothing's broken, what to learn)
 *   2. Optional SECONDARY "Learn next" card (Engine 2, when Engine 1 is primary)
 *
 * Self-contained: fetches /api/today, renders both sections, handles the
 * "not feeling this today" interrupt dialogue.
 *
 * Visual treatment applies `redesign/01_Home.html` spec:
 *   - violet eyebrow + Fraunces-serif headline (40-44px, tracking-tight)
 *   - plain evidence bullets (no chrome)
 *   - left-border italic principle (replaces the old amber rule card)
 *   - violet CTA + ETA tag + "not feeling this today" text link
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
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-6 h-6 border-2 border-violet-400/30 border-t-violet-400 rounded-full animate-spin" />
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

  // Derive the eyebrow label — the design's "TODAY · PIECE SAFETY" pattern.
  const eyebrowParts = ["Today"];
  if (primary.category)
    eyebrowParts.push(primary.category.replace(/_/g, " "));
  else if (primary.label) eyebrowParts.push(primary.label);
  const eyebrow = eyebrowParts.join(" · ").toUpperCase();

  return (
    <>
      {/* ─────────── PRIMARY HERO ─────────── */}
      <motion.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        data-testid="today-hero"
      >
        {/* Violet eyebrow */}
        <div className="text-[10.5px] uppercase tracking-[0.22em] text-violet-500 dark:text-violet-300/80 font-semibold mb-5">
          {eyebrow}
        </div>

        {/* Fraunces-serif headline — the coach's voice */}
        <h1 className="font-serif text-[32px] md:text-[44px] leading-[1.06] tracking-[-0.02em] font-medium text-foreground max-w-[720px]">
          {primary.headline}
        </h1>

        {/* Evidence bullets — plain paragraphs, no card */}
        {primary.evidence?.length > 0 && (
          <div className="mt-6 md:mt-7 space-y-1.5 text-[13.5px] md:text-[14px] text-muted-foreground max-w-[560px]">
            {primary.evidence.map((line, i) => (
              <p key={i} className="leading-relaxed">
                {line}
              </p>
            ))}
          </div>
        )}

        {/* Optional board thumb */}
        {primary.board?.fen && (
          <motion.div
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.15 }}
            className="mt-7 rounded-xl overflow-hidden ring-1 ring-border inline-block"
          >
            <LichessBoard
              fen={primary.board.fen}
              viewOnly={true}
              width={320}
            />
          </motion.div>
        )}

        {/* Principle — violet left-border, italic serif. Replaces the old amber card. */}
        {primary.rule && (
          <div className="mt-8 pl-5 border-l-2 border-violet-400/40 max-w-[560px]">
            <p className="font-serif italic text-[15.5px] md:text-[17px] text-foreground/90 leading-snug">
              {primary.rule}
            </p>
          </div>
        )}

        {/* Streak dots */}
        {primary.streak && primary.streak.results?.length > 0 && (
          <div className="mt-6 flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              {Array.from({ length: primary.streak.total || 5 }).map((_, i) => {
                const r = primary.streak.results[i];
                return (
                  <div
                    key={i}
                    className={`w-2.5 h-2.5 rounded-full border ${
                      r === undefined
                        ? "border-border"
                        : r
                          ? "border-emerald-500 bg-emerald-500"
                          : "border-rose-400 bg-rose-400"
                    }`}
                  />
                );
              })}
            </div>
            <span className="text-[11px] text-muted-foreground">
              {primary.streak.clean}/{primary.streak.target} clean games so far
            </span>
          </div>
        )}

        {/* Primary action row: violet button + ETA + "not feeling this today" */}
        {primary.action && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25 }}
            className="mt-8 md:mt-10 flex flex-wrap items-center gap-4 md:gap-5"
          >
            <button
              onClick={handlePrimary}
              className="h-12 px-6 md:px-7 rounded-xl bg-violet-500 hover:bg-violet-400 text-white font-medium text-[14px] md:text-[15px] transition-colors inline-flex items-center gap-2"
              data-testid="today-primary-action"
            >
              {primary.action.cta}
              <ArrowRight className="h-4 w-4" strokeWidth={2} />
            </button>
            {primary.action.eta && (
              <span className="text-[12px] text-muted-foreground tabular-nums">
                {primary.action.eta}
              </span>
            )}
            {data.alternates?.length > 0 && (
              <button
                onClick={() => setShowInterrupt(true)}
                className="ml-auto text-[12px] text-muted-foreground/70 hover:text-foreground transition-colors"
              >
                not feeling this today
              </button>
            )}
          </motion.div>
        )}
      </motion.section>

      {/* ─────────── SECONDARY: LEARN NEXT ─────────── */}
      {secondary && (
        <motion.section
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.3 }}
          className="mt-12 pt-8 border-t border-border/50"
          data-testid="today-secondary"
        >
          <div className="flex items-center gap-2 mb-3">
            <Sparkles
              className="w-3.5 h-3.5 text-emerald-500/70"
              strokeWidth={2}
            />
            <span className="text-[10.5px] uppercase tracking-[0.22em] text-emerald-600 dark:text-emerald-400/80 font-semibold">
              Learn next
            </span>
            {secondary.tier !== undefined && (
              <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                Tier {secondary.tier}
              </span>
            )}
          </div>

          <p className="font-serif text-[20px] md:text-[22px] leading-snug text-foreground mb-2 tracking-[-0.01em]">
            {secondary.label}
          </p>

          {secondary.reason && (
            <p className="text-[13px] text-muted-foreground leading-relaxed mb-5 max-w-[520px]">
              {secondary.reason}
            </p>
          )}

          {secondary.action && (
            <button
              onClick={handleSecondary}
              className="text-[13px] text-emerald-600 dark:text-emerald-400 hover:underline transition-colors inline-flex items-center gap-1.5"
              data-testid="today-secondary-action"
            >
              {secondary.action.cta}
              <ChevronRight className="w-3.5 h-3.5" strokeWidth={2} />
            </button>
          )}
        </motion.section>
      )}

      {/* Interrupt dialogue */}
      <AnimatePresence>
        {showInterrupt && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setShowInterrupt(false)}
            className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-end sm:items-center justify-center"
          >
            <motion.div
              initial={{ y: 40, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: 40, opacity: 0 }}
              transition={{ duration: 0.22 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full sm:max-w-sm bg-card border border-border rounded-t-2xl sm:rounded-2xl p-6 space-y-5"
            >
              <div className="space-y-1.5">
                <p className="font-serif text-[18px] text-foreground leading-snug">
                  Fair enough. What's on your mind?
                </p>
                <p className="text-[12px] text-muted-foreground">
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
                    <span className="text-[13px] text-foreground">
                      {alt.label}
                    </span>
                    {alt.action !== "dismiss" && (
                      <ChevronRight className="w-3.5 h-3.5 text-muted-foreground/40" />
                    )}
                  </button>
                ))}
              </div>

              <button
                onClick={() => setShowInterrupt(false)}
                className="w-full text-[12px] text-muted-foreground/70 hover:text-foreground transition-colors pt-1"
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
