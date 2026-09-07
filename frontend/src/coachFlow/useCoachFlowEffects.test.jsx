import React, { act } from "react";
import { createRoot } from "react-dom/client";

import useCoachFlow from "./useCoachFlow";

jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });

const MOVE = {
  san: "e4",
  uci: "e2e4",
  from: "e2",
  to: "e4",
  fenBefore: "start",
  fenAfterPreview: "after-e4",
  moveIndexPreview: 0,
};

const Harness = ({ session, gameMode, expose }) => {
  expose(useCoachFlow({ session, gameMode, userRating: 1200 }));
  return null;
};

const response = (body) => ({ ok: true, json: () => Promise.resolve(body) });
const deferred = () => {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
};

describe("useCoachFlow current mode ownership", () => {
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

  test("switching to pure play bypasses coaching evaluation immediately", async () => {
    const session = { session_id: "session-1" };
    let flow;
    const expose = (value) => { flow = value; };
    global.fetch = jest.fn();

    await act(async () => root.render(
      <Harness session={session} gameMode="coach" expose={expose} />
    ));
    await act(async () => root.render(
      <Harness session={session} gameMode="play" expose={expose} />
    ));

    const commit = jest.fn().mockResolvedValue(true);
    let result;
    await act(async () => {
      result = await flow.handleUserMove(MOVE, commit, 2.5);
    });

    expect(result).toEqual({ autoCommitted: true });
    expect(commit).toHaveBeenCalledWith("e4", 2.5);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  test("an evaluation from a replaced session cannot commit its move", async () => {
    const oldEvaluation = deferred();
    let flow;
    const expose = (value) => { flow = value; };
    global.fetch = jest.fn(() => oldEvaluation.promise);

    await act(async () => root.render(
      <Harness session={{ session_id: "session-old" }} gameMode="coach" expose={expose} />
    ));

    const commit = jest.fn().mockResolvedValue(true);
    let pendingResult;
    await act(async () => {
      pendingResult = flow.handleUserMove(MOVE, commit, 2.5);
      await Promise.resolve();
    });

    await act(async () => root.render(
      <Harness session={{ session_id: "session-new" }} gameMode="coach" expose={expose} />
    ));

    oldEvaluation.resolve(response({
      coachingDecision: { layer: "silent" },
      shouldAutoCommit: true,
    }));

    let result;
    await act(async () => { result = await pendingResult; });

    expect(result).toEqual({ autoCommitted: false, cancelled: true });
    expect(commit).not.toHaveBeenCalled();
  });
});
