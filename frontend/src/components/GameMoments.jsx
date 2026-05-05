/**
 * GameMoments — stacked turning points of the game.
 *
 * Real coaching shows multiple moments per game, not just one. This
 * component renders the up-to-4 key blunders the orchestrator picked,
 * each with its own mini board (frozen at fen_before, with the user's
 * move arrow) and 2-3 sentence Plan Decryption prose.
 *
 * Reads the `moments` array from decryption_block. Hidden when the
 * array is empty or absent (older cached games).
 */

import { useState } from "react";
import LichessBoard from "@/components/LichessBoard";
import InteractiveMoment from "@/components/InteractiveMoment";
import { ChevronDown, ChevronUp } from "lucide-react";

function MomentCard({ moment, userColor, defaultOpen }) {
  const [open, setOpen] = useState(!!defaultOpen);

  const moveUci = moment?.move_uci;
  const arrows = moveUci && moveUci.length >= 4
    ? [[moveUci.slice(0, 2), moveUci.slice(2, 4), "#dc2626"]]
    : [];
  const orientation = userColor === "black" ? "black" : "white";

  return (
    <div
      className={`rounded-2xl border ${
        moment.is_pivot
          ? "border-amber-500/30 bg-gradient-to-b from-amber-500/[0.03] to-transparent"
          : "border-border/40 bg-muted/20"
      } overflow-hidden`}
    >
      {/* Header — always visible, click to expand/collapse */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between gap-3 p-4 md:p-5 text-left hover:bg-muted/30 transition-colors"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2 flex-wrap">
            <span className="text-[10.5px] uppercase tracking-[0.18em] text-muted-foreground font-semibold">
              Move {moment.move_number}
            </span>
            <span className="font-serif text-[15px] text-foreground/85">
              {moment.move_san}
            </span>
            {moment.is_pivot && (
              <span className="text-[10px] uppercase tracking-wider text-amber-600 dark:text-amber-300 font-semibold">
                · pivot
              </span>
            )}
          </div>
        </div>
        {open ? (
          <ChevronUp className="w-4 h-4 text-muted-foreground" strokeWidth={2} />
        ) : (
          <ChevronDown className="w-4 h-4 text-muted-foreground" strokeWidth={2} />
        )}
      </button>

      {/* Body — interactive puzzle when candidates are available,
          static board+prose fallback otherwise. */}
      {open && (
        <div className="px-4 pb-5 md:px-5 md:pb-6">
          {moment.candidates && moment.candidates.length >= 2 ? (
            <InteractiveMoment
              fen={moment.fen_before}
              userColor={userColor}
              moveNumber={moment.move_number}
              candidates={moment.candidates}
            />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-[200px_1fr] gap-5 md:gap-6 items-start">
              <div className="aspect-square w-full max-w-[200px] mx-auto md:mx-0">
                <LichessBoard
                  fen={moment.fen_before}
                  orientation={orientation}
                  viewOnly={true}
                  arrows={arrows}
                />
              </div>
              <div className="self-center">
                <p className="text-[14.5px] md:text-[15px] text-foreground/90 leading-relaxed">
                  {moment.text}
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function GameMoments({ moments, userColor }) {
  if (!moments || moments.length === 0) return null;

  return (
    <section
      data-testid="game-moments"
      className="max-w-[680px] mx-auto px-6 pb-10 md:pb-14"
    >
      <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-5">
        The turning points · {moments.length} moments
      </div>

      <div className="space-y-3">
        {moments.map((m, i) => (
          <MomentCard
            key={`${m.move_number}-${m.move_san}`}
            moment={m}
            userColor={userColor}
            defaultOpen={i === 0}
          />
        ))}
      </div>
    </section>
  );
}
