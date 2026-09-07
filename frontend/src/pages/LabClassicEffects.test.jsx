import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { toast } from "sonner";

import LabClassic from "./LabClassic";

let mockGameId = "game-one";
let mockSearchParams = new URLSearchParams();
const mockNavigate = jest.fn();

jest.mock("react-router-dom", () => ({
  useParams: () => ({ gameId: mockGameId }),
  useNavigate: () => mockNavigate,
  useSearchParams: () => [mockSearchParams],
}), { virtual: true });
jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("@/components/Layout", () => ({ children }) => <div>{children}</div>, { virtual: true });
jest.mock("@/components/LichessBoard", () => ({ fen }) => (
  <div data-testid="classic-board" data-fen={fen} />
), { virtual: true });
jest.mock("@/components/ui/button", () => ({
  Button: ({ children, variant: _variant, size: _size, asChild: _asChild, ...props }) => (
    <button {...props}>{children}</button>
  ),
}), { virtual: true });
jest.mock("@/components/ui/card", () => ({
  Card: ({ children }) => <div>{children}</div>,
  CardContent: ({ children }) => <div>{children}</div>,
}), { virtual: true });
jest.mock("@/components/ui/tabs", () => ({
  Tabs: ({ children }) => <div>{children}</div>,
  TabsList: ({ children }) => <div>{children}</div>,
  TabsTrigger: ({ children }) => <button>{children}</button>,
  TabsContent: () => null,
}), { virtual: true });
jest.mock("@/components/ui/scroll-area", () => ({ ScrollArea: ({ children }) => <div>{children}</div> }), { virtual: true });
jest.mock("@/components/ui/badge", () => ({ Badge: ({ children }) => <span>{children}</span> }), { virtual: true });
jest.mock("@/components/Lab", () => ({
  LessonCard: () => null,
  CoachNotice: () => null,
  FocusLockStatus: () => null,
  AlternateTimeline: () => null,
}), { virtual: true });
jest.mock("@/components/FeedbackModal", () => () => null, { virtual: true });
jest.mock("@/components/InlineFeedbackButton", () => () => null, { virtual: true });
jest.mock("@/components/MyFeedback", () => () => null, { virtual: true });
jest.mock("@/components/GuidedAnalysis", () => () => null, { virtual: true });
jest.mock("sonner", () => ({ toast: {
  success: jest.fn(),
  error: jest.fn(),
  info: jest.fn(),
} }));

const PGN = "1. e4 e5 2. Nf3 Nc6";
const AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1";
const AFTER_NF3 = "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2";

const response = (body, options = {}) => ({
  ok: options.ok ?? true,
  status: options.status ?? 200,
  json: () => Promise.resolve(body),
});
const deferred = () => {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
};

const gamePayload = () => ({
  pgn: PGN,
  user_color: "white",
  white_player: "Student",
  black_player: "Opponent",
  result: "1-0",
});

