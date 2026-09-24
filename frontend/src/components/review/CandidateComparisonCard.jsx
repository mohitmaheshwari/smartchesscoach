import { Play, Sparkles } from "lucide-react";


export default function CandidateComparisonCard({
  comparison,
  onCompare,
  playing = false,
}) {
  const played = comparison?.played;
  const stronger = comparison?.stronger;
  if (
    !comparison?.headline
    || !played?.summary
    || !stronger?.summary
    || !played?.moves?.length
    || !stronger?.moves?.length
  ) {
    return null;
  }

  return (
    <section
      className="mt-5 overflow-hidden rounded-2xl border border-[#2a221b] bg-[#181410]"
      data-testid="candidate-comparison-card"
    >
      <div className="p-4 md:p-5">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-[#d0ae6d]/20 text-[#d0ae6d]">
            <Sparkles className="h-4 w-4" aria-hidden="true" />
          </span>
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#d0ae6d]">
              What was possible here
            </p>
            <h3 className="mt-1 font-serif text-xl leading-snug text-[#f4efe6]">
              {comparison.headline}
            </h3>
          </div>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div className="rounded-xl border border-[#2a221b] bg-[#13100d] p-3.5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-rose-400">
              What happened
            </p>
            <p className="mt-1.5 text-sm leading-relaxed text-stone-300">
              {played.summary}
            </p>
          </div>
          <div className="rounded-xl border border-[#84b872]/30 bg-[#84b872]/10 p-3.5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#84b872]">
              What you could play
            </p>
            <p className="mt-1.5 text-sm leading-relaxed text-emerald-100">
              {stronger.summary}
            </p>
          </div>
        </div>

        <button
          type="button"
          disabled={playing}
          onClick={() => onCompare?.(comparison)}
          className="mt-4 inline-flex min-h-10 items-center gap-2 rounded-full bg-[#d0ae6d] px-4 py-2 text-sm font-bold text-[#0c0a08] transition hover:brightness-110 disabled:cursor-wait disabled:opacity-60"
          data-testid="candidate-comparison-play"
        >
          <Play className="h-4 w-4 fill-current" aria-hidden="true" />
          {playing ? "Showing both lines…" : "Show both lines on the board"}
        </button>
      </div>

      {comparison.memory_cue && (
        <div className="border-t border-[#2a221b] bg-[#13100d] px-4 py-3 md:px-5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#84b872]">
            Remember
          </p>
          <p className="mt-1 text-sm font-medium text-stone-200">
            {comparison.memory_cue}
          </p>
        </div>
      )}
    </section>
  );
}
