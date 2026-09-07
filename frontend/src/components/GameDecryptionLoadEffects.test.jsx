import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { toast } from "sonner";

import GameDecryptionV5 from "./GameDecryptionV5";

let mockSearchParams = new URLSearchParams();
const mockSetSearchParams = jest.fn();
jest.mock("react-router-dom", () => ({
  useNavigate: () => jest.fn(),
  useSearchParams: () => [mockSearchParams, mockSetSearchParams],
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
const payload = (label, { severity = "good", motifBlindspot = null } = {}) => ({
  decryption_data: [{
    move_number: 1,
    move_san: "e4",
    is_user_move: true,
    severity,
    opening_name: `${label} Opening`,
    narrative: `${label} NARRATIVE`,
    fen_before: START,
    fen_after: AFTER_E4,
    eval_before: 0,
    eval_after: 12,
  }],
  motif_blindspot: motifBlindspot,
});

describe("GameDecryptionV5 request and navigation ownership", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    mockSearchParams = new URLSearchParams();
    mockSetSearchParams.mockReset();
    window.history.replaceState({}, "", "/");
    toast.success.mockReset();
    toast.error.mockReset();
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

  const clickButton = (label) => {
    const button = [...container.querySelectorAll("button")]
      .find((candidate) => candidate.textContent.includes(label));
    expect(button).toBeDefined();
    act(() => button.dispatchEvent(new MouseEvent("click", { bubbles: true })));
  };

  const enterText = (element, value) => {
    const setter = Object.getOwnPropertyDescriptor(
      Object.getPrototypeOf(element),
      "value",
    ).set;
    act(() => {
      setter.call(element, value);
      element.dispatchEvent(new Event("input", { bubbles: true }));
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

  test("a late show-facts failure cannot write the prior game's coaching fields", async () => {
    window.history.replaceState({}, "", "/?show_facts=1");
    const oldFacts = deferred();
    global.fetch = jest.fn((url) => {
      if (url.includes("/coach/decryption/v5/old-game")) {
        return Promise.resolve(response(payload("OLD", { motifBlindspot: "OLD MOTIF" })));
      }
      if (url.includes("/coach/decryption/v5/new-game")) {
        return Promise.resolve(response(payload("NEW", { motifBlindspot: "NEW MOTIF" })));
      }
      if (url.includes("/coach/decryption/facts/old-game")) return oldFacts.promise;
      if (url.includes("/coach/decryption/facts/new-game")) {
        return Promise.resolve({ ok: false, status: 503 });
      }
      if (url.includes("/coach/decryption/gold/")) return Promise.resolve(response({ gold: {}, prefs: {} }));
      if (url.includes("/focus-badges")) return Promise.resolve(response({ badges: {} }));
      if (url.includes("/coach/decryption/per-move/")) return Promise.resolve(response({ captions: [] }));
      if (url.includes("/thoughts")) return Promise.resolve(response({ thoughts: [] }));
      throw new Error(`Unexpected request: ${url}`);
    });

    await renderReview("old-game");
    await flush();
    await renderReview("new-game");
    await flush();
    expect(container.textContent).toContain("NEW MOTIF");

    oldFacts.resolve({ ok: false, status: 503 });
    await flush();

    expect(container.textContent).toContain("NEW MOTIF");
    expect(container.textContent).not.toContain("OLD MOTIF");
  });

  test("an unsaved thought survives a validation variant reload of the same game", async () => {
    global.fetch = jest.fn((url) => {
      if (url.includes("/coach/decryption/v5/same-game")) {
        return Promise.resolve(response(payload("SAME", { severity: "mistake" })));
      }
      if (url.includes("/coach/decryption/gold/")) return Promise.resolve(response({ gold: {}, prefs: {} }));
      if (url.includes("/focus-badges")) return Promise.resolve(response({ badges: {} }));
      if (url.includes("/coach/decryption/per-move/")) return Promise.resolve(response({ captions: [] }));
      if (url.includes("/thoughts")) return Promise.resolve(response({ thoughts: [] }));
      if (url.includes("/coach/play/position/read")) return Promise.resolve(response({}));
      throw new Error(`Unexpected request: ${url}`);
    });

    await renderReview("same-game");
    await flush();
    act(() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true })));
    await flush();
    clickButton("Why did you play e4?");
    clickButton("Other...");
    const textarea = container.querySelector("textarea[placeholder='What were you thinking...']");
    expect(textarea).not.toBeNull();
    enterText(textarea, "I thought the center was safe.");

    mockSearchParams = new URLSearchParams("review_variant=b");
    await renderReview("same-game");
    await flush();
    act(() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true })));
    await flush();

    const preserved = container.querySelector("textarea[placeholder='What were you thinking...']");
    expect(preserved).not.toBeNull();
    expect(preserved.value).toBe("I thought the center was safe.");
  });

  test("a late thought save cannot mutate or toast inside the replacement game", async () => {
    const oldSave = deferred();
    global.fetch = jest.fn((url, options = {}) => {
      if (url.includes("/coach/decryption/v5/old-game")) {
        return Promise.resolve(response(payload("OLD", { severity: "mistake" })));
      }
      if (url.includes("/coach/decryption/v5/new-game")) {
        return Promise.resolve(response(payload("NEW", { severity: "mistake" })));
      }
      if (url.includes("/games/old-game/thought") && options.method === "POST") return oldSave.promise;
      if (url.includes("/coach/decryption/gold/")) return Promise.resolve(response({ gold: {}, prefs: {} }));
      if (url.includes("/focus-badges")) return Promise.resolve(response({ badges: {} }));
      if (url.includes("/coach/decryption/per-move/")) return Promise.resolve(response({ captions: [] }));
      if (url.includes("/thoughts")) return Promise.resolve(response({ thoughts: [] }));
      if (url.includes("/coach/play/position/read")) return Promise.resolve(response({}));
      throw new Error(`Unexpected request: ${url}`);
    });

    await renderReview("old-game");
    await flush();
    act(() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true })));
    await flush();
    clickButton("Why did you play e4?");
    clickButton("Other...");
    enterText(
      container.querySelector("textarea[placeholder='What were you thinking...']"),
      "I missed the reply.",
    );
    clickButton("Save");

    await renderReview("new-game");
    await flush();
    act(() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true })));
    await flush();
    expect(container.textContent).toContain("Why did you play e4?");

    oldSave.resolve({ ok: true, status: 200 });
    await flush();

    expect(toast.success).not.toHaveBeenCalled();
    expect(container.textContent).not.toContain("Your thinking");
    expect(container.textContent).toContain("Why did you play e4?");
  });
});
