/**
 * The coach in the room on the training page.
 * docs/training_coach_presence_scope.md (signed 2026-11-17).
 *
 *  - WeekStrip: this drill is the player's plan step for the week, in the
 *    plan's own words.
 *  - SessionPath: done / now / to come. No red, no score (feedback rule:
 *    never show a failure scoreboard).
 *  - LandingCheck: after a drop, before the move is judged, the coach asks
 *    which piece can win the moved piece on its new square. "Where should I
 *    look?" walks the three looks from that square.
 *  - whatISaw: today's think against the game's, in words, never seconds.
 */
import React from "react";
import { Eye, Check, X, Undo2, ChevronRight, Search } from "lucide-react";

export function WeekStrip({ week }) {
  if (!week?.do) return null;
  return (
    <section
      data-testid="training-week-strip"
      className="mb-8 md:mb-10 rounded-2xl border border-border/70 bg-card/60 px-5 py-4 md:px-6 md:py-5"
    >
      <p className="cg-eyebrow">Your step this week</p>
      <p className="mt-2 font-serif text-lead text-foreground max-w-[640px]">
        {week.do}
      </p>
      {week.last_week && (
        <p className="mt-1.5 text-meta text-muted-foreground max-w-[640px]">{week.last_week}</p>
      )}
    </section>
  );
}

export function SessionPath({ total, index, doneNow }) {
  if (!total || total < 2) return null;
  return (
    <div className="flex items-center gap-3" data-testid="training-session-path" aria-label="Today's positions">
      <span className="text-meta uppercase text-muted-foreground font-semibold">Today</span>
      <div className="flex items-center gap-1.5">
        {Array.from({ length: total }, (_, i) => {
          const done = i < index || (i === index && doneNow);
          if (done) return <span key={i} data-state="done" className="h-1.5 w-6 rounded-full bg-foreground/55 transition-colors duration-500" />;
          if (i === index)
            return (
              <span
                key={i}
                data-state="now"
                className="h-1.5 w-6 rounded-full bg-accent ring-2 ring-accent/25 ring-offset-2 ring-offset-background"
              />
            );
          return <span key={i} data-state="later" className="h-1.5 w-6 rounded-full bg-muted" />;
        })}
      </div>
    </div>
  );
}

/** The coach's line while it is quietly watching (after it has stepped back). */
export function CoachWatching({ justStepped }) {
  return (
    <div data-testid="coach-watching" className="mt-6 flex items-start gap-3 text-note text-muted-foreground">
      <Eye className="h-4 w-4 mt-0.5 text-accent" strokeWidth={1.75} />
      <p className="max-w-[420px] leading-relaxed">
        {justStepped
          ? "You're checking on your own now. I'll just watch."
          : "I'm watching. Check where your piece lands, then play."}
      </p>
    </div>
  );
}

export function CoachSteppedIn() {
  return (
    <p data-testid="coach-stepped-in" className="mb-4 text-note text-amber-700 dark:text-amber-300/90 leading-relaxed">
      That piece could be won where it landed. I'll ask again for a while.
    </p>
  );
}

/**
 * The check itself. `check` = { san, piece, square, loading, hint, result }.
 * The board (selection-only) sends taps to onTap; this panel holds the rest.
 */
