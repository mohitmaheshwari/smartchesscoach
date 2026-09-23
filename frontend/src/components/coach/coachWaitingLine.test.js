import { shouldShowWaitingLine } from "./coachWaitingLine";

const quietAtMoveZero = {
  gameOver: false,
  guardianIntervention: null,
  geometryMoment: null,
  v5Coaching: null,
  loadingFeedback: false,
  moveCount: 0,
};

test("the void it exists to fill: game just started, nothing to say", () => {
  expect(shouldShowWaitingLine(quietAtMoveZero)).toBe(true);
});

test("never once a move has been played", () => {
  expect(shouldShowWaitingLine({ ...quietAtMoveZero, moveCount: 1 })).toBe(false);
  expect(shouldShowWaitingLine({ ...quietAtMoveZero, moveCount: 40 })).toBe(false);
});

test("never competes with the guardian", () => {
  expect(
    shouldShowWaitingLine({ ...quietAtMoveZero, guardianIntervention: { risk_level: "high" } })
  ).toBe(false);
});

test("never competes with other coaching panels", () => {
  expect(shouldShowWaitingLine({ ...quietAtMoveZero, geometryMoment: {} })).toBe(false);
  expect(shouldShowWaitingLine({ ...quietAtMoveZero, v5Coaching: {} })).toBe(false);
});

test("not while feedback is in flight - that has its own shimmer", () => {
  expect(shouldShowWaitingLine({ ...quietAtMoveZero, loadingFeedback: true })).toBe(false);
});

test("not after the game is over", () => {
  expect(shouldShowWaitingLine({ ...quietAtMoveZero, gameOver: true })).toBe(false);
});

test("a missing move count is treated as move 0", () => {
  expect(shouldShowWaitingLine({ ...quietAtMoveZero, moveCount: undefined })).toBe(true);
});

test("no arguments at all does not throw", () => {
  expect(shouldShowWaitingLine()).toBe(true);
});
