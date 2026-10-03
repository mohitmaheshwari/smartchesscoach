import React, { act } from "react";
import { createRoot } from "react-dom/client";
import CoachPlayBoard from "./CoachPlayBoard";

jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("@/lib/chessSounds", () => ({
  isMuted: () => false,
  setMuted: jest.fn(),
  playForSan: jest.fn(),
}));
jest.mock("@/components/LichessBoard", () => () => <div data-testid="lichess-board" />);
jest.mock("@/components/coach/PreMoveChecklist", () => () => null);
jest.mock("@/components/openings/OpeningCorrectionDialog", () => ({
  OpeningCorrectionDialog: () => null,
}));
jest.mock("@/components/coach-play", () => ({
  EvalBar: () => null,
  PositionCoachingPanel: () => null,
}));

describe("CoachPlayBoard clock pause and resume behavior", () => {
  let container;
  let root;
  let mockFetch;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    jest.useFakeTimers();
    localStorage.clear();
    mockFetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      })
    );
    global.fetch = mockFetch;
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  test("timer ticks down when not paused and turn is active", () => {
    const session = {
      session_id: "test-session-1",
      user_time_remaining: 300,
      coach_time_remaining: 300,
      time_control: "5+0",
      move_history: [],
    };

    act(() => {
      root.render(
        <CoachPlayBoard
          session={session}
          currentFen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
          isPlayerTurn={true}
          gameOver={false}
          isGamePaused={false}
          showResumeModal={false}
        />
      );
    });

    expect(container.textContent).toContain("5:00");

    // Advance by 3 seconds
    act(() => {
      jest.advanceTimersByTime(3000);
    });

    // Player time decreases to 4:57
    expect(container.textContent).toContain("4:57");
  });

  test("timer is FROZEN when isGamePaused is true (leaving / active modal)", () => {
    const session = {
      session_id: "test-session-2",
      user_time_remaining: 300,
      coach_time_remaining: 300,
      time_control: "5+0",
      move_history: [],
    };

    act(() => {
      root.render(
        <CoachPlayBoard
          session={session}
          currentFen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
          isPlayerTurn={true}
          gameOver={false}
          isGamePaused={true} // Paused!
          showResumeModal={true}
        />
      );
    });

    expect(container.textContent).toContain("5:00");

    // Advance timers 10 seconds while paused
    act(() => {
      jest.advanceTimersByTime(10000);
    });

    // Time remains 5:00 because it's paused!
    expect(container.textContent).toContain("5:00");

    // Now resume the game (user clicked Resume)
    act(() => {
      root.render(
        <CoachPlayBoard
          session={session}
          currentFen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
          isPlayerTurn={true}
          gameOver={false}
          isGamePaused={false} // Unpaused!
          showResumeModal={false}
        />
      );
    });

    // Advance by 2 seconds after resume
    act(() => {
      jest.advanceTimersByTime(2000);
    });

    // Time continues from 5:00 down to 4:58!
    expect(container.textContent).toContain("4:58");
  });

  test("clicking toolbar pause button toggles pause state and syncs to backend", () => {
    const session = {
      session_id: "test-session-3",
      user_time_remaining: 600,
      coach_time_remaining: 600,
      time_control: "10+0",
      move_history: [],
    };

    const setIsGamePaused = jest.fn();

    act(() => {
      root.render(
        <CoachPlayBoard
          session={session}
          currentFen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
          isPlayerTurn={true}
          gameOver={false}
          isGamePaused={false}
          setIsGamePaused={setIsGamePaused}
          showResumeModal={false}
        />
      );
    });

    const pauseBtn = container.querySelector("[data-testid='pause-board-btn']");
    expect(pauseBtn).not.toBeNull();

    // Click pause
    act(() => {
      pauseBtn.click();
    });

    expect(setIsGamePaused).toHaveBeenCalledWith(true);
    expect(container.textContent).toContain("PAUSED");

    // Advancing timers while paused does not deduct time
    act(() => {
      jest.advanceTimersByTime(5000);
    });
    expect(container.textContent).toContain("10:00");

    // Click resume button in banner
    const resumeBtn = container.querySelector("[data-testid='resume-banner-btn']");
    expect(resumeBtn).not.toBeNull();
    act(() => {
      resumeBtn.click();
    });

    // Advancing timers continues the clock
    act(() => {
      jest.advanceTimersByTime(4000);
    });
    expect(container.textContent).toContain("9:56");
  });

  test("document visibility change automatically pauses the clock", () => {
    const session = {
      session_id: "test-session-4",
      user_time_remaining: 400,
      coach_time_remaining: 400,
      time_control: "10+0",
      move_history: [],
    };

    const setIsGamePaused = jest.fn();

    act(() => {
      root.render(
        <CoachPlayBoard
          session={session}
          currentFen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
          isPlayerTurn={true}
          gameOver={false}
          isGamePaused={false}
          setIsGamePaused={setIsGamePaused}
          showResumeModal={false}
        />
      );
    });

    // Simulate user switching tabs: document.hidden = true
    Object.defineProperty(document, "hidden", { value: true, configurable: true });
    act(() => {
      document.dispatchEvent(new Event("visibilitychange"));
    });

    expect(setIsGamePaused).toHaveBeenCalledWith(true);
    expect(mockFetch).toHaveBeenCalledWith(
      "https://api.test/coach/play/sync-clock",
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining('"is_paused":true'),
      })
    );
  });
});
