import {
  ANALYTICS_EVENTS,
  ANALYTICS_CONTEXT_VERSION,
  CURRICULUM_ANALYTICS_VERSION,
  REVIEW_VALIDATION_ANALYTICS_VERSION,
  analyticsActorType,
  configureAnalyticsContext,
  resetAnalyticsContext,
  track,
  trackCurriculum,
  trackReviewValidation,
} from "./analytics";

const ANONYMOUS_CONTEXT = {
  analytics_context_version: ANALYTICS_CONTEXT_VERSION,
  actor_type: "anonymous",
  metrics_eligible: false,
};

const installPostHogMock = () => {
  window.posthog = {
    capture: jest.fn(),
    identify: jest.fn(),
    register: jest.fn(),
    reset: jest.fn(),
  };
  resetAnalyticsContext();
  jest.clearAllMocks();
};


describe("Personal Curriculum analytics boundary", () => {
  beforeEach(() => {
    installPostHogMock();
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
        ...ANONYMOUS_CONTEXT,
      }
    );
  });

  test("does not let the curriculum helper emit an unrelated event", () => {
    const warning = jest.spyOn(console, "warn").mockImplementation(() => {});
    trackCurriculum(ANALYTICS_EVENTS.FUNNEL_HOME_VIEWED, {
      surface: "home",
    });

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


describe("Personalized Game Review validation analytics boundary", () => {
  beforeEach(() => {
    installPostHogMock();
  });

  afterEach(() => {
    jest.restoreAllMocks();
    delete window.posthog;
  });

  test("keeps only coarse validation dimensions", () => {
    trackReviewValidation(ANALYTICS_EVENTS.REVIEW_VALIDATION_SUBMITTED, {
      presentation_variant: "a",
      critical_truth_failure: true,
      game_id: "private",
      notes: "private reviewer note",
      caption: "private chess text",
    });

    expect(window.posthog.capture).toHaveBeenCalledWith(
      ANALYTICS_EVENTS.REVIEW_VALIDATION_SUBMITTED,
      {
        instrumentation_version: REVIEW_VALIDATION_ANALYTICS_VERSION,
        presentation_variant: "a",
        critical_truth_failure: true,
        ...ANONYMOUS_CONTEXT,
      }
    );
  });

  test("does not emit unrelated events through the validation helper", () => {
    const warning = jest.spyOn(console, "warn").mockImplementation(() => {});
    trackReviewValidation(ANALYTICS_EVENTS.FUNNEL_HOME_VIEWED, {});
    expect(window.posthog.capture).not.toHaveBeenCalled();
    expect(warning).toHaveBeenCalledWith(
      "[analytics] ignored non-review-validation event: funnel_home_viewed"
    );
  });
});


describe("Acquisition-readiness analytics context", () => {
  beforeEach(() => {
    installPostHogMock();
  });

  afterEach(() => {
    jest.restoreAllMocks();
    delete window.posthog;
  });

  test.each([
    [{ user_id: "user_1", role: "user" }, {}, "player", true],
    [{ user_id: "user_2", role: "admin" }, {}, "staff", false],
    [{ user_id: "user_3", role: "super_admin" }, {}, "staff", false],
    [{ user_id: "user_4", role: "user", is_reviewer: true }, {}, "reviewer", false],
    [{ user_id: "user_5", role: "user", is_demo: true }, {}, "demo", false],
    [{ user_id: "dev_user_local", role: "user" }, {}, "demo", false],
    [{ user_id: "user_6", role: "user" }, { demoMode: true }, "demo", false],
    [{ user_id: "user_7", role: "user", analytics_excluded: true }, {}, "excluded", false],
  ])("classifies %p as %s", (user, options, expectedActor, expectedEligible) => {
    expect(analyticsActorType(user, options)).toBe(expectedActor);
    const context = configureAnalyticsContext(user, options);
    expect(context.actor_type).toBe(expectedActor);
    expect(context.metrics_eligible).toBe(expectedEligible);
  });

  test("identifies by opaque internal id and registers only coarse context", () => {
    configureAnalyticsContext({
      user_id: "user_safe123",
      email: "must-not-be-sent@example.com",
      name: "Must Not Be Sent",
      role: "user",
    });

    expect(window.posthog.identify).toHaveBeenCalledWith("user_safe123");
    expect(window.posthog.register).toHaveBeenCalledWith({
      analytics_context_version: ANALYTICS_CONTEXT_VERSION,
      actor_type: "player",
      metrics_eligible: true,
    });
  });

  test("does not create identified profiles for demo or staff traffic", () => {
    configureAnalyticsContext({ user_id: "demo_account", role: "user", is_demo: true });
    configureAnalyticsContext({ user_id: "staff_account", role: "admin" });

    expect(window.posthog.identify).not.toHaveBeenCalled();
  });

  test("does not emit a duplicate identify event on protected-route remount", () => {
    const user = { user_id: "user_safe123", role: "user" };
    configureAnalyticsContext(user);
    configureAnalyticsContext(user);

    expect(window.posthog.identify).toHaveBeenCalledTimes(1);
  });

  test("resets before switching between authenticated players", () => {
    configureAnalyticsContext({ user_id: "user_first", role: "user" });
    jest.clearAllMocks();
    configureAnalyticsContext({ user_id: "user_second", role: "user" });

    expect(window.posthog.reset).toHaveBeenCalledTimes(1);
    expect(window.posthog.identify).toHaveBeenCalledWith("user_second");
  });

  test("fails closed for invalid identity and sensitive event properties", () => {
    configureAnalyticsContext({ user_id: "player@example.com", role: "user" });
    track(ANALYTICS_EVENTS.FUNNEL_HOME_CTA_CLICKED, {
      cta: "play_with_coach",
      session_id: "private-session",
      game_id: "private-game",
      fen: "private-position",
      caption: "private-coaching-text",
      email: "private@example.com",
      nested: { private: true },
    });

    expect(window.posthog.identify).not.toHaveBeenCalled();
    expect(window.posthog.capture).toHaveBeenCalledWith(
      ANALYTICS_EVENTS.FUNNEL_HOME_CTA_CLICKED,
      {
        cta: "play_with_coach",
        analytics_context_version: ANALYTICS_CONTEXT_VERSION,
        actor_type: "excluded",
        metrics_eligible: false,
      }
    );
  });

  test("resets identity and restores anonymous context on logout", () => {
    configureAnalyticsContext({ user_id: "user_safe123", role: "user" });
    jest.clearAllMocks();

    resetAnalyticsContext();
    track(ANALYTICS_EVENTS.FUNNEL_HOME_VIEWED);

    expect(window.posthog.reset).toHaveBeenCalledTimes(1);
    expect(window.posthog.register).toHaveBeenCalledWith(ANONYMOUS_CONTEXT);
    expect(window.posthog.capture).toHaveBeenCalledWith(
      ANALYTICS_EVENTS.FUNNEL_HOME_VIEWED,
      ANONYMOUS_CONTEXT
    );
  });
});
