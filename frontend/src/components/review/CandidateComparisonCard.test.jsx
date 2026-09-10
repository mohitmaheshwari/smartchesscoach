import { act } from "react";
import { createRoot } from "react-dom/client";

import CandidateComparisonCard from "./CandidateComparisonCard";


const comparison = {
  headline: "Count both sides of the trade",
  played: {
    summary: "Qxd5 takes a pawn, but Rxd5 takes your queen.",
    moves: ["Qxd5", "Rxd5"],
  },
  stronger: {
    summary: "Qa1 keeps your queen safe.",
    moves: ["Qa1", "Kf7"],
  },
  memory_cue: "Count what comes back before starting a capture.",
};


describe("CandidateComparisonCard", () => {
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

  test("shows two compact ideas and one board action", () => {
    const onCompare = jest.fn();
    act(() => root.render(
      <CandidateComparisonCard comparison={comparison} onCompare={onCompare} />
    ));

    expect(container.textContent).toContain(comparison.headline);
    expect(container.textContent).toContain(comparison.played.summary);
    expect(container.textContent).toContain(comparison.stronger.summary);
    expect(container.textContent).toContain(comparison.memory_cue);
    const actions = container.querySelectorAll(
      "[data-testid='candidate-comparison-play']"
    );
    expect(actions).toHaveLength(1);
    act(() => actions[0].dispatchEvent(new MouseEvent("click", { bubbles: true })));
    expect(onCompare).toHaveBeenCalledTimes(1);
    expect(onCompare).toHaveBeenCalledWith(comparison);
  });

  test("fails closed when either replayable line is missing", () => {
    act(() => root.render(
      <CandidateComparisonCard
        comparison={{ ...comparison, stronger: { ...comparison.stronger, moves: [] } }}
      />
    ));
    expect(container.innerHTML).toBe("");
  });
});
