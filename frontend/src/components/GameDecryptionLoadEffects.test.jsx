import React, { act } from "react";
import { createRoot } from "react-dom/client";

import GameDecryptionV5 from "./GameDecryptionV5";

jest.mock("react-router-dom", () => ({
  useNavigate: () => jest.fn(),
  useSearchParams: () => [new URLSearchParams(), jest.fn()],
}), { virtual: true });
jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("@/components/LichessBoard", () => {
  const ReactModule = require("react");
  return ReactModule.forwardRef(({ fen }, ref) => {
    ReactModule.useImperativeHandle(ref, () => ({
      cancelVariation: jest.fn(),
      playVariation: jest.fn(),
    }));
    return <div data-testid="review-board">{fen}</div>;
  });
}, { virtual: true });
jest.mock("@/components/EvalBar", () => () => null, { virtual: true });
jest.mock("@/components/EvalGraph", () => () => null, { virtual: true });
jest.mock("@/components/ClickableLine", () => ({
  __esModule: true,
  default: ({ text }) => <span>{text}</span>,
  extractMovesFromText: () => [],
}), { virtual: true });
jest.mock("@/components/ClickableCaption", () => ({ children, text }) => <span>{children || text}</span>, { virtual: true });
jest.mock("@/components/TruthHeadline", () => () => null, { virtual: true });
jest.mock("@/components/PlayerDecryption", () => () => null, { virtual: true });
jest.mock("@/components/PatternEvidence", () => () => null, { virtual: true });
jest.mock("@/components/GameMoments", () => () => null, { virtual: true });
jest.mock("@/components/review/PersonalizedReviewCoach", () => ({
  __esModule: true,
  default: () => null,
  boardArrowsForReviewVisual: () => [],
}), { virtual: true });
jest.mock("@/components/review/ReviewValidationPanel", () => () => null, { virtual: true });
jest.mock("@/components/shared/FlagMoveDialog", () => ({ InlineFlag: () => null }), { virtual: true });
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

const START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1";

const response = (body) => ({ ok: true, status: 200, json: () => Promise.resolve(body) });
const deferred = () => {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
};
const payload = (label) => ({
  decryption_data: [{
    move_number: 1,
    move_san: "e4",
    is_user_move: true,
    severity: "good",
    opening_name: `${label} Opening`,
    narrative: `${label} NARRATIVE`,
    fen_before: START,
    fen_after: AFTER_E4,
    eval_before: 0,
    eval_after: 12,
  }],
});

describe("GameDecryptionV5 request and navigation ownership", () => {
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
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  const renderReview = async (gameId) => {
    await act(async () => root.render(
      <GameDecryptionV5 gameId={gameId} userColor="white" />
    ));
  };

  const flush = async () => {
    await act(async () => {
      for (let i = 0; i < 12; i += 1) await Promise.resolve();
    });
  };

  test("a late prior-game response cannot replace the current review", async () => {
    const oldLoad = deferred();
    const addListener = jest.spyOn(window, "addEventListener");
    global.fetch = jest.fn((url) => {
      if (url.includes("/coach/decryption/v5/old-game")) return oldLoad.promise;
      if (url.includes("/coach/decryption/v5/new-game")) return Promise.resolve(response(payload("NEW")));
      if (url.includes("/coach/decryption/gold/")) return Promise.resolve(response({ gold: {}, prefs: {} }));
      if (url.includes("/focus-badges")) return Promise.resolve(response({ badges: {} }));
      if (url.includes("/coach/decryption/per-move/")) return Promise.resolve(response({ captions: [] }));
      if (url.includes("/thoughts")) return Promise.resolve(response({ thoughts: [] }));
      throw new Error(`Unexpected request: ${url}`);
    });

    await renderReview("old-game");
    await renderReview("new-game");
    await flush();
    expect(container.textContent).toContain("NEW Opening");

    oldLoad.resolve(response(payload("OLD")));
    await flush();

    expect(container.textContent).toContain("NEW Opening");
    expect(container.textContent).not.toContain("OLD Opening");
    expect(addListener.mock.calls.filter(([type]) => type === "keydown")).toHaveLength(1);

    act(() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true })));
    expect(container.textContent).toContain("NEW NARRATIVE");
    expect(container.textContent).not.toContain("OLD NARRATIVE");
  });

  test("a generating review stays loading and its retry is cancelled on game change", async () => {
    jest.useFakeTimers();
    global.fetch = jest.fn((url) => {
      if (url.includes("/coach/decryption/v5/old-game")) {
        return Promise.resolve(response({ status: "generating" }));
      }
      if (url.includes("/coach/decryption/v5/new-game")) return Promise.resolve(response(payload("NEW")));
      if (url.includes("/coach/decryption/gold/")) return Promise.resolve(response({ gold: {}, prefs: {} }));
      if (url.includes("/focus-badges")) return Promise.resolve(response({ badges: {} }));
      if (url.includes("/coach/decryption/per-move/")) return Promise.resolve(response({ captions: [] }));
      if (url.includes("/thoughts")) return Promise.resolve(response({ thoughts: [] }));
      throw new Error(`Unexpected request: ${url}`);
    });

    await renderReview("old-game");
    await flush();
    expect(container.querySelector("[data-testid='decryption-loading']")).not.toBeNull();

    await renderReview("new-game");
    await flush();
    act(() => jest.advanceTimersByTime(5000));
    await flush();

    expect(global.fetch.mock.calls.filter(([url]) => url.includes("/coach/decryption/v5/old-game"))).toHaveLength(1);
    expect(container.textContent).toContain("NEW Opening");
  });
});