export function LandingCheck({ check, onSafe, onHint, onContinue, onTakeBack }) {
  const { san, piece, square, hint, result, loading } = check;
  const pieceName = piece || "piece";
  return (
    <div data-testid="landing-check" className="flex flex-col">
      <div className="cg-eyebrow mb-6 flex items-center gap-2">
        <Eye className="h-3.5 w-3.5" strokeWidth={1.75} />
        Coach's eye
      </div>
      <p className="text-note text-muted-foreground">
        You played <span className="font-mono text-foreground">{san}</span>. Before I check it:
      </p>
      <p className="mt-2 font-serif italic text-title text-foreground max-w-[440px]">
        Can anything win your {pieceName}{square ? ` on ${square}` : ""}?
      </p>

      {!result && (
        <>
          <p className="mt-4 text-meta text-muted-foreground">
            Tap the piece that would take it, or say it is safe.
          </p>
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={onSafe}
              disabled={loading}
              data-testid="landing-check-safe"
              className="h-10 px-5 rounded-lg border border-border bg-card text-note font-medium text-foreground hover:bg-muted/60 transition-colors disabled:opacity-50"
            >
              It is safe
            </button>
            {!hint && (
              <button
                type="button"
                onClick={onHint}
                disabled={loading}
                data-testid="landing-check-hint"
                className="inline-flex items-center gap-1.5 text-meta text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
              >
                <Search className="h-3.5 w-3.5" strokeWidth={1.75} />
                Where should I look?
              </button>
            )}
          </div>
        </>
      )}

      {hint && !result && (
        <div data-testid="landing-check-looks" className="mt-6 rounded-xl border border-border/70 bg-card/50 px-4 py-3.5">
          <p className="text-meta uppercase text-muted-foreground font-semibold mb-2.5">
            The three looks from {square}
          </p>
          <ul className="space-y-1.5">
            {hint.looks.map((look) => (
              <li key={look.look} className="flex items-baseline justify-between gap-4 text-note">
                <span className="text-muted-foreground">{look.label}</span>
                <span className={look.found.length ? "text-foreground font-medium" : "text-muted-foreground/70"}>
                  {look.found.length
                    ? look.found.map((f) => `${f.piece} on ${f.sq}`).join(", ")
                    : "nothing"}
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-2.5 text-meta text-muted-foreground">
            A piece that can take is not always a piece that wins. Can you take back?
          </p>
        </div>
      )}

      {result && (
        <div
          data-testid="landing-check-result"
          className={`mt-6 flex items-start gap-3 rounded-xl border px-4 py-3.5 ${
            result.correct ? "border-emerald-400/30 bg-emerald-500/[0.05]" : "border-amber-400/35 bg-amber-500/[0.05]"
          }`}
        >
          {result.correct ? (
            <Check className="h-4 w-4 mt-0.5 text-emerald-500" strokeWidth={2.25} />
          ) : (
            <X className="h-4 w-4 mt-0.5 text-amber-600" strokeWidth={2.25} />
          )}
          <p className="text-note leading-relaxed text-foreground">{result.words}</p>
        </div>
      )}

      {result && (
        <div className="mt-6 flex flex-wrap items-center gap-4">
          {!result.safe && (
            <button
              type="button"
              onClick={onTakeBack}
              data-testid="landing-check-take-back"
              className="h-10 px-5 rounded-lg bg-foreground text-background text-note font-medium inline-flex items-center gap-2"
            >
              <Undo2 className="h-3.5 w-3.5" />
              Take the move back
            </button>
          )}
          <button
            type="button"
            onClick={onContinue}
            data-testid="landing-check-continue"
            className={
              result.safe
                ? "h-10 px-5 rounded-lg bg-foreground text-background text-note font-medium inline-flex items-center gap-2"
                : "text-meta text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
            }
          >
            {result.safe ? "Check my move" : "Play it anyway"}
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}

/**
 * Today's think against the game's, in words. Null when either time is
 * missing. Thresholds are wording, not measurement: "quickly" = ten seconds
 * or less in the game; "took your time" = at least twice the game's think and
 * at least twenty seconds.
 */
export function whatISaw({ gameSeconds, todayMs, solved, checkedRight }) {
  if (!(gameSeconds > 0) || !(todayMs > 0)) return null;
  const today = todayMs / 1000;
  const quickGame = gameSeconds <= 10;
  const tookTime = today >= Math.max(20, gameSeconds * 2);
  const checked = checkedRight ? " and checked where your piece lands" : "";
  if (solved) {
    if (quickGame && tookTime) return `In the game you moved quickly here. Today you took your time${checked}, and found it.`;
    if (quickGame) return `In the game you moved quickly here and missed it. Today you found it${checked}.`;
    return `In the game you thought about this one and still missed it. Today you found it${checked}.`;
  }
  if (quickGame && !tookTime) return "In the game you moved quickly here, and today too. Next time, stop and check where your piece lands first.";
  return "You took your time on this one. Look from the square where your piece lands: close by, knight jumps, long lines.";
}
