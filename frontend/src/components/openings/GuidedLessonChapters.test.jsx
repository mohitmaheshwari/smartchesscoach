/**
 * The chapter spine has to be able to move forward.
 *
 * Reported by Mohit on the Philidor lesson: "only one opening is showing,
 * rest are disabled". They were not disabled by data or by design intent —
 * they were unreachable. `chapterIndex` started at 0, the only writer was
 * goToChapter, and its only caller was a spine button guarded by
 * `reached = i <= chapterIndex`. The index could never rise, so in all 36
 * multi-chapter openings every chapter after the first was dead.
 */
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { Chessground as mockedChessground } from "chessground";

import GuidedOpeningLesson from "./GuidedOpeningLesson";

const mockGround = { set: jest.fn(), destroy: jest.fn() };

jest.mock("chessground", () => ({ Chessground: jest.fn() }));
jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("@/components/LichessBoard", () => () => <div data-testid="guided-board" />, { virtual: true });
jest.mock("@/lib/analytics", () => ({
  ANALYTICS_EVENTS: { LESSON_STARTED: "lesson_started", GUIDED_ATTEMPT: "guided_attempt" },
  trackCurriculum: jest.fn(),
}), { virtual: true });
jest.mock("sonner", () => ({ toast: { error: jest.fn() } }));
jest.mock("framer-motion", () => ({
  motion: { div: ({ children, ...props }) => <div {...props}>{children}</div> },
  AnimatePresence: ({ children }) => <>{children}</>,
}));

// Shaped like a real lesson plan: a main line, then a trap, then the close.
const PLAN = {
  chapters: [
    { key: "main_line", title: "The main line", kind: "walkthrough",
      play: [{ move: "e4", say: "Take the centre." }] },
    { key: "trap_0", title: "The c3 Offer", kind: "trap",
      play: [{ move: "c3", say: "Offer the pawn." }] },
    { key: "close", title: "What to remember", kind: "close", play: [] },
  ],
};

const OPENING = { color: "white", main_line: [] };

describe("moving through a multi-chapter lesson", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    jest.useFakeTimers();
    global.ResizeObserver = class {
      observe() {} unobserve() {} disconnect() {}
    };
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    mockedChessground.mockReset();
    mockedChessground.mockReturnValue(mockGround);
  });

  afterEach(() => {
    act(() => root.unmount());
    jest.clearAllTimers();
    jest.useRealTimers();
    container.remove();
    delete global.ResizeObserver;
    jest.restoreAllMocks();
  });

  const render = async () => {
    await act(async () => root.render(
      <GuidedOpeningLesson openingKey="philidor_defense" opening={OPENING} plan={PLAN} />
    ));
  };

  const clickText = async (label) => {
    const btn = Array.from(container.querySelectorAll("button"))
      .find((b) => (b.textContent || "").includes(label));
    if (!btn) throw new Error(`no button labelled ${label}: ${container.textContent}`);
    await act(async () => btn.click());
  };

  // Start the chapter and run it to its last move.
  const playThrough = async () => {
    await clickText("Start Lesson");
    await act(async () => { jest.advanceTimersByTime(20000); });
  };

  const spine = () =>
    Array.from(container.querySelectorAll('[data-testid^="lesson-chapter-"]'));

  test("the spine shows every chapter", async () => {
    await render();
    expect(spine()).toHaveLength(3);
    expect(container.textContent).toContain("The c3 Offer");
    expect(container.textContent).toContain("What to remember");
  });

  test("later chapters start locked, so the student cannot skip ahead", async () => {
    await render();
    const [first, second, third] = spine();
    expect(first.disabled).toBe(false);
    expect(second.disabled).toBe(true);
    expect(third.disabled).toBe(true);
  });

  test("SOMETHING other than the spine can advance the chapter", async () => {
    // The regression, stated directly. Before the fix the only writer of
    // chapterIndex was reachable only from an already-reached tab, so no
    // sequence of clicks could ever unlock chapter 2.
    await render();
    expect(spine().filter((b) => !b.disabled)).toHaveLength(1);
    expect(container.querySelector('[data-testid="lesson-next-chapter"]')).toBeNull();

    await playThrough();
    const advance = container.querySelector('[data-testid="lesson-next-chapter"]');
    expect(advance).not.toBeNull();
    expect(advance.textContent).toContain("The c3 Offer");
  });

  test("the way onward sits on the last move's card, where the student is", async () => {
    // Not on the "Lesson complete" card: that branch is unreachable, because
    // coachMessage is set on the last move and the branch above always wins.
    await render();
    await playThrough();
    expect(container.textContent).toContain("Take the centre.");
    expect(container.querySelector('[data-testid="lesson-next-chapter"]')).not.toBeNull();
  });

  test("taking the next section unlocks it and moves the student there", async () => {
    await render();
    await playThrough();
    await act(async () => {
      container.querySelector('[data-testid="lesson-next-chapter"]').click();
    });
    const [, second] = spine();
    expect(second.disabled).toBe(false);
    expect(second.className).toContain("text-primary");
    // Each chapter opens on its own intro rather than dropping the student
    // mid-line, so the new chapter's content appears once it is played.
    await playThrough();
    expect(container.textContent).toContain("Offer the pawn.");
  });

  test("the last chapter offers practice instead of a next section", async () => {
    await act(async () => root.render(
      <GuidedOpeningLesson
        openingKey="philidor_defense"
        opening={OPENING}
        plan={{ chapters: [PLAN.chapters[0], PLAN.chapters[1]] }}
        onStartPractice={() => {}}
      />
    ));
    await playThrough();
    await act(async () => {
      container.querySelector('[data-testid="lesson-next-chapter"]').click();
    });
    await playThrough();
    expect(container.querySelector('[data-testid="lesson-next-chapter"]')).toBeNull();
    expect(container.querySelector('[data-testid="lesson-start-practice"]')).not.toBeNull();
  });

  test("a single-chapter opening is unaffected", async () => {
    await act(async () => root.render(
      <GuidedOpeningLesson
        openingKey="x"
        opening={OPENING}
        plan={{ chapters: [PLAN.chapters[0]] }}
      />
    ));
    expect(spine()).toHaveLength(0);
    expect(container.querySelector('[data-testid="lesson-next-chapter"]')).toBeNull();
  });
});
