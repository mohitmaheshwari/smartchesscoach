import fs from "fs";
import path from "path";

const page = (name) => fs.readFileSync(
  path.join(process.cwd(), "src", "pages", name),
  "utf8",
);
const lib = (name) => fs.readFileSync(
  path.join(process.cwd(), "src", "lib", name),
  "utf8",
);

test("Lab Coach's Pick consumes the canonical review prescription", () => {
  const source = page("Dashboard.jsx");
  expect(source).toContain("/game-review/recommendation");
  expect(source).toContain("coachSelectedReview");
  expect(source).toContain("/start");
  expect(source).toContain("payload.prescription.review_url");
  expect(source).not.toContain("onClick={() =>\n                        navigate(\n                          // 2026-05-19");
});

test("the review player restores and saves prescription progress", () => {
  const source = page("LabV2.jsx");
  expect(source).toContain('searchParams.get("prescription")');
  expect(source).toContain('searchParams.get("resume")');
  expect(source).toContain("/progress");
  expect(source).toContain("move_index: currentMoveIndex");
  expect(source).toContain("prescription_id: prescriptionParam || undefined");
  expect(source).toContain('returnTo={prescriptionParam ? "/games" : "/lab"}');
});

test("the complete review journey emits only canonical privacy-safe events", () => {
  const analytics = lib("analytics.js");
  const games = page("AllGames.jsx");
  const review = page("LabV2.jsx");
  [
    "GAME_REVIEW_PRESCRIPTION_SERVED",
    "GAME_REVIEW_PRESCRIPTION_STARTED",
    "GAME_REVIEW_PRESCRIPTION_RESUMED",
    "GAME_REVIEW_PRESCRIPTION_DISMISSED",
    "GAME_REVIEW_PRESCRIPTION_COMPLETED",
    "GAME_REVIEW_NO_ELIGIBLE_GAME",
    "GAME_REVIEW_FALLBACK_OFFERED",
    "GAME_REVIEW_NEXT_PRESCRIPTION_SERVED",
  ].forEach((event) => expect(analytics).toContain(event));
  expect(games).toContain("GAME_REVIEW_PRESCRIPTION_SERVED");
  expect(games).toContain("GAME_REVIEW_NO_ELIGIBLE_GAME");
  expect(games).toContain("GAME_REVIEW_FALLBACK_OFFERED");
  expect(review).toContain("GAME_REVIEW_PRESCRIPTION_COMPLETED");
  expect(review).toContain("GAME_REVIEW_NEXT_PRESCRIPTION_SERVED");
  expect(games).not.toContain("track(ANALYTICS_EVENTS.GAME_REVIEW_PRESCRIPTION_SERVED, {\n          game_id");
});
