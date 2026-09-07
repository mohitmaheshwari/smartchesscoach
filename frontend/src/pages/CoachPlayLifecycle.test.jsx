import React, { act } from "react";
import { createRoot } from "react-dom/client";

import CoachPlay from "./CoachPlay";
import useTeachingMode from "@/hooks/useTeachingMode";
import usePlayerData from "@/hooks/usePlayerData";
import useGuardian from "@/hooks/useGuardian";
import useStockfishEval from "@/hooks/useStockfishEval";
import { useCoachFlow } from "@/coachFlow";

let mockSearchParams = new URLSearchParams();
const mockHandleStartLesson = jest.fn();

jest.mock("react-router-dom", () => ({
  useNavigate: () => jest.fn(),
  useSearchParams: () => [mockSearchParams],
}), { virtual: true });
jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("@/lib/analytics", () => ({
  ANALYTICS_EVENTS: { FUNNEL_PWC_STARTED: "pwc_started" },
  track: jest.fn(),
}), { virtual: true });
jest.mock("@/lib/motion", () => ({ navFade: {}, fadeInUp: {} }), { virtual: true });
jest.mock("@/lib/coachingContext", () => ({ coachPlayFocusRule: () => null }), { virtual: true });
jest.mock("@/lib/teachingLessonPrompt", () => ({ nextLessonPrompt: () => null }), { virtual: true });
jest.mock("@/components/Layout", () => ({ children }) => <div>{children}</div>, { virtual: true });
jest.mock("@/components/coach/CoachPlaySetup", () => (props) => (
  <button data-testid="start-game" onClick={props.actuallyStartGame}>Start game</button>
), { virtual: true });
jest.mock("@/components/coach/CoachPlayBoard", () => {
  const ReactModule = require("react");
  return ReactModule.forwardRef((props, _ref) => (
    <div>
      <span data-testid="board-session">{props.session?.session_id || "none"}</span>
      <span data-testid="board-fen">{props.currentFen}</span>
      <button data-testid="new-game" onClick={props.newGame}>New game</button>
    </div>
  ));
}, { virtual: true });
jest.mock("@/components/coach/CoachPlaySidebar", () => (props) => (
  <div>
    <span data-testid="sidebar-session">{props.session?.session_id || "none"}</span>
    <span data-testid="chat-messages">{props.chatMessages.map((message) => message.content || message.message).join("|")}</span>
  </div>
), { virtual: true });
jest.mock("@/components/streak", () => ({ PostGameStreakResult: () => null }), { virtual: true });
jest.mock("@/components/coach-play/EnforcementCheckboxModal", () => () => null, { virtual: true });
jest.mock("@/components/coach/ActiveCoachingCard", () => () => null, { virtual: true });
jest.mock("@/components/coach/ActiveCoachStrip", () => () => null, { virtual: true });
jest.mock("@/components/coach/CoachTimelinePanel", () => () => null, { virtual: true });
jest.mock("@/components/coach/CommentaryPanel", () => () => null, { virtual: true });
jest.mock("@/components/coach/PredictMovePanel", () => () => null, { virtual: true });
jest.mock("@/components/coach/RateMovePanel", () => () => null, { virtual: true });
jest.mock("@/components/coach/SessionReflectionCard", () => () => null, { virtual: true });
jest.mock("framer-motion", () => ({
  motion: new Proxy({}, { get: () => ({ children, ...props }) => <div {...props}>{children}</div> }),
}));
jest.mock("sonner", () => ({
  toast: { success: jest.fn(), error: jest.fn(), info: jest.fn() },
}));
jest.mock("@/hooks/useTeachingMode", () => jest.fn(), { virtual: true });
jest.mock("@/hooks/usePlayerData", () => jest.fn(), { virtual: true });
jest.mock("@/hooks/useGuardian", () => jest.fn(), { virtual: true });
jest.mock("@/hooks/useStockfishEval", () => jest.fn(), { virtual: true });
jest.mock("@/coachFlow", () => ({
  useCoachFlow: jest.fn(),
  INTERACTION_STATES: {},
  CLOCK_STATES: {},
}), { virtual: true });

