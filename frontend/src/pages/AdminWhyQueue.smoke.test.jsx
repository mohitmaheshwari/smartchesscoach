/**
 * /admin/why-queue: a studied position shows Claude's text, an unstudied one
 * says "To be processed", every row has a board and links to its game.
 * docs/why_queue_admin_page_scope.md
 */
import { createRoot } from "react-dom/client";
import { act } from "react";
import AdminWhyQueue from "@/pages/AdminWhyQueue";

jest.mock("react-router-dom", () => ({
  Link: ({ to, children, ...rest }) => <a href={to} {...rest}>{children}</a>,
}), { virtual: true });
jest.mock("@/App", () => ({ API: "http://test/api" }));
jest.mock("@/components/Layout", () => ({ children }) => <div data-testid="layout">{children}</div>);
jest.mock("@/components/LichessBoard", () => (props) => (
  <div data-testid="board" data-fen={props.fen} data-orientation={props.orientation}
       data-arrows={JSON.stringify(props.arrows)} data-viewonly={String(!!props.viewOnly)} />
));

const E5 = {
  key: "k1", fen_before: "r1bqk1nr/pppp1pp1/2n4p/2b5/2BpP3/5N2/PPP2PPP/RNBQ1RK1 w kq - 0 6",
  side_to_move: "white", side: "opponent", played_san: "e5",
  played_squares: { from: "e4", to: "e5" }, better_san: "c3", better_squares: { from: "c2", to: "c3" },
  stored_class: "mistake", status: "held_for_review", status_words: "Waiting for your review",
  processed: true, games: [{ game_id: "2d86e1f9-ca3e", move_number: 6, side: "opponent" }],
  times_asked: 2, last_asked_at: "2026-11-10T16:06:43Z",
  claude_text: "After e5, you can answer d5.", gate_passed: true, gate_failures: [], cost_usd: 0.12,
  model: "claude-opus-5-5",
};
const RF7 = {
  key: "k2", fen_before: "r2q1rk1/ppp1b3/4pp2/6pQ/3Pp3/2P1P1B1/PP3P1P/R4RK1 b - - 4 18",
  side_to_move: "black", side: "user", played_san: "Rf7", played_squares: { from: "f8", to: "f7" },
  better_san: "Kg7", better_squares: { from: "g8", to: "g7" }, status: "queued",
  status_words: "To be processed", processed: false,
  games: [{ game_id: "game_48c2", move_number: 18, side: "user" }], times_asked: 1,
};

let container, root;
beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  global.fetch = jest.fn().mockResolvedValue({
    ok: true, status: 200, json: async () => ({ count: 2, positions: [E5, RF7] }),
  });
});
afterEach(() => { act(() => root.unmount()); container.remove(); delete global.fetch; });

const mount = async () => {
  await act(async () => root.render(<AdminWhyQueue />));
};

test("lists every queued position with a board, its game and its status", async () => {
  await mount();
  expect(global.fetch).toHaveBeenCalledWith("http://test/api/admin/why-queue/positions", { credentials: "include" });
  const rows = container.querySelectorAll("[data-testid='why-queue-row']");
  expect(rows).toHaveLength(2);
  expect(container.textContent).toContain("Why queue — 2 positions");

  const boards = container.querySelectorAll("[data-testid='board']");
  expect(boards[0].getAttribute("data-fen")).toBe(E5.fen_before);
  expect(boards[0].getAttribute("data-viewonly")).toBe("true");
  // An opponent's move by White is seen from Black, the asker's side.
  expect(boards[0].getAttribute("data-orientation")).toBe("black");
  expect(JSON.parse(boards[0].getAttribute("data-arrows"))).toEqual([["e4", "e5", "red"], ["c2", "c3", "green"]]);
  // The player's own move as Black is seen from Black.
  expect(boards[1].getAttribute("data-orientation")).toBe("black");

  expect(rows[0].textContent).toContain("6.e5");
  expect(rows[1].textContent).toContain("18...Rf7");
  expect(rows[0].querySelector("a").getAttribute("href")).toBe("/game/2d86e1f9-ca3e");
});

test("Claude's text when studied, 'To be processed' when not", async () => {
  await mount();
  const [e5, rf7] = container.querySelectorAll("[data-testid='why-queue-row']");
  expect(e5.querySelector("[data-testid='why-queue-claude']").textContent).toBe("After e5, you can answer d5.");
  expect(e5.querySelector("[data-testid='why-queue-status']").textContent).toBe("Waiting for your review");
  expect(rf7.querySelector("[data-testid='why-queue-claude']")).toBeNull();
  expect(rf7.querySelector("[data-testid='why-queue-pending']").textContent).toContain("To be processed");
});

test("a non-admin is told so instead of seeing an empty page", async () => {
  global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 403, json: async () => ({}) });
  await mount();
  expect(container.textContent).toContain("Admin only.");
  expect(container.querySelectorAll("[data-testid='why-queue-row']")).toHaveLength(0);
});
