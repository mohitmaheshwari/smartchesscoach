import { coachPlayFocusRule } from "./coachingContext";


const CONTEXT = {
  schema_version: "coaching_context.v1",
  context_id: "ctx-1",
  primary_focus: {
    focus_id: "focus-1",
    topic_key: "piece_safety",
    label: "Keeping your pieces safe",
    instruction_id: "instruction-1",
    instruction_text: "Before every move, ask: can this piece be taken?",
  },
};


test("Coach Mode projects the exact canonical instruction", () => {
  expect(coachPlayFocusRule(CONTEXT, "coach")).toEqual({
    name: "Keeping your pieces safe",
    rule: "Before every move, ask: can this piece be taken?",
    pattern: "piece_safety",
    contextId: "ctx-1",
    instructionId: "instruction-1",
    evidenceMode: "practice_assisted",
  });
});


test("Play Mode never exposes a live coaching rule", () => {
  expect(coachPlayFocusRule(CONTEXT, "play")).toBeNull();
});


test("an incomplete canonical focus fails closed", () => {
  expect(coachPlayFocusRule({ primary_focus: { label: "Piece safety" } }, "coach")).toBeNull();
});

