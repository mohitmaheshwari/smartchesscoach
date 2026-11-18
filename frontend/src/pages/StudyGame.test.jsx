/**
 * The teaching-game walk-through (docs/daily_coach_plan_scope.md, section 9):
 * replay, stop at the moment, ask, and only then show the idea.
 */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

import StudyGame from "./StudyGame";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

jest.mock("@/lib/analytics", () => ({ ANALYTICS_EVENTS: new Proxy({}, { get: (_t, k) => k }), track: jest.fn() }), { virtual: true });
jest.mock("@/App", () => ({ API: "/api" }), { virtual: true });
jest.mock("@/components/Layout", () => ({ children }) => <div>{children}</div>, { virtual: true });
jest.mock("react-chessboard", () => ({ Chessboard: ({ position }) => <div data-testid="board">{position}</div> }), { virtual: true });
jest.mock("lucide-react", () => new Proxy({}, { get: () => () => <span /> }), { virtual: true });
jest.mock("react-router-dom", () => ({
  useParams: () => ({ puzzleId: "p1" }),
  useSearchParams: () => [new URLSearchParams("from=today")],
  useNavigate: () => jest.fn(),
}), { virtual: true });

const STUDY = {
  puzzle_id: "p1", position_id: "lichess_puzzles:p1", topic: "study-p1",
  idea_title: "Fork", idea_text: "One piece attacks two things at once.",
  opening: "Italian Game: Blackburne Shilling Gambit", solver: "black",
  moves_before: ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nd4", "Nxe5", "Qg5", "Nxf7"],
  pause_fen: "r1b1kbnr/pppp1Npp/8/6q1/2BnP3/8/PPPP1PPP/RNBQK2R b KQkq - 0 5",
  solution: ["Qxg2", "Rf1", "Qxe4+", "Be2", "Nf3#"], game_after: ["Qxg2", "Rf1"], found_in_game: true, result: "0-1",
};

async function render() {
  global.fetch = jest.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(STUDY) }));
  const host = document.createElement("div");
  document.body.appendChild(host);
  await act(async () => { createRoot(host).render(<StudyGame user={{}} />); });
  return host;
}

afterEach(() => { document.body.innerHTML = ""; delete global.fetch; });

test("replays the game, then stops and asks before showing anything about the answer", async () => {
  const host = await render();
  expect(global.fetch.mock.calls[0][0]).toBe("/api/study/p1");
  expect(host.querySelector('[data-testid="study-replay"]').textContent).toContain("stops at the moment");
  await act(async () => { host.querySelector('[data-testid="study-skip"]').click(); });
  const ask = host.querySelector('[data-testid="study-ask"]');
  expect(ask.textContent).toContain("What would you play here?");
  expect(host.textContent).not.toContain("Qxg2");
  expect(host.querySelector('[data-testid="board"]').textContent).toBe(STUDY.pause_fen);
});
