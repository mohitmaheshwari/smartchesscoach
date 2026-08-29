export const nextLessonPrompt = (instruction) => {
  if (!instruction) return null;
  if (instruction.answer_hidden) {
    return instruction.message || "Find the move without seeing the answer.";
  }
  return instruction.is_user_move
    ? `Your turn: play ${instruction.move}`
    : `Watch: I'll play ${instruction.move}`;
};
