import { act } from "react";
import { createRoot } from "react-dom/client";

import PersonalizedReviewCoach, {
  boardArrowsForReviewVisual,
} from "./PersonalizedReviewCoach";


jest.mock("framer-motion", () => {
  const React = require("react");
  const motionProps = new Set(["initial", "animate", "exit", "transition", "layout"]);
  return {
    AnimatePresence: ({ children }) => children,
    motion: new Proxy({}, {
      get: (_target, tag) => React.forwardRef(({ children, ...props }, ref) => {
        const domProps = Object.fromEntries(
          Object.entries(props).filter(([key]) => !motionProps.has(key))
        );
        return React.createElement(tag, { ...domProps, ref }, children);
      }),
    }),
  };
});
jest.mock("../../App", () => ({ API: "/api" }));
jest.mock("../../lib/analytics", () => ({
  ANALYTICS_EVENTS: {
    REVIEW_COACH_STARTED: "review_coach_started",
    REVIEW_COACH_REFLECTION_SUBMITTED: "review_coach_reflection_submitted",
    REVIEW_COACH_VISUAL_SHOWN: "review_coach_visual_shown",
    REVIEW_COACH_COMPLETED: "review_coach_completed",
    REVIEW_COACH_NEXT_ACTION_STARTED: "review_coach_next_action_started",
  },
  track: jest.fn(),
}));


const EVENT_ID = "game:23:piece_safety.simple_hang:allowed";
const plan = {
  plan_id: "plan",
  opening: "I watched how this game unfolded.",
  game_arc: "I found one moment worth studying in this game.",
  chapters: [{ event_id: EVENT_ID, role: "turning_point" }],
  takeaway: "Before you move, check whether every piece is safe.",
  next_action: {
    href: "/training/pattern/piece_safety",
    action_kind: "practice",
    content_kind: "concept",
  },
};
const event = {
  event_id: EVENT_ID,
  move: { ply: 23, number: 12, san: "Bg5", actor: "user" },
  teaching: {
    caption: "Your bishop could be taken because its defender could not move.",
    principle: "Check whether a defender can actually move before relying on it.",
    visual: { arrows: [["c6", "g2"]], highlights: ["g2"] },
  },
};
const prompt = {
  prompt_id: "prompt",
  event_id: EVENT_ID,
  question: "What were you thinking before this move?",
  options: [
    { id: "thought_piece_safe", label: "I thought my piece was safe" },
    { id: "not_sure", label: "Not sure what to do" },
    { id: "none_of_these", label: "None of these" },
  ],
};


