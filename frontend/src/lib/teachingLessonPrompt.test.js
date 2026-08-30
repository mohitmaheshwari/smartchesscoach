import { nextLessonPrompt } from "./teachingLessonPrompt";


describe("nextLessonPrompt", () => {
  it("keeps a hidden-answer exercise question-first", () => {
    expect(nextLessonPrompt({
      answer_hidden: true,
      message: "How would you stop the threat?",
      move: "Qe7",
      is_user_move: true,
    })).toBe("How would you stop the threat?");
  });

  it("never prints an undefined answer", () => {
    expect(nextLessonPrompt({ answer_hidden: true })).toBe(
      "Find the move without seeing the answer.",
    );
  });

  it("keeps guided demonstrations explicit", () => {
    expect(nextLessonPrompt({
      answer_hidden: false,
      move: "Ke6",
      is_user_move: false,
    })).toBe("Watch: I'll play Ke6");
  });
});