const response = (body, options = {}) => ({
  ok: options.ok ?? true,
  status: options.status ?? 200,
  json: () => Promise.resolve(body),
});
const deferred = () => {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
};
const session = (sessionId) => ({
  session_id: sessionId,
  user_color: "white",
  user_rating: 1100,
  move_history: [],
  curriculum_active: false,
  teaching_opening: null,
});
const state = (sessionId, fen) => ({
  session: session(sessionId),
  current_fen: fen,
  is_player_turn: true,
  game_over: false,
  evaluation: { score: 0, mate_in: null },
});

const teachingState = () => ({
  teachingOffer: null, setTeachingOffer: jest.fn(),
  activeLesson: null, setActiveLesson: jest.fn(),
  lessonInstruction: null, setLessonInstruction: jest.fn(),
  lessonComplete: false, setLessonComplete: jest.fn(),
  isInTeachingMode: false, setIsInTeachingMode: jest.fn(),
  openingGuidance: null, setOpeningGuidance: jest.fn(),
  inlineOpening: null, setInlineOpening: jest.fn(),
  inlineTrap: null, setInlineTrap: jest.fn(),
  coachIntroMessage: null, setCoachIntroMessage: jest.fn(),
  curriculumFeedback: null, setCurriculumFeedback: jest.fn(),
  lastCoachMoveSan: null, setLastCoachMoveSan: jest.fn(),
  positionCoaching: null, setPositionCoaching: jest.fn(),
  openingCorrectionCount: 0, setOpeningCorrectionCount: jest.fn(),
  handleStartLesson: mockHandleStartLesson,
  handleSkipTeachingOffer: jest.fn(),
  handleExitLesson: jest.fn(),
  handleTeachingMove: jest.fn(),
  resetTeachingState: jest.fn(),
});

const playerState = () => ({
  pastGamesHistory: [], playerIdentityData: null,
  blundersThisGame: 0, setBlundersThisGame: jest.fn(), recentResults: [],
  showPreGameStreakPopup: false, setShowPreGameStreakPopup: jest.fn(),
  showPostGameStreakResult: false, setShowPostGameStreakResult: jest.fn(),
  postGameStreakResult: null, hasCastled: false, developedPieces: [],
  playerWeaknesses: [], showChecklist: false, setShowChecklist: jest.fn(),
  hideEvalBar: false, setHideEvalBar: jest.fn(),
  opportunitiesFound: [], setOpportunitiesFound: jest.fn(),
  opportunitiesMissed: [], setOpportunitiesMissed: jest.fn(),
  resetPlayerData: jest.fn(),
});

const guardianState = () => ({
  guardianIntervention: null, setGuardianIntervention: jest.fn(),
  pendingMove: null, remainingInterventions: 0, setRemainingInterventions: jest.fn(),
  evaluateMove: jest.fn(), cancelRiskyMove: jest.fn(),
  setIntervention: jest.fn(), clearIntervention: jest.fn(),
});

const flowState = () => ({
  setOpeningGuidance: jest.fn(), setTrapWarning: jest.fn(),
  handleUserMove: jest.fn(), isInHold: false, cancelPendingMove: jest.fn(), pendingMove: null,
  timeline: [], interactionState: "idle", activeStripCoaching: null,
  activeCoachingMoment: null, liveChecklist: [], playerWeaknessList: [],
  playerProfile: null, rootProblem: null, clockState: "idle",
  handleClockTap: jest.fn(() => Promise.resolve(false)), resetFlow: jest.fn(),
});

