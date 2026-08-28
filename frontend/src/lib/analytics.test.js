import {
  ANALYTICS_EVENTS,
  CURRICULUM_ANALYTICS_VERSION,
  trackCurriculum,
} from "./analytics";


describe("Personal Curriculum analytics boundary", () => {
  beforeEach(() => {
    window.posthog = { capture: jest.fn() };
  });

  afterEach(() => {
    jest.restoreAllMocks();
    delete window.posthog;
  });

  test("adds the baseline cohort and keeps only allowlisted primitive dimensions", () => {
    trackCurriculum(ANALYTICS_EVENTS.LESSON_STARTED, {
      surface: "legacy_opening_lesson",
      content_type: "opening",
      content_id: "italian_game",
      position_index: 0,
      is_recommended: false,
      fen: "must never leave the page",
      coaching_text: "private",
      nested: { private: true },
    });

    expect(window.posthog.capture).toHaveBeenCalledWith(
      ANALYTICS_EVENTS.LESSON_STARTED,
      {
        instrumentation_version: CURRICULUM_ANALYTICS_VERSION,
        flag_state: "legacy_control",
        surface: "legacy_opening_lesson",
        content_type: "opening",
        content_id: "italian_game",
        position_index: 0,
        is_recommended: false,
      }
    );
  });

  test("does not let the curriculum helper emit an unrelated event", () => {
    const warning = jest.spyOn(console, "warn").mockImplementation(() => {});
    trackCurriculum("funnel_home_viewed", { surface: "home" });

    expect(window.posthog.capture).not.toHaveBeenCalled();
    expect(warning).toHaveBeenCalledWith(
      "[analytics] ignored non-curriculum event: funnel_home_viewed"
    );
  });

  test("caps string dimensions before capture", () => {
    trackCurriculum(ANALYTICS_EVENTS.EXPLORE_OPENED, {
      surface: "x".repeat(200),
    });

    const properties = window.posthog.capture.mock.calls[0][1];
    expect(properties.surface).toHaveLength(120);
  });
});
