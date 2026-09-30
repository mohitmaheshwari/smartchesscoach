import { createRoot } from "react-dom/client";
import { act } from "react";
import AdminGeometryGaps from "@/pages/AdminGeometryGaps";

jest.mock("@/App", () => ({ API: "http://test/api" }));
jest.mock("@/components/Layout", () => ({ children }) => <div data-testid="layout">{children}</div>);
let lastBoardProps = null;
jest.mock("@/components/LichessBoard", () => (props) => {
  lastBoardProps = props;
  return <div data-testid="board" data-fen={props.fen} />;
});

const ITEM = {
  fen: "5rk1/1ppq2p1/3Rp2p/p3p3/P3Pn2/N1P2N1P/1PQ2BP1/6K1 b - - 0 23",
  side_to_move: "black",
  move_number: 23,
  played_san: "Qxd6",
  best_san: "cxd6",
  cp_loss: 174,
  cluster: "best_move_capture_not_priceable",
  pv_after_played: ["Nc4", "Qd3", "Qxd3", "Nxd3"],
  pv_after_best: ["Kh2", "Qf7", "Be3", "Nxg2"],
};

let container, root;
beforeEach(() => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  global.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ITEM });
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(() => { act(() => root.unmount()); container.remove(); delete global.fetch; });

const boardFen = () => container.querySelector('[data-testid="board"]').getAttribute("data-fen");
const clickMove = async (san) => {
  const btn = Array.from(container.querySelectorAll("button")).find((b) => b.textContent === san);
  await act(async () => btn.click());
};

test("the punishment line is clickable and steps the board", async () => {
  await act(async () => root.render(<AdminGeometryGaps />));
  expect(boardFen()).toBe(ITEM.fen);

  // the mistake itself
  await clickMove("Qxd6");
  expect(boardFen()).toContain("3q");      // black queen now on d6

  // the punishment: the knight hits it
  await clickMove("Nc4");
  expect(boardFen()).not.toBe(ITEM.fen);
  expect(boardFen()).toContain("2N");      // knight arrived on c4

  // and the engine's line is walkable too
  await clickMove("cxd6");
  expect(boardFen()).not.toBe(ITEM.fen);

  // back to the start
  const back = Array.from(container.querySelectorAll("button"))
    .find((b) => /Back to the position/.test(b.textContent));
  await act(async () => back.click());
  expect(boardFen()).toBe(ITEM.fen);
});

test("an illegal line truncates instead of corrupting the board", async () => {
  global.fetch = jest.fn().mockResolvedValue({
    ok: true, status: 200,
    json: async () => ({ ...ITEM, pv_after_played: ["Nc4", "Qxa1", "totally-illegal", "Nxd3"] }),
  });
  await act(async () => root.render(<AdminGeometryGaps />));
  await clickMove("Nxd3");
  expect(boardFen()).toBeTruthy();   // still a legal FEN, not a crash
});

test("a 403 says so instead of rendering an empty page", async () => {
  global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 403, json: async () => ({}) });
  await act(async () => root.render(<AdminGeometryGaps />));
  expect(container.querySelector('[data-testid="geometry-gaps-denied"]')).not.toBeNull();
  expect(container.textContent).toContain("do not have access");
});


// ── playing your own move and asking the engine ──────────────────────
//
// Mohit, 2026-09-30: "if I play a move on the board, can you give me stockfish
// response for that move, so I really know why the move I play doesn't work?"
// The two stored lines only answer for the move played and the move the engine
// wanted; a reviewer's question is usually about some third move.

const AFTER = "5rk1/1ppq2p1/3Rp2p/p3p3/P3Pn2/N1P2N1P/1PQ2BP1/6K1 w - - 1 24";
const ENGINE = {
  evaluation: { centipawns: -255, mate_in: null },
  best_move: { san: "Qxc8", uci: "d7c8" },
  pv: ["Qxc8", "Qa1+", "Kg2", "Qb2+"],
  depth: 18,
};

const playMove = async (san = "Rc6", fen = AFTER) => {
  await act(async () => { lastBoardProps.onMove({ from: "c1", to: "c6", san, fen }); });
};

test("playing a move asks the engine and shows what it answers", async () => {
  await act(async () => root.render(<AdminGeometryGaps />));
  global.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ENGINE });
  await playMove();

  const posted = global.fetch.mock.calls[0];
  expect(posted[0]).toContain("/analyze-position");
  expect(JSON.parse(posted[1].body).fen).toBe(AFTER);

  expect(container.textContent).toContain("Qxc8");
  expect(container.textContent).toContain("-2.55");
  expect(boardFen()).toBe(AFTER);
});

