import {
  EXPLORE_DESTINATIONS,
  curriculumCta,
  curriculumHeadline,
} from "./personalCurriculum";

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

test("the primary message and action stay coach-led", () => {
  expect(curriculumHeadline("repair")).toBe(
    "Let's fix one thing that keeps getting in your way."
  );
  expect(curriculumCta("expand")).toBe("Learn with your coach · 6 min");
});
