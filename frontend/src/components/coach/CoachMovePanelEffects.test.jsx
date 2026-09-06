import React, { act } from "react";
import { createRoot } from "react-dom/client";

import CoachMovePanel from "./CoachMovePanel";


jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("framer-motion", () => ({
  motion: { div: ({ children, ...props }) => {
    const domProps = { ...props };
    delete domProps.initial;
    delete domProps.animate;
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

const moves = [{ san: "e4" }];
const importantAnalysis = {
  stockfish_analysis: {
    move_evaluations: [{
      move_number: 1,
      move: "e4",
      classification: "mistake",
      best_move: "Nf3",
    }],
  },
};


describe("CoachMovePanel board-reading effect", () => {
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

  const renderPanel = ({ analysis = importantAnalysis, fen = "fen-1" } = {}) => act(async () => root.render(
    <CoachMovePanel
      gameId="game-1"
      currentMoveIndex={0}
      moves={moves}
      analysis={analysis}
      userColor="white"
      currentFen={fen}
    />
  ));

  test("loads when the selected move becomes reviewable without changing its index", async () => {
    global.fetch = jest.fn(() => Promise.resolve(response({ summary: "The center is under pressure." })));

    await renderPanel({ analysis: { stockfish_analysis: { move_evaluations: [] } } });
    await flush();
    expect(global.fetch).not.toHaveBeenCalled();

    await renderPanel({ analysis: importantAnalysis });
    await flush();

    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(JSON.parse(global.fetch.mock.calls[0][1].body)).toEqual({
      fen: "fen-1",
      user_color: "white",
    });
    expect(container.textContent).toContain("The center is under pressure.");
  });

  test("a late reading from the prior FEN cannot replace the current position", async () => {
    const oldReading = deferred();
    global.fetch = jest.fn()
      .mockImplementationOnce(() => oldReading.promise)
      .mockImplementationOnce(() => Promise.resolve(response({ summary: "Current position reading." })));

    await renderPanel({ fen: "fen-old" });
    await renderPanel({ fen: "fen-current" });
    await flush();
    expect(container.textContent).toContain("Current position reading.");

    oldReading.resolve(response({ summary: "Old position reading." }));
    await flush();

    expect(container.textContent).toContain("Current position reading.");
    expect(container.textContent).not.toContain("Old position reading.");
    expect(global.fetch).toHaveBeenCalledTimes(2);
  });
});
