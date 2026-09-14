import React, { act } from "react";
import { createRoot } from "react-dom/client";

import useCoachFlow from "./useCoachFlow";

jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });

/**
 * The coaching text must never describe a position that is no longer there.
 *
 * `handleUserMove` cleared `activeCoachingMoment` and nothing else. The board
 * reading -- commentary, checklist, rootProblem, openingGuidance, trapWarning
 * -- was only ever cleared by `resetFlow`, which runs on a new game, not on a
 * new move.
 *
 * So the panel kept the PREVIOUS move's reading on screen against the NEW
 * position, and then rewrote itself when the evaluation resolved. That is the
 * reported "the caption says one thing and then redoes itself after a few
 * seconds", and the first half was not just stale, it was wrong.
 *
 * The window is not brief. `/evaluate-pending` is raced against a 3000ms
 * timeout; when the timeout wins the move commits and the coach then takes
 * several more seconds to reply, and the late result is reapplied whenever it
 * lands.
 */

const MOVE_ONE = {
  san: "e4", uci: "e2e4", from: "e2", to: "e4",
  fenBefore: "fen-before-1", fenAfterPreview: "fen-after-1",
  moveIndexPreview: 0,
};
const MOVE_TWO = {
  san: "Nf3", uci: "g1f3", from: "g1", to: "f3",
  fenBefore: "fen-before-2", fenAfterPreview: "fen-after-2",
  moveIndexPreview: 1,
};

const Harness = ({ expose }) => {
  expose(useCoachFlow({
    session: { session_id: "s1" },
    gameMode: "coach",
    experienceVersion: "legacy",
    userRating: 1200,
  }));
  return null;
};

const response = (body) => ({ ok: true, json: () => Promise.resolve(body) });
const deferred = () => {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
};

describe("the board reading never outlives its position", () => {
  let container;
  let root;
  let api;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    jest.useRealTimers();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    api = null;
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    jest.restoreAllMocks();
  });

  const render = async () => {
    await act(async () => {
      root.render(<Harness expose={(v) => { api = v; }} />);
    });
  };

  test("a new move drops the previous move's commentary at once", async () => {
    // Move one resolves fast and sets a real board reading.
    global.fetch = jest.fn(() => Promise.resolve(response({
      commentary: "Your knight on f3 is doing the work here.",
      checklist: { phase: "opening", fundamentals: ["develop"] },
      rootProblem: "You leave pieces undefended.",
      openingGuidance: "Italian: aim for d3 and c3.",
      trapWarning: { name: "Legal" },
      decision: { action: "commit" },
    })));

    await render();
    await act(async () => {
      await api.handleUserMove(MOVE_ONE, jest.fn(), 4000);
    });
    expect(api.commentary).toBe("Your knight on f3 is doing the work here.");
    expect(api.liveChecklist).not.toBeNull();
    expect(api.rootProblem).not.toBeNull();
    expect(api.openingGuidance).not.toBeNull();
    expect(api.trapWarning).not.toBeNull();

    // Move two: hold the evaluation open, so we observe exactly the window the
    // player sees -- new position on the board, evaluation still running.
    const pendingEval = deferred();
    global.fetch = jest.fn(() => pendingEval.promise);

    let inFlight;
    await act(async () => {
      inFlight = api.handleUserMove(MOVE_TWO, jest.fn(), 4000);
      await Promise.resolve();
    });

    expect(api.commentary).toBeNull();
    expect(api.liveChecklist).toBeNull();
    expect(api.rootProblem).toBeNull();
    expect(api.openingGuidance).toBeNull();
    expect(api.trapWarning).toBeNull();

    await act(async () => {
      pendingEval.resolve(response({ decision: { action: "commit" } }));
      await inFlight;
    });
  });

  test("the reading that does arrive still belongs to the move that asked", async () => {
    // Clearing must not throw the answer away -- only the stale one.
    global.fetch = jest.fn(() => Promise.resolve(response({
      commentary: "This knight has no square to go to.",
      decision: { action: "commit" },
    })));

    await render();
    await act(async () => {
      await api.handleUserMove(MOVE_ONE, jest.fn(), 4000);
    });

    expect(api.commentary).toBe("This knight has no square to go to.");
  });
});
