import React, { act } from "react";
import { createRoot } from "react-dom/client";

import LabV2 from "./LabV2";

const mockNavigate = jest.fn();

jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
  useParams: () => ({ gameId: "game-1" }),
  useSearchParams: () => [new URLSearchParams(), jest.fn()],
}), { virtual: true });
jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("@/lib/analytics", () => ({
  ANALYTICS_EVENTS: { FUNNEL_REVIEW_OPENED: "review_opened" },
  track: jest.fn(),
}), { virtual: true });
jest.mock("@/components/Layout", () => ({ children }) => <div>{children}</div>, { virtual: true });
jest.mock("@/components/LichessBoard", () => ({ fen }) => <div data-testid="lab-board">{fen}</div>, { virtual: true });
jest.mock("@/components/FeedbackModal", () => () => null, { virtual: true });
jest.mock("@/components/GameDecryptionV5", () => () => <div data-testid="decrypt-view" />, { virtual: true });
jest.mock("@/components/Lab/CoachInsightPanel", () => () => null, { virtual: true });
jest.mock("@/components/coach/CoachSession", () => () => null, { virtual: true });
jest.mock("@/components/Lab/CoachAction", () => () => null, { virtual: true });
jest.mock("@/components/coach/CoachMovePanel", () => () => null, { virtual: true });
jest.mock("@/components/experience/CanonicalReviewFocus", () => () => null, { virtual: true });
jest.mock("@/components/shared/FlagMoveDialog", () => ({ InlineFlag: () => null }), { virtual: true });
jest.mock("@/hooks/usePuzzleSubmissionIdentity", () => () => ["submission-1", jest.fn()], { virtual: true });
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));
jest.mock("framer-motion", () => ({
  motion: new Proxy({}, { get: () => ({ children, ...props }) => <div {...props}>{children}</div> }),
}));

const response = (body) => ({ ok: true, status: 200, json: () => Promise.resolve(body) });

describe("LabV2 keyboard listener ownership", () => {
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
    jest.restoreAllMocks();
  });

  test("one listener stays installed while using the latest move index and PGN", async () => {
    const addListener = jest.spyOn(window, "addEventListener");
    global.fetch = jest.fn((url) => {
      if (url.endsWith("/games/game-1")) {
        return Promise.resolve(response({
          game_id: "game-1",
          user_color: "white",
          opponent_name: "Opponent",
          result: "1-0",
          pgn: "[Result \"*\"]\n\n1. e4 e5 2. Nf3 Nc6 *",
        }));
      }
      if (url.includes("/analysis/game-1/enriched")) {
        return Promise.resolve(response({
          stockfish_analysis: {
            move_evaluations: [{
              move_number: 1,
              move: "e4",
              classification: "mistake",
              eval_after: -1,
            }],
          },
        }));
      }
      if (url.endsWith("/lab/game-1")) return Promise.resolve(response({}));
      if (url.endsWith("/games/game-1/coach-review")) return Promise.resolve(response({}));
      if (url.includes("/coach/coaching-context/review")) return Promise.resolve(response({}));
      if (url.endsWith("/lab/game-1/deep-strategy")) return Promise.resolve(response({}));
      throw new Error(`Unexpected request: ${url}`);
    });

    await act(async () => root.render(<LabV2 user={{ user_id: "student-1" }} />));
    await act(async () => {
      for (let i = 0; i < 16; i += 1) await Promise.resolve();
    });

    act(() => container.querySelector("[data-testid='habits-view-btn']").click());
    expect(container.textContent).toContain("0 / 4");
    expect(addListener.mock.calls.filter(([type]) => type === "keydown")).toHaveLength(1);

    act(() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true })));
    expect(container.textContent).toContain("1 / 4");
    expect(addListener.mock.calls.filter(([type]) => type === "keydown")).toHaveLength(1);

    act(() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true })));
    expect(container.textContent).toContain("4 / 4");
    expect(addListener.mock.calls.filter(([type]) => type === "keydown")).toHaveLength(1);
  });
});
