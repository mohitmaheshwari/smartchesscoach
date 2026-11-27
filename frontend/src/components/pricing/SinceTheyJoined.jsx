/**
 * "Since they joined" — real rating curves on the pricing page.
 *
 * Mohit pointed at this twice: a row of real players with a sparkline from
 * the day they joined to now. We had not built it. This is ours, with two
 * deliberate differences from the reference.
 *
 * 1. IT CARRIES ITS OWN DENOMINATOR. Measured on production 2026-11-27: of
 *    the 55 players with enough games since signing up, 32 went up, 2 held
 *    and 21 went DOWN. The strip shows the best eight, like any such strip,
 *    but the line underneath says how many there were and how many fell. A
 *    proof panel you cannot check against its own base rate is an advert.
 *    It is also, in practice, more convincing: a page that admits 21 people
 *    lost rating is easier to believe about the eight who gained.
 *
 * 2. NO HANDLES, NO FACES. The reference shows usernames and avatars. A
 *    chess.com handle is public, but printing it beside our product name
 *    asserts that this person uses ChessGuru, which nobody agreed to, and
 *    there is no consent field on the user document. Turning that on needs
 *    a consent flow and is Mohit's call, not a default.
 *
 * And nothing here says we caused it. On 2026-11-26 one player's rating rose
 * 337 points across 754 analysed games while their mistake rates barely
 * moved, and most of these accounts predate the coaching features. "Since
 * they joined" states when the clock started, not what moved the needle.
 */

import React from "react";

/** A plain polyline. No library for twenty-four numbers. */
function Spark({ curve, width = 132, height = 44 }) {
  if (!curve || curve.length < 2) return null;
  const lo = Math.min(...curve);
  const hi = Math.max(...curve);
  const span = hi - lo || 1;
  const stepX = width / (curve.length - 1);
  // 3px inset top and bottom so the stroke is never clipped.
  const y = (v) => 3 + (height - 6) * (1 - (v - lo) / span);
  const points = curve.map((v, i) => `${(i * stepX).toFixed(1)},${y(v).toFixed(1)}`);

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="overflow-visible"
      aria-hidden="true"
      focusable="false"
    >
      <polyline
        points={points.join(" ")}
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle
        cx={(curve.length - 1) * stepX}
        cy={y(curve[curve.length - 1])}
        r="3"
        fill="currentColor"
      />
    </svg>
  );
}

function JourneyCard({ journey }) {
  const up = journey.delta > 0;
  return (
    <li
      className="flex w-56 shrink-0 flex-col gap-3 rounded-2xl border border-border bg-card p-4"
      data-testid="journey-card"
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs uppercase tracking-wide text-muted-foreground">
          {journey.games.toLocaleString()} games
        </span>
        <span
          className={`text-xl font-bold tabular-nums ${
            up ? "text-emerald-400" : "text-muted-foreground"
          }`}
        >
          {up ? "+" : ""}
          {journey.delta}
        </span>
      </div>

      <div className={up ? "text-emerald-400" : "text-muted-foreground"}>
        <Spark curve={journey.curve} />
      </div>

      <div className="flex items-baseline justify-between gap-2 text-sm tabular-nums text-muted-foreground">
        <span>{journey.start}</span>
        <span aria-hidden="true">→</span>
        <span className="font-semibold text-foreground">{journey.end}</span>
      </div>
    </li>
  );
}

export default function SinceTheyJoined({ data }) {
  if (!data || !data.journeys || data.journeys.length === 0) return null;
  const c = data.counts;

  return (
    <section className="mt-16" data-testid="since-they-joined">
      <h2 className="text-2xl font-semibold text-foreground sm:text-3xl">
        Since they joined
      </h2>

      {/* The denominator, in the same breath as the curves. */}
      <p className="mt-2 max-w-2xl text-base leading-relaxed text-muted-foreground">
        Real ratings from ChessGuru players, counted from the day they signed
        up.{" "}
        {c ? (
          <span data-testid="journey-denominator">
            Of the {c.measurable} who have played enough games to measure,{" "}
            {c.up} went up and {c.down} went down. These are the {data.journeys.length}{" "}
            biggest gains.
          </span>
        ) : null}
      </p>

      <ul
        className="mt-6 flex gap-3 overflow-x-auto pb-2"
        // A horizontal strip is the shape; on a phone it scrolls rather
        // than wrapping into a wall of eight cards.
        data-testid="journey-strip"
      >
        {data.journeys.map((j, i) => (
          <JourneyCard key={i} journey={j} />
        ))}
      </ul>

      <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted-foreground">
        A rating moves for many reasons. We are not claiming we caused these.
      </p>
    </section>
  );
}
