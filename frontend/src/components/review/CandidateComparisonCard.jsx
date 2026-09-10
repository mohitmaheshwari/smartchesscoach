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
      className="mt-5 overflow-hidden rounded-2xl border border-violet-200/80 bg-gradient-to-br from-violet-50 via-white to-emerald-50/60"
      data-testid="candidate-comparison-card"
    >
      <div className="p-4 md:p-5">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-violet-900 text-white">
            <Sparkles className="h-4 w-4" aria-hidden="true" />
          </span>
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-violet-700">
              What was possible here
            </p>
            <h3 className="mt-1 font-serif text-xl leading-snug text-slate-950">
              {comparison.headline}
            </h3>
          </div>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div className="rounded-xl border border-slate-200 bg-white/80 p-3.5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
              What happened
            </p>
            <p className="mt-1.5 text-sm leading-6 text-slate-700">
              {played.summary}
            </p>
          </div>
          <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-3.5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-700">
              What you could play
            </p>
            <p className="mt-1.5 text-sm leading-6 text-emerald-950">
              {stronger.summary}
            </p>
          </div>
        </div>

        <button
          type="button"
          disabled={playing}
          onClick={() => onCompare?.(comparison)}
          className="mt-4 inline-flex min-h-10 items-center gap-2 rounded-full bg-slate-950 px-4 py-2 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-violet-900 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:ring-offset-2 disabled:cursor-wait disabled:opacity-60"
          data-testid="candidate-comparison-play"
        >
          <Play className="h-4 w-4" aria-hidden="true" />
          {playing ? "Showing both lines…" : "Show both lines on the board"}
        </button>
      </div>

      {comparison.memory_cue && (
        <div className="border-t border-violet-100 bg-white/65 px-4 py-3 md:px-5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-700">
            Remember
          </p>
          <p className="mt-1 text-sm font-medium text-slate-800">
            {comparison.memory_cue}
          </p>
        </div>
      )}
    </section>
  );
}
