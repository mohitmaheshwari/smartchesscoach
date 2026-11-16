/**
 * An own-game piece-safety drill shows which game move was the problem.
 *
 * 2026-11-16, Mohit, on his move 22: "it should tell what move is the problem,
 * from this position how do you know piece safety". The page showed the
 * position and a generic question; the game move (Be7, taken by the queen on
 * c7) appeared only after "Show the solution". The backend now sends the game
 * move and the capture; before the solve the board draws both and the text
 * names them. The answer itself (Bc2) is never drawn before the solve.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";

let mockBoardProps = null;

jest.mock("react-router-dom", () => ({
  useNavigate: () => jest.fn(),
  useSearchParams: () => [new URLSearchParams(""), jest.fn()],
  useParams: () => ({ pattern: "piece_safety" }),
  Link: ({ children }) => children,
}), { virtual: true });
jest.mock("@/App", () => ({ API: "https://api.test/api" }), { virtual: true });
jest.mock("framer-motion", () => ({
  motion: new Proxy({}, { get: () => ({ children }) => children }),
}), { virtual: true });
jest.mock("@/components/LichessBoard", () => ({
  __esModule: true,
  default: (props) => { mockBoardProps = props; return null; },
}), { virtual: true });
jest.mock("@/components/training/PICPieceSafetyLesson", () => ({ __esModule: true, default: () => null }), { virtual: true });
jest.mock("@/components/training/CanonicalTrainingAssignment", () => ({ __esModule: true, default: () => null }), { virtual: true });
jest.mock("@/components/training/DifficultySelector", () => ({ __esModule: true, default: () => null }), { virtual: true });
jest.mock("@/components/training/PersonalizedLessonWorkspace", () => ({ __esModule: true, default: () => null }), { virtual: true });
jest.mock("@/hooks/useMoveCaption", () => ({ __esModule: true, default: () => ({}) }), { virtual: true });

const PrescribedTraining = require("./PrescribedTraining").default;

const puzzle = (coaching) => ({
  puzzle_id: "g_m22",
  source: "your_game",
  fen: "5r1k/2q3pp/pb4b1/1pn1pp2/7B/1BP2P2/PP2Q1PP/3R1R1K w - - 0 22",
  solution: ["b3c2"],
  your_move: "Be7",
  your_move_uci: "h4e7",
  move_number: 22,
  pattern_type: "piece_safety",
  coaching,
});

const WITH_PROBLEM = {
  lesson: "Piece Safety",
  question: "Before you play a move, can the opponent take the piece on its new square?",
  personal_note: "This is move 22 from your game.",
  why_this_matters: "You played Be7 here, and the queen on c7 could take your bishop on e7. Find a better move.",
  problem_move_uci: "h4e7",
  problem_reply_uci: "c7e7",
};

let container;
let root;

const render = async (coaching) => {
  global.fetch = jest.fn((url) => {
    const body = String(url).includes("/training/")
      ? { puzzles: [puzzle(coaching)], coaching_intro: { lesson: "Piece Safety" } }
      : {};
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
  });
  act(() => root.render(<PrescribedTraining user={{ id: "u1" }} />));
  await act(async () => { for (let i = 0; i < 10; i += 1) await Promise.resolve(); });
};

beforeEach(() => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  window.posthog = { capture: jest.fn() };
  mockBoardProps = null;
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

test("before the solve, the board draws the game move and the capture, and the text names them", async () => {
  await render(WITH_PROBLEM);
  expect(container.textContent).toContain("You played Be7 here, and the queen on c7 could take your bishop on e7.");
  expect(mockBoardProps.arrows).toEqual([["h4", "e7", "red"], ["c7", "e7", "blue"]]);
  expect(container.querySelector("[data-testid='training-problem-legend']")).not.toBeNull();
  // The answer is not drawn.
  expect(JSON.stringify(mockBoardProps.arrows)).not.toContain("c2");
});

test("a puzzle without a named problem move draws nothing before the solve", async () => {
  const { problem_move_uci, problem_reply_uci, ...plain } = WITH_PROBLEM;
  await render(plain);
  expect(mockBoardProps.arrows).toEqual([]);
  expect(container.querySelector("[data-testid='training-problem-legend']")).toBeNull();
});
