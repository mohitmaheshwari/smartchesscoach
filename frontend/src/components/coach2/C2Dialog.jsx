/**
 * C2Dialog — the dialog treatment proposed for the redesign.
 *
 * Local to the /coach2 preview ON PURPOSE. components/ui/dialog.jsx is
 * imported by 80+ screens; nothing here touches it. If Mohit signs off,
 * the change there is a one-line `overlayClassName` prop plus new
 * defaults — not a rewrite.
 *
 * What differs from components/ui/dialog.jsx today, and why. The numbers
 * on the right are measured off chessiro.com/settings (screenshot
 * 2026-11-25, 1910px wide, sampled with PIL — not eyeballed):
 *
 *   scrim    ours bg-black/80   theirs rgb(0 0 0 / 0.50)
 *            Their page is rgb(243 230 219), dimmed to rgb(122 115 110).
 *            Solving dimmed = page x (1-a) per channel gives
 *            a = 122/243 -> 0.498, 115/230 -> 0.500, 110/219 -> 0.498.
 *            Three channels agreeing to 0.002 means it is plain black at
 *            exactly 50%, not a tinted or blurred scrim.
 *            At 80% that same cream drops to rgb(49 46 44) and the page
 *            behind is gone. A modal should sit ON the app, not in a void.
 *   radius   ours rounded-lg (8px)      theirs ~14-16px -> rounded-card (14)
 *   width    ours max-w-lg (512px)      theirs 382px    -> max-w-sm (384)
 *   padding  ours p-6 (24px)            theirs ~20px    -> p-5
 *   buttons  ours justify-end, auto-width, 8px apart
 *            theirs two EQUAL buttons filling the content row:
 *            167px + 164px with an ~11px gap inside 341px of content.
 *            -> flex-1 each, gap-3.
 *   cancel   theirs is filled with the PAGE colour, exactly, and
 *            outlined, so it reads as "go back to what is behind".
 *
 * The surface is bg-card (--card 42 48% 99%), which is already lighter
 * than --background (42 41% 96%), so the modal lifts off the page the
 * same way theirs does. No new colour is introduced.
 */
import React from "react";
import * as Dlg from "@radix-ui/react-dialog";
import { X } from "lucide-react";

export function C2Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  cancelLabel = "Cancel",
  confirmLabel,
  confirmDisabled = false,
  onConfirm,
}) {
  return (
    <Dlg.Root open={open} onOpenChange={onOpenChange}>
      <Dlg.Portal>
        <Dlg.Overlay
          className="fixed inset-0 z-50 data-[state=closed]:animate-out data-[state=open]:animate-in data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0"
          style={{ background: "rgb(0 0 0 / 0.5)" }}
        />
        <Dlg.Content
          className="coach2-surface fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-card border border-border bg-card p-5 text-foreground shadow-e3 duration-200 data-[state=closed]:animate-out data-[state=open]:animate-in data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95"
        >
          <Dlg.Title className="m-0 pr-8 font-heading text-lead font-bold">
            {title}
          </Dlg.Title>
          {description ? (
            <Dlg.Description className="mb-0 mt-1.5 text-note text-muted-foreground">
              {description}
            </Dlg.Description>
          ) : null}

          {children ? <div className="mt-4">{children}</div> : null}

          {/* Equal-width, filling the row. Not right-aligned and auto-width:
              on a 384px modal two auto buttons leave a ragged gutter, and on
              a phone the primary ends up under the thumb's blind spot. */}
          <div className="mt-5 flex gap-3">
            <Dlg.Close asChild>
              <button
                type="button"
                className="flex-1 rounded-card border border-border bg-background px-4 py-2.5 font-heading text-note font-semibold text-foreground"
              >
                {cancelLabel}
              </button>
            </Dlg.Close>
            <button
              type="button"
              disabled={confirmDisabled}
              onClick={onConfirm}
              className="flex-1 rounded-card px-4 py-2.5 font-heading text-note font-semibold disabled:cursor-not-allowed"
              style={
                confirmDisabled
                  ? {
                      // --muted (40 26% 91%) rendered at rgb(238 234 226):
                      // against a rgb(254 253 251) modal that is a 1.07:1
                      // difference, so the disabled primary disappeared
                      // rather than reading as "a button, not yet usable".
                      // Ink at 20% lands on rgb(196 197 192), which is what
                      // the reference does too (its disabled fill measures
                      // rgb(151 143 135)). Label contrast is 3.6:1 — under
                      // AA, but WCAG 1.4.3 exempts disabled controls, and
                      // the alternative is an invisible button.
                      background: "hsl(var(--experience-ink) / 0.20)",
                      color: "hsl(var(--muted-foreground))",
                    }
                  : {
                      background: "hsl(var(--experience-ink))",
                      color: "hsl(var(--background))",
                    }
              }
            >
              {confirmLabel}
            </button>
          </div>

          {/* Last in the DOM on purpose: Radix autofocuses the first
              tabbable child, and an X with a focus ring is the wrong thing
              to greet someone with. Now the input takes focus, or Cancel
              when there is no input — the safe default either way. */}
          <Dlg.Close
            aria-label="Close"
            className="absolute right-3.5 top-3.5 flex h-7 w-7 items-center justify-center rounded-control text-muted-foreground"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </Dlg.Close>
        </Dlg.Content>
      </Dlg.Portal>
    </Dlg.Root>
  );
}

export default C2Dialog;

/** Deep link: /coach2/settings?dialog=connect opens that dialog on load.
 *  Lets a reviewer (and a screenshot) land directly on a dialog state. */
export function initialDialog() {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get("dialog");
}
