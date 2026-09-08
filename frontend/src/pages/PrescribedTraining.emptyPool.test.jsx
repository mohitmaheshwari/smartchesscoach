/**
 * The coaching panel (framing text + Socratic question + Show-the-solution/
 * Skip links) was gated only on `puzzleState`, never on `currentPuzzle`
 * actually existing. With an empty puzzle pool, currentPuzzle is undefined
 * and puzzleState stays at its initial "thinking" — so the panel rendered
 * anyway, falling through to static per-weakness copy
 * ("Which of your pieces has no defender?" for piece_safety) as if a real
 * puzzle were loaded, right next to a board that correctly said "No puzzle
 * available". Reported live 2026-09-09 on /training/pattern/piece_safety.
 *
 * Fix: render an honest empty state in the coaching panel too when there's
 * no currentPuzzle, instead of falling through to fabricated content.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";

const mockNavigate = jest.fn();

jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
  useSearchParams: () => [new URLSearchParams(""), jest.fn()],
  useParams: () => ({ pattern: "piece_safety" }),
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

const emptyPoolPayload = { puzzles: [], weakness: "piece_safety", pool_thin: true };

beforeEach(() => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  window.posthog = { capture: jest.fn() };
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve(emptyPoolPayload) })
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

test("an empty puzzle pool never fabricates a Socratic question", async () => {
  act(() => root.render(<PrescribedTraining user={{ id: "u1" }} />));
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });

  expect(container.textContent).toContain("No puzzle available");
  expect(container.textContent).not.toContain("Which of your pieces has no defender?");
  expect(container.textContent).not.toContain("Show the solution");
  expect(container.textContent).not.toContain("Skip this one");
});
