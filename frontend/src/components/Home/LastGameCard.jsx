/**
 * LastGameCard
 *
 * Who was the better player in the game he just finished.
 *
 * Every other card on this page is built from his moves alone, because
 * `move_evaluations` only ever stored his side. This one reads both sides of
 * the PGN, which is why it can say something none of the others can: whether
 * he was outplayed, whether he outplayed them, and whether the board or the
 * clock decided it.
 *
 * Two rules it follows and the others do not:
 *   - no engine figure reaches the player. The numbers are in `measured`,
 *     for review, and are never rendered.
 *   - no counts, no streaks, no "your fourth time". One game, described once.
 *
 * It is laid out as the section below it is laid out -- board left, writing
 * right, `cg-` primitives, one quiet action -- because it is part of that
 * page and not a widget visiting it. Mohit, 2026-10-16, on the first cut:
 * *"UX sucks"*. That cut drew its own board out of unicode glyphs with a
 * text-shadow outline, stacked everything in a column and finished with a
 * full-width slab of teal, none of which this page does anywhere else.
 *
 * The review costs several seconds the first time a game is seen, so this
 * fetches on its own and renders nothing until it has an answer. It must
 * never hold up the rest of Home.
 */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Chessboard } from "react-chessboard";
import { ChevronRight, Clock3 } from "lucide-react";

import { API } from "@/App";

export default function LastGameCard() {
  const navigate = useNavigate();
  const [card, setCard] = useState(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await fetch(`${API}/coach/last-game-card`, { credentials: "include" });
        // 204 is the honest empty state: nothing to say, so show nothing.
        if (!alive || !res.ok || res.status === 204) return;
        const body = await res.json();
        if (alive && body && body.headline) setCard(body);
      } catch {
        /* Home must render without this card. */
      }
    })();
    return () => { alive = false; };
  }, []);

  if (!card) return null;
  const turning = card.turning_point || {};

  return (
    <section
      data-testid="last-game-card"
      className="mb-10 overflow-hidden rounded-[28px] border border-border/70 bg-card p-6 shadow-[0_24px_70px_-50px_rgba(15,23,42,0.35)] md:p-8"
    >
      <div className="flex flex-col gap-7 md:flex-row md:items-start md:gap-9">
        {turning.fen_before && (
          <div className="w-full max-w-[240px] shrink-0">
            <div className="aspect-square w-full">
              <Chessboard
                position={turning.fen_before}
                arePiecesDraggable={false}
                boardOrientation={turning.board_orientation === "black" ? "black" : "white"}
                customBoardStyle={{ borderRadius: "10px" }}
              />
            </div>
            {turning.san && (
              <p className="mt-3 text-[13px] leading-relaxed text-muted-foreground">
                {card.turning_point_is_theirs ? "They played " : "You played "}
                <span className="font-mono text-foreground">{turning.san}</span>
                {" here. It is where the game turned."}
              </p>
            )}
          </div>
        )}

        <div className="min-w-0 flex-1">
          <p className="cg-eyebrow !text-[10px]">Your last game</p>

          <h2 className="mt-3 font-heading text-[22px] leading-[1.2] tracking-[-0.025em] text-foreground md:text-[26px]">
            {card.headline}
          </h2>
          <p className="mt-3 max-w-[560px] text-[15px] leading-relaxed text-muted-foreground">
            {card.detail}
          </p>

          {card.decided_by === "clock" && card.state === "clock" && (
            <span className="mt-4 inline-flex items-center gap-1.5 rounded-full border border-amber-500/40 bg-amber-500/10 px-3 py-1 text-[11px] font-semibold text-amber-700 dark:text-amber-300">
              <Clock3 className="h-3 w-3" />
              The clock, not the board
            </span>
          )}

          <div>
            <button
              type="button"
              onClick={() => card.game_id && navigate(`/game/${card.game_id}`)}
              className="cg-secondary-action mt-6"
            >
              See the moment
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
