/**
 * EvalGraph — horizontal engine-evaluation timeline below the board.
 *
 * Built 2026-06-06. Plots white-POV eval across every ply of the game as a
 * filled area (white-better above the midline, black-better below). The
 * current move is marked; clicking anywhere seeks to that ply.
 *
 * Props:
 *   data         array  — decryption_v5_data (each item has eval_after + is_user_move).
 *   currentIndex number — index into data of the current move (-1 = start).
 *   onSeek       (idx)  — jump to ply idx (wires to goToMove).
 *
 * Data source: decryption_v5_data[i].eval_after — already on the frontend,
 * no backend change.
 */

const CLAMP_PAWNS = 6;      // y-scale cap, matches EvalBar
const W = 600;              // viewBox width (scales to container)
const H = 90;               // viewBox height

function clampPawns(evalCp) {
  if (evalCp == null) return 0;
  const p = evalCp / 100;
  return Math.max(-CLAMP_PAWNS, Math.min(CLAMP_PAWNS, p));
}

export default function EvalGraph({ data = [], currentIndex = -1, onSeek }) {
  const plies = Array.isArray(data) ? data.filter((d) => d && typeof d === "object") : [];
  if (plies.length < 3) return null;   // not enough to be a meaningful graph

  const n = plies.length;
  const midY = H / 2;
  const xFor = (i) => (n === 1 ? 0 : (i / (n - 1)) * W);
  const yFor = (evalCp) => midY - (clampPawns(evalCp) / CLAMP_PAWNS) * (H / 2 - 4);

  // Build the eval line points (use eval_after = position after that ply).
  const pts = plies.map((d, i) => `${xFor(i)},${yFor(d.eval_after)}`);
  const linePath = `M ${pts.join(" L ")}`;
  // Area fill down to the midline.
  const areaPath =
    `M ${xFor(0)},${midY} ` +
    plies.map((d, i) => `L ${xFor(i)},${yFor(d.eval_after)}`).join(" ") +
    ` L ${xFor(n - 1)},${midY} Z`;

  const curX = currentIndex >= 0 && currentIndex < n ? xFor(currentIndex) : null;

  const handleClick = (e) => {
    if (!onSeek) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const frac = (e.clientX - rect.left) / rect.width;
    const idx = Math.round(frac * (n - 1));
    onSeek(Math.max(0, Math.min(n - 1, idx)));
  };

  return (
    <div className="w-full" data-testid="eval-graph">
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1 px-1">
        Evaluation over the game · click to jump
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        className="w-full h-[72px] cursor-pointer rounded bg-neutral-900/90 border border-border/40"
        onClick={handleClick}
      >
        {/* midline (eval 0) */}
        <line x1="0" y1={midY} x2={W} y2={midY} stroke="rgba(255,255,255,0.25)" strokeWidth="1" />
        {/* area fill — white-ish, advantage shading */}
        <path d={areaPath} fill="rgba(230,230,230,0.55)" />
        {/* eval line */}
        <path d={linePath} fill="none" stroke="rgba(255,255,255,0.9)" strokeWidth="1.5" />
        {/* current-move marker */}
        {curX != null && (
          <>
            <line x1={curX} y1="0" x2={curX} y2={H} stroke="#22d3ee" strokeWidth="1.5" />
            <circle cx={curX} cy={yFor(plies[currentIndex].eval_after)} r="3.5" fill="#22d3ee" />
          </>
        )}
      </svg>
    </div>
  );
}
