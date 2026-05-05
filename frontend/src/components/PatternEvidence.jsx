/**
 * PatternEvidence — visual proof of the pattern that broke the game.
 *
 * When a Lab card carries an urgent king-safety chip and the user
 * clicks through, this is what they see: a frozen mini board at the
 * critical moment, with the king highlighted, red arrows from every
 * piece pointed at the king zone, and a coach-voice caption beneath.
 *
 * Reads `pattern_evidence` from the V5 endpoint payload. Hidden when
 * the field is null (game without a tracked pattern, or pattern type
 * we haven't built an evidence extractor for yet).
 */

import LichessBoard from "@/components/LichessBoard";

export default function PatternEvidence({ patternEvidence, userColor }) {
  if (!patternEvidence || !patternEvidence.fen) return null;

  const {
    fen,
    pattern,
    move_number: moveNumber,
    highlighted_squares: highlightedSquares = [],
    arrows: rawArrows = [],
    caption,
  } = patternEvidence;

  // LichessBoard takes arrows as [from, to, color] tuples. Threats render red.
  const arrows = rawArrows.map((a) => [a.from, a.to, "#dc2626"]);

  const orientation = userColor === "black" ? "black" : "white";

  const headerLabel =
    pattern === "king_safety"
      ? "King-safety evidence"
      : pattern === "piece_safety"
      ? "Piece-safety evidence"
      : "Evidence";

  return (
    <section
      data-testid="pattern-evidence"
      className="max-w-[680px] mx-auto px-6 pb-10 md:pb-14"
    >
      <div className="text-[10.5px] uppercase tracking-[0.22em] text-rose-500 dark:text-rose-300 font-semibold mb-5">
        {headerLabel}
        {moveNumber ? ` · move ${moveNumber}` : ""}
      </div>

      <div className="rounded-2xl border border-rose-500/25 bg-gradient-to-b from-rose-500/[0.04] to-transparent p-6 md:p-7">
        <div className="grid grid-cols-1 md:grid-cols-[260px_1fr] gap-6 md:gap-8 items-start">
          {/* Mini board */}
          <div className="aspect-square w-full max-w-[260px] mx-auto md:mx-0 relative">
            <LichessBoard
              fen={fen}
              orientation={orientation}
              viewOnly={true}
              arrows={arrows}
              highlights={highlightedSquares}
            />
          </div>

          {/* Caption */}
          <div className="self-center">
            {caption && (
              <p className="font-serif italic text-[18px] md:text-[20px] leading-snug text-foreground/90">
                {caption}
              </p>
            )}
            <p className="mt-4 text-[12px] text-muted-foreground/80 leading-relaxed">
              The red squares show your king's exposed zone. Arrows point
              from the pieces aimed at it.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
