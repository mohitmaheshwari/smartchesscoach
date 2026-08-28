export default function CanonicalTrainingAssignment({ context }) {
  const assignment = context?.surface_context?.assignment;
  if (!assignment) return null;

  return (
    <section
      className="mb-8 md:mb-10 border-l-2 border-violet-400/50 pl-4 max-w-[680px]"
      data-testid="canonical-training-assignment"
      data-focus-id={assignment.focus_id || undefined}
      data-instruction-id={assignment.instruction_id || undefined}
    >
      <p className="experience-eyebrow text-[10px] uppercase tracking-[0.2em] text-violet-600 dark:text-violet-400 font-semibold mb-2">
        Today&apos;s assignment
      </p>
      {context.primary_focus?.label && (
        <p className="text-[16px] font-medium text-foreground mb-2">
          {context.primary_focus.label}
        </p>
      )}
      {assignment.instruction_text && (
        <p className="text-[14px] leading-relaxed text-foreground mb-2">
          {assignment.instruction_text}
        </p>
      )}
      {context.evidence?.message && (
        <p className="text-[12.5px] leading-relaxed text-muted-foreground">
          {context.evidence.message}
        </p>
      )}
    </section>
  );
}

