/**
 * The parts that make a finished game feel finished: a move list you can walk
 * back through, the material each side has taken, and a result card carrying
 * the real rating change.
 *
 * The rule from PlayVsHuman.jsx still holds here and is easy to break by
 * accident: **nothing in this file may help the player choose a move while the
 * game is live.** A move list is a record of what was played, which Lichess's
 * own board shows, so it is fine. An evaluation beside those moves would not
 * be. Move navigation is deliberately only enabled once the game is over —
 * not because browsing is forbidden, but because a board that can show a
 * position other than the live one is one refactor away from showing an
 * analysed one.
 */

import React, { useEffect, useMemo, useRef, useState } from "react";
import { Chess } from "chess.js";

// Lichess status -> something a person would say. Anything unmapped falls
// through to the raw status rather than a wrong guess.
const REASONS = {
  mate: "by checkmate",
  resign: "by resignation",
  outoftime: "on time",
  timeout: "by timeout",
  stalemate: "by stalemate",
  draw: "by agreement",
  aborted: "aborted",
  nostart: "never started",
  cheat: "ended by Lichess",
  variantEnd: "by variant rule",
  unknownfinish: "",
};

const PIECE_GLYPH = { p: "♟", n: "♞", b: "♝", r: "♜", q: "♛" };
const PIECE_VALUE = { p: 1, n: 3, b: 3, r: 5, q: 9 };
const FULL_SET = { p: 8, n: 2, b: 2, r: 2, q: 1 };

/** Replay the UCI moves once; everything else is derived from this. */
export function replay(initialFen, moves) {
  const chess =
    !initialFen || initialFen === "startpos" ? new Chess() : new Chess(initialFen);
  const sans = [];
  const fens = [chess.fen()];
  for (const uci of (moves || "").split(" ").filter(Boolean)) {
    try {
      const move = chess.move({
        from: uci.slice(0, 2),
        to: uci.slice(2, 4),
        promotion: uci.length > 4 ? uci[4] : undefined,
      });
      if (!move) break;
      sans.push(move.san);
      fens.push(chess.fen());
    } catch (_) {
      break; // a move we cannot replay stops the list rather than throwing
    }
  }
  return { sans, fens };
}

/** What each side has captured, from a position. */
export function captured(fen) {
  const board = (fen || "").split(" ")[0] || "";
  const left = { w: { ...FULL_SET }, b: { ...FULL_SET } };
  for (const ch of board) {
    const lower = ch.toLowerCase();
    if (!(lower in FULL_SET)) continue;
    const side = ch === lower ? "b" : "w";
    left[side][lower] -= 1;
  }
  const take = (side) => {
    const gone = [];
    let points = 0;
    for (const piece of ["q", "r", "b", "n", "p"]) {
      const n = Math.max(0, left[side][piece]);
      for (let i = 0; i < n; i += 1) gone.push(piece);
      points += n * PIECE_VALUE[piece];
    }
    return { gone, points };
  };
  const white = take("b"); // pieces black has lost = white's captures
  const black = take("w");
  return {
    white: white.gone,
    black: black.gone,
    advantage: white.points - black.points,
  };
}

export function CapturedRow({ pieces = [], advantage = 0 }) {
  if (!pieces.length && !advantage) return <span className="h-4 block" />;
  return (
    <span className="flex items-center gap-0.5 text-sm leading-none text-muted-foreground">
      {pieces.map((p, i) => (
        <span key={i}>{PIECE_GLYPH[p]}</span>
      ))}
      {advantage > 0 ? (
        <span className="ml-1 text-xs font-medium">+{advantage}</span>
      ) : null}
    </span>
  );
}

// Fast enough that a second boundary never lands late enough to see, and
// fast enough to show tenths under ten seconds, which is where a tenth is the
// only number that matters.
const TICK_MS = 100;

/** Monotonic where the browser has one, so a system clock change cannot jump it. */
function nowMs() {
  return typeof performance !== "undefined" && performance.now
    ? performance.now()
    : Date.now();
}

