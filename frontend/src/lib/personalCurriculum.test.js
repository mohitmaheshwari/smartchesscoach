import {
  CURRICULUM_ROUTES,
  EXPLORE_DESTINATIONS,
  curriculumCta,
  curriculumHeadline,
  loadPersonalCurriculum,
  resetPersonalCurriculumRequestsForTests,
} from "./personalCurriculum";

afterEach(() => {
  resetPersonalCurriculumRequestsForTests();
  delete global.fetch;
});

test("Explore exposes every signed learning family through a real route", () => {
  expect(EXPLORE_DESTINATIONS).toEqual([
    { id: "openings", label: "Openings", href: "/openings" },
    { id: "tactics_traps", label: "Tactics & traps", href: "/training" },
    {
      id: "endgames",
      label: "Endgames",
      href: "/openings-overview?tab=endgames",
    },
    { id: "plans", label: "Plans", href: "/coach" },
    {
      id: "thinking_habits",
      label: "Thinking habits",
      href: "/training",
    },
  ]);
});

test("Game Review opens the player's reviewable game history", () => {
  expect(CURRICULUM_ROUTES.gameReview).toBe("/games");
  expect(CURRICULUM_ROUTES.gameReview).not.toBe("/lab");
  expect(CURRICULUM_ROUTES.gameReview).not.toBe("/review");
});

test("the primary message and action stay coach-led", () => {
  expect(curriculumHeadline("repair")).toBe(
    "Let's fix one thing that keeps getting in your way."
  );
  expect(curriculumCta("expand")).toBe("Learn with your coach · 6 min");
});

test("Home, Learn, and navigation share one account-scoped request", async () => {
  const payload = { enabled: true, decision: { decision_id: "pcv1:test" } };
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    json: jest.fn().mockResolvedValue(payload),
  });

  const [home, learn, layout] = await Promise.all([
    loadPersonalCurriculum("/api", "u1"),
    loadPersonalCurriculum("/api", "u1"),
    loadPersonalCurriculum("/api", "u1"),
  ]);

  expect(home).toBe(payload);
  expect(learn).toBe(payload);
  expect(layout).toBe(payload);
  expect(global.fetch).toHaveBeenCalledTimes(1);
  expect(global.fetch).toHaveBeenCalledWith(
    "/api/coach/personal-curriculum",
    { credentials: "include" }
  );
});

test("curriculum responses are never shared between accounts", async () => {
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    json: jest.fn().mockResolvedValue({ enabled: true }),
  });

  await loadPersonalCurriculum("/api", "u1");
  await loadPersonalCurriculum("/api", "u2");

  expect(global.fetch).toHaveBeenCalledTimes(2);
});

test("reach-attributed surfaces use distinct cached requests", async () => {
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    json: jest.fn().mockResolvedValue({ enabled: true }),
  });

  await loadPersonalCurriculum("/api", "u1", "home");
  await loadPersonalCurriculum("/api", "u1", "learn");
  await loadPersonalCurriculum("/api", "u1", "home");

  expect(global.fetch).toHaveBeenCalledTimes(2);
  expect(global.fetch).toHaveBeenNthCalledWith(
    1,
    "/api/coach/personal-curriculum?surface=home",
    { credentials: "include" }
  );
  expect(global.fetch).toHaveBeenNthCalledWith(
    2,
    "/api/coach/personal-curriculum?surface=learn",
    { credentials: "include" }
  );
});
