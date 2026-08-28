export function coachPlayFocusRule(context, gameMode) {
  if (gameMode !== "coach") return null;

  const primary = context?.primary_focus;
  if (!primary?.instruction_id || !primary?.instruction_text) return null;

  return {
    name: primary.label,
    rule: primary.instruction_text,
    pattern: primary.topic_key,
    contextId: context.context_id,
    instructionId: primary.instruction_id,
    evidenceMode: "practice_assisted",
  };
}