/**
 * A clock that runs down between server readings.
 *
 * Lichess sends a clock reading with every board update and nothing in
 * between, so a clock drawn straight from the poll moves in 1.5-second lurches
 * and sits frozen through a long think. The fix is not to poll harder: it is to
 * take each reading with the age the server reports for it, anchor it against
 * our own monotonic clock, and run it down locally until the next reading
 * arrives. Every reading re-anchors, so any drift of ours lives for at most one
 * poll, and the number on screen is always Lichess's number plus elapsed time
 * -- never a number we invented.
 *
 * `running` comes from the server too (`ticking`), because only the server
 * knows whose turn it is. It is deliberately false before the first move and
 * while the stream is down: see `ticking()` in lichess_board_play.py.
 */
export function useLiveClock(baseMs, ageMs, running) {
  const [, redraw] = useState(0);
  const anchor = useRef({ key: null, from: null, at: 0 });

  // Re-anchor on each new reading. Keyed on the reading itself rather than
  // done in an effect, so the very first render already has an anchor.
  const key = `${baseMs}|${ageMs}|${running}`;
  if (anchor.current.key !== key) {
    const known = baseMs !== null && baseMs !== undefined;
    // The age correction belongs ONLY to the player on move. clock_age_ms is
    // how stale the reading is, and only the side whose clock is running has
    // been losing time during it. Subtracting it from the idle side made
    // their clock fall by a step on every poll -- not a smooth tick, since
    // no interval runs for them, but indistinguishable from one on screen,
    // and it ran both clocks down at once.
    anchor.current = {
      key,
      from: known ? Math.max(0, baseMs - (running ? ageMs || 0 : 0)) : null,
      at: nowMs(),
    };
  }

  useEffect(() => {
    if (!running) return undefined;
    const id = setInterval(() => redraw((n) => n + 1), TICK_MS);
    return () => clearInterval(id);
  }, [running]);

  const { from, at } = anchor.current;
  if (from === null) return null;
  if (!running) return from;
  return Math.max(0, from - (nowMs() - at));
}

/** M:SS, and M:SS.d under ten seconds, which is what Lichess shows. */
export function clockText(ms) {
  if (ms === null || ms === undefined) return "—:—";
  const left = Math.max(0, ms);
  const secs = Math.floor(left / 1000);
  const mmss = `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, "0")}`;
  if (left >= 10000) return mmss;
  return `${mmss}.${Math.floor((left % 1000) / 100)}`;
}

export function PlayerCard({
  name,
  rating,
  clockMs,
  clockAgeMs,
  running,
  pieces,
  advantage,
  active,
  testId,
}) {
  const remaining = useLiveClock(clockMs, clockAgeMs, running);
  // Under half a minute the clock is the only thing that matters on this card.
  const urgent = remaining !== null && remaining <= 30000;
  const initial = (name || "?").trim().charAt(0).toUpperCase();

  return (
    <div
      className={`flex items-center justify-between gap-3 rounded-2xl border px-3 py-2.5 transition-colors ${
        active ? "border-emerald-500/70 bg-emerald-500/[0.07]" : "border-border bg-card"
      }`}
      data-testid={testId}
    >
      <div className="flex min-w-0 items-center gap-3">
        <div
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-muted text-sm font-semibold"
          aria-hidden
        >
          {initial}
        </div>
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold leading-tight">
            {name}
            {rating ? (
              <span className="ml-1 font-normal text-muted-foreground">({rating})</span>
            ) : null}
          </div>
          <CapturedRow pieces={pieces} advantage={advantage} />
        </div>
      </div>
      <div
        className={`shrink-0 rounded-xl px-4 py-1.5 font-mono text-2xl font-semibold tabular-nums ${
          urgent
            ? "bg-rose-500/15 text-rose-300"
            : active
            ? "bg-emerald-500/15"
            : "bg-muted/60 text-muted-foreground"
        }`}
        data-testid={testId ? `${testId}-clock` : undefined}
      >
        {clockText(remaining)}
      </div>
    </div>
  );
}

