import { act } from "react";
import { createRoot } from "react-dom/client";
import { Chess } from "chess.js";

let mockBoard;
const mockNavigate = jest.fn();
const mockTrack = jest.fn();
jest.mock("react-router-dom", () => ({ useNavigate: () => mockNavigate }), { virtual: true });
jest.mock("@/App", () => ({ API: "https://api.test/api" }), { virtual: true });
jest.mock("@/lib/analytics", () => ({
  ANALYTICS_EVENTS: { DIAGNOSTIC_PUZZLE_COMPLETED: "puzzle_completed" },
  track: (...args) => mockTrack(...args),
}), { virtual: true });
jest.mock("@/components/LichessBoard", () => {
  const React = require("react");
  return React.forwardRef((props, ref) => {
    mockBoard = props;
    return <div data-testid="board" data-fen={props.fen} />;
  });
}, { virtual: true });
jest.mock("@/components/ChessLoader", () => () => <p>Loading</p>, { virtual: true });
jest.mock("@/components/Layout", () => ({ children }) => children, { virtual: true });
jest.mock("@/components/ui/button", () => ({
  Button: ({ children, variant, ...props }) => <button {...props}>{children}</button>,
}), { virtual: true });
import DiagnosticPuzzles from "./DiagnosticPuzzles";

const FEN = new Chess().fen();
const boardAfterMove = new Chess();
boardAfterMove.move("e4");
const PLAYED_FEN = boardAfterMove.fen();
boardAfterMove.move("e5");
const REPLY_FEN = boardAfterMove.fen();
const START = { status: "in_progress", current_index: 1,
  puzzle: { puzzle_id: "first", fen: FEN, side_to_move: "white" } };
const NEXT = { status: "in_progress", puzzle_number: 1, current_index: 2,
  verdict: "UNDERSTOOD", explanation: "Stored fixture feedback.",
  puzzle: { puzzle_id: "second", fen: FEN, side_to_move: "white" } };
const response = (data, status = 200) => ({ ok: status === 200, status, json: async () => data });

