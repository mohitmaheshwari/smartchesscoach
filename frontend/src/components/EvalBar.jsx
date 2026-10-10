/**
 * EvalBar — vertical engine-evaluation bar beside the board (chess.com style).
 *
 * Built 2026-06-06. Reads the current move's white-POV centipawn eval and
 * fills white-from-bottom / dark-from-top proportional to who's winning.
 * Flips with board orientation so "your side" is always at the bottom.
 *
 * Props:
 *   evalCp      number | null  — white-POV centipawns (e.g. +30 = white +0.3).
 *   mateIn      number | null  — signed mate distance (white POV); + = white mates.
 *   orientation "white"|"black" — board orientation (bar flips to match).
 *
 * Data source: decryption_v5_data[i].eval_after (already on the frontend).
 */

// Clamp eval to +-6 pawns for the visual scale — beyond that the side is
// just "winning". Most decisive-but-not-mating evals live within this band.
const CLAMP_PAWNS = 6;

function whiteFraction(evalCp, mateIn) {
  // Mate dominates: full bar to the mating side.
  if (mateIn != null) return mateIn > 0 ? 1 : 0;
  if (evalCp == null) return 0.5;
  const pawns = Math.max(-CLAMP_PAWNS, Math.min(CLAMP_PAWNS, evalCp / 100));
  // Linear map: eval 0 -> 0.5, +CLAMP -> 1.0 (all white), -CLAMP -> 0.0.
  return 0.5 + (pawns / CLAMP_PAWNS) * 0.5;
}

function evalLabel(evalCp, mateIn) {
  if (mateIn != null) return `M${Math.abs(mateIn)}`;
  if (evalCp == null) return "0.0";
  const pawns = evalCp / 100;
  const sign = pawns > 0 ? "+" : "";
  return `${sign}${pawns.toFixed(1)}`;
}

export default function EvalBar({ evalCp = null, mateIn = null, orientation = "white" }) {
  const wf = whiteFraction(evalCp, mateIn);          // 0..1 white share
  const whitePct = Math.round(wf * 100);
  const label = evalLabel(evalCp, mateIn);

  // When the board is oriented for black, the bottom of the board is black's
  // side — so the white fill should come from the TOP instead of the bottom.
  const whiteFromBottom = orientation === "white";

  return (
    <div
      // 2026-10-10: the bar WAS rendering on the review screen and could not be
      // seen - bg-neutral-800 on a near-black page is almost no contrast, and
      // when one side is winning there is barely any white fill left to read.
      // Matched to the Play-with-Coach bar (coach-play/EvalBar.jsx): the same
      // gradient surface and border, so the two eval bars in the product stop
      // looking like two different components.
      className="relative w-6 md:w-7 rounded-md overflow-hidden border border-zinc-700 bg-gradient-to-b from-zinc-800 via-zinc-700 to-zinc-800 select-none"
      style={{ height: "100%" }}
      data-testid="eval-bar"
      title={`Engine eval: ${label} (${label.startsWith("-") ? "Black" : "White"} better)`}
    >
      {/* White fill */}
      <div
        className="absolute left-0 right-0 bg-neutral-100 transition-[height,top,bottom] duration-300 ease-out"
        style={
          whiteFromBottom
            ? { bottom: 0, height: `${whitePct}%` }
            : { top: 0, height: `${whitePct}%` }
        }
      />
      {/* Numeric eval, centred on its own chip - same treatment as the
          Play-with-Coach bar. Centring means it stays legible whichever side
          is winning, instead of sitting on a sliver of fill at one end. */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <span className="px-1 py-0.5 rounded text-[10px] md:text-[11px] font-bold leading-none tabular-nums bg-zinc-900/85 text-neutral-100 shadow-sm">
          {label}
        </span>
      </div>
    </div>
  );
}