export function MoveList({ sans, ply, onSeek, canSeek }) {
  const rows = useMemo(() => {
    const out = [];
    for (let i = 0; i < sans.length; i += 2) {
      out.push({ n: i / 2 + 1, white: sans[i], black: sans[i + 1] });
    }
    return out;
  }, [sans]);

  if (!sans.length) {
    return (
      <p className="px-3 py-4 text-center text-xs text-muted-foreground">
        No moves yet.
      </p>
    );
  }

  const cell = (san, index) => {
    if (!san) return <span />;
    const isHere = canSeek && ply === index + 1;
    return (
      <button
        type="button"
        disabled={!canSeek}
        onClick={() => onSeek(index + 1)}
        className={`w-full rounded px-2 py-0.5 text-left font-mono text-sm ${
          isHere ? "bg-emerald-500/20 font-semibold" : canSeek ? "hover:bg-muted/50" : ""
        }`}
      >
        {san}
      </button>
    );
  };

  return (
    <div className="max-h-56 overflow-y-auto" data-testid="live-move-list">
      {rows.map((row, i) => (
        <div key={row.n} className="grid grid-cols-[2rem_1fr_1fr] items-center gap-1 px-2">
          <span className="text-xs tabular-nums text-muted-foreground">{row.n}</span>
          {cell(row.white, i * 2)}
          {cell(row.black, i * 2 + 1)}
        </div>
      ))}
    </div>
  );
}

export function MoveNav({ ply, total, onSeek, enabled }) {
  const go = (next) => onSeek(Math.max(0, Math.min(total, next)));
  const button = (label, to, disabled, testId) => (
    <button
      type="button"
      onClick={() => go(to)}
      disabled={!enabled || disabled}
      data-testid={testId}
      className="rounded-lg border border-border px-3 py-1.5 text-sm disabled:opacity-40"
    >
      {label}
    </button>
  );
  return (
    <div className="mt-2 flex items-center justify-center gap-2">
      {button("|◀", 0, ply === 0, "live-nav-start")}
      {button("◀", ply - 1, ply === 0, "live-nav-prev")}
      <span className="min-w-14 text-center font-mono text-xs tabular-nums text-muted-foreground">
        {ply}/{total}
      </span>
      {button("▶", ply + 1, ply >= total, "live-nav-next")}
      {button("▶|", total, ply >= total, "live-nav-end")}
    </div>
  );
}

export function resultWords(game, ourColor) {
  const reason = REASONS[game.status] !== undefined ? REASONS[game.status] : game.status;
  if (game.status === "draw" || game.status === "stalemate") {
    return { headline: "Draw", reason };
  }
  if (!game.winner) return { headline: "Game over", reason };
  return { headline: game.winner === ourColor ? "You won" : "You lost", reason };
}

/* ------------------------------------------------------------------ result */

const RATING_PENDING_TEXT = "Asking Lichess for your new rating…";

const RESULT_STYLES = `
@keyframes cg-result-in   { from { opacity: 0 } to { opacity: 1 } }
@keyframes cg-result-rise { from { opacity: 0; transform: translateY(18px) }
                            to   { opacity: 1; transform: none } }
@keyframes cg-spin        { to { transform: rotate(360deg) } }
.cg-result-overlay { animation: cg-result-in .16s ease-out both; }
.cg-result-panel   { animation: cg-result-rise .26s cubic-bezier(.22,1,.36,1) both; }
.cg-spin           { animation: cg-spin .9s linear infinite; }
@media (prefers-reduced-motion: reduce) {
  .cg-result-overlay, .cg-result-panel, .cg-spin { animation: none; }
}
`;