test("the tried move is shown so the reviewer knows what they asked", async () => {
  await act(async () => root.render(<AdminGeometryGaps />));
  global.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ENGINE });
  await playMove("Rc6");
  expect(container.textContent).toContain("Rc6");
});

test("a mate score is words, not a centipawn number", async () => {
  await act(async () => root.render(<AdminGeometryGaps />));
  global.fetch = jest.fn().mockResolvedValue({
    ok: true, status: 200,
    json: async () => ({ ...ENGINE, evaluation: { centipawns: null, mate_in: -3 } }),
  });
  await playMove();
  expect(container.textContent).toContain("mate in 3");
});

test("an engine that does not answer says so instead of showing nothing", async () => {
  await act(async () => root.render(<AdminGeometryGaps />));
  global.fetch = jest.fn().mockRejectedValue(new Error("offline"));
  await playMove();
  expect(container.textContent).toContain("Could not reach the engine");
});

test("going back to the position clears the engine answer", async () => {
  await act(async () => root.render(<AdminGeometryGaps />));
  global.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ENGINE });
  await playMove();
  expect(boardFen()).toBe(AFTER);
  const back = Array.from(container.querySelectorAll("button"))
    .find((b) => b.textContent.includes("Back to the position"));
  await act(async () => back.click());
  expect(boardFen()).toBe(ITEM.fen);
  expect(container.textContent).not.toContain("Qxc8");
});

// ── the board must stay playable wherever it is ──────────────────────
//
// Mohit, 2026-09-30: "this stops working when we start clicking the line ...
// after playing the engine line, if I want to see what happens next, I can
// make the move on the board and it should show the stockfish answer."

test("dragging works AFTER stepping into a stored line", async () => {
  await act(async () => root.render(<AdminGeometryGaps />));
  await clickMove("Nc4");                       // step one ply into the punishment line
  const fenAtPly1 = boardFen();
  expect(fenAtPly1).not.toBe(ITEM.fen);

  global.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ENGINE });
  await act(async () => {
    lastBoardProps.onMove({ from: "d7", to: "d3", san: "Qd3", fen: "PROBE_FROM_LINE" });
  });

  expect(global.fetch).toHaveBeenCalled();
  expect(JSON.parse(global.fetch.mock.calls[0][1].body).fen).toBe("PROBE_FROM_LINE");
  expect(boardFen()).toBe("PROBE_FROM_LINE");
  expect(container.textContent).toContain("Qxc8");
});

test("the line you came from is still shown after you drag off it", async () => {
  await act(async () => root.render(<AdminGeometryGaps />));
  await clickMove("Nc4");
  global.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ENGINE });
  await act(async () => {
    lastBoardProps.onMove({ from: "d7", to: "d3", san: "Qd3", fen: "PROBE_FROM_LINE" });
  });
  expect(container.textContent).toContain("Qd3");
});

test("you can keep dragging: a second move asks the engine again", async () => {
  await act(async () => root.render(<AdminGeometryGaps />));
  global.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ENGINE });
  await playMove("Rc6", "FEN_ONE");
  await act(async () => {
    lastBoardProps.onMove({ from: "d7", to: "a7", san: "Qxa7", fen: "FEN_TWO" });
  });
  expect(global.fetch).toHaveBeenCalledTimes(2);
  expect(JSON.parse(global.fetch.mock.calls[1][1].body).fen).toBe("FEN_TWO");
  expect(boardFen()).toBe("FEN_TWO");
  expect(container.textContent).toContain("Rc6 Qxa7");
});

// The affordance itself was the bug: the hint was swapped out for the Back
// button the moment a line was stepped, so it read as "it stopped working".
test("the drag hint survives stepping into a line", async () => {
  await act(async () => root.render(<AdminGeometryGaps />));
  expect(container.textContent).toContain("Drag a piece to try a move");
  await clickMove("Nc4");
  expect(container.textContent).toContain("Drag a piece to try a move");
});

test("the drag hint survives playing your own move", async () => {
  await act(async () => root.render(<AdminGeometryGaps />));
  global.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ENGINE });
  await playMove();
  expect(container.textContent).toContain("Drag a piece to try a move");
});

test("branching off a line keeps that line on screen", async () => {
  await act(async () => root.render(<AdminGeometryGaps />));
  await clickMove("Nc4");
  global.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ENGINE });
  await act(async () => {
    lastBoardProps.onMove({ from: "d7", to: "d3", san: "Qd3", fen: "PROBE_FROM_LINE" });
  });
  // the stored line's moves are still rendered as buttons to step back through
  const buttons = Array.from(container.querySelectorAll("button")).map((b) => b.textContent);
  expect(buttons).toContain("Nc4");
  expect(buttons).toContain("Qd3");
});
