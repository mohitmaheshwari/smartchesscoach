/**
 * The similar-moment card (docs/similar_moments_scope.md, 2026-11-17).
 */
import { act } from "react";
import { createRoot } from "react-dom/client";

const boards = [];
jest.mock("@/App", () => ({ API: "https://api.test/api" }), { virtual: true });
jest.mock("@/components/coachfile/CoachFileBlocks", () => ({
  PLAYED: "orange", BETTER: "green",
  Board: (props) => { boards.push(props); return null; },
}), { virtual: true });
jest.mock("lucide-react", () => new Proxy({}, { get: () => () => null }), { virtual: true });

const SimilarMoment = require("./SimilarMoment").default;

const DATA = {
  available: true,
  yours: { san: "Be7", piece: "bishop", square: "e7", taker: { piece: "queen", sq: "c7" } },
  stronger: {
    fen: "8/8/8/8/8/8/8/8 w - - 0 1", side: "White", dangerous_uci: "h4e7", played_uci: "b3c2", taker_uci: "c7e7",
    words: "Their bishop could go to e7, where the queen on c7 could win it along a long straight line. They played Bc2 instead.",
  },
  thinking: {
    lead: "Before your bishop lands on e7, look from e7:",
    looks: [{ label: "Pieces close by", found: "nothing" }, { label: "Knight jumps", found: "nothing" },
            { label: "Long lines to the edge", found: "the queen on c7" }],
    end: "One of them can take it. Stop and find another move.",
  },
  other_side: { fen: "8/8/8/8/8/8/8/8 b - - 0 1", side: "Black", solution_uci: "c7e7", solution_san: "Qxe7",
                words: "Someone left a bishop where it could be taken. You are Black. Find the move that wins it." },
};

let container; let root;
beforeEach(() => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  boards.length = 0;
  container = document.createElement("div"); document.body.appendChild(container); root = createRoot(container);
});
afterEach(() => { act(() => root.unmount()); container.remove(); delete global.fetch; });

const render = async (body) => {
  global.fetch = jest.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(body) }));
  await act(async () => root.render(<SimilarMoment puzzleId="p1" />));
  await act(async () => { for (let i = 0; i < 6; i += 1) await Promise.resolve(); });
};

test("it shows the stronger player's moment, the three looks and the other side, with the answer hidden", async () => {
  await render(DATA);
  expect(JSON.parse(global.fetch.mock.calls[0][1].body)).toEqual({ puzzle_id: "p1" });
  expect(container.textContent).toContain("They played Bc2 instead.");
  expect(container.textContent).toContain("Before your bishop lands on e7, look from e7:");
  expect(container.textContent).toContain("the queen on c7");
  expect(boards[0].arrows).toEqual([["h4", "e7", "orange"], ["b3", "c2", "green"]]);
  expect(boards[1].orientation).toBe("black");
  expect(boards[1].arrows).toEqual([]);
  expect(container.textContent).not.toContain("Qxe7");
  const show = [...container.querySelectorAll("button")].find((b) => b.textContent === "Show me");
  await act(async () => show.click());
  expect(container.textContent).toContain("Qxe7 wins it.");
});

test("it shows nothing when there is no match and no puzzle", async () => {
  await render({ available: false });
  expect(container.querySelector("[data-testid='similar-moment']")).toBeNull();
});
