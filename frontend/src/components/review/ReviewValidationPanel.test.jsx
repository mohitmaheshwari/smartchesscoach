import { act } from "react";
import { createRoot } from "react-dom/client";

import ReviewValidationPanel from "./ReviewValidationPanel";


jest.mock("../../App", () => ({ API: "/api" }));
jest.mock("../../lib/analytics", () => ({
  ANALYTICS_EVENTS: {
    REVIEW_VALIDATION_MODE_CHANGED: "review_validation_mode_changed",
    REVIEW_VALIDATION_SUBMITTED: "review_validation_submitted",
  },
  trackReviewValidation: jest.fn(),
}));


const rubric = [
  { id: "chess_truth", label: "Chess truth", options: [
    { id: "correct", label: "Correct" },
    { id: "critical_false_claim", label: "Critical false claim" },
  ] },
  { id: "moment_choice", label: "Moment choice", options: [
    { id: "strong", label: "Strong" },
  ] },
  { id: "explanation_clarity", label: "Explanation clarity", options: [
    { id: "clear", label: "Clear" },
  ] },
  { id: "personalization", label: "Personalization", options: [
    { id: "specific", label: "Specific to this player" },
  ] },
  { id: "reflection_value", label: "Reflection value", options: [
    { id: "useful", label: "Useful" },
  ] },
  { id: "story_coherence", label: "Story coherence", options: [
    { id: "coherent", label: "Coherent" },
  ] },
  { id: "next_action_quality", label: "Next action", options: [
    { id: "useful", label: "Useful" },
  ] },
];

const validation = {
  enabled: true,
  active_variant: "a",
  comparison_ready: true,
  presentation_options: [
    { id: "a", label: "Review A" },
    { id: "b", label: "Review B" },
  ],
  rubric,
  existing_submission: null,
};


describe("ReviewValidationPanel", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    global.fetch = jest.fn();
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    jest.restoreAllMocks();
  });

  const renderPanel = (overrides = {}) => {
    const props = {
      gameId: "game-1",
      validation,
      onModeChange: jest.fn(),
      onSubmission: jest.fn(),
      ...overrides,
    };
    act(() => root.render(<ReviewValidationPanel {...props} />));
    return props;
  };

  const click = (selector) => act(() => {
    container.querySelector(selector).dispatchEvent(
      new MouseEvent("click", { bubbles: true })
    );
  });

  test("renders server labels and changes only to a server-provided mode", () => {
    const props = renderPanel();
    expect(container.textContent).toContain("Internal validation");
    expect(container.textContent).toContain("Review A");
    expect(container.textContent).toContain("Review B");

    click("[data-testid='review-validation-mode-b']");
    expect(props.onModeChange).toHaveBeenCalledWith("b");
  });

  test("disables the new mode when the backend says no verified plan exists", () => {
    renderPanel({
      validation: { ...validation, comparison_ready: false },
    });
    expect(
      container.querySelector("[data-testid='review-validation-mode-b']").disabled
    ).toBe(true);
    expect(container.textContent).toContain("not ready for a blinded comparison");
  });

  test("submits one exact answer per server rubric dimension", async () => {
    const submission = {
      presentation_variant: "a",
      ratings: Object.fromEntries(rubric.map((item) => [item.id, item.options[0].id])),
      notes: "Clear baseline.",
      critical_truth_failure: false,
    };
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, submission }),
    });
    const props = renderPanel();
    click("[data-testid='review-validation-open']");

    for (const dimension of rubric) {
      click(`[data-testid='review-validation-${dimension.id}-${dimension.options[0].id}']`);
    }
    act(() => {
      const notes = container.querySelector("#review-validation-notes");
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLTextAreaElement.prototype,
        "value"
      ).set;
      setter.call(notes, "Clear baseline.");
      notes.dispatchEvent(new Event("input", { bubbles: true }));
    });

    await act(async () => {
      container.querySelector("[data-testid='review-validation-submit']")
        .dispatchEvent(new MouseEvent("click", { bubbles: true }));
      await Promise.resolve();
      await Promise.resolve();
    });

    const body = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(body).toEqual({
      presentation_variant: "a",
      ratings: submission.ratings,
      notes: "Clear baseline.",
    });
    expect(props.onSubmission).toHaveBeenCalledWith(submission);
    expect(container.textContent).toContain("Review saved");
  });

  test("restores a prior scorecard and marks a critical truth failure", () => {
    const existingRatings = Object.fromEntries(
      rubric.map((item) => [item.id, item.options[0].id])
    );
    existingRatings.chess_truth = "critical_false_claim";
    renderPanel({
      validation: {
        ...validation,
        existing_submission: {
          presentation_variant: "a",
          ratings: existingRatings,
          notes: "Wrong relationship.",
          critical_truth_failure: true,
        },
      },
    });
    click("[data-testid='review-validation-open']");
    expect(container.textContent).toContain("rollout blocker");
    expect(container.querySelector("#review-validation-notes").value).toBe(
      "Wrong relationship."
    );
    expect(global.fetch).not.toHaveBeenCalled();
  });
});