/** ↑ 6 / ↓ 7 / ±0, or nothing. One renderer, so the card and the pop-up agree. */
export function RatingDelta({ diff, testId }) {
  if (typeof diff !== "number") return null;
  return (
    <span
      className={`text-sm font-medium tabular-nums ${
        diff > 0
          ? "text-emerald-400"
          : diff < 0
          ? "text-rose-400"
          : "text-muted-foreground"
      }`}
      data-testid={testId}
    >
      {diff > 0 ? `↑ ${diff}` : diff < 0 ? `↓ ${Math.abs(diff)}` : "±0"}
    </span>
  );
}

/**
 * The rating change on the sidebar card, which is Lichess's number and never
 * ours.
 *
 * Three states, and they are different things:
 *   - a number        -> show it, with the change
 *   - still asking    -> say so, on a rated game only
 *   - casual, or gone -> say nothing at all, rather than guess
 *
 * The middle one matters more than it sounds. The server learns the game is
 * over from the Lichess game stream, and only THEN asks their export endpoint
 * what the game was worth, so for a second or two a finished game legitimately
 * has no rating attached to it.
 */
export function RatingLine({ game, pending }) {
  if (game.our_rating == null) {
    if (!pending || !game.rated) return null;
    return (
      <div
        className="mt-4 text-sm text-muted-foreground"
        data-testid="live-rating-pending"
      >
        {RATING_PENDING_TEXT}
      </div>
    );
  }

  return (
    <div className="mt-4 flex items-baseline justify-center gap-2">
      <span className="text-2xl font-semibold tabular-nums" data-testid="live-new-rating">
        {game.our_rating}
      </span>
      <RatingDelta diff={game.our_rating_diff} testId="live-rating-diff" />
    </div>
  );
}

/** The review door, in whichever of its two states is true right now. */
function ReviewAction({ review, testIdReady, testIdPending, size = "md" }) {
  const tall = size === "lg" ? "min-h-[52px] text-base" : "min-h-[44px] text-sm";
  if (review && review.ready) {
    return (
      <a
        href={review.review_url}
        data-testid={testIdReady}
        className={`flex ${tall} items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 font-semibold text-white transition-colors hover:bg-emerald-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400`}
      >
        Review this game <span aria-hidden="true">→</span>
      </a>
    );
  }
  return (
    <div
      data-testid={testIdPending}
      className={`flex ${tall} items-center justify-center gap-2.5 rounded-xl border border-border px-4 text-muted-foreground`}
    >
      <span
        aria-hidden="true"
        className="cg-spin h-3.5 w-3.5 shrink-0 rounded-full border-2 border-border border-t-emerald-500"
      />
      {review && review.imported
        ? "Analysing your game…"
        : "Picking your game up from Lichess…"}
    </div>
  );
}

export function ResultCard({
  game,
  ourColor,
  review,
  onReview,
  onNewGame,
  busy,
  ratingPending,
}) {
  const { headline, reason } = resultWords(game, ourColor);
  const won = game.winner === ourColor;
  const drawn = !game.winner;

  return (
    <div
      className={`rounded-2xl border p-5 text-center ${
        drawn
          ? "border-border"
          : won
          ? "border-emerald-500/60 bg-emerald-500/5"
          : "border-rose-500/50 bg-rose-500/5"
      }`}
      data-testid="live-result-card"
    >
      <div
        className={`text-2xl font-bold ${
          drawn ? "" : won ? "text-emerald-400" : "text-rose-400"
        }`}
        data-testid="live-result-headline"
      >
        {headline}
      </div>
      {reason ? (
        <div className="mt-0.5 text-sm text-muted-foreground">{reason}</div>
      ) : null}

      <RatingLine game={game} pending={ratingPending} />

      <div className="mt-5 flex flex-col gap-2">
        <ReviewAction
          review={review}
          testIdReady="live-open-review"
          testIdPending="live-review-pending"
        />
        <button
          type="button"
          onClick={onNewGame}
          disabled={busy}
          data-testid="live-new-game"
          className="flex min-h-[44px] items-center justify-center rounded-lg border border-border px-4 text-sm font-medium"
        >
          New game
        </button>
      </div>
    </div>
  );
}