describe("the learner controls diagnostic feedback", () => {
  let root, container, answer;
  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    mockNavigate.mockReset();
    mockTrack.mockReset();
    answer = response(NEXT);
    global.fetch = jest.fn((url) => {
      if (url.endsWith("/start")) return Promise.resolve(response(START));
      if (url.endsWith("/attempt")) return Promise.resolve(answer);
      return Promise.resolve(response({}));
    });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });
  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    jest.useRealTimers();
  });
  const mount = () => act(async () => root.render(<DiagnosticPuzzles />));
  const move = () => act(async () => {
    await mockBoard.onMove({ from: "e2", to: "e4" });
  });
  const click = async (id) => act(async () => {
    container.querySelector(`[data-testid="${id}"]`).click();
  });
  const attempts = () => global.fetch.mock.calls.filter(([url]) => url.endsWith("/attempt"));
  const completed = () => mockTrack.mock.calls.filter(([name]) => name === "puzzle_completed");

  test("restores unread feedback and board after reload, then acknowledges Continue", async () => {
    const saved = { ...NEXT, feedback_id: "receipt-one" };
    global.fetch.mockImplementation((url) => Promise.resolve(response(
      url.endsWith("/start") ? {
        status: "feedback", feedback_protocol: "explicit_v1", feedback_session: "s1",
        current_index: 1, puzzle: START.puzzle, played_fen: PLAYED_FEN, feedback: saved,
      } : saved)));
    await mount();
    expect(mockBoard.fen).toBe(PLAYED_FEN);
    expect(mockBoard.interactive).toBe(false);
    expect(container.textContent).toContain(saved.explanation);
    expect(completed()).toHaveLength(0);
    await click("diagnostic-feedback-continue");
    const acks = global.fetch.mock.calls.filter(([url]) => url.endsWith("/feedback/continue"));
    expect(acks).toHaveLength(1);
    expect(JSON.parse(acks[0][1].body)).toEqual({ feedback_id: "receipt-one" });
    expect(mockBoard.interactive).toBe(true);
    expect(attempts()).toHaveLength(0);
  });

  test("lost Continue response keeps feedback readable and retries only acknowledgement", async () => {
    answer = response({ ...NEXT, feedback_id: "receipt-one" });
    const original = global.fetch.getMockImplementation();
    let fails = true;
    global.fetch.mockImplementation((url, options) => {
      if (url.endsWith("/feedback/continue")) {
        return fails ? Promise.reject(new Error("connection lost")) : Promise.resolve(answer);
      }
      return original(url, options);
    });
    await mount();
    await move();
    await click("diagnostic-feedback-continue");
    expect(container.textContent).toContain("Your answer is saved");
    expect(mockBoard.fen).toBe(PLAYED_FEN);
    expect(mockBoard.interactive).toBe(false);
    fails = false;
    await click("diagnostic-feedback-continue");
    expect(mockBoard.interactive).toBe(true);
    expect(attempts()).toHaveLength(1);
  });

  test("sends session and exact starting board only when the API supports saved feedback", async () => {
    const original = global.fetch.getMockImplementation();
    global.fetch.mockImplementation((url, options) => url.endsWith("/start")
      ? Promise.resolve(response({ ...START, feedback_protocol: "explicit_v1", feedback_session: "s1" }))
      : original(url, options));
    await mount();
    await move();
    expect(JSON.parse(attempts()[0][1].body)).toMatchObject({ feedback_session: "s1", feedback_fen: FEN });
  });

  test("restores final feedback before the summary without submitting an exit", async () => {
    const saved = { status: "complete", verdict: "UNDERSTOOD", feedback_id: "final",
      explanation: "Final saved feedback.", diagnosis: { summary: "A provisional summary." } };
    global.fetch.mockImplementation((url) => Promise.resolve(response(url.endsWith("/start")
      ? { status: "feedback", feedback_protocol: "explicit_v1", feedback_session: "s1",
          current_index: 3, puzzle: START.puzzle, played_fen: PLAYED_FEN, feedback: saved }
      : saved)));
    await mount();
    expect(container.textContent).toContain("Final saved feedback.");
    expect(container.textContent).not.toContain("A provisional summary.");
    await click("diagnostic-feedback-continue");
    expect(container.textContent).toContain("A provisional summary.");
    expect(global.fetch.mock.calls.some(([url]) => url.includes("/exit"))).toBe(false);
  });

  test("feedback and the played board stay until Continue, not a timer", async () => {
    jest.useFakeTimers();
    await mount();
    await move();
    await act(async () => jest.advanceTimersByTime(60000));
    expect(container.textContent).toContain("Stored fixture feedback.");
    expect(mockBoard.fen).toBe(PLAYED_FEN);
    expect(mockBoard.interactive).toBe(false);
    expect(attempts()).toHaveLength(1);
    await click("diagnostic-feedback-continue");
    expect(container.querySelector('[data-testid="diagnostic-feedback"]')).toBeNull();
    expect(mockBoard.fen).toBe(FEN);
    expect(mockBoard.interactive).toBe(true);
    await move();
    expect(JSON.parse(attempts()[1][1].body).puzzle_id).toBe("second");
    expect(completed()[1][1]).toEqual({ puzzle_number: 2 });
  });

  test.each([
    [{ verdict: "UNDERSTOOD" }, "Yes — your move works here"],
    [{ verdict: "PARTIAL" }, "There’s a stronger move to consider"],
    [{ verdict: "MISSING" }, "Let’s look once more"],
    [{ is_correct: true }, "Yes — your move works here"],
    [{ is_correct: false }, "Let’s look once more"],
    [{}, "Your move was recorded"],
  ])("renders the API verdict without inventing understanding: %p", async (fields, expected) => {
    answer = response({ ...NEXT, verdict: undefined, ...fields });
    await mount();
    await move();
    expect(container.textContent).toContain(expected);
    expect(container.querySelector('[data-testid="diagnostic-feedback-continue"]')).not.toBeNull();
  });

  test("an intermediate success is green, not a failed or completed puzzle", async () => {
    answer = response({ ...NEXT, current_index: undefined, verdict: null,
      step_verdict: "UNDERSTOOD", multi_move: { opponent_reply_san: "e5" },
      puzzle: { ...START.puzzle, fen: REPLY_FEN, step: 2 } });
    await mount();
    await move();
    expect(container.textContent).toContain("Yes — your move works here");
    expect(container.textContent).toContain("Next, your opponent plays e5");
    expect(container.textContent).toContain("Continue this position");
    expect(completed()).toHaveLength(0);
    expect(mockBoard.fen).toBe(PLAYED_FEN);
    await click("diagnostic-feedback-continue");
    expect(mockBoard.fen).toBe(REPLY_FEN);
    answer = response({ ...NEXT, status: "complete", diagnosis: { per_concept: {} } });
    await act(async () => mockBoard.onMove({ from: "g1", to: "f3" }));
    expect(completed()).toEqual([["puzzle_completed", { puzzle_number: 1 }]]);
  });

  test("the final answer stays visible before the summary and causes no extra exit", async () => {
    answer = response({ ...NEXT, status: "complete", diagnosis: { per_concept: {} } });
    await mount();
    await move();
    expect(container.textContent).toContain("Stored fixture feedback.");
    expect(container.textContent).toContain("See what we can work on");
    await act(async () => window.dispatchEvent(new Event("pagehide")));
    expect(global.fetch.mock.calls.filter(([url]) => url.includes("/exit"))).toHaveLength(0);
    await click("diagnostic-feedback-continue");
    expect(container.querySelector('[data-testid="diagnostic-feedback"]')).toBeNull();
    expect(container.querySelector('[data-testid="diagnostic-start-training"]')).not.toBeNull();
  });

  test("two board events in the same render submit only once", async () => {
    let release;
    const pending = new Promise(resolve => { release = resolve; });
    const previousFetch = global.fetch;
    global.fetch = jest.fn((url, opts) => url.endsWith("/attempt") ? pending : previousFetch(url, opts));
    await mount();
    await act(async () => {
      mockBoard.onMove({ from: "e2", to: "e4" });
      mockBoard.onMove({ from: "e2", to: "e4" });
    });
    expect(attempts()).toHaveLength(1);
    expect(container.textContent).toContain("Checking your move");
    expect(mockBoard.interactive).toBe(false);
    await act(async () => release(response(NEXT)));
    await move();
    expect(attempts()).toHaveLength(1);
  });

  test.each([409, 500])("HTTP %s preserves context without a failure verdict or automatic retry", async status => {
    answer = response({}, status);
    await mount();
    await move();
    expect(container.querySelector('[role="alert"]')).not.toBeNull();
    expect(container.textContent).toContain("Check saved position");
    expect(mockBoard.fen).toBe(PLAYED_FEN);
    expect(mockBoard.interactive).toBe(false);
    expect(container.querySelector('[data-testid="diagnostic-feedback"]')).toBeNull();
    await move();
    expect(attempts()).toHaveLength(1);
    expect(completed()).toHaveLength(0);
  });

  test("a dropped response never blindly repeats a possibly-saved move", async () => {
    const previousFetch = global.fetch;
    global.fetch = jest.fn((url, opts) => url.endsWith("/attempt")
      ? Promise.reject(new Error("offline")) : previousFetch(url, opts));
    await mount();
    await move();
    expect(container.textContent).toContain("Your answer may have saved");
    expect(mockBoard.fen).toBe(PLAYED_FEN);
    await move();
    expect(attempts()).toHaveLength(1);
  });

  test("missing next position is recoverable rather than an endless loader", async () => {
    answer = response({ ...NEXT, puzzle: null });
    await mount();
    await move();
    await click("diagnostic-feedback-continue");
    expect(container.textContent).toContain("next step is unavailable");
    expect(mockBoard.fen).toBe(PLAYED_FEN);
  });

  test("failed early finish does not discard the board or navigate away", async () => {
    await mount();
    await click("diagnostic-skip-btn");
    await click("diagnostic-exit-confirm");
    expect(container.textContent).toContain("I couldn't finish the session");
    expect(container.querySelector('[data-testid="board"]')).not.toBeNull();
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
