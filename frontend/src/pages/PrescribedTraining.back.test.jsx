/**
 * The "Back" button on /training/pattern/:pattern used a bare `navigate(-1)`.
 * That is a no-op when the page was reached with no in-app history to pop
 * (a direct link, a refresh, or the first page loaded in the tab) — six
 * different pages link into this route, so that is a common landing state,
 * not an edge case. Reported 2026-09-09: "back button doesn't work".
 *
 * Fix: fall back to /home when window.history.state.idx shows there is
 * nothing to go back to.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";

const mockNavigate = jest.fn();

jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
  useSearchParams: () => [new URLSearchParams(""), jest.fn()],
  useParams: () => ({ pattern: "king_safety" }),
  Link: ({ children }) => children,
}), { virtual: true });

jest.mock("@/App", () => ({ API: "https://api.test/api" }), { virtual: true });
jest.mock("framer-motion", () => ({
  motion: new Proxy({}, { get: () => ({ children }) => children }),
}), { virtual: true });
jest.mock("@/components/LichessBoard", () => ({
  __esModule: true, default: () => null,
}), { virtual: true });
jest.mock("@/components/training/PICPieceSafetyLesson", () => ({
  __esModule: true, default: () => null,
}), { virtual: true });
jest.mock("@/components/training/CanonicalTrainingAssignment", () => ({
  __esModule: true, default: () => null,
}), { virtual: true });
jest.mock("@/components/training/DifficultySelector", () => ({
  __esModule: true, default: () => null,
}), { virtual: true });
jest.mock("@/components/training/PersonalizedLessonWorkspace", () => ({
  __esModule: true, default: () => null,
}), { virtual: true });
jest.mock("@/hooks/useMoveCaption", () => ({
  __esModule: true, default: () => ({}),
}), { virtual: true });

const PrescribedTraining = require("./PrescribedTraining").default;

let container;
let root;

const puzzlePayload = {
  puzzles: [
    {
      puzzle_id: "p1",
      fen: "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
      solution_san: "e4",
      issue_type: "king_safety",
      difficulty: "medium",
      source: "your_game",
    },
  ],
  weakness: "king_safety",
};

beforeEach(() => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  window.posthog = { capture: jest.fn() };
  mockNavigate.mockClear();
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve(puzzlePayload) })
  );
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  delete window.posthog;
  delete global.fetch;
});

const renderAndReachBackButton = async () => {
  act(() => root.render(<PrescribedTraining user={{ id: "u1" }} />));
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
  return container.querySelector("button");
};

test("falls back to /home when there is no in-app history to pop", async () => {
  const originalState = window.history.state;
  Object.defineProperty(window.history, "state", {
    configurable: true,
    get: () => ({ idx: 0 }),
  });

  const backButton = await renderAndReachBackButton();
  expect(backButton?.textContent).toContain("Back");
  act(() => backButton.click());

  expect(mockNavigate).toHaveBeenCalledWith("/home");
  expect(mockNavigate).not.toHaveBeenCalledWith(-1);

  Object.defineProperty(window.history, "state", {
    configurable: true,
    value: originalState,
  });
});

test("uses real back navigation when in-app history exists", async () => {
  const originalState = window.history.state;
  Object.defineProperty(window.history, "state", {
    configurable: true,
    get: () => ({ idx: 2 }),
  });

  const backButton = await renderAndReachBackButton();
  act(() => backButton.click());

  expect(mockNavigate).toHaveBeenCalledWith(-1);
  expect(mockNavigate).not.toHaveBeenCalledWith("/home");

  Object.defineProperty(window.history, "state", {
    configurable: true,
    value: originalState,
  });
});
