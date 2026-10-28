import { Chess } from "chess.js";

/**
 * The frames the board plays to show what the card is talking about.
 *
 * Mohit 2026-10-28, looking at his Nxe4 card: "ik clearly asked you to build
 * arrow, but you didn't do that". The caption said "then d5 hits the bishop
 * and the knight at once" and the board showed nothing, because the only
 * thing that drew an arrow was a button -- and the fork is not true on the
 * position the card sits on. There the pawn is still on d7 and e4 is their
 * pawn, so an arrow from d5 would be drawn from an empty square.
 *
 * So the line is replayed and the fork arrows are drawn on the frame the
 * fork actually happens on. Every square comes from line_steps, computed on
 * the board in describe_line_steps, so the picture cannot disagree with the
 * sentence.
 *
 * Returns [] when there is nothing honest to show.
 */
export const buildLineFrames = (card, namesMoveInText) => {
  const steps = (card?.line_steps || {}).best || [];
  const fenBefore = card?.fen_before;
  if (!fenBefore || steps.length === 0) return [];

  // How far to play. The fork is the lesson, so stop there; otherwise stop
  // at the deepest ply whose move the caption actually names, and failing
  // that show the recommended move alone. Playing all eight plies says more
  // than the card does and takes ten seconds to say it.
  // Both searches look only at our own plies. A fork the OPPONENT gets in
  // this line is not the lesson, and matching their move by name is worse
  // than useless: in Mohit's own line "Nxe4" is both his move and their
  // recapture, so a search over every ply stopped on theirs by a string
  // collision and played a ply further than the card talks about.
  const caption = String(card.caption || "");
  const ours = (s) => s?.side === "mover";
  let last = steps.findIndex((s) => ours(s) && (s?.fork_targets || []).length >= 2);
  if (last < 0 && typeof namesMoveInText === "function") {
    for (let i = steps.length - 1; i >= 0; i -= 1) {
      if (ours(steps[i]) && namesMoveInText(caption, steps[i]?.san)) {
        last = i;
        break;
      }
    }
  }
  if (last < 0) last = 0;

  const frames = [];
  try {
    const game = new Chess(fenBefore);
    const drawn = [];
    for (let i = 0; i <= last; i += 1) {
      const done = game.move(steps[i].san);
      if (!done) break;
      // Ours in blue, theirs in grey, the ply that just landed in amber.
      drawn.forEach((a) => {
        if (a[2] === "amber") a[2] = "blue";
      });
      drawn.push([
        done.from,
        done.to,
        steps[i].side === "mover" ? "amber" : "palegrey",
      ]);
      const forks = (steps[i].fork_targets || []).map((sq) => [
        steps[i].to,
        sq,
        "red",
      ]);
      frames.push({
        san: steps[i].san,
        fen: game.fen(),
        arrows: drawn.map((a) => [...a]).concat(forks),
        highlights: steps[i].captured_square ? [steps[i].captured_square] : [],
      });
    }
  } catch (err) {
    // A line that will not replay shows nothing rather than something wrong.
    return [];
  }
  return frames;
};