describe("LabClassic committed navigation and polling ownership", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    mockGameId = "game-one";
    mockSearchParams = new URLSearchParams();
    mockNavigate.mockReset();
    toast.success.mockReset();
    toast.error.mockReset();
    toast.info.mockReset();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    delete global.fetch;
    jest.useRealTimers();
  });

  const flush = async () => {
    await act(async () => {
      for (let i = 0; i < 30; i += 1) await Promise.resolve();
    });
  };

  const renderLab = async () => {
    await act(async () => root.render(<LabClassic user={{ username: "Student" }} />));
    await flush();
  };

  const standardFetch = (status = { status: "analyzed" }) => jest.fn((url) => {
    if (url.endsWith(`/games/${mockGameId}`)) return Promise.resolve(response(gamePayload()));
    if (url.endsWith(`/analysis/${mockGameId}`)) {
      return Promise.resolve(response({ stockfish_analysis: { move_evaluations: [], accuracy: 91 } }));
    }
    if (url.includes("/coach/commentary/")) return Promise.resolve(response({}));
    if (url.endsWith(`/games/${mockGameId}/analysis-status`)) return Promise.resolve(response(status));
    if (url.endsWith(`/lab/${mockGameId}`)) return Promise.resolve(response({}));
    if (url.endsWith("/cognitive/training-priority")) return Promise.resolve(response({}));
    if (url.endsWith("/coach/focus-lock")) return Promise.resolve(response({}));
    if (url.endsWith("/coach/home-intelligence")) return Promise.resolve(response({}));
    if (url.includes("/coach/module/")) return Promise.resolve(response({}));
    throw new Error(`Unexpected request: ${url}`);
  });

  test("the journey move parameter navigates with the current parsed game", async () => {
    mockSearchParams = new URLSearchParams("move=2&src=journey");
    global.fetch = standardFetch();

    await renderLab();

    expect(container.querySelector("[data-testid='classic-board']").dataset.fen).toBe(AFTER_NF3);
    expect(container.textContent).toContain("From Journey");
  });

  test("autoplay advances by one current-game ply", async () => {
    jest.useFakeTimers();
    global.fetch = standardFetch();
    await renderLab();

    const playButton = container.querySelector("svg.lucide-play")?.closest("button");
    expect(playButton).not.toBeNull();
    act(() => playButton.dispatchEvent(new MouseEvent("click", { bubbles: true })));
    act(() => jest.advanceTimersByTime(600));
    await flush();

    expect(container.querySelector("[data-testid='classic-board']").dataset.fen).toBe(AFTER_E4);
  });

  test("an in-flight queue poll cannot complete inside a replacement game", async () => {
    jest.useFakeTimers();
    const oldPoll = deferred();
    let oldStatusCalls = 0;
    global.fetch = jest.fn((url) => {
      const id = url.includes("game-two") ? "game-two" : "game-one";
      if (url.endsWith(`/games/${id}`)) return Promise.resolve(response(gamePayload()));
      if (url.endsWith(`/analysis/${id}`)) {
        return Promise.resolve(response({ stockfish_analysis: { move_evaluations: [], accuracy: 91 } }));
      }
      if (url.includes("/coach/commentary/")) return Promise.resolve(response({}));
      if (url.endsWith("/games/game-one/analysis-status")) {
        oldStatusCalls += 1;
        return oldStatusCalls === 1
          ? Promise.resolve(response({ status: "processing" }))
          : oldPoll.promise;
      }
      if (url.endsWith("/games/game-two/analysis-status")) {
        return Promise.resolve(response({ status: "analyzed" }));
      }
      if (url.endsWith(`/lab/${id}`)) return Promise.resolve(response({}));
      if (url.endsWith("/cognitive/training-priority")) return Promise.resolve(response({}));
      if (url.endsWith("/coach/focus-lock")) return Promise.resolve(response({}));
      if (url.endsWith("/coach/home-intelligence")) return Promise.resolve(response({}));
      if (url.includes("/coach/module/")) return Promise.resolve(response({}));
      throw new Error(`Unexpected request: ${url}`);
    });

    await renderLab();
    act(() => jest.advanceTimersByTime(5000));
    await flush();
    expect(oldStatusCalls).toBe(2);

    mockGameId = "game-two";
    await renderLab();
    oldPoll.resolve(response({ status: "analyzed" }));
    await flush();

    expect(toast.success).not.toHaveBeenCalledWith("Analysis complete!");
    expect(global.fetch.mock.calls.filter(([url]) => url.endsWith("/analysis/game-one"))).toHaveLength(1);
    expect(container.textContent).toContain("vs Opponent");
  });

  test("a reanalyze request cannot start polling after its game is replaced", async () => {
    const oldReanalyze = deferred();
    global.fetch = jest.fn((url, options = {}) => {
      const id = url.includes("game-two") ? "game-two" : "game-one";
      if (url.endsWith("/games/game-one/reanalyze") && options.method === "POST") {
        return oldReanalyze.promise;
      }
      if (url.endsWith(`/games/${id}`)) return Promise.resolve(response(gamePayload()));
      if (url.endsWith(`/analysis/${id}`)) {
        return Promise.resolve(response({ stockfish_analysis: { move_evaluations: [], accuracy: 91 } }));
      }
      if (url.includes("/coach/commentary/")) return Promise.resolve(response({}));
      if (url.endsWith(`/games/${id}/analysis-status`)) return Promise.resolve(response({ status: "analyzed" }));
      if (url.endsWith(`/lab/${id}`)) return Promise.resolve(response({}));
      if (url.endsWith("/cognitive/training-priority")) return Promise.resolve(response({}));
      if (url.endsWith("/coach/focus-lock")) return Promise.resolve(response({}));
      if (url.endsWith("/coach/home-intelligence")) return Promise.resolve(response({}));
      if (url.includes("/coach/module/")) return Promise.resolve(response({}));
      throw new Error(`Unexpected request: ${url}`);
    });

    await renderLab();
    const reanalyzeButton = container.querySelector("[data-testid='reanalyze-header-btn']");
    expect(reanalyzeButton).not.toBeNull();
    act(() => reanalyzeButton.click());
    await flush();

    mockGameId = "game-two";
    await renderLab();
    oldReanalyze.resolve(response({ message: "Old game queued", status: "pending" }));
    await flush();

    expect(toast.success).not.toHaveBeenCalledWith("Old game queued");
    expect(container.textContent).toContain("vs Opponent");
  });

  test("an analyzed status is not published until both review payloads refresh", async () => {
    jest.useFakeTimers();
    let statusCalls = 0;
    let analysisCalls = 0;
    global.fetch = jest.fn((url) => {
      if (url.endsWith("/games/game-one")) return Promise.resolve(response(gamePayload()));
      if (url.endsWith("/analysis/game-one")) {
        analysisCalls += 1;
        return analysisCalls === 1
          ? Promise.resolve(response({ stockfish_analysis: { move_evaluations: [], accuracy: 91 } }))
          : Promise.resolve(response({ detail: "refresh failed" }, { ok: false, status: 503 }));
      }
      if (url.includes("/coach/commentary/")) return Promise.resolve(response({}));
      if (url.endsWith("/games/game-one/analysis-status")) {
        statusCalls += 1;
        return Promise.resolve(response(statusCalls === 1
          ? { status: "processing" }
          : { status: "analyzed" }));
      }
      if (url.endsWith("/lab/game-one")) return Promise.resolve(response({ refreshed: true }));
      if (url.endsWith("/cognitive/training-priority")) return Promise.resolve(response({}));
      if (url.endsWith("/coach/focus-lock")) return Promise.resolve(response({}));
      if (url.endsWith("/coach/home-intelligence")) return Promise.resolve(response({}));
      if (url.includes("/coach/module/")) return Promise.resolve(response({}));
      throw new Error(`Unexpected request: ${url}`);
    });

    await renderLab();
    act(() => jest.advanceTimersByTime(5000));
    await flush();

    expect(toast.success).not.toHaveBeenCalledWith("Analysis complete!");
    expect(toast.error).toHaveBeenCalledWith(
      "Analysis finished, but the complete review could not be refreshed. Please retry."
    );
    expect(container.querySelector("[data-testid='lab-analysis-queue-status-inline']")?.textContent)
      .toContain("Analysis failed");
  });

  test("the backend queued contract starts the single poll and publishes a complete refresh", async () => {
    jest.useFakeTimers();
    let statusCalls = 0;
    let analysisCalls = 0;
    let labCalls = 0;
    global.fetch = jest.fn((url, options = {}) => {
      if (url.endsWith("/games/game-one/reanalyze") && options.method === "POST") {
        return Promise.resolve(response({ status: "queued", message: "Game queued" }));
      }
      if (url.endsWith("/games/game-one")) return Promise.resolve(response(gamePayload()));
      if (url.endsWith("/analysis/game-one")) {
        analysisCalls += 1;
        return Promise.resolve(response({
          stockfish_analysis: { move_evaluations: [], accuracy: analysisCalls === 1 ? 91 : 96 },
        }));
      }
      if (url.includes("/coach/commentary/")) return Promise.resolve(response({}));
      if (url.endsWith("/games/game-one/analysis-status")) {
        statusCalls += 1;
        return Promise.resolve(response({ status: "analyzed" }));
      }
      if (url.endsWith("/lab/game-one")) {
        labCalls += 1;
        return Promise.resolve(response({ refresh_version: labCalls }));
      }
      if (url.endsWith("/cognitive/training-priority")) return Promise.resolve(response({}));
      if (url.endsWith("/coach/focus-lock")) return Promise.resolve(response({}));
      if (url.endsWith("/coach/home-intelligence")) return Promise.resolve(response({}));
      if (url.includes("/coach/module/")) return Promise.resolve(response({}));
      throw new Error(`Unexpected request: ${url}`);
    });

    await renderLab();
    const reanalyzeButton = container.querySelector("[data-testid='reanalyze-header-btn']");
    expect(reanalyzeButton).not.toBeNull();
    act(() => reanalyzeButton.click());
    await flush();
    expect(reanalyzeButton.textContent).toContain("Re-analyzing");

    act(() => jest.advanceTimersByTime(5000));
    await flush();

    expect(statusCalls).toBe(2);
    expect(analysisCalls).toBe(2);
    expect(labCalls).toBe(2);
    expect(toast.success).toHaveBeenCalledWith("Analysis complete!");
    expect(container.querySelector("[data-testid='reanalyze-header-btn']")?.textContent)
      .toContain("Re-analyze");
  });
});
