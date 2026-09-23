/**
 * The authored opening line is indexed by ply, so guidance is only valid
 * while the game is still ON that line.
 *
 * Regression: the Scotch line was loaded, the coach answered d6 (Philidor),
 * and ply 4 still drew an arrow for Nf3->e5. Stockfish depth 20: 3.Nxe5 dxe5
 * is -625cp, L:100% -- the pawn is defended by d6.
 */
import { isOnAuthoredLine } from "./openingLineGuard";

const SCOTCH = [{ move: "e4" }, { move: "e5" }, { move: "Nf3" }, { move: "Nc6" }, { move: "d4" }];

test("a game still on the line keeps its guidance", () => {
  const played = [{ san: "e4" }, { san: "e5" }, { san: "Nf3" }];
  expect(isOnAuthoredLine(played, SCOTCH)).toBe(true);
});

test("the reported regression: coach answers d6, guidance stops", () => {
  // 1.e4 e5 2.Nf3 d6 -- Philidor, not the Scotch line that was loaded.
  const played = [{ san: "e4" }, { san: "e5" }, { san: "Nf3" }, { san: "d6" }];
  expect(isOnAuthoredLine(played, SCOTCH)).toBe(false);
});

test("the USER deviating stops it too, not just the coach", () => {
  const played = [{ san: "e4" }, { san: "e5" }, { san: "Bc4" }];
  expect(isOnAuthoredLine(played, SCOTCH)).toBe(false);
});

test("an empty game is on the line", () => {
  expect(isOnAuthoredLine([], SCOTCH)).toBe(true);
});

test("playing past the end of the line is not a deviation", () => {
  const played = SCOTCH.map((i) => ({ san: i.move })).concat([{ san: "exd4" }]);
  expect(isOnAuthoredLine(played, SCOTCH)).toBe(true);
});

test("falls back to .move when .san is absent", () => {
  const played = [{ move: "e4" }, { move: "e5" }];
  expect(isOnAuthoredLine(played, SCOTCH)).toBe(true);
});

test("no ideas means nothing to guide from", () => {
  expect(isOnAuthoredLine([{ san: "e4" }], [])).toBe(false);
  expect(isOnAuthoredLine([{ san: "e4" }], null)).toBe(false);
});
