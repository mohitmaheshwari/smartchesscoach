import React, { act } from "react";
import { createRoot } from "react-dom/client";

import ActiveCoachStrip from "./ActiveCoachStrip";
import EmotionalStateIndicator from "./EmotionalStateIndicator";


jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("framer-motion", () => ({
  motion: { div: ({ children, ...props }) => {
    const domProps = { ...props };
    delete domProps.initial;
    delete domProps.animate;
    delete domProps.exit;
    delete domProps.transition;
    return <div {...domProps}>{children}</div>;
  } },
  AnimatePresence: ({ children }) => <>{children}</>,
}));


const response = (body) => ({ ok: true, json: () => Promise.resolve(body) });

const deferred = () => {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
};


describe("coach prop synchronization effects", () => {
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
    delete global.fetch;
  });

  const flush = () => act(async () => {
    await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });

  test("coach strip updates phase and question even when text and layer stay the same", async () => {
    await act(async () => root.render(<ActiveCoachStrip coaching={{
      text: "Look once more.",
      layer: "advisory",
      gamePhase: "Opening",
      question: { prompt: "What changed?" },
    }} />));
    expect(container.textContent).toContain("Opening");
    expect(container.textContent).toContain("What changed?");

    await act(async () => root.render(<ActiveCoachStrip coaching={{
      text: "Look once more.",
      layer: "advisory",
      gamePhase: "Middlegame",
      question: { prompt: "Which piece is loose?" },
    }} />));
    expect(container.textContent).toContain("Middlegame");
    expect(container.textContent).toContain("Which piece is loose?");
    expect(container.textContent).not.toContain("What changed?");
  });

  test("emotional check keys off payload values and ignores equivalent array identity", async () => {
    global.fetch = jest.fn(() => Promise.resolve(response({ emotional_state: "neutral" })));

    await act(async () => root.render(<EmotionalStateIndicator
      blundersThisGame={1}
      avgMoveTime={12}
      recentResults={["loss"]}
    />));
    await flush();
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(JSON.parse(global.fetch.mock.calls[0][1].body)).toEqual({
      recent_results: ["loss"],
      avg_move_time: 12,
      blunders_this_game: 1,
    });

    await act(async () => root.render(<EmotionalStateIndicator
      blundersThisGame={1}
      avgMoveTime={12}
      recentResults={["loss"]}
    />));
    await flush();
    expect(global.fetch).toHaveBeenCalledTimes(1);

    await act(async () => root.render(<EmotionalStateIndicator
      blundersThisGame={1}
      avgMoveTime={12}
      recentResults={["win"]}
    />));
    await flush();
    expect(global.fetch).toHaveBeenCalledTimes(2);
    expect(JSON.parse(global.fetch.mock.calls[1][1].body).recent_results).toEqual(["win"]);

    await act(async () => root.render(<EmotionalStateIndicator
      blundersThisGame={1}
      avgMoveTime={20}
      recentResults={["win"]}
    />));
    await flush();
    expect(global.fetch).toHaveBeenCalledTimes(3);
    expect(JSON.parse(global.fetch.mock.calls[2][1].body).avg_move_time).toBe(20);
  });

  test("superseded emotional response cannot overwrite current state", async () => {
    const oldRequest = deferred();
    global.fetch = jest.fn()
      .mockImplementationOnce(() => oldRequest.promise)
      .mockImplementationOnce(() => Promise.resolve(response({ emotional_state: "confident" })));

    await act(async () => root.render(<EmotionalStateIndicator
      blundersThisGame={2}
      avgMoveTime={12}
      recentResults={["loss"]}
    />));

    await act(async () => root.render(<EmotionalStateIndicator
      blundersThisGame={0}
      avgMoveTime={12}
      recentResults={["win"]}
    />));
    await flush();
    expect(container.textContent).toContain("You're on fire!");

    oldRequest.resolve(response({ emotional_state: "frustrated" }));
    await flush();
    expect(container.textContent).toContain("You're on fire!");
    expect(container.textContent).not.toContain("Tough stretch");
  });
});
