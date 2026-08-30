import { act } from "react";
import { createRoot } from "react-dom/client";
import CurriculumPrimary from "./CurriculumPrimary";


const curriculum = {
  enabled: true,
  decision: {
    decision_id: "pcv1:test",
    primary: {
      outcome: "expand",
      state: "learning",
      title: "Rule of the Square",
      reason: "This has started to show up in your games.",
      evidence: "I have seen this once or twice, and now is a good time to work on it.",
      destination: {
        href: "/endgames/king_and_pawn/square_rule",
        lesson_kind: "endgame",
        lesson_id: "king_and_pawn/square_rule",
      },
    },
    review: null,
  },
};


describe("CurriculumPrimary", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    window.posthog = { capture: jest.fn() };
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    delete window.posthog;
  });

  test("renders one coach-owned action and its honest evidence", () => {
    const onNavigate = jest.fn();

    act(() => root.render(
      <CurriculumPrimary
        curriculum={curriculum}
        surface="learn"
        onNavigate={onNavigate}
      />
    ));

    expect(container.textContent).toContain("Rule of the Square");
    expect(container.textContent).toContain("I have seen this once or twice");
    expect(container.textContent).not.toContain("Reliable");
    expect(container.querySelectorAll("button")).toHaveLength(1);

    act(() => {
      container.querySelector("button").dispatchEvent(
        new MouseEvent("click", { bubbles: true })
      );
    });

    expect(onNavigate).toHaveBeenCalledWith(
      "/endgames/king_and_pawn/square_rule"
    );
  });

  test("adds at most one review action", () => {
    const withReview = {
      ...curriculum,
      decision: {
        ...curriculum.decision,
        review: {
          outcome: "review",
          title: "Castle before attacking",
          destination: {
            href: "/training/pattern/king_safety",
            lesson_kind: "concept",
            lesson_id: "king_safety",
          },
        },
      },
    };

    act(() => root.render(
      <CurriculumPrimary
        curriculum={withReview}
        surface="home"
        onNavigate={jest.fn()}
      />
    ));

    expect(container.querySelectorAll("button")).toHaveLength(2);
    expect(container.textContent).toContain("One quick review");
  });

  test("explains personalization without inventing application evidence", () => {
    const personalized = {
      ...curriculum,
      personalized_teaching: {
        enabled: true,
        profile: {
          why_now: "This is the one idea in your current coaching plan.",
        },
      },
    };

    act(() => root.render(
      <CurriculumPrimary
        curriculum={personalized}
        surface="learn"
        onNavigate={jest.fn()}
      />
    ));

    expect(container.textContent).toContain("Why this lesson is for you");
    expect(container.textContent).toContain("Used in your games");
    expect(container.textContent).toContain("Remembered later");
    expect(container.textContent.match(/Not measured/g)).toHaveLength(2);
    expect(container.textContent).not.toContain("Reliable");
  });
});
