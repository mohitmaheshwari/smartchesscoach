/**
 * LearnedThisCard.jsx — the emotional-payoff card for the home page.
 *
 * "You learned this" — proof-of-improvement surface. Reads
 * GET /api/coach/learned-this which composes:
 *   - improvement_proof (root patterns, reduction%)
 *   - motif_recognition deltas (fork/pin/skewer/discovered/loose)
 *   - freshly-mastered concepts (last 30 days)
 *
 * Design: silent when there's nothing to say (has_data=false → returns
 * null). When present, it's THE hero of the page — not a footnote.
 *
 * The card celebrates ONE headline win prominently, then lists up to 5
 * supporting wins below. No dashboards, no diagnostic language. This
 * page says "you got better at chess" in numbers you can trust.
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, TrendingUp, Trophy, ArrowRight, Award, ChevronDown } from "lucide-react";
import { API } from "@/App";

const iconFor = (kind) => {
  if (kind === "pattern_reduction") return TrendingUp;
  if (kind === "motif_gain") return Award;
  if (kind === "concept_mastered") return Trophy;
  return Sparkles;
};

export default function LearnedThisCard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [conceptsOpen, setConceptsOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API}/coach/learned-this`, {
          credentials: "include",
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (!cancelled) setData(json);
      } catch {
        // silence — the card is optional; failure just hides it
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  if (loading || !data || !data.has_data) return null;

  const HeadlineIcon = iconFor(data.headline?.kind);

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      className="mb-10 md:mb-14"
      data-testid="learned-this-card"
    >
      {/* Section eyebrow */}
      <div className="flex items-center gap-2 mb-4">
        <Sparkles className="h-3.5 w-3.5 text-emerald-500" strokeWidth={2.4} />
        <div className="text-[10.5px] uppercase tracking-[0.22em] text-emerald-600 dark:text-emerald-400 font-semibold">
          You learned this
        </div>
        {data.window?.recent_games ? (
          <div className="text-[10.5px] text-muted-foreground/70">
            · last {data.window.recent_games} games
          </div>
        ) : null}
      </div>

      {/* Headline block */}
      <div className="rounded-2xl border border-emerald-500/25 bg-gradient-to-br from-emerald-500/[0.06] via-transparent to-transparent p-6 md:p-7">
        <div className="flex items-start gap-4">
          <HeadlineIcon
            className="h-6 w-6 text-emerald-500 shrink-0 mt-1"
            strokeWidth={2}
          />
          <div className="min-w-0 flex-1">
            <p className="font-serif text-[22px] md:text-[26px] leading-tight tracking-[-0.01em] text-foreground">
              {data.headline?.label}
            </p>
            {data.headline?.detail && (
              <p className="mt-2 text-[14px] md:text-[15px] text-muted-foreground tabular-nums">
                {data.headline.detail}
              </p>
            )}
            {data.headline?.meta && (
              <p className="mt-1 text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground/70 font-medium">
                {data.headline.meta}
              </p>
            )}
          </div>
        </div>

        {/* Supporting wins */}
        {data.supporting && data.supporting.length > 0 && (
          <div className="mt-6 pt-5 border-t border-border/40">
            <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground/70 font-semibold mb-3">
              Also
            </div>
            <ul className="space-y-2.5">
              {data.supporting.map((s, i) => {
                const isConcepts = s.type === "concept_summary" && Array.isArray(s.concepts) && s.concepts.length > 0;
                if (!isConcepts) {
                  return (
                    <li
                      key={i}
                      className="flex items-baseline gap-3 text-[13.5px] md:text-[14px] text-foreground/80"
                    >
                      <span className="text-emerald-500/70 shrink-0">·</span>
                      <span className="flex-1">
                        <span className="text-foreground">{s.label}</span>
                        {s.detail && (
                          <span className="text-muted-foreground tabular-nums ml-2">
                            ({s.detail})
                          </span>
                        )}
                      </span>
                    </li>
                  );
                }
                // Concept summary — clickable, expands to the full named list.
                return (
                  <li key={i} className="text-[13.5px] md:text-[14px]">
                    <button
                      type="button"
                      onClick={() => setConceptsOpen((v) => !v)}
                      className="flex items-baseline gap-3 w-full text-left group text-foreground/80 hover:text-foreground transition-colors"
                      aria-expanded={conceptsOpen}
                    >
                      <span className="text-emerald-500/70 shrink-0">·</span>
                      <span className="flex-1">
                        <span className="text-foreground">{s.label}</span>
                        <span className="text-muted-foreground ml-2">
                          {conceptsOpen ? "hide" : "show"}
                        </span>
                      </span>
                      <ChevronDown
                        className={`h-3.5 w-3.5 text-muted-foreground/70 shrink-0 transition-transform ${conceptsOpen ? "rotate-180" : ""}`}
                        strokeWidth={2}
                      />
                    </button>
                    <AnimatePresence initial={false}>
                      {conceptsOpen && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: "auto", opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
                          className="overflow-hidden"
                        >
                          <ul className="mt-3 ml-6 pl-3 border-l border-emerald-500/20 space-y-1.5">
                            {s.concepts.map((c) => (
                              <li
                                key={c.concept_id}
                                className="text-[13px] text-foreground/85 flex items-baseline gap-2"
                              >
                                <span className="flex-1">{c.name}</span>
                                {/* Rate over raw count — 2026-07-08 fix.
                                    "226 clean" is a vanity number; a clean
                                    rate anchored on opportunity count is
                                    the skill signal. */}
                                <span className="text-[11.5px] text-emerald-600 dark:text-emerald-400 tabular-nums shrink-0 font-medium">
                                  {c.clean_rate_pct}% clean
                                </span>
                                <span className="text-[10.5px] text-muted-foreground/60 tabular-nums shrink-0">
                                  · {c.opportunity_count}
                                </span>
                              </li>
                            ))}
                          </ul>
                          <button
                            type="button"
                            onClick={() => navigate("/progress#in-game-mastery")}
                            className="mt-3 ml-6 inline-flex items-center gap-1.5 text-[11.5px] text-emerald-600 dark:text-emerald-400 hover:text-emerald-500 dark:hover:text-emerald-300 transition-colors group"
                          >
                            Open in your mastery ledger
                            <ArrowRight
                              className="h-3 w-3 transition-transform group-hover:translate-x-0.5"
                              strokeWidth={2}
                            />
                          </button>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {/* CTA if we have a before/after moment */}
        {(data.before_after || []).length > 0 && (
          <button
            onClick={() => {
              const gid = data.before_after[0]?.new_game_id;
              if (gid) navigate(`/game/${gid}`);
            }}
            className="mt-6 inline-flex items-center gap-1.5 text-[12.5px] text-emerald-600 dark:text-emerald-400 hover:text-emerald-500 dark:hover:text-emerald-300 transition-colors group"
          >
            See the game where it clicked
            <ArrowRight
              className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5"
              strokeWidth={2}
            />
          </button>
        )}
      </div>
    </motion.section>
  );
}
