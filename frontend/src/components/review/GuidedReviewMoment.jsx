import { useEffect, useState } from "react";
import {
  ArrowRight,
  Check,
  Eye,
  Lightbulb,
  Loader2,
  RotateCcw,
} from "lucide-react";

const ROLE_COPY = {
  setup: "First, notice what the position was asking for",
  turning_point: "This is where the game changed",
  consequence: "Now see what that decision caused",
  finish: "This is how the story ends",
};

export default function GuidedReviewMoment({
  chapter,
  chapterNumber,
  chapterCount,
  progress = {},
  restoredHint = null,
  restoredReveal = null,
  onHint,
  onPredict,
  onWatch,
  onBeginReplay,
  onContinue,
  isLast,
}) {
  const [selected, setSelected] = useState("");
  const [hint, setHint] = useState(restoredHint?.hint || "");
  const [reveal, setReveal] = useState(restoredReveal || null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    setSelected(restoredReveal?.selected_option_id || "");
    setHint(restoredHint?.hint || "");
    setReveal(restoredReveal || null);
    setBusy("");
    setError("");
  }, [chapter?.event_id, restoredHint, restoredReveal]);

  const request = async (kind, callback) => {
    if (busy) return null;
    setBusy(kind);
    setError("");
    try {
      return await callback();
    } catch (requestError) {
      setError(requestError?.message || "That step could not be saved.");
      return null;
    } finally {
      setBusy("");
    }
  };

  const askForHint = async () => {
    const result = await request("hint", onHint);
    if (result?.hint) setHint(result.hint);
  };

  const submitPrediction = async () => {
    if (!selected) return;
    const result = await request("predict", () => onPredict(selected));
    if (result?.demonstration) setReveal(result);
  };

  const watchLine = async () => {
    if (!reveal?.demonstration) return;
    await request("watch", () => onWatch(reveal.demonstration));
  };

  const beginReplay = async () => {
    if (!reveal?.demonstration) return;
    await request("replay", () => onBeginReplay(reveal.demonstration));
  };

  const predicted = progress.predicted || Boolean(reveal);
  const watched = progress.watched;
  const replayed = progress.replayed;

  return (
    <section
      className="rounded-[28px] border border-emerald-950/10 bg-white/90 p-6 shadow-[0_28px_70px_rgba(23,42,34,0.10)] md:p-8"
      data-testid="guided-review-moment"
    >
      <div className="mb-7 flex items-start justify-between gap-4">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-emerald-700">
            {chapter.phase} · chapter {chapterNumber} of {chapterCount}
          </p>
          <h2 className="mt-2 font-serif text-2xl leading-tight text-slate-950 md:text-3xl">
            {ROLE_COPY[chapter.role] || "A decision worth understanding"}
          </h2>
        </div>
        <span className="rounded-full bg-lime-100 px-3 py-1 text-xs font-medium text-emerald-950">
          From a real game
        </span>
      </div>

      <p className="mb-4 text-base font-medium text-slate-900">
        {chapter.interaction.question}
      </p>

      <div className="space-y-3">
        {chapter.interaction.options.map((option) => {
          const chosen = selected === option.id;
          const correct = reveal?.correct_option_id === option.id;
          const wrongChosen = predicted && chosen && !correct;
          return (
            <button
              key={option.id}
              type="button"
              disabled={predicted || Boolean(busy)}
              onClick={() => setSelected(option.id)}
              className={[
                "w-full rounded-2xl border px-4 py-3 text-left text-sm leading-relaxed transition",
                correct && predicted
                  ? "border-emerald-500 bg-emerald-50 text-emerald-950"
                  : wrongChosen
                    ? "border-rose-300 bg-rose-50 text-rose-950"
                    : chosen
                      ? "border-emerald-700 bg-emerald-50 text-slate-950"
                      : "border-slate-200 bg-white text-slate-700 hover:border-emerald-400",
              ].join(" ")}
            >
              <span className="flex items-start gap-3">
                <span
                  className={[
                    "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border",
                    chosen ? "border-emerald-700 bg-emerald-700 text-white" : "border-slate-300",
                  ].join(" ")}
                >
                  {chosen && <Check className="h-3 w-3" />}
                </span>
                {option.label}
              </span>
            </button>
          );
        })}
      </div>

      {!predicted && (
        <div className="mt-5 flex flex-wrap gap-3">
          <button
            type="button"
            disabled={!selected || Boolean(busy)}
            onClick={submitPrediction}
            className="inline-flex items-center gap-2 rounded-full bg-emerald-950 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy === "predict" && <Loader2 className="h-4 w-4 animate-spin" />}
            Show me
            <ArrowRight className="h-4 w-4" />
          </button>
          {chapter.interaction.hint_available && !hint && (
            <button
              type="button"
              disabled={Boolean(busy)}
              onClick={askForHint}
              className="inline-flex items-center gap-2 rounded-full border border-slate-200 px-5 py-2.5 text-sm text-slate-700 hover:border-emerald-400"
            >
              <Lightbulb className="h-4 w-4" />
              Give me one clue
            </button>
          )}
        </div>
      )}

      {hint && !predicted && (
        <p className="mt-4 rounded-2xl bg-amber-50 px-4 py-3 text-sm leading-relaxed text-amber-950">
          <span className="font-semibold">One clue:</span> {hint}
        </p>
      )}

      {reveal && (
        <div className="mt-6 space-y-4 border-t border-slate-200 pt-6">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-700">
              {reveal.correct ? "You saw it" : "Here is the idea"}
            </p>
            <h3 className="mt-2 font-serif text-2xl text-slate-950">
              {reveal.headline}
            </h3>
            <p className="mt-3 text-[15px] leading-7 text-slate-700">
              {reveal.explanation}
            </p>
          </div>
          <p className="rounded-2xl bg-emerald-50 px-4 py-3 text-sm font-medium leading-relaxed text-emerald-950">
            Remember: {reveal.principle}
          </p>

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              disabled={Boolean(busy)}
              onClick={watchLine}
              className={[
                "inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold transition",
                watched
                  ? "border border-emerald-200 bg-emerald-50 text-emerald-900"
                  : "bg-emerald-950 text-white hover:bg-emerald-800",
              ].join(" ")}
            >
              {busy === "watch" ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Eye className="h-4 w-4" />
              )}
              {watched ? "Watch again" : "Watch the line"}
            </button>
            {watched && !replayed && (
              <button
                type="button"
                disabled={Boolean(busy)}
                onClick={beginReplay}
                className="inline-flex items-center gap-2 rounded-full border border-emerald-800 px-5 py-2.5 text-sm font-semibold text-emerald-950 hover:bg-emerald-50"
              >
                <RotateCcw className="h-4 w-4" />
                Let me play the key move
              </button>
            )}
            {replayed && (
              <button
                type="button"
                onClick={onContinue}
                className="inline-flex items-center gap-2 rounded-full bg-lime-300 px-5 py-2.5 text-sm font-semibold text-emerald-950 hover:bg-lime-200"
              >
                {isLast ? "Finish this study" : "Continue the story"}
                <ArrowRight className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
      )}

      {error && (
        <p className="mt-4 text-sm text-rose-700" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
