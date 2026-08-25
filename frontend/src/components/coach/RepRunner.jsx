/**
 * RepRunner — the one board-first rep component.
 *
 * A "rep" is a single live decision on a board, answered in seconds and
 * corrected immediately. See docs/coached_experience_design.md.
 *
 * DESIGN RULES THIS COMPONENT ENFORCES
 * ------------------------------------
 * 1. The board is the screen. One line of text above it, one line after. No
 *    side panel of prose — a coach who only talks does not get paid.
 * 2. Correctness is never signalled by colour alone: every verdict carries a
 *    glyph and words.
 * 3. The demonstration happens ON the board (arrow + highlighted squares), not
 *    in a sentence describing what would have happened.
 * 4. Mobile first. The board stays visible while answering; nothing the player
 *    must read or tap sits below the fold.
 *
 * This component is presentational. It renders one rep and reports the answer.
 * Fetching, ordering and session state belong to the caller, so every rep type
 * and every future concept reuses this one runner. If a second rep component
 * ever appears, the abstraction has failed.
 */

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Chessboard } from "react-chessboard";
import {
  SQUARE_ANSWER_TYPES,
  buildRepView,
  isAnswerCorrect,
  repArrows,
  revealHighlights,
} from "@/lib/repView";

const SQUARE_HIGHLIGHT = "rgba(239, 68, 68, 0.45)";

export default function RepRunner({ rep, index = 0, total = 0, onAnswer, onNext }) {
  const [selected, setSelected] = useState(null);
  const [revealed, setRevealed] = useState(false);

  useEffect(() => {
    setSelected(null);
    setRevealed(false);
  }, [rep?.fen, rep?.rep_type, rep?.move_uci]);

  // View geometry lives in @/lib/repView so it can be unit-tested; CI renders
  // no components.
  const { displayFen, orientation } = useMemo(() => buildRepView(rep), [rep]);

  const demo = rep?.demonstration || {};

  const isCorrect = useMemo(
    () => (selected == null ? null : isAnswerCorrect(rep, selected)),
    [selected, rep]
  );

  const submit = useCallback(
    (value) => {
      if (revealed || !rep) return;
      setSelected(value);
      setRevealed(true);
      onAnswer?.(isAnswerCorrect(rep, value), rep, value);
    },
    [revealed, rep, onAnswer]
  );

  const handleSquareClick = useCallback(
    (square) => {
      if (!SQUARE_ANSWER_TYPES.has(rep?.rep_type)) return;
      submit(square);
    },
    [rep, submit]
  );

  /** Highlights: only after the answer, so nothing gives the answer away. */
  const squareStyles = useMemo(() => {
    const styles = {};
    revealHighlights(rep, revealed).forEach((sq) => {
      styles[sq] = { background: SQUARE_HIGHLIGHT };
    });
    if (revealed && selected && SQUARE_ANSWER_TYPES.has(rep?.rep_type)) {
      styles[selected] = {
        ...(styles[selected] || {}),
        boxShadow: "inset 0 0 0 3px rgba(59,130,246,0.9)",
      };
    }
    return styles;
  }, [rep, revealed, selected]);

  const arrows = useMemo(() => repArrows(rep, revealed), [rep, revealed]);

  if (!rep || !displayFen) return null;

  return (
    <div className="w-full max-w-[560px] mx-auto flex flex-col gap-3">
      {/* Board — always first, always dominant. */}
      <div className="w-full rounded-lg overflow-hidden ring-1 ring-border">
        <Chessboard
          position={displayFen}
          boardOrientation={orientation}
          arePiecesDraggable={false}
          onSquareClick={handleSquareClick}
          customArrows={arrows}
          customSquareStyles={squareStyles}
          customBoardStyle={{ borderRadius: 0 }}
        />
      </div>

      {/* One line. Before the answer it frames the decision; after, it names
          what happened. It never does both. */}
      <p className="text-[15px] leading-snug text-foreground min-h-[2.5rem]">
        {revealed ? (
          <span className="flex items-start gap-2">
            <span aria-hidden="true" className="mt-[1px]">
              {isCorrect ? "✓" : "✗"}
            </span>
            <span>
              <span className="sr-only">{isCorrect ? "Correct. " : "Not quite. "}</span>
              {demo.caption}
            </span>
          </span>
        ) : (
          rep.prompt
        )}
      </p>

      {/* Answer controls */}
      {!revealed && rep.rep_type === "is_safe" && (
        <div className="grid grid-cols-2 gap-3">
          <button
            type="button"
            onClick={() => submit("safe")}
            className="py-3 rounded-lg border border-border text-[15px] font-medium
                       hover:bg-muted/50 focus:outline-none focus-visible:ring-2
                       focus-visible:ring-primary"
          >
            Safe
          </button>
          <button
            type="button"
            onClick={() => submit("not_safe")}
            className="py-3 rounded-lg border border-border text-[15px] font-medium
                       hover:bg-muted/50 focus:outline-none focus-visible:ring-2
                       focus-visible:ring-primary"
          >
            Not safe
          </button>
        </div>
      )}

      {!revealed && SQUARE_ANSWER_TYPES.has(rep.rep_type) && (
        <p className="text-[13px] text-muted-foreground">Tap a square on the board.</p>
      )}

      {revealed && (
        <button
          type="button"
          onClick={() => onNext?.()}
          autoFocus
          className="py-3 rounded-lg bg-primary text-primary-foreground text-[15px]
                     font-medium focus:outline-none focus-visible:ring-2
                     focus-visible:ring-primary"
        >
          Next
        </button>
      )}

      {total > 0 && (
        <p className="text-[12px] text-muted-foreground text-center tabular-nums">
          {Math.min(index + 1, total)} / {total}
        </p>
      )}
    </div>
  );
}

