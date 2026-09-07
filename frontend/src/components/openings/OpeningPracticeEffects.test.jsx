import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { Chessground as mockedChessground } from "chessground";

import GuidedOpeningLesson from "./GuidedOpeningLesson";
import InteractivePractice from "./InteractivePractice";
import TrapPractice from "./TrapPractice";
import { ANALYTICS_EVENTS, trackCurriculum } from "@/lib/analytics";

const mockGround = {
  set: jest.fn(),
  destroy: jest.fn(),
};

jest.mock("chessground", () => ({ Chessground: jest.fn() }));
jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("@/components/LichessBoard", () => () => <div data-testid="guided-board" />, { virtual: true });
jest.mock("@/lib/analytics", () => ({
  ANALYTICS_EVENTS: {
    LESSON_STARTED: "lesson_started",
    GUIDED_ATTEMPT: "guided_attempt",
    INDEPENDENT_ATTEMPT: "independent_attempt",
  },
  trackCurriculum: jest.fn(),
}), { virtual: true });
jest.mock("sonner", () => ({ toast: { error: jest.fn() } }));
jest.mock("framer-motion", () => ({
  motion: { div: ({ children, ...props }) => <div {...props}>{children}</div> },
  AnimatePresence: ({ children }) => <>{children}</>,
}));

const START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const response = (body) => ({ ok: true, json: () => Promise.resolve(body) });

describe("opening practice hook ownership", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    jest.useFakeTimers();
    global.ResizeObserver = class {
      observe() {}
      disconnect() {}
    };
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    mockGround.set.mockReset();
    mockGround.destroy.mockReset();
    mockedChessground.mockReset();
    mockedChessground.mockReturnValue(mockGround);
    trackCurriculum.mockReset();
  });

  afterEach(() => {
    act(() => root.unmount());
    jest.clearAllTimers();
    jest.useRealTimers();
    container.remove();
    delete global.fetch;
    delete global.ResizeObserver;
    jest.restoreAllMocks();
  });

  test("the guided coach introduction stays stable across unrelated rerenders", async () => {
    jest.spyOn(Math, "random")
      .mockReturnValueOnce(0)
      .mockReturnValue(0.99);

    await act(async () => root.render(
      <GuidedOpeningLesson openingKey="italian" opening={{ color: "white", main_line: [] }} />
    ));
    expect(container.textContent).toContain("Let me show you how to play this opening as White.");

    await act(async () => root.render(
      <GuidedOpeningLesson openingKey="italian" opening={{ color: "white", main_line: [] }} />
    ));
    expect(container.textContent).toContain("Let me show you how to play this opening as White.");
    expect(container.textContent).not.toContain("This is one of my favorite openings to teach.");
  });

  test("InteractivePractice updates orientation without recreating its board", async () => {
    await act(async () => root.render(
      <InteractivePractice openingKey="old" openingName="Old" userColor="white" />
    ));
    expect(mockedChessground).toHaveBeenCalledTimes(1);
    mockGround.set.mockClear();

    await act(async () => root.render(
      <InteractivePractice openingKey="old" openingName="Old" userColor="black" />
    ));

    expect(mockedChessground).toHaveBeenCalledTimes(1);
    expect(mockGround.set).toHaveBeenCalledWith({ orientation: "black" });
  });

  test("InteractivePractice board events use the latest opening identity", async () => {
    global.fetch = jest.fn()
      .mockResolvedValueOnce(response({ session_id: "session-1", fen: START, move_number: 1 }))
      .mockResolvedValueOnce(response({ try_again: true, fen: START, feedback: { message: "Try again" } }));

    await act(async () => root.render(
      <InteractivePractice openingKey="old-opening" openingName="Old" userColor="white" />
    ));
    await act(async () => {
      container.querySelector("[data-testid='start-practice-btn']").click();
      await Promise.resolve();
      await Promise.resolve();
    });
    act(() => jest.advanceTimersByTime(500));
    const moveEvent = mockGround.set.mock.calls
      .map(([config]) => config?.events?.move)
      .find(Boolean);
    expect(moveEvent).toBeDefined();

    await act(async () => root.render(
      <InteractivePractice openingKey="current-opening" openingName="Current" userColor="white" />
    ));
    await act(async () => {
      await moveEvent("e2", "e4");
      await Promise.resolve();
    });

    expect(trackCurriculum).toHaveBeenCalledWith(
      ANALYTICS_EVENTS.INDEPENDENT_ATTEMPT,
      expect.objectContaining({ content_id: "current-opening", outcome: "incorrect" })
    );
  });

  test("TrapPractice board events use the current trap after a prop change", async () => {
    const oldTrap = {
      key: "old-trap",
      name: "Old trap",
      trap_color: "white",
      setup_moves: [],
      trap_line: [{ move: "e4", explanation: "Old move" }],
    };
    const currentTrap = {
      key: "current-trap",
      name: "Current trap",
      trap_color: "white",
      setup_moves: [],
      trap_line: [{ move: "d4", explanation: "Current move" }],
    };

    await act(async () => root.render(<TrapPractice trap={oldTrap} openingKey="opening" />));
    act(() => container.querySelector("[data-testid='start-trap-practice']").click());
    const moveEvent = mockGround.set.mock.calls
      .map(([config]) => config?.events?.move)
      .find(Boolean);
    expect(moveEvent).toBeDefined();

    await act(async () => root.render(<TrapPractice trap={currentTrap} openingKey="opening" />));
    act(() => moveEvent("d2", "d4"));

    expect(trackCurriculum).toHaveBeenCalledWith(
      ANALYTICS_EVENTS.GUIDED_ATTEMPT,
      expect.objectContaining({
        content_id: "opening:current-trap",
        outcome: "correct",
      })
    );
  });
});
