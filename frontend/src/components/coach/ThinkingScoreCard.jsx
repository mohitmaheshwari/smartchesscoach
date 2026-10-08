/**
 * ThinkingScoreCard — which thinking step is breaking down.
 *
 * REBUILT 2026-10-05. Mohit asked whether this and the area grades were the
 * same thing. Measured on 59 players carrying both, and the answer was worse
 * than redundancy — where they overlapped they disagreed:
 *
 *   piece_safety  <-> threat awareness   agreed
 *   king_safety   <-> king safety        no relationship at all
 *   missed_tactic <-> tactical vision    contradicted ("Needs work" averaged 92.6)
 *
 * A player could read "Keeping your king safe — Needs work" here and a
 * king-safety score near ninety in the card above.
 *
 * The contradicting habits were the saturated ones: more than half the
 * population scores exactly 100 on king safety, patience and tactical vision,
 * so those numbers separated nobody. The server now drops every habit whose
 * median sits at the ceiling, which removes both contradictions under one rule.
 *
 * WHAT WENT, AND WHY IT IS NOT A LOSS:
 *   the 0–100 score   — ran p10 77 to p90 92 across the population, which is
 *                       every player getting a B, and it was the only number
 *                       any card on this page showed.
 *   the progress bars — they rendered that score.
 *   three of five habits — they could not tell two players apart.
 *
 * The component now renders words from `card`, and nothing at all when no
 * habit is at an end. Saying "your thinking is fine" off a saturated measure
 * would repeat the mistake the balanced behaviour line made.
 */

import { useState, useEffect } from "react";
import { API } from "@/App";
import { Loader2 } from "lucide-react";

export default function ThinkingScoreCard() {
  const [card, setCard] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API}/thinking-score`, { credentials: "include" });
        if (res.ok && !cancelled) {
          const body = await res.json();
          setCard(body?.card || null);
        }
      } catch (e) {
        // Non-fatal: the card simply does not render.
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div className="cg-panel flex items-center justify-center p-10">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const lines = Array.isArray(card?.lines) ? card.lines : [];
  if (!card?.measured || lines.length === 0) return null;

  return (
    <section className="cg-panel p-6 md:p-7" data-testid="thinking-score-card">
      <p className="cg-eyebrow">Where your thinking breaks down</p>
      <h3 className="mt-2 font-heading text-[22px] tracking-[-0.025em] text-foreground md:text-[25px]">
        {lines[0].headline}
      </h3>

      <div className="mt-5 space-y-6">
        {lines.map((line, index) => (
          <div
            key={line.habit}
            data-testid={`thinking-habit-${line.habit}`}
            className={index > 0 ? "border-t border-border/40 pt-6" : undefined}
          >
            {index > 0 && (
              <p className="mb-2 font-heading text-[17px] tracking-[-0.02em] text-foreground">
                {line.headline}
              </p>
            )}
            <p className="text-[14px] leading-relaxed text-foreground">
              {line.body}
            </p>
            {/* The instruction reads differently from the description, so it
                gets its own weight rather than becoming a third sentence the
                eye slides past. */}
            <p className="mt-3 border-l-2 border-emerald-600/40 pl-3 text-[13.5px] leading-relaxed text-muted-foreground">
              {line.next}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
