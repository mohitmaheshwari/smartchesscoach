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
  // White advantage is positive eval. Label sits on whichever side is winning.
  const whiteWinning = wf >= 0.5;

  // When the board is oriented for black, the bottom of the board is black's
  // side — so the white fill should come from the TOP instead of the bottom.
  const whiteFromBottom = orientation === "white";

  return (
    <div
      className="relative w-5 md:w-6 rounded overflow-hidden border border-border/50 bg-neutral-800 select-none"
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
      {/* Numeric eval — on the winning side, in contrasting color */}
      <span
        className={`absolute left-0 right-0 text-center text-[9px] md:text-[10px] font-semibold tabular-nums ${
          whiteWinning ? "text-neutral-800" : "text-neutral-100"
        }`}
        style={
          // Put the label at the winning side's end of the bar.
          whiteWinning === whiteFromBottom
            ? { bottom: 2 }
            : { top: 2 }
        }
      >
        {label}
      </span>
    </div>
  );
}
