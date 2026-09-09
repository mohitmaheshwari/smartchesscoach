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
const mockEvaluateMove = jest.fn();
const mockHandleFlowUserMove = jest.fn();

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
  <div>
    <button
      data-testid="choose-checkpoint"
      onClick={() => {
        props.setGameMode("play");
        props.setEvidenceMode("checkpoint_unassisted");
      }}
    >
      Test this lesson
    </button>
    <button data-testid="start-game" onClick={props.actuallyStartGame}>Start game</button>
  </div>
), { virtual: true });
jest.mock("@/components/coach/CoachPlayBoard", () => {
  const ReactModule = require("react");
  return ReactModule.forwardRef((props, _ref) => (
    <div>
      <span data-testid="board-session">{props.session?.session_id || "none"}</span>
      <span data-testid="board-fen">{props.currentFen}</span>
      <button data-testid="make-e4" onClick={() => props.makeMove("e2", "e4", "wP")}>Play e4</button>
      <button data-testid="resign-game" onClick={props.resignGame}>Resign</button>
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
jest.mock("@/components/coach/SessionReflectionCard", () => ({ sessionId, reflection }) => (
  <div data-testid="reflection-card">{sessionId}:{reflection?.title || "reflection"}</div>
), { virtual: true });
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
  evaluateMove: mockEvaluateMove, cancelRiskyMove: jest.fn(),
  setIntervention: jest.fn(), clearIntervention: jest.fn(),
});

const flowState = () => ({
  setOpeningGuidance: jest.fn(), setTrapWarning: jest.fn(),
  handleUserMove: mockHandleFlowUserMove, isInHold: false, cancelPendingMove: jest.fn(), pendingMove: null,
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
    mockEvaluateMove.mockReset();
    mockHandleFlowUserMove.mockReset();
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
    const startCall = global.fetch.mock.calls.find(
      ([url]) => url.endsWith("/coach/play/start")
    );
    expect(JSON.parse(startCall[1].body)).toMatchObject({
      game_mode: "coach",
      evidence_mode: "practice_assisted",
    });

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

  test("manual start wins over a late active-session discovery", async () => {
    const activeDiscovery = deferred();
    const newFen = "8/8/8/8/8/8/3K4/6k1 w - - 0 1";
    global.fetch = jest.fn((url) => {
      if (url.endsWith("/coach/play/active")) return activeDiscovery.promise;
      if (url.endsWith("/coaching/current-prescriptions")) {
        return Promise.resolve(response({ prescriptions: [] }));
      }
      if (url.endsWith("/coach/active-focus")) {
        return Promise.resolve(response({ personal_improvement_cycle: { eligible: false } }));
      }
      if (url.endsWith("/lab-coach-pick")) return Promise.resolve(response({}));
      if (url.endsWith("/coach/play/start")) {
        return Promise.resolve(response({
          session: session("session-new"), current_fen: newFen, is_player_turn: true,
        }));
      }
      if (url.endsWith("/coach/play/state/session-new")) {
        return Promise.resolve(response(state("session-new", newFen)));
      }
      if (url.endsWith("/coach/play/state/session-old")) {
        throw new Error("late discovery must not resume the old session");
      }
      return fallback(url);
    });

    await act(async () => root.render(<CoachPlay user={{ user_id: "student-1" }} />));
    await act(async () => container.querySelector("[data-testid='start-game']").click());
    await flush();
    expect(container.querySelector("[data-testid='board-session']").textContent).toBe("session-new");

    activeDiscovery.resolve(response({ active_sessions: [{ session_id: "session-old" }] }));
    await flush();

    expect(container.querySelector("[data-testid='board-session']").textContent).toBe("session-new");
    expect(global.fetch.mock.calls.some(([url]) => url.endsWith("/coach/play/state/session-old"))).toBe(false);
  });

  test("an unassisted checkpoint starts pure play and bypasses every coaching hold", async () => {
    const startFen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
    const afterE4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1";
    global.fetch = jest.fn((url) => {
      if (url.endsWith("/coach/play/active")) {
        return Promise.resolve(response({ active_sessions: [] }));
      }
      if (url.endsWith("/coaching/current-prescriptions")) {
        return Promise.resolve(response({ prescriptions: [] }));
      }
      if (url.endsWith("/coach/active-focus")) {
        return Promise.resolve(response({
          coaching_context: {
            primary_focus: {
              topic_key: "piece_safety",
              detector_quality_id: "gap:piece_safety:destination_safety_exact",
              focus_id: "focus-1",
              instruction_id: "instruction-1",
            },
          },
        }));
      }
      if (url.endsWith("/coach/play/start")) {
        return Promise.resolve(response({
          session: {
            ...session("checkpoint-session"),
            game_mode: "play",
            evidence_mode: "checkpoint_unassisted",
          },
          current_fen: startFen,
          is_player_turn: true,
        }));
      }
      if (url.endsWith("/coach/play/move")) {
        return Promise.resolve(response({
          current_fen: afterE4,
          awaiting_coach: false,
          game_over: false,
        }));
      }
      return fallback(url);
    });

    await act(async () => root.render(<CoachPlay user={{ user_id: "student-1" }} />));
    await flush();
    act(() => container.querySelector("[data-testid='choose-checkpoint']").click());
    await act(async () => container.querySelector("[data-testid='start-game']").click());
    await flush();

    const startCall = global.fetch.mock.calls.find(
      ([url]) => url.endsWith("/coach/play/start")
    );
    expect(JSON.parse(startCall[1].body)).toMatchObject({
      game_mode: "play",
      evidence_mode: "checkpoint_unassisted",
    });

    act(() => container.querySelector("[data-testid='make-e4']").click());
    await flush();

    expect(mockEvaluateMove).not.toHaveBeenCalled();
    expect(mockHandleFlowUserMove).not.toHaveBeenCalled();
    expect(global.fetch.mock.calls.some(
      ([url]) => url.endsWith("/coach/play/move")
    )).toBe(true);
  });

  test("a checkpoint downgraded by the server is explained to the player", async () => {
    const startFen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
    global.fetch = jest.fn((url) => {
      if (url.endsWith("/coach/play/active")) {
        return Promise.resolve(response({ active_sessions: [] }));
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
          session: {
            ...session("ordinary-session"),
            game_mode: "play",
            evidence_mode: "just_play",
          },
          current_fen: startFen,
          is_player_turn: true,
        }));
      }
      return fallback(url);
    });

    await act(async () => root.render(<CoachPlay user={{ user_id: "student-1" }} />));
    await flush();
    act(() => container.querySelector("[data-testid='choose-checkpoint']").click());
    await act(async () => container.querySelector("[data-testid='start-game']").click());
    await flush();

    expect(jest.requireMock("sonner").toast.info).toHaveBeenCalledWith(
      "I don’t have a lesson ready to test yet, so I started a regular game instead."
    );
  });

  test("a late coach response cannot overwrite a replacement session", async () => {
    const oldCoachPoll = deferred();
    const startFen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
    const newFen = "8/8/8/8/8/8/3K4/6k1 w - - 0 1";
    let oldStateCalls = 0;
    const currentFlow = flowState();
    currentFlow.handleUserMove = jest.fn(async (moveData, commit, timeSpent) => ({
      autoCommitted: await commit(moveData.san, timeSpent),
    }));
    useCoachFlow.mockReturnValue(currentFlow);
    global.fetch = jest.fn((url) => {
      if (url.endsWith("/coach/play/active")) {
        return Promise.resolve(response({ active_sessions: [{ session_id: "session-old" }] }));
      }
      if (url.endsWith("/coach/play/state/session-old")) {
        oldStateCalls += 1;
        return oldStateCalls === 1
          ? Promise.resolve(response(state("session-old", startFen)))
          : oldCoachPoll.promise;
      }
      if (url.endsWith("/coach/play/move")) {
        return Promise.resolve(response({ current_fen: startFen, awaiting_coach: true }));
      }
      if (url.endsWith("/coaching/current-prescriptions")) return Promise.resolve(response({ prescriptions: [] }));
      if (url.endsWith("/coach/active-focus")) {
        return Promise.resolve(response({ personal_improvement_cycle: { eligible: false } }));
      }
      if (url.endsWith("/lab-coach-pick")) return Promise.resolve(response({}));
      if (url.endsWith("/coach/play/start")) {
        return Promise.resolve(response({ session: session("session-new"), current_fen: newFen, is_player_turn: true }));
      }
      if (url.endsWith("/coach/play/state/session-new")) return Promise.resolve(response(state("session-new", newFen)));
      return fallback(url);
    });

    await act(async () => root.render(<CoachPlay user={{ user_id: "student-1" }} />));
    await flush();
    act(() => container.querySelector("[data-testid='make-e4']").click());
    await flush();
    expect(oldStateCalls).toBe(2);

    act(() => container.querySelector("[data-testid='new-game']").click());
    await flush();
    await act(async () => container.querySelector("[data-testid='start-game']").click());
    await flush();

    oldCoachPoll.resolve(response({
      ...state("session-old", startFen),
      session: { ...session("session-old"), coach_move_pending: false },
    }));
    await flush();

    expect(container.querySelector("[data-testid='board-session']").textContent).toBe("session-new");
    expect(container.querySelector("[data-testid='board-fen']").textContent).toBe(newFen);
  });

  test("new game removes the completed session reflection", async () => {
    const fen = "8/8/8/8/8/8/4K3/6k1 w - - 0 1";
    global.fetch = jest.fn((url) => {
      if (url.endsWith("/coach/play/active")) {
        return Promise.resolve(response({ active_sessions: [{ session_id: "session-1" }] }));
      }
      if (url.endsWith("/coach/play/state/session-1")) return Promise.resolve(response(state("session-1", fen)));
      if (url.endsWith("/coach/play/end")) {
        return Promise.resolve(response({ summary: {}, cpr: {}, identity: {} }));
      }
      if (url.endsWith("/coach/play/session-reflection/session-1")) {
        return Promise.resolve(response({ reflection: { title: "Old lesson" } }));
      }
      if (url.endsWith("/coach/play/improvement-proof")) return Promise.resolve(response({ show_proof: false }));
      return fallback(url);
    });

    await act(async () => root.render(<CoachPlay user={{ user_id: "student-1" }} />));
    await flush();
    act(() => container.querySelector("[data-testid='resign-game']").click());
    await flush();
    expect(container.querySelector("[data-testid='reflection-card']")?.textContent).toContain("Old lesson");

    act(() => container.querySelector("[data-testid='new-game']").click());
    await flush();
    expect(container.querySelector("[data-testid='reflection-card']")).toBeNull();
  });
});
