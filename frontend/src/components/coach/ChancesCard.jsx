/**
 * "The chances you got" — of what the board offered, how much did you take?
 *
 * docs/chances_not_games_scope.md
 *
 * THE CHANCE IS THE UNIT, NOT THE GAME. Mohit, 2026-10-05: "it should be game
 * independent really, like quality of moves vs chances provided." A game is a
 * container that varies from one chance to sixteen, so a per-game figure says
 * nothing. The denominator is what the board offered; the numerator is the
 * player.
 *
 * NO NUMBERS ARE RENDERED. The server sends counts and shares; this draws bars
 * and sentences. Mohit has not settled whether plain counts may be shown, so
 * the decision stays a one-line UI change in either direction rather than
 * something that has to be undone.
 *
 * A shape with too few chances of its own is drawn without a bar and never
 * named as the weak one — the gate's own measurement is that a single pattern
 * is unstable until it has hundreds of chances behind it.
 */

import { useState, useEffect } from "react";
import { API } from "@/App";
import { Loader2, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";

export default function ChancesCard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API}/home/chances`, { credentials: "include" });
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

  const habits = data?.habits?.lines || [];
  // The habit lines stand on their own: a player with too few chances to rate
  // can still be told how regular they have been this month.
  if (!data?.measured && habits.length === 0) return null;
  const shapes = (data.shapes || []).filter((s) => s.judgeable);
  const weakestShape = data.weakest?.shape;

  return (
    <section className="cg-panel p-6 md:p-7" data-testid="chances-card">
      <p className="cg-eyebrow">How your chess is going</p>
      {data.measured && (
        <h3 className="mt-2 font-heading text-[22px] tracking-[-0.025em] text-foreground md:text-[25px]">
          {data.headline}
        </h3>
      )}

      {/* The context the bars were missing. "Half" says nothing without
          "against what" — this is the week, the rhythm, and the one reading
          that is true of this player and not of the population. */}
      {habits.length > 0 && (
        <div className="mt-4 space-y-3" data-testid="chances-habits">
          {habits.map((h) => (
            <div key={h.kind} data-testid={`habit-${h.kind}`}>
              <p className="text-[14px] leading-relaxed text-foreground">
                {h.line}
              </p>
              {h.next && (
                <p className="mt-1 border-l-2 border-emerald-600/40 pl-3 text-[13px] leading-relaxed text-muted-foreground">
                  {h.next}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {shapes.length > 0 && (
        <div className="mt-6 space-y-2.5">
          {shapes.map((s) => (
            <div key={s.shape} className="flex items-center gap-3">
              <span
                className={`w-[132px] shrink-0 text-[13px] ${
                  s.shape === weakestShape
                    ? "font-semibold text-foreground"
                    : "text-muted-foreground"
                }`}
              >
                {s.label}
              </span>
              <span className="h-[9px] flex-1 overflow-hidden rounded-full bg-foreground/[0.06] dark:bg-foreground/10">
                <span
                  className={`block h-full rounded-full ${
                    s.shape === weakestShape
                      ? "bg-amber-500"
                      : "bg-emerald-500/70"
                  }`}
                  /* A share, drawn. The figure behind it is never printed. */
                  style={{ width: `${Math.round(s.share * 100)}%` }}
                />
              </span>
            </div>
          ))}
        </div>
      )}

      {data.weakest_line && (
        <p className="mt-5 text-[14px] leading-relaxed text-foreground">
          {data.weakest_line}
        </p>
      )}

      {data.practice?.href && (
        <Link
          to={data.practice.href}
          data-testid="chances-practice"
          className="group mt-4 inline-flex items-center gap-1 text-[13px] font-medium text-emerald-700 hover:underline dark:text-emerald-400"
        >
          {data.practice.label}
          <ChevronRight
            className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5"
            aria-hidden="true"
          />
        </Link>
      )}
    </section>
  );
}
