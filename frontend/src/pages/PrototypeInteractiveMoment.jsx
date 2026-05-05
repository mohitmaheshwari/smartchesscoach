/**
 * PrototypeInteractiveMoment — standalone demo page for the
 * "Show → Ask → Reveal" pattern.
 *
 * Hardcoded sample from Game 4db4149b move 54: black king on c6,
 * white pawn pushing toward promotion, white rook on g2. The user
 * played Kc7 (wrong direction); should have played Kd6 to use the
 * open d-file and reach e7.
 *
 * Hit /prototype/interactive-moment to see the interaction shape
 * before we wire it into real games.
 */

import InteractiveMoment from "@/components/InteractiveMoment";

// Hardcoded position — black king on c6, white king g1, white pawn
// e4 about to push, white rook g2. Black to move (their turn).
// All three candidate king moves (Kc7, Kd6, Kb6) are legal from c6.
const SAMPLE_FEN = "8/8/2k5/8/4P3/8/6R1/6K1 b - - 0 53";

const SAMPLE_CANDIDATES = [
  {
    san: "Kc7",
    line: ["Kc7", "e5", "Kd7", "e6+"],
    caption:
      "Your king moves away from the pawn. White pushes e5, e6 — by the time you turn around, the pawn is too far ahead. No way back.",
    isCorrect: false,
  },
  {
    san: "Kd6",
    line: ["Kd6", "e5+", "Ke7"],
    caption:
      "Your king walks into the d-file and reaches e7 next move. The pawn cannot promote with your king sitting in front of it.",
    isCorrect: true,
  },
  {
    san: "Kb6",
    line: ["Kb6", "e5", "Kc7", "e6"],
    caption:
      "Wrong direction. While you walk away, the pawn races forward. Your king will not catch it.",
    isCorrect: false,
  },
];

export default function PrototypeInteractiveMoment() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="max-w-[800px] mx-auto px-6 py-12 md:py-16">
        <p className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-3">
          Prototype · interactive moment
        </p>
        <h1 className="font-serif text-[28px] md:text-[36px] leading-tight tracking-tight mb-2">
          You were drifting. This was your last chance to come back.
        </h1>
        <p className="text-[14.5px] text-muted-foreground leading-relaxed mb-10 max-w-[560px]">
          Game 4db4149b · move 54. Their pawn was on e4, racing to promote.
          You played Kc7 — which was the wrong way. Three options below.
          Pick the one you'd play today.
        </p>

        <InteractiveMoment
          fen={SAMPLE_FEN}
          userColor="black"
          moveNumber={54}
          candidates={SAMPLE_CANDIDATES}
        />

        <div className="mt-10 text-[12px] text-muted-foreground/70 leading-relaxed border-t border-border/40 pt-6">
          <p>
            <strong>What this is.</strong> A prototype of the post-game
            "Show → Ask → Reveal" interaction. After you click an option,
            the board animates the line that follows and a short caption
            explains the outcome. No long prose by default — the player
            sees the consequence on the board first, reads only after.
          </p>
          <p className="mt-2">
            In the real product, each game gets up to 4 of these (one per
            turning point). The candidates and lines come from Stockfish,
            not hardcoded — this is just the visual prototype.
          </p>
        </div>
      </div>
    </div>
  );
}