/** One line of the little crosstable: who, and what they are rated now. */
function ScoreRow({ name, rating, diff, mine, testId }) {
  return (
    <div
      className={`flex items-center justify-between gap-3 px-4 py-3 ${
        mine ? "bg-muted/50" : ""
      }`}
      data-testid={testId}
    >
      <div className="flex min-w-0 items-baseline gap-2">
        <span className="truncate text-sm font-medium text-foreground">{name}</span>
        {mine ? (
          <span className="shrink-0 text-xs text-muted-foreground">you</span>
        ) : null}
      </div>
      <div className="flex shrink-0 items-baseline gap-2">
        <span
          className={`text-sm tabular-nums ${
            mine ? "font-semibold text-foreground" : "text-muted-foreground"
          }`}
          data-testid={mine && rating != null ? "live-new-rating" : undefined}
        >
          {rating == null ? "—" : rating}
        </span>
        <RatingDelta diff={diff} testId={mine ? "live-rating-diff" : undefined} />
      </div>
    </div>
  );
}

/**
 * The game-over pop-up.
 *
 * Mohit, 2026-11-27, having just won a rated game on time: "this game ended
 * ... but no popup, on winning, it should show popup, the rating winner or
 * lost, all should come up as soon as game ends with a result."
 *
 * He was right that nothing happened. The result existed, but only as a card
 * in the right-hand column, swapping places with a locked panel that looked
 * much the same. On a phone that column sits below the board, so the end of a
 * game -- the one moment the screen actually has something to announce --
 * changed nothing in view.
 *
 * What it says, in the order it says it:
 *
 *   1. the verdict, large, in one of three words
 *   2. how the game ended, quietly
 *   3. a two-line crosstable: both players, both ratings, your change
 *   4. ONE primary action -- the review, which is the whole product
 *   5. the two ways out, side by side and deliberately lighter
 *
 * The crosstable replaced a floating rating with "against someone" under it.
 * A rated game is a transaction between two players and reads as one; it also
 * gives the unknown-rating case somewhere honest to sit (an em dash in the
 * cell, with a line underneath saying we are still asking) instead of a hole
 * where a number should be.
 *
 * No board in here, on purpose. On a phone this is a sheet at the bottom with
 * the real board still above it, and on a desktop the real board is behind the
 * dimmed overlay. A second copy of a board we are already showing is clutter,
 * not chess.
 *
 * It is dismissible, and dismissing leaves the identical result standing in
 * the sidebar. The pop-up is the announcement, not the only copy, so closing
 * it never costs the player the rating or the review link.
 *
 * Hand-rolled rather than the shared Radix dialog for one reason: this has to
 * be able to sit at the bottom of a phone screen as a sheet with the board
 * still visible above it, and the shared dialog is centred by construction.
 * The pieces Radix would have given us -- Escape, a focus trap, the aria
 * wiring, focus handed back on close -- are written out below instead,
 * because those are what make it usable rather than what make it pretty.
 */
