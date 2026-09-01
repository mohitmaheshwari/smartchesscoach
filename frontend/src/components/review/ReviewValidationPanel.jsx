import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Check, ChevronDown, FlaskConical, Loader2 } from "lucide-react";

import { API } from "../../App";
import { ANALYTICS_EVENTS, trackReviewValidation } from "../../lib/analytics";


export default function ReviewValidationPanel({
  gameId,
  validation,
  onModeChange,
  onSubmission,
}) {
  const [open, setOpen] = useState(false);
  const [ratings, setRatings] = useState({});
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const rubric = useMemo(() => validation?.rubric || [], [validation?.rubric]);
  const activeVariant = validation?.active_variant;

  useEffect(() => {
    const existing = validation?.existing_submission;
    setRatings(existing?.ratings || {});
    setNotes(existing?.notes || "");
    setSaved(Boolean(existing));
    setError("");
    setOpen(false);
  }, [validation]);

  const complete = useMemo(
    () => rubric.length > 0 && rubric.every((item) => ratings[item.id]),
    [ratings, rubric]
  );
  const comparisonUnavailable = !validation?.comparison_ready;
  const criticalTruthFailure = ratings.chess_truth === "critical_false_claim";

  if (!validation?.enabled) return null;

  const chooseMode = (mode) => {
    if (mode === activeVariant) return;
    trackReviewValidation(ANALYTICS_EVENTS.REVIEW_VALIDATION_MODE_CHANGED, {
      presentation_variant: mode,
    });
    onModeChange?.(mode);
  };

  const submit = async () => {
    if (!complete || saving || comparisonUnavailable) return;
    setSaving(true);
    setError("");
    try {
      const response = await fetch(
        `${API}/coach/decryption/v5/${gameId}/validation-review`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            presentation_variant: activeVariant,
            ratings,
            notes,
          }),
        }
      );
      if (!response.ok) {
        const failure = await response.json().catch(() => ({}));
        throw new Error(failure.detail || "Scorecard could not be saved");
      }
      const result = await response.json();
      setSaved(true);
      trackReviewValidation(ANALYTICS_EVENTS.REVIEW_VALIDATION_SUBMITTED, {
        presentation_variant: activeVariant,
        critical_truth_failure: criticalTruthFailure,
      });
      onSubmission?.(result.submission);
    } catch (submissionError) {
      setError(submissionError.message || "Scorecard could not be saved");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section
      className="mx-4 mt-4 rounded-2xl border border-violet-200 bg-gradient-to-r from-violet-50 via-white to-emerald-50 p-4 shadow-sm"
      data-testid="review-validation-panel"
    >
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-violet-800">
            <FlaskConical className="h-4 w-4" />
            Internal validation
          </div>
          <p className="mt-1 text-sm text-slate-600">
            Compare the same game. Score each version independently.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-full border border-slate-200 bg-white p-1">
            {(validation.presentation_options || []).map((option) => {
              const unavailable = (
                !validation.comparison_ready
              );
              return (
                <button
                  type="button"
                  key={option.id}
                  disabled={unavailable}
                  onClick={() => chooseMode(option.id)}
                  className={`min-h-9 rounded-full px-4 py-2 text-xs font-semibold transition focus:outline-none focus:ring-2 focus:ring-violet-500 focus:ring-offset-2 ${
                    activeVariant === option.id
                      ? "bg-slate-950 text-white"
                      : "text-slate-600 hover:bg-slate-100"
                  } disabled:cursor-not-allowed disabled:opacity-40`}
                  aria-pressed={activeVariant === option.id}
                  data-testid={`review-validation-mode-${option.id}`}
                >
                  {option.label}
                </button>
              );
            })}
          </div>
          <button
            type="button"
            disabled={comparisonUnavailable}
            onClick={() => setOpen((current) => !current)}
            className="inline-flex min-h-10 items-center gap-2 rounded-full bg-violet-700 px-4 py-2 text-xs font-semibold text-white transition hover:bg-violet-800 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-40"
            aria-expanded={open}
            data-testid="review-validation-open"
          >
            {saved ? <Check className="h-4 w-4" /> : null}
            {saved ? "Review saved" : "Score this version"}
            <ChevronDown className={`h-4 w-4 transition ${open ? "rotate-180" : ""}`} />
          </button>
        </div>
      </div>

      {!validation.comparison_ready && (
        <p className="mt-3 text-sm text-amber-800" role="status">
          This game is not ready for a blinded comparison because one version is incomplete.
        </p>
      )}

      {open && !comparisonUnavailable && (
        <div className="mt-5 border-t border-violet-100 pt-5" data-testid="review-validation-scorecard">
          <div className="grid gap-5 lg:grid-cols-2">
            {rubric.map((dimension) => (
              <fieldset key={dimension.id} className="min-w-0">
                <legend className="text-sm font-semibold text-slate-900">
                  {dimension.label}
                </legend>
                <div className="mt-2 flex flex-wrap gap-2">
                  {dimension.options.map((option) => (
                    <button
                      type="button"
                      key={option.id}
                      onClick={() => {
                        setSaved(false);
                        setRatings((current) => ({
                          ...current,
                          [dimension.id]: option.id,
                        }));
                      }}
                      className={`min-h-9 rounded-full border px-3 py-2 text-xs font-medium transition focus:outline-none focus:ring-2 focus:ring-violet-500 focus:ring-offset-2 ${
                        ratings[dimension.id] === option.id
                          ? "border-violet-600 bg-violet-600 text-white"
                          : "border-slate-200 bg-white text-slate-700 hover:border-violet-300"
                      }`}
                      aria-pressed={ratings[dimension.id] === option.id}
                      data-testid={`review-validation-${dimension.id}-${option.id}`}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </fieldset>
            ))}
          </div>

          {criticalTruthFailure && (
            <div className="mt-5 flex gap-3 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900" role="alert">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              This is a rollout blocker. Add a short note identifying the false claim.
            </div>
          )}

          <label className="mt-5 block text-sm font-semibold text-slate-900" htmlFor="review-validation-notes">
            Optional reviewer note
          </label>
          <textarea
            id="review-validation-notes"
            value={notes}
            maxLength={1000}
            onChange={(event) => {
              setSaved(false);
              setNotes(event.target.value);
            }}
            className="mt-2 min-h-24 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 outline-none transition focus:border-violet-400 focus:ring-2 focus:ring-violet-200"
            placeholder="What should the product team inspect?"
          />

          {error && <p className="mt-3 text-sm text-rose-700" role="alert">{error}</p>}
          <div className="mt-4 flex items-center justify-end gap-3">
            {!complete && (
              <span className="text-xs text-slate-500">Score every row before saving.</span>
            )}
            <button
              type="button"
              disabled={!complete || saving}
              onClick={submit}
              className="inline-flex min-h-11 items-center gap-2 rounded-full bg-slate-950 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-violet-800 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-40"
              data-testid="review-validation-submit"
            >
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              Save this scorecard
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

