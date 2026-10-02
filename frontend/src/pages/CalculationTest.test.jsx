/**
 * The board must not move.
 *
 * That is the whole exercise. If the pieces follow the clicks, the player is
 * looking at the position instead of calculating it, and the test measures
 * nothing it was built to measure. Everything else here is secondary.
 */
import { createRoot } from "react-dom/client";
import { act } from "react";
import CalculationTest from "@/pages/CalculationTest";

jest.mock("@/App", () => ({ API: "http://test/api" }));
jest.mock("@/components/Layout", () => ({ children }) => <div>{children}</div>);

let boardProps = null;
jest.mock("@/components/LichessBoard", () => (props) => {
  boardProps = props;
  return <div data-testid="board" data-fen={props.fen} />;
});

// Rook swings to e1 and the knight on e5 is pinned to the king on e8.
const FEN = "4k3/8/8/4n3/8/8/8/R5K1 w - - 0 1";
const POSITIONS = {
  positions: [{
    position_id: "g1:12", fen: FEN, game_id: "g1", move_number: 12,
    you_played: "Kf1", needs_half_moves: 3,
  }, {
    position_id: "g2:30", fen: FEN, game_id: "g2", move_number: 30,
    you_played: "a3", needs_half_moves: 3,
  }],
};

let container, root;
const boardFen = () => container.querySelector('[data-testid="board"]').getAttribute("data-fen");
const text = () => container.textContent;
const clickButton = async (label) => {
  const b = Array.from(container.querySelectorAll("button"))
    .find((x) => x.textContent.includes(label));
  await act(async () => b.click());
};

beforeEach(() => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  boardProps = null;
  global.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200, json: async () => POSITIONS });
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(() => { act(() => root.unmount()); container.remove(); delete global.fetch; });

const render = async () => {
  await act(async () => root.render(<CalculationTest />));
};
const playMove = async (fromSq, toSq) => {
  await act(async () => boardProps.onSquareClick(fromSq));
  await act(async () => boardProps.onSquareClick(toSq));
};


test("THE BOARD DOES NOT MOVE when a move is entered", async () => {
  await render();
  expect(boardFen()).toBe(FEN);
  await playMove("a1", "e1");
  expect(text()).toContain("Re1");
  expect(boardFen()).toBe(FEN);
});

test("the board still does not move after several half-moves", async () => {
  await render();
  await playMove("a1", "e1");
  await playMove("e8", "d8");
  expect(boardFen()).toBe(FEN);
});

test("the pieces are not draggable, only selectable", async () => {
  await render();
  expect(boardProps.selectionOnly).toBe(true);
});


// ── entering a line ───────────────────────────────────────────────────

test("two clicks name a move, so nobody has to write notation", async () => {
  await render();
  await playMove("a1", "e1");
  expect(text()).toContain("Re1");
});

test("an illegal pair of squares is not recorded as a move", async () => {
  // a1 to b3 is not a rook move. The first attempt here used a1 to a8, which
  // IS legal in this position -- the a-file is empty -- so the test failed and
  // the code was right. Fixtures get verified, not reasoned about.
  await render();
  await playMove("a1", "b3");
  expect(text()).not.toContain("Rb3");
  expect(text()).toContain("Nothing yet.");
});

test("the line alternates you and them", async () => {
  await render();
  await playMove("a1", "e1");
  await playMove("e8", "d8");
  expect(text()).toContain("you");
  expect(text()).toContain("them");
});

test("taking a move back removes only the last one", async () => {
  await render();
  await playMove("a1", "e1");
  await playMove("e8", "d8");
  await clickButton("Take back");
  expect(text()).toContain("Re1");
  expect(text()).not.toContain("Kd8");
});

test("the line may be a single move", async () => {
  await render();
  await playMove("a1", "e1");
  global.fetch = jest.fn().mockResolvedValue({
    ok: true, status: 200,
    json: async () => ({ plies: [{ ply: 1, by: "you", move: "Re1", verdict: "sound" }],
                         sound_through: 1, stopped_early: false }),
  });
  await clickButton("Check my line");
  const body = JSON.parse(global.fetch.mock.calls[0][1].body);
  expect(body.moves).toEqual(["Re1"]);
});

test("how deep the position runs is shown, so stopping short is avoidable", async () => {
  await render();
  expect(text()).toContain("3 half-moves");
});


// ── the verdict ───────────────────────────────────────────────────────

test("a line that holds all the way says so", async () => {
  await render();
  await playMove("a1", "e1");
  global.fetch = jest.fn().mockResolvedValue({
    ok: true, status: 200,
    json: async () => ({ plies: [{ ply: 1, by: "you", move: "Re1", verdict: "sound" }],
                         sound_through: 1, stopped_early: false }),
  });
  await clickButton("Check my line");
  expect(container.querySelector('[data-testid="verdict"]')).not.toBeNull();
  expect(text()).toContain("That is the line");
});

test("stopping short is told apart from going wrong", async () => {
  await render();
  await playMove("a1", "e1");
  global.fetch = jest.fn().mockResolvedValue({
    ok: true, status: 200,
    json: async () => ({ plies: [{ ply: 1, by: "you", move: "Re1", verdict: "sound" }],
                         sound_through: 1, stopped_early: true }),
  });
  await clickButton("Check my line");
  expect(text()).toContain("more to see past where you stopped");
});

test("a misjudged ending is reported even when the line was right", async () => {
  await render();
  await playMove("a1", "e1");
  global.fetch = jest.fn().mockResolvedValue({
    ok: true, status: 200,
    json: async () => ({
      plies: [{ ply: 1, by: "you", move: "Re1", verdict: "sound" }],
      sound_through: 1, stopped_early: false,
      judged_the_end: { said: "level", actually: "winning", right: false },
    }),
  });
  await clickButton("Check my line");
  expect(text()).toContain("you read the end as level".replace("you", "You"));
});

test("a player with no position is told so rather than shown a made-up one", async () => {
  global.fetch = jest.fn().mockResolvedValue({
    ok: true, status: 200,
    json: async () => ({ positions: [], reason: "no position from your games needs working out yet" }),
  });
  await render();
  expect(text()).toContain("Nothing to work out yet");
  expect(container.querySelector('[data-testid="board"]')).toBeNull();
});
