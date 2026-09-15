import React, { act } from "react";
import { createRoot } from "react-dom/client";

import GuidedReviewMoment from "./GuidedReviewMoment";


const chapter = {
  event_id: "event-1",
  phase: "middlegame",
  role: "turning_point",
  interaction: {
    question: "What danger should decide the move?",
    options: [
      { id: "capture_next", label: "The knight can take the queen on d5." },
      { id: "activity", label: "The move is active enough." },
    ],
    hint_available: true,
  },
};

describe("GuidedReviewMoment", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  const click = async (text) => {
    const target = [...container.querySelectorAll("button")].find(
      (button) => button.textContent.includes(text),
    );
    expect(target).toBeDefined();
    await act(async () => {
      target.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      await Promise.resolve();
      await Promise.resolve();
    });
  };

  test("withholds the answer, then reveals only after a prediction", async () => {
    const onHint = jest.fn(async () => ({
      hint: "Follow the knight from f6 to d5.",
    }));
    const onPredict = jest.fn(async (selected) => ({
      selected_option_id: selected,
      correct_option_id: "capture_next",
      correct: selected === "capture_next",
      headline: "The queen on d5 is left unprotected",
      explanation: "Bg5 allows Nxd5 because the knight can take the queen.",
      principle: "Before choosing a move, check every capture.",
      demonstration: {
        kind: "played_refutation",
        moves_san: ["Bg5", "Nxd5"],
      },
    }));

    await act(async () => root.render(
      <GuidedReviewMoment
        chapter={chapter}
        chapterNumber={1}
        chapterCount={2}
        onHint={onHint}
        onPredict={onPredict}
        onWatch={jest.fn()}
        onBeginReplay={jest.fn()}
        onContinue={jest.fn()}
      />,
    ));

    expect(container.textContent).not.toContain("left unprotected");
    expect(container.textContent).not.toContain("Follow the knight");

    await click("Give me one clue");
    expect(container.textContent).toContain("Follow the knight from f6 to d5.");
    expect(container.textContent).not.toContain("left unprotected");

    await click("The knight can take");
    await click("Show me");
    expect(onPredict).toHaveBeenCalledWith("capture_next");
    expect(container.textContent).toContain("The queen on d5 is left unprotected");
    expect(container.textContent).toContain(
      "Before choosing a move, check every capture.",
    );
    expect(container.textContent).toContain("Watch the line");
  });

  test("restores only evidence already earned by the learner", async () => {
    await act(async () => root.render(
      <GuidedReviewMoment
        chapter={chapter}
        chapterNumber={1}
        chapterCount={2}
        progress={{ predicted: true, revealed: true, watched: true }}
        restoredHint={{ hint: "Follow the knight." }}
        restoredReveal={{
          selected_option_id: "activity",
          correct_option_id: "capture_next",
          correct: false,
          headline: "The queen on d5 is left unprotected",
          explanation: "The knight can take it.",
          principle: "Check every capture.",
          demonstration: { moves_san: ["Bg5", "Nxd5"] },
        }}
        onHint={jest.fn()}
        onPredict={jest.fn()}
        onWatch={jest.fn()}
        onBeginReplay={jest.fn()}
        onContinue={jest.fn()}
      />,
    ));
    expect(container.textContent).toContain("Here is the idea");
    expect(container.textContent).toContain("Let me play the key move");
    expect(container.textContent).not.toContain("Continue the story");
  });
});
