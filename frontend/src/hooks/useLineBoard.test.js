jest.mock("@/App", () => ({ API: "http://test/api" }));

import { clientEvalFrom } from "./useLineBoard";

test("the browser's numbers go to the server in the route's shape", () => {
  const before = { depth: 19, lines: { 1: { score: 245, pv: ["b5a6", "b8a6"] }, 2: { score: 200, pv: ["b1c3"] } } };
  const after = { depth: 18, lines: { 1: { score: 276, pv: ["a6b5", "f3a8", "b5c6"] } } };
  expect(clientEvalFrom(before, after)).toEqual({
    engine: "sf17.1-lite", best: "b5a6", best_cp: 245, second_cp: 200,
    after_cp: 276, pv_after: ["a6b5", "f3a8", "b5c6"], depth_before: 19, depth_after: 18,
  });
});

test("no search, no numbers", () => {
  expect(clientEvalFrom(null, null)).toBeNull();
  expect(clientEvalFrom({ lines: {} }, null)).toBeNull();
});

test("a move that ends the game has no after-search", () => {
  const before = { depth: 12, lines: { 1: { score: 9999, pv: ["d8h4"] } } };
  expect(clientEvalFrom(before, null)).toMatchObject({ after_cp: null, pv_after: [], second_cp: null });
});
