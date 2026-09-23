/**
 * Is the game still following the authored opening line?
 *
 * The opening ideas returned by /coach/play/start are indexed by PLY, so
 * idea[n] only describes the real board while every move so far has matched
 * the line. Nothing checked that: once either side deviated,
 * openingIdeas[gamePly] returned a move for a position that no longer existed
 * and its arrow was drawn on the board anyway.
 *
 * Reported 2026-09-23: the Scotch line was loaded, the coach answered d6
 * (Philidor), and ply 4 still drew Nf3->e5. Stockfish at depth 20 puts
 * 3.Nxe5 dxe5 at -625cp (L:100%) -- the e5 pawn is defended by d6, so the
 * arrow pointed at a move that drops a knight.
 *
 * Deviating from a line is not a mistake. We simply stop guiding from a line
 * nobody is playing any more.
 *
 * Lives in its own module so the guard and its tests share one definition
 * instead of a copy that can drift.
 */
export const isOnAuthoredLine = (moveHistory, ideas) => {
  if (!ideas || !ideas.length) return false;
  const played = (moveHistory || []).map((m) => m?.san || m?.move || "");
  return played.every((san, i) => !ideas[i]?.move || san === ideas[i].move);
};

export default isOnAuthoredLine;
