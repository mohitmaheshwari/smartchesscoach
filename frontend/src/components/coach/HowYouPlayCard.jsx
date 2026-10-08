/**
 * HowYouPlayCard - the player's behavioural traits, described not graded.
 *
 * Its sibling AreaGradesCard grades board areas Excellent to Needs work, which
 * is right for a skill and wrong for a disposition. "Thinks too long - Needs
 * work" is a judgement the data refuses: measured per player, thinking longer
 * goes with FEWER errors, not more. So these are sentences, with no grade, no
 * rank and no comparison.
 *
 * Seven traits earned a place by being stable within a player across time AND
 * spread across players. Fourteen candidates failed and are named in
 * backend/services/behaviour_profile.py so nobody rebuilds them - tilt is not
 * real, aggression is not measurable, saving lost games is the opponent's
 * doing.
 *
 * A player inside the middle half of the population is told nothing about that
 * trait, so most people see two to four lines rather than seven. Someone in the
 * middle of everything is told that outright, because a blank page is the worst
 * outcome for the most engaged player we have.
 *
 * Display-only, like its sibling: it says who you are, never what to do. The
 * one instruction stays on Home.
 */

import { useState, useEffect } from "react";
import { API } from "@/App";
import { Loader2 } from "lucide-react";

export default function HowYouPlayCard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API}/progress/how-you-play`, {
          credentials: "include",
        });
        if (res.ok && !cancelled) setData(await res.json());
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

  // Not enough games watched is a real answer, but it is not worth a card.
  if (!data || !data.measured) return null;
  const lines = Array.isArray(data.lines) ? data.lines : [];
  if (lines.length === 0) return null;

  return (
    <section className="cg-panel p-6 md:p-7" data-testid="how-you-play-card">
      <p className="cg-eyebrow">How you play</p>
      <h3 className="mt-2 font-heading text-[22px] tracking-[-0.025em] text-foreground md:text-[25px]">
        Habits that hold up.
      </h3>
      <p className="mt-2 max-w-[560px] text-[13px] leading-relaxed text-muted-foreground">
        Seen across your games, not one of them.
      </p>
      <div className="mt-6">
        <ul className="space-y-3">
          {lines.map((line) => (
            <li
              key={line.trait}
              className="text-[14px] leading-relaxed text-foreground border-b border-border/40 pb-3 last:border-0 last:pb-0"
            >
              {line.sentence}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