export function ResultModal({
  game,
  ourColor,
  me,
  review,
  ratingPending,
  onDismiss,
  onNewGame,
  busy,
}) {
  const { headline, reason } = resultWords(game, ourColor);
  const won = game.winner === ourColor;
  const drawn = !game.winner;
  const panelRef = useRef(null);

  useEffect(() => {
    // Where focus was when the game ended, so closing puts it back.
    const previous = document.activeElement;
    // Focus the PANEL, not a control inside it.
    //
    // Focusing a control was the first version and it looked wrong the moment
    // it was on screen: Chrome treats a programmatic focus with no prior
    // interaction as keyboard focus, so "Look at the board" opened wearing a
    // ring and read as a second primary action next to the review. The panel
    // carries role=dialog and aria-labelledby, so landing here is what a
    // screen reader wants anyway, and Tab then walks the controls in order,
    // starting at the review.
    if (panelRef.current) panelRef.current.focus();
    return () => {
      if (previous && typeof previous.focus === "function") previous.focus();
    };
  }, []);

  // Escape closes, and Tab stays inside. Without the second half, tabbing
  // walks into the board behind the overlay, which cannot be seen or used.
  useEffect(() => {
    const onKey = (event) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onDismiss();
        return;
      }
      if (event.key !== "Tab" || !panelRef.current) return;
      const focusable = panelRef.current.querySelectorAll(
        'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])'
      );
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
  }, [onDismiss]);

  const opponent = game.opponent || {};
  const accent = drawn
    ? "bg-border"
    : won
    ? "bg-emerald-500"
    : "bg-rose-500";
  const showPending = game.our_rating == null && game.rated && ratingPending;
  // A casual game leaves an em dash in our rating cell with nothing to explain
  // it, which reads like a value that failed to load. It did not fail: there
  // is no number because nothing was at stake. Say that.
  const showCasual = !game.rated;

  return (
    <div
      className="cg-result-overlay fixed inset-0 z-50 flex items-end justify-center bg-background/80 backdrop-blur-sm sm:items-center sm:p-4"
      data-testid="live-result-overlay"
      onMouseDown={(event) => {
        // Only a press on the backdrop itself. A drag that began inside the
        // panel and ended out here is not a dismissal.
        if (event.target === event.currentTarget) onDismiss();
      }}
    >
      <style>{RESULT_STYLES}</style>
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="live-result-title"
        tabIndex={-1}
        data-testid="live-result-modal"
        className="cg-result-panel focus:outline-none w-full max-w-sm overflow-hidden rounded-t-2xl border border-border bg-card shadow-2xl sm:rounded-2xl"
      >
        {/* The only place the outcome is coloured besides the word itself.
            A fully tinted card shouts; a 3px rule states it. */}
        <div className={`h-[3px] w-full ${accent}`} aria-hidden="true" />

        <div className="px-6 pb-6 pt-5 text-center">
          <div
            id="live-result-title"
            className={`text-3xl font-bold leading-tight ${
              drawn ? "" : won ? "text-emerald-400" : "text-rose-400"
            }`}
            data-testid="live-modal-headline"
          >
            {headline}
          </div>
          {reason ? (
            <div className="mt-1 text-sm text-muted-foreground">{reason}</div>
          ) : null}

          <div className="mt-5 divide-y divide-border overflow-hidden rounded-xl border border-border text-left">
            <ScoreRow
              name={(me && me.username) || "You"}
              rating={game.our_rating}
              diff={game.our_rating_diff}
              mine
            />
            <ScoreRow
              name={opponent.username || "Opponent"}
              rating={game.opponent_rating_after || opponent.rating}
              testId="live-modal-opponent"
            />
          </div>

          {showPending ? (
            <div
              className="mt-2.5 text-xs text-muted-foreground"
              data-testid="live-rating-pending"
            >
              {RATING_PENDING_TEXT}
            </div>
          ) : null}

          {showCasual ? (
            <div
              className="mt-2.5 text-xs text-muted-foreground"
              data-testid="live-casual-note"
            >
              Casual game, so no rating changed.
            </div>
          ) : null}

          <div className="mt-6">
            <ReviewAction
              review={review}
              testIdReady="live-modal-review"
              testIdPending="live-modal-review-pending"
              size="lg"
            />
          </div>

          {/* Deliberately lighter than the review, and side by side so neither
              reads as the thing to do next. */}
          <div className="mt-2 grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={onNewGame}
              disabled={busy}
              data-testid="live-modal-new-game"
              className="flex min-h-[44px] items-center justify-center rounded-xl border border-border px-3 text-sm font-medium transition-colors hover:bg-muted disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              New game
            </button>
            <button
              type="button"
              onClick={onDismiss}
              data-testid="live-modal-close"
              className="flex min-h-[44px] items-center justify-center rounded-xl px-3 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              Look at the board
            </button>
          </div>
        </div>

        {/* A phone's home indicator sits over the bottom of a sheet. */}
        <div className="h-[env(safe-area-inset-bottom)] sm:hidden" aria-hidden="true" />
      </div>
    </div>
  );
}
