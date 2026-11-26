/**
 * The "finding an opponent" screen.
 *
 * A seek can sit for a minute in a quiet pool. The job of this screen is to
 * make that minute feel like the product working rather than a dead button.
 *
 * Everything stated here is true. The handle and rating are the player's real
 * Lichess ones, the pool is the seek we actually sent, the timer is real
 * elapsed seconds. There is deliberately no "searching among N players"
 * counter -- but the earlier reason given here was wrong and is corrected
 * below, because a false "we checked, it is impossible" stops anyone looking
 * again.
 *
 * What is actually true (checked 2026-11-26): Lichess's published API has no
 * site-wide online count -- the OpenAPI spec offers only /api/users/status
 * (per username) and /api/bot/online (bots). But the number IS real and is
 * NOT invented: lichess.org's own live counter is fed over their socket, and
 * Chessiro displays it as "Searching among 88,998 users", which matches what
 * third-party trackers report. So the figure exists; we simply have no
 * sanctioned way to read it. Reaching that socket means presenting as
 * Lichess's own web client, which would break silently whenever they change
 * the message format, so it is not done here.
 *
 * If we ever want this line, the honest routes are to ask Lichess for a
 * supported endpoint, or to show a number we own -- our measured time from
 * seek to pairing, which is what a player actually wants to know anyway.
 *
 * REBUILT 2026-11-26 after Mohit hit three faults on the live page:
 *
 *   1. The content was one `absolute inset-0` layer over the WHOLE card, and
 *      the card included the Cancel footer. `justify-between` therefore put
 *      the player plate exactly on top of the Cancel button. Now the board
 *      stage is its own positioned box and every other row is normal flow,
 *      so nothing can land on anything.
 *   2. The board was held at `opacity-[0.18]`, which on light paper is very
 *      nearly invisible — the screen read as washed-out mush rather than a
 *      board. It now sits at a legible strength, and the status block carries
 *      its own solid plate so text contrast never depends on what is behind.
 *   3. Nine saturated rainbow tiles drifting past read as a toy. The house
 *      style is mature premium. One accent, muted furniture, and the real
 *      payoff is an unknown plate turning into a named player.
 *
 * Mobile is the default here, not an afterthought: one column, every row in
 * flow, the board fluid and square, and Cancel a full 44px target.
 *
 * Motion is CSS only, and the whole thing holds still for anyone who asked
 * their system for reduced motion.
 */

import React, { useEffect, useRef, useState } from "react";
import LichessBoard from "@/components/LichessBoard";

const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

// Chess glyphs rather than a generic person icon: the player we have not met
// yet should still feel like a player, and this is a chess product.
const UNKNOWN_GLYPHS = ["♟", "♞", "♝", "♜", "♛"];

const STYLES = `
@keyframes cg-scan {
  0%   { transform: translateY(-100%); opacity: 0; }
  10%  { opacity: 1; }
  90%  { opacity: 1; }
  100% { transform: translateY(800%); opacity: 0; }
}
@keyframes cg-breathe {
  0%, 100% { box-shadow: 0 0 0 0 rgba(16,185,129,.40); }
  50%      { box-shadow: 0 0 0 10px rgba(16,185,129,0); }
}
@keyframes cg-land {
  0%   { transform: translateY(-4px); opacity: 0; }
  100% { transform: translateY(0); opacity: 1; }
}
@keyframes cg-fade {
  0%, 100% { opacity: .35; }
  50%      { opacity: .85; }
}
.cg-scan    { animation: cg-scan 3.4s cubic-bezier(.4,0,.2,1) infinite; }
.cg-breathe { animation: cg-breathe 2.4s ease-in-out infinite; }
.cg-land    { animation: cg-land .4s cubic-bezier(.22,1,.36,1) both; }
.cg-fade    { animation: cg-fade 2.4s ease-in-out infinite; }
@media (prefers-reduced-motion: reduce) {
  .cg-scan, .cg-breathe, .cg-land, .cg-fade { animation: none; }
  .cg-scan { opacity: .3; }
  .cg-fade { opacity: .7; }
}
`;

