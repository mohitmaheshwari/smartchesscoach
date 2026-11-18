jest.mock("react-router-dom", () => ({ Link: () => null, useParams: () => ({}) }), { virtual: true });
jest.mock("@/App", () => ({ API: "http://test/api" }));
jest.mock("@/components/LichessBoard", () => () => null);
jest.mock("@/components/Layout", () => ({ children }) => children);

import { gamePositions } from "./AcademyStudentGame";

test("every position of the game, starting position first", () => {
  const p = gamePositions("1. e4 e5 2. Nf3 *");
  expect(p).toHaveLength(4);
  expect(p[0].san).toBeNull();
  expect(p[1]).toMatchObject({ san: "e4", from: "e2", to: "e4" });
  expect(p[3].fen.startsWith("rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b")).toBe(true);
});

test("a game from a set-up position starts there", () => {
  const pgn = '[SetUp "1"]\n[FEN "4k3/8/8/8/8/8/4P3/4K3 w - - 0 1"]\n\n1. e4 *';
  const p = gamePositions(pgn);
  expect(p[0].fen).toBe("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1");
  expect(p[1].san).toBe("e4");
});
