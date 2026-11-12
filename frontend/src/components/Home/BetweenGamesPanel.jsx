/**
 * BetweenGamesPanel
 *
 * What a coach says between games: the opening habit that keeps costing him,
 * and -- only when his own games prove it -- that long sittings cost him.
 *
 * docs/coach_pages_scope.md. Reads GET /home/between-games, which reads one
 * per-player file the analysis worker keeps current, so this never computes
 * anything on the page. Behind BETWEEN_GAMES_USERS on the server: for anyone
 * else the endpoint answers {enabled: false} and this renders nothing.
 *
 * Rules carried from LastGameCard: no figure reaches the player (the server
 * keeps numbers in `measured`, never rendered); chess notation only in mono
 * spans; board left, writing right, cg- primitives.
 */
import { useEffect, useState } from "react";
import { Chessboard } from "react-chessboard";
import { Coffee } from "lucide-react";

import { API } from "@/App";

const POLL_MS = 6000;
const MAX_POLLS = 10;

function OpeningHabit({ habit }) {
  const side = habit.side === "black" ? "Black" : "White";
  return (
    <div
      className="flex flex-col gap-6 md:flex-row md:items-start md:gap-8"
      data-testid="between-games-opening"
    >
      <div className="w-full max-w-[220px] shrink-0">
        <div className="aspect-square w-full">
          <Chessboard
            position={habit.fen}
            arePiecesDraggable={false}
            boardOrientation={habit.side === "black" ? "black" : "white"}
            customBoardStyle={{ borderRadius: "10px" }}
            customArrows={[
              [habit.played_from, habit.played_to, "#b45309"],
              [habit.better_from, habit.better_to, "#047857"],
            ]}
            customSquareStyles={{
              [habit.played_to]: { background: "rgba(180,83,9,0.25)" },
              [habit.better_to]: { background: "rgba(4,120,87,0.22)" },
            }}
          />
        </div>
      </div>
      <div className="min-w-0 flex-1">
        <p className="cg-eyebrow !text-[10px]">
          {side} · <span className="font-mono normal-case tracking-normal">{habit.line}</span>
        </p>
        <h3 className="mt-3 font-heading text-[19px] leading-[1.25] tracking-[-0.02em] text-foreground md:text-[21px]">
          {habit.headline}
        </h3>
        <p className="mt-2 max-w-[520px] text-[15px] leading-relaxed text-muted-foreground">
          {habit.detail}
        </p>
        <p className="mt-4 text-[14px] leading-relaxed text-foreground/90">
          You played <span className="font-mono text-amber-700 dark:text-amber-400">{habit.san}</span> here.
          {" "}Better was <span className="font-mono text-emerald-700 dark:text-emerald-400">{habit.better_san}</span>.
        </p>
      </div>
    </div>
  );
}

export default function BetweenGamesPanel() {
  const [data, setData] = useState(null);

  useEffect(() => {
    let alive = true;
    let polls = 0;
    let timer = null;
    const load = async () => {
      try {
        const res = await fetch(`${API}/home/between-games`, { credentials: "include" });
        if (!alive || !res.ok) return;
        const body = await res.json();
        if (!alive) return;
        setData(body);
        // The first visit builds the file in the background; ask again shortly.
        if (body?.enabled && body.state === "building" && polls < MAX_POLLS) {
          polls += 1;
          timer = setTimeout(load, POLL_MS);
        }
      } catch {
        /* Home must render without this panel. */
      }
    };
    load();
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }, []);

  if (!data || !data.enabled) return null;

  if (data.state === "building") {
    return (
      <section
        data-testid="between-games-building"
        className="mb-10 rounded-[28px] border border-border/70 bg-card p-6 md:p-8"
      >
        <p className="cg-eyebrow !text-[10px]">Between games</p>
        <p className="mt-3 text-[15px] leading-relaxed text-muted-foreground">
          Your coach is reading your games. This takes a moment the first time.
        </p>
      </section>
    );
  }

  const openings = Array.isArray(data.openings) ? data.openings : [];
  const sitting = data.sitting || {};
  if (!openings.length && !sitting.show) return null;

  return (
    <section
      data-testid="between-games-panel"
      className="mb-10 overflow-hidden rounded-[28px] border border-border/70 bg-card p-6 shadow-[0_24px_70px_-50px_rgba(15,23,42,0.35)] md:p-8"
    >
      <p className="cg-eyebrow !text-[10px]">Before your next game</p>

      {sitting.show && (
        <div
          data-testid="between-games-sitting"
          className={`mt-4 flex items-start gap-3 rounded-2xl border p-4 ${
            sitting.live
              ? "border-amber-500/40 bg-amber-500/10"
              : "border-border/70 bg-muted/30"
          }`}
        >
          <Coffee
            className={`mt-0.5 h-5 w-5 shrink-0 ${
              sitting.live ? "text-amber-700 dark:text-amber-300" : "text-muted-foreground"
            }`}
            aria-hidden="true"
          />
          <div className="min-w-0">
            <p className="text-[15px] font-semibold text-foreground">{sitting.headline}</p>
            <p className="mt-1 text-[14px] leading-relaxed text-muted-foreground">{sitting.detail}</p>
          </div>
        </div>
      )}

      {openings.length > 0 && (
        <div className="mt-7">
          <h2 className="font-heading text-[22px] leading-[1.2] tracking-[-0.025em] text-foreground md:text-[24px]">
            Your openings
          </h2>
          <div className="mt-6 space-y-9">
            {openings.map((habit) => (
              <OpeningHabit key={`${habit.side}-${habit.line}-${habit.idea}`} habit={habit} />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
