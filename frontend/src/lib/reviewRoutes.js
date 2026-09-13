export const canonicalGameReviewPath = (gameId) =>
  "/game/" + encodeURIComponent(String(gameId || ""));
