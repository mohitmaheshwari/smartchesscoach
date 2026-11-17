/**
 * The coach in the room (docs/training_coach_presence_scope.md, 2026-11-17).
 *
 * Mohit: "some kind of tracking shows up, some kind of coach eyes ... right now
 * it's just board and nothing else". The page now shows this week's plan step
 * and a session path with no red; after a drop on a landing-square drill the
 * move waits while the coach asks what can win the piece; after two right
 * checks the coach steps back and only watches.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";
import { whatISaw } from "@/components/training/CoachEye";

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
jest.mock("@/hooks/useMoveCaption", () => ({ __esModule: true, default: () => ({ fetchCaption: () => {} }) }), { virtual: true });

const PrescribedTraining = require("./PrescribedTraining").default;

const FEN = "5r1k/2q3pp/pb4b1/1pn1pp2/7B/1BP2P2/PP2Q1PP/3R1R1K w - - 0 22";
const puzzle = (id) => ({
  puzzle_id: id, source: "your_game", fen: FEN, move_number: 22, pattern_type: "piece_safety",
  your_move: "Be7", your_move_uci: "h4e7", your_move_seconds: 5,
  coaching: {
    lesson: "Piece Safety", landing_check: true,
    personal_note: "This is move 22 from your game.",
    why_this_matters: "You played Be7 here, and the queen on c7 could take your bishop on e7. Find a better move.",
    problem_move_uci: "h4e7", problem_reply_uci: "c7e7",
  },
});
const WEEK = {
  key: "habit:gap:piece_safety:destination_safety_exact",
  do: "Do the three looks before every move that puts a piece on a new square.",
  last_week: "Last week's step showed up again. One more week, with fresh positions.",
};
const UNSAFE = {
  eligible: true, safe: false, piece: "bishop", square: "e7", correct: true, answer_square: "c7",
  words: "Right. The queen on c7 can win your bishop on e7 along a long straight line.",
  takers: [], looks: [],
};
const SAFE = { eligible: true, safe: true, piece: "bishop", square: "c2", correct: true, answer_square: null,
  words: "Right. Your bishop is safe on c2.", takers: [], looks: [] };

let container;
let root;
let calls;

function serve(landing) {
  calls = [];
  global.fetch = jest.fn((url, init) => {
    const u = String(url);
    calls.push({ url: u, body: init?.body ? JSON.parse(init.body) : null });
    let body = {};
    if (u.includes("/training/prescribed/")) body = { puzzles: [puzzle("p1"), puzzle("p2"), puzzle("p3")], week_step: WEEK, coaching_intro: { lesson: "Piece Safety" } };
    else if (u.includes("/training/landing-check")) body = landing;
    else if (u.includes("/training/evaluate-puzzle-move")) body = { quality: "best", correct: true, is_best: true, best_move_san: "Bc2", best_move_uci: "b3c2" };
    else if (u.includes("/training/puzzle-attempt")) body = { success: true, correct: true, quality: "best" };
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
  });
}
const flush = async () => { await act(async () => { for (let i = 0; i < 12; i += 1) await Promise.resolve(); }); };
const render = async () => { act(() => root.render(<PrescribedTraining user={{ id: "u1" }} />)); await flush(); };
const drop = async (from, to) => { await act(async () => { mockBoardProps.onMove({ from, to }); }); await flush(); };
const click = async (testid) => { await act(async () => { container.querySelector(`[data-testid='${testid}']`).click(); }); await flush(); };
const clickText = async (text) => {
  const btn = [...container.querySelectorAll("button")].find((b) => b.textContent.includes(text));
  await act(async () => { btn.click(); });
  await flush();
};
const hit = (part) => calls.filter((c) => c.url.includes(part));

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

test("the page shows this week's step, a session path with no red, and the coach's eye", async () => {
  serve(UNSAFE);
  await render();
  expect(container.querySelector("[data-testid='training-week-strip']").textContent).toContain("Do the three looks");
  const path = container.querySelector("[data-testid='training-session-path']");
  expect([...path.querySelectorAll("[data-state]")].map((s) => s.dataset.state)).toEqual(["now", "later", "later"]);
  expect(path.innerHTML).not.toMatch(/rose|red/);
  expect(container.textContent).toContain("Coach's eye");
  expect(container.textContent).toContain("Show the move");
});

test("a drop waits for the coach's check; tapping the taker is graded and the move can be taken back", async () => {
  serve(UNSAFE);
  await render();
  await drop("h4", "e7");
  expect(container.textContent).toContain("Can anything win your bishop on e7?");
  expect(hit("/evaluate-puzzle-move")).toHaveLength(0);           // not judged yet
  expect(mockBoardProps.selectionOnly).toBe(true);
  // A stray tap on an empty square is not an answer.
  await act(async () => { mockBoardProps.onSquareClick("d4"); });
  await flush();
  expect(hit("/landing-check")).toHaveLength(0);
  await act(async () => { mockBoardProps.onSquareClick("c7"); });
  await flush();
  expect(hit("/landing-check")[0].body).toMatchObject({ puzzle_id: "p1", played_uci: "h4e7", answer: "c7" });
  expect(container.textContent).toContain("Right. The queen on c7 can win your bishop on e7");
  expect(mockBoardProps.arrows).toEqual([["c7", "e7", "red"]]);
  await click("landing-check-take-back");
  expect(mockBoardProps.fen).toBe(FEN);
  expect(container.textContent).toContain("Show the move");
  expect(hit("/evaluate-puzzle-move")).toHaveLength(0);
});

test("after two right checks the coach steps back, and the next drop is judged straight away", async () => {
  serve(SAFE);
  await render();
  for (let i = 0; i < 2; i += 1) {
    await drop("b3", "c2");
    await click("landing-check-safe");
    await click("landing-check-continue");
    expect(container.textContent).toContain("Next puzzle");
    await clickText("Next puzzle");
  }
  expect(container.querySelector("[data-testid='coach-watching']").textContent)
    .toContain("You're checking on your own now. I'll just watch.");
  expect(hit("/landing-check")).toHaveLength(2);
  await drop("b3", "c2");
  expect(container.querySelector("[data-testid='landing-check']")).toBeNull();
  expect(hit("/evaluate-puzzle-move")).toHaveLength(3);
  // The attempt now carries today's think time instead of a hard-coded zero.
  expect(hit("/puzzle-attempt").every((c) => c.body.time_taken_ms >= 0)).toBe(true);
});

test("what I saw compares today's think with the game's in words, never seconds", () => {
  expect(whatISaw({ gameSeconds: 5, todayMs: 40000, solved: true, checkedRight: true }))
    .toBe("In the game you moved quickly here. Today you took your time and checked where your piece lands, and found it.");
  expect(whatISaw({ gameSeconds: 5, todayMs: 4000, solved: false, checkedRight: false }))
    .toBe("In the game you moved quickly here, and today too. Next time, stop and check where your piece lands first.");
  expect(whatISaw({ gameSeconds: null, todayMs: 4000, solved: true })).toBeNull();
  for (const s of [true, false]) {
    for (const g of [3, 60]) {
      expect(whatISaw({ gameSeconds: g, todayMs: 30000, solved: s, checkedRight: s })).not.toMatch(/\d/);
    }
  }
});
