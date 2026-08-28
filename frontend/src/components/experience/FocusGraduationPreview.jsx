import { useEffect, useRef, useState } from "react";
import { Check, Sparkles, X } from "lucide-react";

/**
 * Privacy-safe V1 milestone preview. This component deliberately performs no
 * network, clipboard, file, or native-share operation. Export remains gated
 * behind explicit user authorization.
 */
export default function FocusGraduationPreview({ focusLabel, evidence }) {
  const [open, setOpen] = useState(false);
  const closeRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    closeRef.current?.focus();
    const onKeyDown = (event) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="experience-share-trigger inline-flex items-center gap-1.5 text-[11px] font-semibold text-muted-foreground hover:text-foreground"
      >
        <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
        Preview milestone
      </button>

      {open && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/65 p-4 backdrop-blur-sm"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setOpen(false);
          }}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="focus-preview-title"
            className="experience-share-dialog w-full max-w-2xl rounded-3xl border border-border bg-card p-4 shadow-2xl sm:p-6"
          >
            <div className="mb-4 flex items-center justify-between gap-4">
              <div>
                <p className="experience-eyebrow text-[10px] font-bold uppercase">Milestone preview</p>
                <h2 id="focus-preview-title" className="mt-1 text-lg font-semibold">Your Focus Graduation</h2>
              </div>
              <button
                ref={closeRef}
                type="button"
                onClick={() => setOpen(false)}
                className="rounded-full p-2 text-muted-foreground hover:bg-muted hover:text-foreground"
                aria-label="Close milestone preview"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="experience-share-card aspect-[1200/630] rounded-2xl p-7 sm:p-10">
              <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-amber-300 sm:text-xs">ChessGuru · Focus graduated</p>
              <p className="mt-6 max-w-[85%] font-heading text-3xl font-semibold leading-tight text-[#fff8e8] sm:text-5xl">{focusLabel}</p>
              <p className="mt-6 max-w-[82%] text-sm leading-relaxed text-teal-100/80 sm:text-lg">{evidence || "Consistent decisions moved this focus out of active training."}</p>
              <p className="mt-auto text-[10px] text-white/50 sm:text-xs">Personal coaching built from real games.</p>
            </div>

            <div className="mt-4 flex items-start gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3 text-xs text-muted-foreground">
              <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" />
              <p>Private preview only. No username, opponent, rating, game link, or progress fact leaves ChessGuru.</p>
            </div>
          </section>
        </div>
      )}
    </>
  );
}

