/**
 * "Chances you took" — the lead section of /progress.
 *
 * docs/progress_page_scope.md. Built 2026-11-27 after /progress was found to
 * be off for every user: the live access gate returned enabled=0 across all
 * 139, so 49 people saw "Nothing you learned has disappeared" and 90 saw
 * "Your progress will show here". Neither is a layout problem.
 *
 * Every row is n out of the m chances that actually came up. Three rules
 * follow from that, and each one is load-bearing:
 *
 *   - Never a percentage on its own. "36 of 36" is honest in a week when it
 *     does not move; "100%" invites a trend line the data cannot carry.
 *   - A row with no chances this week says so. It does not show 0, because
 *     nought out of nought is not a performance.
 *   - No verdict words. Nothing here says better, worse, improving or
 *     mastered. The habit test that produces those compares 20 recent games
 *     with the previous 40 at p<0.10, which cannot report improvement for
 *     any habit rarer than about 1 game in 9, while "worse" needs only three
 *     occurrences. A page built on it says "same as before" forever.
 *
 * Why "found it when it mattered" is absent, since it is the obvious fourth
 * row: it correlates with rating at r = +0.50, the strongest single axis
 * measured on this corpus, so the data is the best we have. But the whole
 * human range is 1.7% to 13.1% and even 1600+ players find 8.6%, so an
 * absolute "you found it 7 times in 100" reads as "you are bad at chess" to
 * everybody while giving them nothing to do. It comes back relative to
 * level, or coach-side.
 */

import React from "react";

const nf = (n) => Number(n).toLocaleString();

/** "49 of 50", or an honest dash. Never a bare percentage. */
function Count({ took, chances, muted }) {
  if (!chances) {
    return (
      <span className="text-sm text-muted-foreground" data-testid="chance-none">
        no chances
      </span>
    );
  }
  return (
    <span className={`tabular-nums ${muted ? "text-muted-foreground" : "text-foreground"}`}>
      <span className="font-semibold">{nf(took)}</span>
      <span className="text-muted-foreground"> of {nf(chances)}</span>
    </span>
  );
}

function Row({ axis, recentGames }) {
  const recent = axis.recent;
  return (
    <div
      className="grid gap-1 border-t border-border/60 py-3.5 sm:grid-cols-[1fr_auto_auto] sm:items-baseline sm:gap-6"
      data-testid={`chance-row-${axis.key}`}
    >
      <div className="text-base font-medium text-foreground">{axis.label}</div>

      <div className="flex items-baseline gap-2 sm:block sm:w-28 sm:text-right">
        <span className="text-xs uppercase tracking-wide text-muted-foreground sm:hidden">
          Last {recentGames}
        </span>
        {recent ? (
          <Count took={recent.took} chances={recent.chances} />
        ) : (
          // Deliberate, not missing data: this axis offers about 0.7 chances
          // a game, so ten games give about seven, and seven chances must
          // not be drawn as a rate.
          <span className="text-sm text-muted-foreground" data-testid="chance-alltime-only">
            —
          </span>
        )}
      </div>

      <div className="flex items-baseline gap-2 sm:block sm:w-32 sm:text-right">
        <span className="text-xs uppercase tracking-wide text-muted-foreground sm:hidden">
          All time
        </span>
        <Count took={axis.took} chances={axis.chances} muted />
      </div>
    </div>
  );
}

export default function ProgressChances({ data }) {
  if (!data || !data.axes || !data.axes.length) return null;

  const games = data.analysed_games || 0;
  const recentGames = data.recent_games || 0;

  if (!data.has_evidence) {
    return (
      <section className="cg-panel" data-testid="progress-chances-empty">
        <h2 className="text-xl font-semibold text-foreground">
          Nothing to count yet
        </h2>
        <p className="mt-2 text-base leading-relaxed text-muted-foreground">
          {games
            ? "Your games are still being read. This page fills in as they are."
            : "Once a game of yours has been read, this page shows the chances that came up in it and what you did with them."}
        </p>
      </section>
    );
  }

  return (
    <section className="cg-panel" data-testid="progress-chances">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <h2 className="text-xl font-semibold text-foreground">Chances you took</h2>
        <p className="text-sm text-muted-foreground">
          From {nf(games)} {games === 1 ? "game" : "games"} we have read.
        </p>
      </div>

      <p className="mt-2 text-base leading-relaxed text-muted-foreground">
        Each line counts the times the chance actually came up, and how many
        of them you took. Not a score.
      </p>

      {/* Column headings, desktop only; on a phone each row carries its own. */}
      <div className="mt-5 hidden sm:grid sm:grid-cols-[1fr_auto_auto] sm:gap-6 sm:text-right">
        <span />
        <span className="w-28 text-xs uppercase tracking-wide text-muted-foreground">
          Last {recentGames}
        </span>
        <span className="w-32 text-xs uppercase tracking-wide text-muted-foreground">
          All time
        </span>
      </div>

      <div className="mt-1">
        {data.axes.map((axis) => (
          <Row key={axis.key} axis={axis} recentGames={recentGames} />
        ))}
      </div>

      <p className="mt-4 border-t border-border/60 pt-4 text-sm leading-relaxed text-muted-foreground">
        “Punished their mistake” has no recent column because it comes up
        about once every game and a half — too rarely for ten games to say
        anything.
      </p>
    </section>
  );
}
