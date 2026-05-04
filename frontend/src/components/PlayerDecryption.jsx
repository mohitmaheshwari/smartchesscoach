/**
 * PlayerDecryption — "What kind of player showed up in this game?"
 *
 * Three short coaching beats:
 *   Story         — orientation, what arc this game took (1–2 sentences)
 *   Pattern       — the gold. Identity-level inner-voice line about
 *                   how the player thinks. The "this is me" beat.
 *   Carry-forward — one mutterable line for the next game.
 *
 * Renders below TruthHeadline, above the Plan Decryption (board prose).
 * Hidden when player_decryption is null (user won).
 */

export default function PlayerDecryption({ playerDecryption }) {
  if (!playerDecryption || !playerDecryption.pattern) return null;

  const { story, pattern, carry_forward: carryForward } = playerDecryption;

  return (
    <section
      data-testid="player-decryption"
      className="max-w-[680px] mx-auto px-6 pb-10 md:pb-14"
    >
      <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-6">
        Player decryption · this is how you played
      </div>

      <div className="rounded-2xl border border-border/40 bg-gradient-to-b from-violet-500/[0.03] to-transparent p-6 md:p-8">
        {story && (
          <p className="text-[15px] md:text-[16px] text-foreground/85 leading-relaxed mb-5">
            {story}
          </p>
        )}

        {pattern && (
          <p className="font-serif italic text-[19px] md:text-[22px] leading-snug text-foreground mb-6">
            {pattern}
          </p>
        )}

        {carryForward && (
          <div className="pt-5 border-t border-border/30">
            <div className="text-[10px] uppercase tracking-[0.22em] text-violet-500 dark:text-violet-300 font-semibold mb-2">
              Take this into the next game
            </div>
            <p className="text-[14.5px] md:text-[15px] text-foreground/90 leading-snug">
              {carryForward}
            </p>
          </div>
        )}
      </div>
    </section>
  );
}
