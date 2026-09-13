/**
 * A player who answers some positions and leaves still gets a profile.
 *
 * The backend has always been willing to score a partial run -- /diagnostic/exit
 * says "Score whatever they solved and STILL build their profile from it" --
 * but only the confirm-dialog button ever called it. Navigating away, pressing
 * back or closing the tab left the session stuck in_progress and the answers
 * discarded.
 *
 * Measured on production: 40 diagnostic sessions, 34 stranded in_progress,
 * holding 104 answered puzzles between them. One player answered 19 of 20 and
 * got nothing for it. Only 2 sessions ever reached "complete".
 *
 * This matters most for a player with no Chess.com or Lichess account, for whom
 * the positions are one of only two doors into the product.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";

const mockNavigate = jest.fn();

jest.mock("react-router-dom", () => ({ useNavigate: () => mockNavigate }), { virtual: true });
jest.mock("@/App", () => ({ API: "https://api.test/api" }), { virtual: true });
jest.mock("@/lib/analytics", () => ({
  ANALYTICS_EVENTS: {},
  track: jest.fn(),
}), { virtual: true });
jest.mock("@/components/LichessBoard", () => () => null, { virtual: true });
jest.mock("@/components/ChessLoader", () => () => null, { virtual: true });
jest.mock("@/components/Layout", () => ({ children }) => children, { virtual: true });
jest.mock("@/components/ui/button", () => ({ Button: () => null }), { virtual: true });

import DiagnosticPuzzles from "./DiagnosticPuzzles";

const START_PAYLOAD = {
  status: "in_progress",
  puzzle: { fen: "8/8/8/8/8/8/8/K6k w - - 0 1", user_color: "white" },
  current_index: 1,
};

function exitCalls() {
  return global.fetch.mock.calls.filter(
    ([url, opts]) =>
      String(url).includes("/diagnostic/exit") && opts?.method === "POST"
  );
}

describe("leaving the diagnostic part-way through", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    mockNavigate.mockReset();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    container.remove();
    jest.resetAllMocks();
  });

  const mountWith = (payload) => {
    global.fetch = jest.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(payload) })
    );
    return act(async () => {
      root.render(<DiagnosticPuzzles />);
    });
  };

  test("an answered position is reported when the player navigates away", async () => {
    await mountWith({ ...START_PAYLOAD, current_index: 4 });

    expect(exitCalls()).toHaveLength(0);          // nothing while they are here
    await act(async () => root.unmount());

    const calls = exitCalls();
    expect(calls).toHaveLength(1);
    // keepalive lets the request outlive the page being torn down, and
    // checkpoint=true scores the partial run WITHOUT closing it, so the
    // player can still come back and finish.
    expect(String(calls[0][0])).toContain("checkpoint=true");
    expect(calls[0][1]).toEqual(
      expect.objectContaining({ method: "POST", keepalive: true, credentials: "include" })
    );
  });

  test("closing the tab reports it too", async () => {
    await mountWith({ ...START_PAYLOAD, current_index: 4 });

    await act(async () => {
      window.dispatchEvent(new Event("pagehide"));
    });

    expect(exitCalls()).toHaveLength(1);
  });

  test("it is reported once, not once per exit route", async () => {
    await mountWith({ ...START_PAYLOAD, current_index: 4 });

    await act(async () => {
      window.dispatchEvent(new Event("pagehide"));
    });
    await act(async () => root.unmount());

    expect(exitCalls()).toHaveLength(1);
  });

  test("a player who answered nothing is not reported", async () => {
    // current_index 1 means the first position is still on screen unanswered.
    await mountWith(START_PAYLOAD);

    await act(async () => root.unmount());

    expect(exitCalls()).toHaveLength(0);
  });

  test("a finished diagnostic is not re-reported on the way out", async () => {
    await mountWith({
      status: "complete",
      diagnosis: { version: 2, rating_estimate: { low: 900, high: 1100 } },
    });

    await act(async () => root.unmount());

    expect(exitCalls()).toHaveLength(0);
  });
});
