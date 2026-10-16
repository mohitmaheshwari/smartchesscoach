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
 * Three rules it follows and the others do not:
 *   - no engine figure reaches the player. The numbers are in `measured`,
 *     for review, and are never rendered.
 *   - no counts, no streaks, no "your fourth time". One game, described once.
 *   - the turning point is usually the OPPONENT'S mistake, so the card leads
 *     with the chance he was handed rather than a list of his errors.
 *
 * The review costs several seconds the first time a game is seen, so this
 * fetches on its own and renders nothing until it has an answer. It must
 * never hold up the rest of Home.
 */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronRight, Clock3 } from "lucide-react";

import { API } from "@/App";

const PIECES = {
  k: "♚", q: "♛", r: "♜", b: "♝", n: "♞", p: "♟",
};

/** The eight-by-eight from a FEN, oriented to the side he was playing. */
function Board({ fen, orientation }) {
  if (!fen) return null;
  const rows = fen.split(" ")[0].split("/").map((row) => {
    const out = [];
    for (const ch of row) {
      if (/\d/.test(ch)) for (let i = 0; i < Number(ch); i += 1) out.push(null);
      else out.push(ch);
    }
    return out;
  });
  const flip = orientation === "black";
  const order = flip ? [...Array(8).keys()].reverse() : [...Array(8).keys()];
  const squares = [];
  for (const r of order) {
    for (const f of flip ? [...Array(8).keys()].reverse() : [...Array(8).keys()]) {
      const piece = rows[r]?.[f];
      const light = (r + f) % 2 === 0;
      squares.push(
        <div
          key={`${r}-${f}`}
          className={`flex items-center justify-center ${light ? "bg-[#e7dcc6]" : "bg-[#9c8664]"}`}
        >
          {piece && (
            <span
              className="leading-none text-[min(5.4vw,1.35rem)]"
              style={
                piece === piece.toUpperCase()
                  ? { color: "#fcfcfb", textShadow: "0 0 1px #000,0 1px 1px #000,1px 0 1px #000,-1px 0 1px #000" }
                  : { color: "#15181d", textShadow: "0 0 1px #ece9e2,0 1px 1px #ece9e2,1px 0 1px #ece9e2,-1px 0 1px #ece9e2" }
              }
            >
              {PIECES[piece.toLowerCase()]}
            </span>
          )}
        </div>,
      );
    }
  }
  return (
    <div
      className="mt-3 grid aspect-square w-full max-w-[320px] grid-cols-8 overflow-hidden rounded-md border border-border/60"
      role="img"
      aria-label="The position where the game turned"
    >
      {squares}
    </div>
  );
}

const TONE = {
  clock: "text-amber-600 dark:text-amber-300",
  sharper: "text-emerald-600 dark:text-emerald-400",
  sharper_no_win: "text-emerald-600 dark:text-emerald-400",
  outplayed: "text-sky-700 dark:text-sky-300",
  even: "text-foreground",
};

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
    <div className="rounded-xl border border-border/60 bg-card p-4" data-testid="last-game-card">
      <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-muted-foreground/70">
        Your last game
      </p>

      <p className={`text-[1.02rem] font-semibold leading-snug ${TONE[card.state] || ""}`}>
        {card.headline}
      </p>
      <p className="mt-1.5 text-[13px] text-muted-foreground">{card.detail}</p>

      {card.decided_by === "clock" && card.state === "clock" && (
        <span className="mt-2.5 inline-flex items-center gap-1.5 rounded-full border border-amber-500/50 bg-amber-500/10 px-2.5 py-1 text-[11px] font-medium text-amber-700 dark:text-amber-300">
          <Clock3 className="h-3 w-3" />
          The clock, not the board
        </span>
      )}

      <Board fen={turning.fen_before} orientation={turning.board_orientation} />

      {turning.san && (
        <p className="mt-2.5 text-[13px] text-muted-foreground">
          {card.turning_point_is_theirs ? "They played " : "You played "}
          <span className="font-mono text-foreground">{turning.san}</span>
          {" here. It is where the game turned."}
        </p>
      )}

      <button
        type="button"
        onClick={() => card.game_id && navigate(`/game/${card.game_id}`)}
        className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-lg bg-teal-600 py-2.5 text-[14px] font-medium text-white transition hover:bg-teal-700"
      >
        See the moment
        <ChevronRight className="h-4 w-4" />
      </button>
    </div>
  );
}
