/**
 * The "finding an opponent" screen.
 *
 * A seek can sit for a minute in a quiet pool. The job of this screen is to
 * make that minute feel like the product working rather than a dead button —
 * which is exactly how the first version read.
 *
 * Everything stated here is true. The handle and rating are the player's real
 * Lichess ones, the pool is the seek we actually sent, the timer is real
 * elapsed seconds. There is deliberately no "searching among N players"
 * counter: Lichess publishes no online-player count (`/api/count` and
 * `/api/users/online` are 404, `/api/status` is API-version info, and the
 * numbers on their homepage are per-tournament), so any such figure would be
 * invented. The motion carries the feeling instead of a made-up number.
 *
 * Motion is CSS only — no animation library, nothing to pull into the bundle —
 * and the whole thing holds still for anyone who asked their system for
 * reduced motion.
 */

import React, { useEffect, useRef, useState } from "react";
import LichessBoard from "@/components/LichessBoard";

const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

// Chess glyphs rather than generic person icons: the candidates drifting past
// should feel like players, and this is a chess product.
const CANDIDATES = ["♟", "♞", "♝", "♜", "♛", "♞", "♟", "♝", "♜"];

const STYLES = `
@keyframes cg-sweep {
  0%   { transform: translateX(-120%) skewX(-12deg); opacity: 0; }
  12%  { opacity: 1; }
  88%  { opacity: 1; }
  100% { transform: translateX(220%) skewX(-12deg); opacity: 0; }
}
@keyframes cg-drift {
  0%   { transform: translateX(0); }
  100% { transform: translateX(-50%); }
}
@keyframes cg-breathe {
  0%, 100% { transform: scale(1);    box-shadow: 0 0 0 0 rgba(16,185,129,.45); }
  50%      { transform: scale(1.04); box-shadow: 0 0 0 14px rgba(16,185,129,0); }
}
@keyframes cg-land {
  0%   { transform: scale(.7); opacity: 0; }
  60%  { transform: scale(1.12); opacity: 1; }
  100% { transform: scale(1); opacity: 1; }
}
.cg-sweep   { animation: cg-sweep 2.6s cubic-bezier(.4,0,.2,1) infinite; }
.cg-drift   { animation: cg-drift 18s linear infinite; }
.cg-breathe { animation: cg-breathe 2.2s ease-in-out infinite; }
.cg-land    { animation: cg-land .45s cubic-bezier(.34,1.56,.64,1) both; }
@media (prefers-reduced-motion: reduce) {
  .cg-sweep, .cg-drift, .cg-breathe, .cg-land { animation: none; }
  .cg-sweep { opacity: .35; }
}
`;

function Avatar({ glyph, tone, focused }) {
  return (
    <div
      className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-xl transition-all duration-300 ${tone} ${
        focused
          ? "scale-110 ring-2 ring-emerald-400 brightness-110"
          : "opacity-60"
      }`}
      aria-hidden
    >
      <span className="drop-shadow">{glyph}</span>
    </div>
  );
}

// Named scale, not raw hex: the repo's design-system check caps distinct hex
// values precisely so component-local palettes do not accumulate.
const TONES = [
  "bg-violet-600", "bg-emerald-600", "bg-amber-600", "bg-pink-600",
  "bg-cyan-600", "bg-lime-600", "bg-purple-600", "bg-rose-600", "bg-sky-600",
];
const ME_TONE = "bg-pink-600";

export default function LiveSearchBoard({
  timeControl,
  rated,
  waited,
  me,
  opponent,          // set the moment Lichess pairs us — the payoff
  onCancel,
  busy,
}) {
  const [focus, setFocus] = useState(0);
  const paired = Boolean(opponent);
  const liveRef = useRef(null);

  // Move the focus ring along the rail. Stops the instant we are paired.
  useEffect(() => {
    if (paired) return undefined;
    const tick = setInterval(
      () => setFocus((i) => (i + 1) % CANDIDATES.length),
      600
    );
    return () => clearInterval(tick);
  }, [paired]);

  // Screen readers get the state changes, not the animation.
  useEffect(() => {
    if (liveRef.current) {
      liveRef.current.textContent = paired
        ? `Paired with ${opponent.username || "an opponent"}`
        : `Still looking for a ${rated ? "rated" : "casual"} ${timeControl} opponent`;
    }
  }, [paired, opponent, rated, timeControl]);

  return (
    <div className="relative overflow-hidden rounded-2xl border border-border bg-card">
      <style>{STYLES}</style>

      {/* The real board, held back so the search reads on top of it. It is the
          position they are about to play, not decoration. */}
      <div className="pointer-events-none select-none opacity-[0.18]">
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

      {/* radar sweep */}
      {!paired && (
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div
            className="cg-sweep absolute inset-y-0 w-1/3"
            style={{
              background:
                "linear-gradient(90deg, transparent, rgba(16,185,129,.16), transparent)",
            }}
          />
        </div>
      )}

      <div className="absolute inset-0 flex flex-col items-center justify-between p-5">
        {/* the opponent end of the board */}
        <div className="w-full">
          {paired ? (
            <div className="cg-land flex items-center justify-center gap-3">
              <div
                className={`flex h-12 w-12 items-center justify-center rounded-xl text-xl ring-2 ring-emerald-400 ${TONES[0]}`}
                aria-hidden
              >
                ♞
              </div>
              <div className="text-left">
                <div className="font-semibold" data-testid="search-opponent">
                  {opponent.username || "Opponent"}
                </div>
                {opponent.rating ? (
                  <div className="text-xs text-muted-foreground">
                    {opponent.rating}
                  </div>
                ) : null}
              </div>
            </div>
          ) : (
            <div className="relative overflow-hidden">
              <div className="cg-drift flex gap-3 will-change-transform">
                {[...CANDIDATES, ...CANDIDATES].map((glyph, i) => (
                  <Avatar
                    key={i}
                    glyph={glyph}
                    tone={TONES[i % TONES.length]}
                    focused={i % CANDIDATES.length === focus}
                  />
                ))}
              </div>
              {/* fade the rail into the edges so it reads as endless */}
              <div className="pointer-events-none absolute inset-y-0 left-0 w-12 bg-gradient-to-r from-card to-transparent" />
              <div className="pointer-events-none absolute inset-y-0 right-0 w-12 bg-gradient-to-l from-card to-transparent" />
            </div>
          )}
        </div>

        {/* what is actually happening */}
        <div className="text-center">
          <div className="text-base font-semibold" data-testid="search-headline">
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
          <div ref={liveRef} className="sr-only" role="status" aria-live="polite" />
        </div>

        {/* our end of the board: their real Lichess identity, not a placeholder */}
        <div className="flex w-full items-center justify-center gap-3">
          <div
            className={`flex h-12 w-12 items-center justify-center rounded-xl text-xl ${ME_TONE} ${
              paired ? "" : "cg-breathe"
            }`}
            aria-hidden
          >
            ♔
          </div>
          <div className="text-left">
            <div className="font-semibold" data-testid="search-me">
              {(me && me.username) || "You"}
            </div>
            {me && me.rating ? (
              <div className="text-xs text-muted-foreground">{me.rating}</div>
            ) : null}
          </div>
        </div>
      </div>

      {!paired && (
        <div className="relative border-t border-border p-3 text-center">
          <button
            onClick={onCancel}
            disabled={busy}
            data-testid="live-cancel-seek"
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            Cancel search
          </button>
        </div>
      )}
    </div>
  );
}