/** One player row: a tile, a name, a rating. Same shape both ends of the board. */
function Plate({ glyph, name, rating, tone, pulse, align, testId, landed }) {
  return (
    <div
      className={`flex min-w-0 items-center gap-3 ${
        align === "end" ? "flex-row-reverse text-right" : ""
      } ${landed ? "cg-land" : ""}`}
    >
      <div
        className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border text-xl leading-none ${tone} ${
          pulse ? "cg-breathe" : ""
        }`}
        aria-hidden="true"
      >
        {glyph}
      </div>
      <div className="min-w-0">
        <div
          className="truncate text-sm font-semibold text-foreground"
          data-testid={testId}
        >
          {name}
        </div>
        <div className="text-xs tabular-nums text-muted-foreground">
          {rating || "—"}
        </div>
      </div>
    </div>
  );
}

export default function LiveSearchBoard({
  timeControl,
  rated,
  waited,
  me,
  opponent, // set the moment Lichess pairs us — the payoff
  onCancel,
  busy,
}) {
  const [tick, setTick] = useState(0);
  const paired = Boolean(opponent);
  const liveRef = useRef(null);

  // Cycle the unknown opponent's glyph. Stops the instant we are paired.
  useEffect(() => {
    if (paired) return undefined;
    const id = setInterval(() => setTick((i) => i + 1), 900);
    return () => clearInterval(id);
  }, [paired]);

  // Screen readers get the state changes, not the animation.
  useEffect(() => {
    if (liveRef.current) {
      liveRef.current.textContent = paired
        ? `Paired with ${opponent.username || "an opponent"}`
        : `Still looking for a ${rated ? "rated" : "casual"} ${timeControl} opponent`;
    }
  }, [paired, opponent, rated, timeControl]);

  const unknownGlyph = UNKNOWN_GLYPHS[tick % UNKNOWN_GLYPHS.length];

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-card">
      <style>{STYLES}</style>

      {/* ── the far side of the board ───────────────────────────── */}
      <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
        {paired ? (
          <Plate
            landed
            glyph={"♞"}
            name={opponent.username || "Opponent"}
            rating={opponent.rating}
            tone="border-emerald-500/40 bg-emerald-500/10 text-foreground"
            testId="search-opponent"
          />
        ) : (
          <Plate
            glyph={unknownGlyph}
            name={"Looking…"}
            rating={null}
            tone="cg-fade border-border bg-muted text-muted-foreground"
          />
        )}
        <span className="shrink-0 rounded-md border border-border px-2 py-1 font-mono text-xs tabular-nums text-muted-foreground">
          {timeControl}
        </span>
      </div>

      {/* ── the board, with the status standing on its own plate ── */}
      <div className="relative">
        <div className="pointer-events-none select-none opacity-[0.45]">
          <LichessBoard
            fen={START_FEN}
            orientation="white"
            interactive={false}
            viewOnly
            showDests={false}
            disableArrows
            showCoordinates={false}
          />
        </div>

        {!paired && (
          <div
            className="pointer-events-none absolute inset-0 overflow-hidden"
            aria-hidden="true"
          >
            <div
              className="cg-scan absolute inset-x-0 h-[12.5%]"
              style={{
                background:
                  "linear-gradient(180deg, transparent, rgba(16,185,129,.20), transparent)",
              }}
            />
          </div>
        )}

        <div className="pointer-events-none absolute inset-0 flex items-center justify-center p-4">
          <div className="pointer-events-auto max-w-full rounded-xl border border-border bg-card/95 px-5 py-4 text-center shadow-sm backdrop-blur-sm">
            <div
              className="text-base font-semibold text-foreground"
              data-testid="search-headline"
            >
              {paired ? "Opponent found" : "Finding an opponent"}
            </div>
            <div className="mt-1 text-sm text-muted-foreground">
              {rated ? "Rated" : "Casual"} · {timeControl} · on Lichess
            </div>
            {!paired && (
              <div
                className="mt-1 font-mono text-xs tabular-nums text-muted-foreground"
                data-testid="search-elapsed"
              >
                {waited}s
              </div>
            )}
            <div
              ref={liveRef}
              className="sr-only"
              role="status"
              aria-live="polite"
            />
          </div>
        </div>
      </div>

      {/* ── our side: their real Lichess identity, never a placeholder ── */}
      <div className="flex items-center justify-between gap-3 border-t border-border px-4 py-3">
        <Plate
          glyph={"♚"}
          name={(me && me.username) || "You"}
          rating={me && me.rating}
          tone="border-border bg-muted text-foreground"
          pulse={!paired}
          testId="search-me"
        />
        <span className="shrink-0 text-xs text-muted-foreground">You</span>
      </div>

      {!paired && (
        <div className="border-t border-border p-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            data-testid="live-cancel-seek"
            className="flex min-h-[44px] w-full items-center justify-center rounded-lg text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50"
          >
            Cancel search
          </button>
        </div>
      )}
    </div>
  );
}