describe("PersonalizedReviewCoach", () => {
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

  const renderCoach = (overrides = {}) => {
    const props = {
      gameId: "game",
      plan,
      events: [event],
      prompts: [prompt],
      reflectionResponses: [],
      onChapterSelect: jest.fn(),
      onShowVisual: jest.fn(),
      onNavigate: jest.fn(),
      onReplay: jest.fn(),
      ...overrides,
    };
    act(() => root.render(<PersonalizedReviewCoach {...props} />));
    return props;
  };

  test("starts with the server story and hides teaching until reflection", () => {
    const props = renderCoach();
    expect(container.textContent).toContain("I watched how this game unfolded.");
    expect(container.textContent).toContain("one moment worth studying");

    act(() => {
      container.querySelector("[data-testid='personalized-review-start']")
        .dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(props.onChapterSelect).toHaveBeenCalledWith(event, 0);
    expect(container.textContent).toContain("What were you thinking before this move?");
    expect(container.textContent).not.toContain("Your bishop could be taken");
    expect(
      container.querySelector("[data-testid='personalized-reflection-option-not_sure']").tagName
    ).toBe("BUTTON");
  });

  test("shows practical framing before reflection and maps cause roles to board colors", () => {
    const v2Event = {
      ...event,
      teaching: {
        ...event.teaching,
        headline: "You kept control — but left one piece behind",
        practical_lead: "You were already winning and Bh6 did not throw the game away.",
        visual: {
          arrows: [["c2", "a1"], ["a1", "d1"]],
          highlights: ["a1"],
          relationship_arrows: [
            { from: "c2", to: "a1", role: "threat" },
            { from: "a1", to: "d1", role: "safe_move" },
            { from: "d5", to: "f6", role: "opportunity" },
          ],
        },
      },
    };
    renderCoach({ events: [v2Event] });
    act(() => {
      container.querySelector("[data-testid='personalized-review-start']")
        .dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(container.textContent).toContain("You kept control");
    expect(container.textContent).toContain("did not throw the game away");
    expect(container.textContent).not.toContain(v2Event.teaching.caption);
    expect(boardArrowsForReviewVisual(v2Event.teaching.visual)).toEqual([
      ["c2", "a1", "amber"],
      ["a1", "d1", "green"],
      ["d5", "f6", "blue"],
    ]);
  });

  test("submits exact server option IDs before revealing and shows visuals", async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ selected_option_id: "thought_piece_safe" }),
    });
    const props = renderCoach();
    act(() => {
      container.querySelector("[data-testid='personalized-review-start']")
        .dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await act(async () => {
      container.querySelector(
        "[data-testid='personalized-reflection-option-thought_piece_safe']"
      ).dispatchEvent(new MouseEvent("click", { bubbles: true }));
      await Promise.resolve();
    });

    const request = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(request.event_id).toBe(EVENT_ID);
    expect(request.prompt_id).toBe("prompt");
    expect(request.shown_option_ids).toEqual([
      "thought_piece_safe",
      "not_sure",
      "none_of_these",
    ]);
    expect(request.answered_before_reveal).toBe(true);
    expect(container.textContent).toContain("Your bishop could be taken");
    expect(container.textContent).toContain("Check whether a defender can actually move");

    act(() => {
      container.querySelector("[data-testid='personalized-review-show-visual']")
        .dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(props.onShowVisual).toHaveBeenCalledWith(event.teaching.visual);
  });

  test("restores an existing answer on refresh without resubmitting", () => {
    renderCoach({
      reflectionResponses: [{
        event_id: EVENT_ID,
        prompt_id: "prompt",
        selected_option_id: "not_sure",
        answered_before_reveal: true,
      }],
    });
    act(() => {
      container.querySelector("[data-testid='personalized-review-start']")
        .dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(container.textContent).toContain("Not sure what to do");
    expect(container.textContent).toContain("Your bishop could be taken");
    expect(global.fetch).not.toHaveBeenCalled();
  });

  test("finishes with one takeaway and routes the canonical next action", () => {
    const props = renderCoach({
      reflectionResponses: [{
        event_id: EVENT_ID,
        prompt_id: "prompt",
        selected_option_id: "not_sure",
      }],
    });
    act(() => {
      container.querySelector("[data-testid='personalized-review-start']")
        .dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    act(() => {
      container.querySelector("[data-testid='personalized-review-continue']")
        .dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(container.textContent).toContain("What I want you to take forward");
    expect(container.textContent).toContain("check whether every piece is safe");

    act(() => {
      container.querySelector("[data-testid='personalized-review-next-action']")
        .dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(props.onNavigate).toHaveBeenCalledWith(
      "/training/pattern/piece_safety"
    );
  });

  test("keeps the explanation hidden and offers retry when save fails", async () => {
    global.fetch.mockResolvedValue({ ok: false });
    renderCoach();
    act(() => {
      container.querySelector("[data-testid='personalized-review-start']")
        .dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await act(async () => {
      container.querySelector("[data-testid='personalized-reflection-option-not_sure']")
        .dispatchEvent(new MouseEvent("click", { bubbles: true }));
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(container.querySelector("[role='alert']").textContent).toContain(
      "couldn't save"
    );
    expect(container.textContent).not.toContain("Your bishop could be taken");
  });
});