describe("CoachPlay lifecycle ownership", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    mockSearchParams = new URLSearchParams();
    mockHandleStartLesson.mockReset();
    useTeachingMode.mockReturnValue(teachingState());
    usePlayerData.mockReturnValue(playerState());
    useGuardian.mockReturnValue(guardianState());
    useStockfishEval.mockReturnValue({ ready: false, evalMove: jest.fn() });
    useCoachFlow.mockReturnValue(flowState());
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    delete global.fetch;
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  const flush = async () => {
    await act(async () => {
      for (let i = 0; i < 24; i += 1) await Promise.resolve();
    });
  };

  const fallback = (url) => {
    if (url.includes("/geometry?")) return Promise.resolve(response({ plans: [] }));
    return Promise.resolve(response({}));
  };

  test("mount resumes the server session and publishes its exact board", async () => {
    const fen = "8/8/8/8/8/8/4K3/6k1 w - - 0 1";
    global.fetch = jest.fn((url) => {
      if (url.endsWith("/coach/play/active")) {
        return Promise.resolve(response({ active_sessions: [{ session_id: "session-1" }] }));
      }
      if (url.endsWith("/coach/play/state/session-1")) {
        return Promise.resolve(response(state("session-1", fen)));
      }
      return fallback(url);
    });

    await act(async () => root.render(<CoachPlay user={{ user_id: "student-1" }} />));
    await flush();

    expect(container.querySelector("[data-testid='board-session']").textContent).toBe("session-1");
    expect(container.querySelector("[data-testid='board-fen']").textContent).toBe(fen);
  });

  test("a late message poll from the replaced session cannot enter the new game", async () => {
    jest.useFakeTimers();
    const oldMessages = deferred();
    const fen1 = "8/8/8/8/8/8/4K3/6k1 w - - 0 1";
    const fen2 = "8/8/8/8/8/8/3K4/6k1 w - - 0 1";
    global.fetch = jest.fn((url) => {
      if (url.endsWith("/coach/play/active")) {
        return Promise.resolve(response({ active_sessions: [{ session_id: "session-1" }] }));
      }
      if (url.endsWith("/coach/play/state/session-1")) {
        return Promise.resolve(response(state("session-1", fen1)));
      }
      if (url.endsWith("/coach/play/messages/session-1")) return oldMessages.promise;
      if (url.endsWith("/coaching/current-prescriptions")) {
        return Promise.resolve(response({ prescriptions: [] }));
      }
      if (url.endsWith("/coach/active-focus")) {
        return Promise.resolve(response({ personal_improvement_cycle: { eligible: false } }));
      }
      if (url.endsWith("/lab-coach-pick")) return Promise.resolve(response({}));
      if (url.endsWith("/coach/play/start")) {
        return Promise.resolve(response({
          session: session("session-2"),
          current_fen: fen2,
          is_player_turn: true,
          evaluation: { score: 0, mate_in: null },
        }));
      }
      if (url.endsWith("/coach/play/state/session-2")) {
        return Promise.resolve(response(state("session-2", fen2)));
      }
      return fallback(url);
    });

    await act(async () => root.render(<CoachPlay user={{ user_id: "student-1" }} />));
    await flush();
    act(() => jest.advanceTimersByTime(2001));
    await flush();
    expect(global.fetch.mock.calls.some(([url]) => url.endsWith("/coach/play/messages/session-1"))).toBe(true);

    act(() => container.querySelector("[data-testid='new-game']").click());
    await flush();
    await act(async () => container.querySelector("[data-testid='start-game']").click());
    await flush();
    expect(container.querySelector("[data-testid='board-session']").textContent).toBe("session-2");

    oldMessages.resolve(response({ messages: [{ content: "OLD SESSION MESSAGE" }] }));
    await flush();
    expect(container.querySelector("[data-testid='chat-messages']").textContent).not.toContain("OLD SESSION MESSAGE");
    expect(container.querySelector("[data-testid='sidebar-session']").textContent).toBe("session-2");
  });

  test("an in-flight staleness check cannot resurrect the replaced session", async () => {
    jest.useFakeTimers();
    const oldStalenessCheck = deferred();
    const fen1 = "8/8/8/8/8/8/4K3/6k1 w - - 0 1";
    const fen2 = "8/8/8/8/8/8/3K4/6k1 w - - 0 1";
    let sessionOneStateCalls = 0;
    global.fetch = jest.fn((url) => {
      if (url.endsWith("/coach/play/active")) {
        return Promise.resolve(response({ active_sessions: [{ session_id: "session-1" }] }));
      }
      if (url.endsWith("/coach/play/state/session-1")) {
        sessionOneStateCalls += 1;
        return sessionOneStateCalls === 1
          ? Promise.resolve(response(state("session-1", fen1)))
          : oldStalenessCheck.promise;
      }
      if (url.endsWith("/coach/play/messages/session-1")) {
        return Promise.resolve(response({ messages: [] }));
      }
      if (url.endsWith("/coaching/current-prescriptions")) {
        return Promise.resolve(response({ prescriptions: [] }));
      }
      if (url.endsWith("/coach/active-focus")) {
        return Promise.resolve(response({ personal_improvement_cycle: { eligible: false } }));
      }
      if (url.endsWith("/lab-coach-pick")) return Promise.resolve(response({}));
      if (url.endsWith("/coach/play/start")) {
        return Promise.resolve(response({
          session: session("session-2"), current_fen: fen2, is_player_turn: true,
        }));
      }
      if (url.endsWith("/coach/play/state/session-2")) {
        return Promise.resolve(response(state("session-2", fen2)));
      }
      return fallback(url);
    });

    await act(async () => root.render(<CoachPlay user={{ user_id: "student-1" }} />));
    await flush();
    act(() => jest.advanceTimersByTime(5001));
    await flush();
    expect(sessionOneStateCalls).toBe(2);

    act(() => container.querySelector("[data-testid='new-game']").click());
    await flush();
    await act(async () => container.querySelector("[data-testid='start-game']").click());
    await flush();
    expect(container.querySelector("[data-testid='board-session']").textContent).toBe("session-2");

    oldStalenessCheck.resolve(response({
      ...state("session-1", fen1),
      session: { ...session("session-1"), move_history: [{ san: "e4" }] },
    }));
    await flush();

    expect(sessionOneStateCalls).toBe(2);
    expect(container.querySelector("[data-testid='board-session']").textContent).toBe("session-2");
    expect(container.querySelector("[data-testid='board-fen']").textContent).toBe(fen2);
  });

  test("a trap deep link starts the requested lesson only for the committed session", async () => {
    mockSearchParams = new URLSearchParams("trap=legal_trap");
    const fen = "8/8/8/8/8/8/4K3/6k1 w - - 0 1";
    global.fetch = jest.fn((url) => {
      if (url.endsWith("/coach/play/active")) {
        return Promise.resolve(response({ active_sessions: [{ session_id: "ignored" }] }));
      }
      if (url.endsWith("/coaching/current-prescriptions")) {
        return Promise.resolve(response({ prescriptions: [] }));
      }
      if (url.endsWith("/coach/active-focus")) {
        return Promise.resolve(response({ personal_improvement_cycle: { eligible: false } }));
      }
      if (url.endsWith("/lab-coach-pick")) return Promise.resolve(response({}));
      if (url.endsWith("/coach/play/start")) {
        return Promise.resolve(response({
          session: session("trap-session"), current_fen: fen, is_player_turn: true,
        }));
      }
      if (url.endsWith("/coach/play/state/trap-session")) {
        return Promise.resolve(response(state("trap-session", fen)));
      }
      if (url.endsWith("/coach/play/teaching/start")) {
        return Promise.resolve(response({
          lesson_id: "legal_trap", teaching_fen: fen, instruction: "Find the idea",
        }));
      }
      return fallback(url);
    });

    await act(async () => root.render(<CoachPlay user={{ user_id: "student-1" }} />));
    await flush();

    const teachingCall = global.fetch.mock.calls.find(([url]) => url.endsWith("/coach/play/teaching/start"));
    expect(teachingCall).toBeTruthy();
    expect(JSON.parse(teachingCall[1].body)).toMatchObject({
      session_id: "trap-session",
      lesson_type: "trap",
      trap_key: "legal_trap",
    });
    expect(mockHandleStartLesson).toHaveBeenCalledTimes(1);
    expect(container.querySelector("[data-testid='board-session']").textContent).toBe("trap-session");
  });
});
