/**
 * AreaGradesCard - where the player stands in every part of their game.
 *
 * A player currently sees exactly one area on Home, because one topic is
 * authorised to drive a plan. Their games contain five more, plus an
 * opening/middlegame/endgame split that is computed on every move.
 *
 * Deliberately carries NO numbers. The grade comes from how this player
 * compares with others in THAT area, and the rate that produced it is never
 * rendered.
 *
 * VISUAL CONTRACT, 2026-10-05. Mohit: the page "looks so unprofessional". It
 * did, and the reason was not decoration -- this card ignored the design
 * language every other section on /progress uses. It rendered a generic
 * <Card> with a 17px title while its neighbours use `cg-panel`, a `cg-eyebrow`
 * and a `font-heading` h2, so it read as something bolted on.
 *
 * Three changes, each with a reason beyond taste:
 *
 *   The grade is a four-step meter, not coloured words. Four steps because
 *   there are exactly four grades, so the meter is the grade rather than a
 *   decoration of it, and a reader sees the shape of their game at a glance
 *   instead of parsing six adjectives.
 *
 *   A row with somewhere to go is a LINK ACROSS THE WHOLE ROW, not a small
 *   tail of text. The practice affordance was easy to miss, which is what
 *   "nothing is clickable" meant.
 *
 *   Areas and phases are separated by a labelled rule rather than by a bare
 *   uppercase line, because they answer different questions -- what you do,
 *   and when in the game you do it.
 */

import { useState, useEffect } from "react";
import { API } from "@/App";
import { Loader2, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";

// Worst reads warmest, so the eye lands on what is worth working on without
// the page turning into a wall of red.
const GRADE_STYLES = {
  "Excellent": {
    text: "text-emerald-600 dark:text-emerald-400",
    fill: "bg-emerald-500",
  },
  "Good": {
    text: "text-foreground",
    fill: "bg-emerald-500/60",
  },
  "Fair": {
    text: "text-amber-600 dark:text-amber-400",
    fill: "bg-amber-500",
  },
  "Needs work": {
    text: "text-rose-600 dark:text-rose-400",
    fill: "bg-rose-500",
  },
};

// Four steps for four grades, so the meter IS the grade and cannot drift out
// of step with the words beside it.
const GRADE_STEPS = { "Needs work": 1, "Fair": 2, "Good": 3, "Excellent": 4 };

function Meter({ grade }) {
  const filled = GRADE_STEPS[grade] || 0;
  const fill = GRADE_STYLES[grade]?.fill || "bg-muted-foreground/30";
  return (
    <span className="inline-flex items-center gap-[3px]" aria-hidden="true">
      {[1, 2, 3, 4].map((step) => (
        <span
          key={step}
          className={`h-[6px] w-[14px] rounded-full transition-colors ${
            step <= filled ? fill : "bg-foreground/[0.08] dark:bg-foreground/10"
          }`}
        />
      ))}
    </span>
  );
}

function RowBody({ row, practice }) {
  const measured = row.measured;
  const grade = measured ? row.grade : "Not enough games yet";
  const tone = measured
    ? (GRADE_STYLES[row.grade]?.text || "text-foreground")
    : "text-muted-foreground";
  return (
    <>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[14.5px] text-foreground">
          {row.label}
        </span>
        {practice && (
          <span className="mt-0.5 flex items-center gap-1 text-[12px] font-medium text-emerald-700 dark:text-emerald-400">
            {practice.label}
            <ChevronRight
              className="h-3 w-3 transition-transform group-hover:translate-x-0.5"
              aria-hidden="true"
            />
          </span>
        )}
      </span>
      <span className="flex shrink-0 items-center gap-3">
        {measured && <Meter grade={row.grade} />}
        <span
          className={`w-[104px] text-right text-[12.5px] font-semibold tracking-[-0.01em] ${tone}`}
        >
          {grade}
        </span>
      </span>
    </>
  );
}

function GradeRow({ row }) {
  // The link is rendered ONLY when the backend attached one, and it attaches
  // one only after finding real unsolved supply for this player. A row with
  // nothing behind it stays plain text on purpose -- 20 of 48 players once had
  // a practice button that led to an empty page.
  const practice = row.practice?.href ? row.practice : null;
  const shared =
    "flex items-center gap-4 py-3 first:pt-0 last:pb-0 border-b border-border/40 last:border-0";

  if (!practice) {
    return (
      <div className={shared}>
        <RowBody row={row} practice={null} />
      </div>
    );
  }
  return (
    <Link
      to={practice.href}
      data-testid={`area-practice-${row.key}`}
      className={`group -mx-3 rounded-xl px-3 transition-colors hover:bg-foreground/[0.03] dark:hover:bg-foreground/[0.05] ${shared}`}
    >
      <RowBody row={row} practice={practice} />
    </Link>
  );
}

export default function AreaGradesCard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API}/progress/area-grades`, {
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

  if (!data || !Array.isArray(data.areas) || data.areas.length === 0) return null;

  const phases = Array.isArray(data.phases) ? data.phases : [];

  return (
    <section className="cg-panel p-6 md:p-7" data-testid="area-grades-card">
      <p className="cg-eyebrow">Where you stand</p>
      <h3 className="mt-2 font-heading text-[22px] tracking-[-0.025em] text-foreground md:text-[25px]">
        Every part of your game
      </h3>
      <p className="mt-2 max-w-[560px] text-[13px] leading-relaxed text-muted-foreground">
        Compared with other players, from your own games.
      </p>

      <div className="mt-6">
        {data.areas.map((row) => <GradeRow key={row.key} row={row} />)}
      </div>

      {phases.length > 0 && (
        <>
          <div className="mt-7 mb-1 flex items-center gap-3">
            <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">
              Across the game
            </span>
            <span className="h-px flex-1 bg-border/60" />
          </div>
          <div className="mt-2">
            {phases.map((row) => <GradeRow key={row.key} row={row} />)}
          </div>
        </>
      )}
    </section>
  );
}
