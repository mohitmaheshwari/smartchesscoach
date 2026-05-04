/**
 * TruthHeadline — the post-game first screen.
 *
 * Renders the 3-line Truth (identity / anchor / forward trigger) shown
 * before any board, any stats, any move-by-move. The Decryption block
 * lives behind a "Show me why" toggle so the player can:
 *
 *   - Read the Truth, take it into the next game (memory)
 *   - OR expand for the consequence prose (understanding)
 *
 * Coach Voice rules govern the Truth lines; Decryption Voice rules
 * govern the expansion prose. Both come from the API ready-to-render —
 * this component does not generate, validate, or transform either.
 *
 * Props:
 *   truthLine        — { identity, anchor, trigger, scenario } | null
 *   decryptionBlock  — { text, source, attempts, critical_move_san } | null
 */

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

export default function TruthHeadline({ truthLine, decryptionBlock }) {
  const [expanded, setExpanded] = useState(false);

  // Don't render if we have no Truth (e.g., user won).
  if (!truthLine || !truthLine.identity) return null;

  const { identity, anchor, trigger } = truthLine;
  const hasDecryption = !!(decryptionBlock && decryptionBlock.text);

  return (
    <section
      data-testid="truth-headline"
      className="max-w-[680px] mx-auto px-6 py-12 md:py-16"
    >
      {/* Eyebrow — small caps, restraint */}
      <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-6">
        The truth
      </div>

      {/* Three lines — identity, anchor, trigger */}
      <div className="space-y-4 mb-10">
        <p className="font-serif text-[22px] md:text-[26px] leading-[1.25] tracking-[-0.015em] text-foreground">
          {identity}
        </p>
        <p className="text-[15px] md:text-[16px] text-foreground/85 leading-relaxed">
          {anchor}
        </p>
        <p className="text-[14px] md:text-[15px] text-violet-500 dark:text-violet-300 italic leading-snug">
          {trigger}
        </p>
      </div>

      {/* Show me why toggle — only when there's a decryption to show */}
      {hasDecryption && (
        <>
          <button
            onClick={() => setExpanded((v) => !v)}
            data-testid="truth-show-me-why"
            className="text-[12px] uppercase tracking-[0.18em] text-muted-foreground hover:text-foreground font-semibold inline-flex items-center gap-1.5 transition-colors"
          >
            {expanded ? (
              <>
                Hide
                <ChevronUp className="w-3.5 h-3.5" strokeWidth={2.2} />
              </>
            ) : (
              <>
                Show me why
                <ChevronDown className="w-3.5 h-3.5" strokeWidth={2.2} />
              </>
            )}
          </button>

          {expanded && (
            <div
              data-testid="decryption-block"
              className="mt-6 rounded-xl border border-border/40 bg-muted/20 p-5 md:p-6"
            >
              <p className="text-[14.5px] md:text-[15px] text-foreground/90 leading-relaxed">
                {decryptionBlock.text}
              </p>
            </div>
          )}
        </>
      )}
    </section>
  );
}
