import { createRoot } from "react-dom/client";
import { act } from "react";
import AdminGeometryGaps from "@/pages/AdminGeometryGaps";

jest.mock("@/App", () => ({ API: "http://test/api" }));
jest.mock("@/components/Layout", () => ({ children }) => <div data-testid="layout">{children}</div>);
jest.mock("@/components/LichessBoard", () => (props) => (
  <div data-testid="board" data-fen={props.fen} />
));

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
