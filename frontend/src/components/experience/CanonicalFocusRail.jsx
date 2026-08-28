import { ArrowRight } from "lucide-react";


export default function CanonicalFocusRail({ context, onAction }) {
  if (!context) return null;

  const primary = context.primary_focus;
  const support = (context.supporting_focuses || []).slice(0, 1);
  const evidenceMessage = context.evidence?.message;
  const nextAction = context.next_action;

  return (
    <div
      className="experience-focus-rail border-l-2 border-violet-400/50 pl-4 mb-7 max-w-[600px]"
      data-testid="canonical-focus-rail"
    >
      <p className="experience-eyebrow text-[10px] uppercase tracking-[0.2em] text-violet-600 dark:text-violet-400 font-semibold mb-2">
        {primary ? "Your main focus" : "Your coaching plan"}
      </p>

      {primary && (
        <>
          <p className="text-[17px] font-medium text-foreground mb-2">
            {primary.label}
          </p>
          {primary.instruction_text && (
            <p className="text-[14px] leading-relaxed text-foreground mb-2">
              {primary.instruction_text}
            </p>
          )}
        </>
      )}

      {support.map((item) => (
        <p
          key={`${item.detector_quality_id || item.topic_key}`}
          className="text-[12.5px] leading-relaxed text-muted-foreground mb-2"
          data-testid="canonical-supporting-focus"
        >
          Also watching: {item.label}
        </p>
      ))}

      {evidenceMessage && (
        <p className="text-[12.5px] leading-relaxed text-muted-foreground">
          {evidenceMessage}
        </p>
      )}

      {nextAction?.href && nextAction?.label && (
        <button
          type="button"
          onClick={() => onAction?.(nextAction)}
          className="experience-primary mt-4 h-9 px-4 rounded-lg bg-violet-500 hover:bg-violet-400 text-white font-medium text-[13px] transition-colors inline-flex items-center gap-2"
          data-testid="canonical-context-action"
        >
          {nextAction.label}
          <ArrowRight className="h-3.5 w-3.5" strokeWidth={2} />
        </button>
      )}
    </div>
  );
}

