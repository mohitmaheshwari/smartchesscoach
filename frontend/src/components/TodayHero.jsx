/**
 * TodayHero — the coach's single-voice prescription.
 *
 * Self-contained: does its own fetch from /api/today and renders:
 *   greeting → headline → evidence → board → rule → streak dots → action → "not feeling this today"
 *
 * Used as the hero section of HomePage and as the whole body of /today
 * (the URL route aliases HomePage for backwards compatibility).
 *
 * Design principles:
 *   - The coach speaks in sentences, not labels.
 *   - Evidence is always visible when we have it.
 *   - One primary action button. Everything else is subtext.
 *   - "not feeling this today" is a conversation, not a library.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { API } from "@/App";
import LichessBoard from "@/components/LichessBoard";
import { ChevronRight, ArrowRight } from "lucide-react";


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

  const handlePrimary = () => {
    if (data.action?.href) navigate(data.action.href);
  };

  const handleAlternate = (alt) => {
    setShowInterrupt(false);
    if (alt.action === "dismiss") return;
    if (alt.href) navigate(alt.href);
  };

  return (
    <>
      <motion.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="space-y-8"
        data-testid="today-hero"
      >
        {/* Tiny section label — premium tailored feel */}
        <div className="flex items-center gap-2">
          <span className="text-[10px] uppercase tracking-[0.2em] font-bold text-primary/60">
            Today's focus
          </span>
        </div>

        {/* Greeting — conversational, not a title */}
        <p className="text-sm text-muted-foreground font-light -mt-6">{data.greeting}</p>

        {/* The ONE headline — the coach's voice */}
        <h1 className="text-[26px] leading-[1.25] font-heading font-medium text-foreground tracking-tight">
          {data.headline}
        </h1>

        {/* Evidence — specific, countable */}
        {data.evidence?.length > 0 && (
          <div className="space-y-1.5">
            {data.evidence.map((line, i) => (
              <p key={i} className="text-[13px] text-muted-foreground leading-relaxed">
                {line}
              </p>
            ))}
          </div>
        )}

        {/* The board — concrete */}
        {data.board?.fen && (
          <motion.div
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.15 }}
            className="rounded-xl overflow-hidden border border-border"
          >
            <LichessBoard fen={data.board.fen} viewOnly={true} width={360} />
          </motion.div>
        )}

        {/* Rule — the memorable one-liner */}
        {data.rule && (
          <div className="py-3.5 px-4 rounded-xl bg-amber-500/[0.04] border border-amber-500/10">
            <p className="text-[13px] text-foreground font-medium leading-snug">{data.rule}</p>
          </div>
        )}

        {/* Streak — only if meaningful progress */}
        {data.streak && data.streak.results?.length > 0 && (
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              {Array.from({ length: data.streak.total || 5 }).map((_, i) => {
                const r = data.streak.results[i];
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
              {data.streak.clean}/{data.streak.target} clean games so far
            </span>
          </div>
        )}

        {/* THE action — one verb, one button */}
        {data.action && (
          <motion.button
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25 }}
            onClick={handlePrimary}
            className="w-full py-4 px-6 text-[15px] font-semibold rounded-xl bg-foreground text-background hover:opacity-90 transition-all flex items-center justify-center gap-2.5 shadow-sm"
            data-testid="today-primary-action"
          >
            {data.action.cta}
            <ArrowRight className="w-4 h-4" strokeWidth={2.25} />
          </motion.button>
        )}

        {/* "Not feeling this" — subtle, conversational */}
        {data.alternates?.length > 0 && (
          <div className="text-center pt-1">
            <button
              onClick={() => setShowInterrupt(true)}
              className="text-[12px] text-muted-foreground/60 hover:text-muted-foreground transition-colors"
            >
              not feeling this today
            </button>
          </div>
        )}
      </motion.section>

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
