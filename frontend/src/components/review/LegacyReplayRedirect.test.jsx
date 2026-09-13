import { canonicalGameReviewPath } from "../../lib/reviewRoutes";


describe("LegacyReplayRedirect", () => {
  test("builds the canonical encoded review path", () => {
    expect(canonicalGameReviewPath("game/id")).toBe("/game/game%2Fid");
  });

  test("preserves an ordinary stored game identifier", () => {
    expect(canonicalGameReviewPath("game-42")).toBe("/game/game-42");
  });
});
