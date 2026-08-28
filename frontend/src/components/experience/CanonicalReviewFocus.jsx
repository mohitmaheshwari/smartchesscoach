export default function CanonicalReviewFocus({ context, onMoveSelect }) {
  if (!context?.surface_context) return null;

  const primary = context.primary_focus;
  const review = context.surface_context;
  const matches = review.primary_matches || [];

  return (
    <section
      className="border-l-2 border-violet-400/50 pl-4"
      data-testid="canonical-review-focus"
    >
      <p className="text-[10px] uppercase tracking-[0.2em] text-violet-600 dark:text-violet-400 font-semibold mb-1.5">
        {primary ? "Your focus in this game" : "Focus connection"}
      </p>
      {primary?.instruction_text && (
        <p className="text-[13px] leading-relaxed text-foreground mb-1.5">
          {primary.instruction_text}
        </p>
      )}
      {review.message && (
        <p className="text-[11.5px] leading-relaxed text-muted-foreground">
          {review.message}
        </p>
      )}
      {matches.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-2.5">
          {matches.map((match) => (
            <button
              key={`${match.move_number}-${match.detector_quality_id || match.move_san}`}
              type="button"
              onClick={() => onMoveSelect?.(match.move_number)}
              className="h-7 px-2.5 rounded-md border border-border text-[11px] font-medium text-foreground hover:bg-muted/60 transition-colors"
              data-testid="canonical-review-move"
            >
              Move {match.move_number}{match.move_san ? ` · ${match.move_san}` : ""}
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

