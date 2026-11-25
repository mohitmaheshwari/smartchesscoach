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

import React, { useMemo } from "react";
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

export function CapturedRow({ pieces, advantage }) {
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

export function PlayerCard({ name, rating, clockMs, pieces, advantage, active, testId }) {
  const total =
    clockMs === null || clockMs === undefined ? null : Math.max(0, Math.floor(clockMs / 1000));
  // Under a minute the clock is the only thing that matters on this card.
  const urgent = total !== null && total <= 30;
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
        {total === null
          ? "—:—"
          : `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`}
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

export function ResultCard({ game, ourColor, review, onReview, onNewGame, busy }) {
  const { headline, reason } = resultWords(game, ourColor);
  const won = game.winner === ourColor;
  const drawn = !game.winner;
  const diff = game.our_rating_diff;

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

      {/* Lichess's number, not ours. Absent rather than guessed if the export
          did not answer. */}
      {game.our_rating ? (
        <div className="mt-4 flex items-baseline justify-center gap-2">
          <span className="text-2xl font-semibold tabular-nums" data-testid="live-new-rating">
            {game.our_rating}
          </span>
          {typeof diff === "number" ? (
            <span
              className={`text-sm font-medium tabular-nums ${
                diff > 0 ? "text-emerald-400" : diff < 0 ? "text-rose-400" : "text-muted-foreground"
              }`}
              data-testid="live-rating-diff"
            >
              {diff > 0 ? `↑ ${diff}` : diff < 0 ? `↓ ${Math.abs(diff)}` : "±0"}
            </span>
          ) : null}
        </div>
      ) : null}

      <div className="mt-5 flex flex-col gap-2">
        {review && review.ready ? (
          <a
            href={review.review_url}
            data-testid="live-open-review"
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white"
          >
            Review this game →
          </a>
        ) : (
          <button
            type="button"
            disabled
            data-testid="live-review-pending"
            className="rounded-lg border border-border px-4 py-2 text-sm text-muted-foreground"
          >
            {review && review.imported
              ? "Analysing your game…"
              : "Picking your game up from Lichess…"}
          </button>
        )}
        <button
          type="button"
          onClick={onNewGame}
          disabled={busy}
          data-testid="live-new-game"
          className="rounded-lg border border-border px-4 py-2 text-sm font-medium"
        >
          New game
        </button>
      </div>
    </div>
  );
}
