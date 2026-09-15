import { act } from "react";
import { createRoot } from "react-dom/client";
import PersonalizedLessonWorkspace from "./PersonalizedLessonWorkspace";
import { loadPersonalCurriculum, resetPersonalCurriculumRequestsForTests } from "../../lib/personalCurriculum";

const mockNavigate = jest.fn();

jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}), { virtual: true });
jest.mock("../../App", () => ({ API: "https://api.test/api" }));
jest.mock("../LichessBoard", () => {
  const React = require("react");
  return React.forwardRef(({ onMove, interactive }, ref) => {
    React.useImperativeHandle(ref, () => ({
      highlightSquares: jest.fn(),
      clearArrows: jest.fn(),
    }));
    return (
      <button
        type="button"
        data-testid="lesson-board"
        disabled={!interactive}
        onClick={() => onMove({ from: "e2", to: "f3" })}
      >
        Lesson board
      </button>
    );
  });
});

const response = (body, ok = true) => Promise.resolve({
  ok,
  json: () => Promise.resolve(body),
});

const session = {
  session_id: "session-1",
  status: "active",
  current_index: 0,
  total_items: 1,
  stage: "transfer",
  lesson: {
    kind: "concept",
    id: "piece_safety",
    title: "Piece safety",
    rule: "Before you move, check what the opponent can take.",
  },
  teaching_profile: {
    why_now: "This is the one idea in your current coaching plan.",
    anchors: [],
  },
  learner_state: { state: "learning" },
  current_item: {
    item_id: "p1",
    fen: "8/8/8/8/8/8/4K3/7k w - - 0 1",
    orientation: "white",
    stage: "transfer",
    source: "own_game",
    prompt: "Which move keeps every piece safe?",
    reason_prompt: "What did you check before choosing the move?",
    reason_choices: [
      { id: "keeps_piece_safe", label: "My pieces stay safe." },
      { id: "looks_active", label: "It only looks active." },
    ],
  },
};

describe("PersonalizedLessonWorkspace", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    mockNavigate.mockReset();
    resetPersonalCurriculumRequestsForTests();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    global.fetch = jest.fn((url) => {
      if (url.endsWith("/start")) return response(session);
      if (url.endsWith("/help")) {
        return response({
          action: "show_on_board",
          message: "Look at the marked piece before choosing a move.",
          highlight_squares: ["e2"],
        });
      }
      if (url.endsWith("/respond")) {
        return response({
          correct: true,
          feedback: "Good scan.",
          earned_state: "can_do_alone",
          highest_earned_state: "can_do_alone",
          complete: true,
          current_index: 1,
          total_items: 1,
          next_item: null,
        });
      }
      if (url.includes("/evidence")) return response({ evidence: [] });
      return response({});
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    delete global.fetch;
  });

  const settle = async () => {
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });
  };

  const finishLesson = async () => {
    await act(async () => root.render(<PersonalizedLessonWorkspace contentKind="concept" contentId="piece_safety" />));
    await settle();
    await act(async () => container.querySelector('[data-testid="lesson-board"]').click());
    await settle();
    const reason = [...container.querySelectorAll('button')].find(b => b.textContent.includes('My pieces stay safe'));
    await act(async () => reason.click());
    await settle();
  };

  test("refreshes a stale plan after completion and follows the coach's exact destination", async () => {
    const originalFetch = global.fetch;
    let planRequests = 0;
    global.fetch = jest.fn((url, options) => {
      if (url.includes('/personal-curriculum')) {
        planRequests += 1;
        return response({ enabled: true, decision: { decision_id: 'after-practice', primary: {
          title: planRequests === 1 ? 'Old lesson' : 'Try the idea in a game',
          outcome: 'apply', state: 'can_do_alone', reason: 'Try it without a hint.',
          destination: { href: '/play-with-coach?evidence_mode=checkpoint' },
        } } });
      }
      return originalFetch(url, options);
    });
    await loadPersonalCurriculum('https://api.test/api', undefined, 'training');
    await finishLesson();
    expect(planRequests).toBe(2);
    expect(container.textContent).not.toContain('Old lesson');
    expect(container.textContent).toContain('Try the idea in a game');
    expect(container.querySelector('[data-testid="lesson-final-feedback"]').textContent).toContain("That's the move.");
    const next = [...container.querySelectorAll('button')].find(b => b.textContent.includes('Play a focus game'));
    await act(async () => next.click());
    expect(mockNavigate).toHaveBeenCalledWith('/play-with-coach?evidence_mode=checkpoint');
  });

  test("retains a negative final verdict and retries a failed next-plan request", async () => {
    const originalFetch = global.fetch;
    let planRequests = 0;
    global.fetch = jest.fn((url, options) => {
      if (url.endsWith('/respond')) return response({ correct: false, complete: true,
        feedback: 'That move did not solve this position.', highest_earned_state: 'learning', next_item: null });
      if (url.includes('/personal-curriculum')) {
        planRequests += 1;
        return planRequests === 1 ? response({}, false) : response({ enabled: false });
      }
      return originalFetch(url, options);
    });
    await finishLesson();
    expect(container.textContent).toContain('Not this one.');
    expect(container.textContent).toContain('That move did not solve this position.');
    expect(container.textContent).not.toContain('You found the idea');
    expect(container.querySelector('[role="alert"]').textContent).toContain("couldn't load your next step");
    await act(async () => [...container.querySelectorAll('button')].find(b => b.textContent === 'Try again').click());
    await settle();
    expect(planRequests).toBe(2);
    expect(container.querySelector('[role="alert"]')).toBeNull();
    expect(container.querySelector('[data-testid="curriculum-primary-training"]')).toBeNull();
    expect(global.fetch.mock.calls.filter(([url]) => url.endsWith('/respond'))).toHaveLength(1);
  });

  test.each(['http', 'network'])("a %s pause failure keeps the student in the lesson; retry saves before leaving", async (failure) => {
    const originalFetch = global.fetch;
    let attempts = 0;
    global.fetch = jest.fn((url, options) => {
      if (url.endsWith('/pause')) {
        attempts += 1;
        if (attempts === 1) return failure === 'http' ? response({}, false) : Promise.reject(new Error('offline'));
        return response({});
      }
      return originalFetch(url, options);
    });
    await act(async () => root.render(<PersonalizedLessonWorkspace contentKind="concept" contentId="piece_safety" />));
    await settle();
    const pause = [...container.querySelectorAll('button')].find(b => b.textContent.includes('Continue later'));
    await act(async () => pause.click());
    await settle();
    expect(mockNavigate).not.toHaveBeenCalled();
    expect(container.querySelector('[role="alert"]').textContent).toContain("couldn't save your place");
    expect(container.querySelector('[data-testid="lesson-board"]').disabled).toBe(false);
    await act(async () => pause.click());
    await settle();
    expect(mockNavigate).toHaveBeenCalledTimes(1);
    expect(mockNavigate).toHaveBeenCalledWith('/learn');
  });

  test("changing lessons clears the completed lesson while the new session loads", async () => {
    await finishLesson();
    expect(container.querySelector('[data-testid="lesson-complete"]')).toBeTruthy();
    let resolveStart;
    global.fetch.mockImplementation(() => new Promise(resolve => { resolveStart = resolve; }));
    await act(async () => root.render(<PersonalizedLessonWorkspace contentKind="endgame" contentId="new-lesson" />));
    expect(container.querySelector('[data-testid="lesson-complete"]')).toBeNull();
    expect(container.textContent).not.toContain('Good scan.');
    await act(async () => resolveStart({ ok: true, json: async () => ({ ...session, session_id: 'new-session' }) }));
    await settle();
    expect(container.querySelector('[data-testid="lesson-board"]')).toBeTruthy();
  });

  test("accepts the move first, then asks for a reason and reports only proved state", async () => {
    await act(async () => {
      root.render(
        <PersonalizedLessonWorkspace
          contentKind="concept"
          contentId="piece_safety"
        />
      );
    });
    await settle();

    const board = container.querySelector('[data-testid="lesson-board"]');
    expect(board.disabled).toBe(false);
    expect(container.textContent).toContain("This is the one idea in your current coaching plan");
    expect(container.textContent).toContain("Make your move first");
    expect(container.textContent).not.toContain("My pieces stay safe");

    const showHelp = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent.includes("Show it on the board")
    );
    await act(async () => showHelp.click());
    await settle();

    await act(async () => board.click());
    await settle();
    expect(board.disabled).toBe(true);
    expect(container.textContent).toContain("My pieces stay safe");
    expect(global.fetch.mock.calls.filter(([url]) => url.endsWith("/respond"))).toHaveLength(0);

    const changeMove = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent.includes("Choose a different move")
    );
    await act(async () => changeMove.click());
    await settle();
    const resetBoard = container.querySelector('[data-testid="lesson-board"]');
    expect(resetBoard.disabled).toBe(false);
    expect(container.textContent).not.toContain("My pieces stay safe");
    await act(async () => resetBoard.click());
    await settle();

    const reason = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent.includes("My pieces stay safe")
    );
    await act(async () => reason.click());
    await settle();

    const helpCall = global.fetch.mock.calls.find(([url]) => url.endsWith("/help"));
    const answerCall = global.fetch.mock.calls.find(([url]) => url.endsWith("/respond"));
    expect(JSON.parse(helpCall[1].body).action).toBe("show_on_board");
    expect(JSON.parse(answerCall[1].body).reason_choice).toBe("keeps_piece_safe");
    expect(container.textContent).toContain("Can do alone");
    expect(container.textContent).toContain("Your later games will show whether you use the idea on your own");
    expect(container.textContent).toContain("Good scan.");
    expect(container.textContent).not.toContain("Not measured");
    expect(container.textContent).not.toContain("Reliable");
  });

  test("asks exact position questions after the move and keeps the move staged", async () => {
    const dynamicSession = {
      ...session,
      current_item: {
        ...session.current_item,
        position_relative_reasoning: true,
        reason_prompt: undefined,
        reason_choices: undefined,
      },
    };
    let respondCount = 0;
    global.fetch.mockImplementation((url, options) => {
      if (url.endsWith("/start")) return response(dynamicSession);
      if (url.endsWith("/respond")) {
        respondCount += 1;
        if (respondCount === 1) {
          return response({
            awaiting_reason: true,
            current_item: {
              ...dynamicSession.current_item,
              move_san: "Kf3",
              reason_question: {
                question_id: "destination-safety",
                prompt: "After Kf3, can Black take your king there?",
                choices: [
                  { id: "no", label: "No, the square is safe." },
                  { id: "yes", label: "Yes, Black can take it." },
                ],
                progress: { current: 1, total: 2 },
              },
            },
          });
        }
        if (respondCount === 2) {
          return response({
            awaiting_reason: true,
            component_result: { feedback: "Correct. The landing square is safe." },
            current_item: {
              ...dynamicSession.current_item,
              move_san: "Kf3",
              reason_question: {
                question_id: "one-reply",
                prompt: "What can Black try next?",
                choices: [
                  { id: "wait", label: "Black has no immediate capture." },
                  { id: "capture", label: "Black wins the king." },
                ],
                progress: { current: 2, total: 2 },
              },
            },
          });
        }
        return response({
          correct: true,
          feedback: "You checked the whole position.",
          earned_state: "can_do_alone",
          highest_earned_state: "can_do_alone",
          reasoning_consistent: true,
          complete: true,
          current_index: 1,
          total_items: 1,
          next_item: null,
        });
      }
      if (url.includes("/evidence")) return response({ evidence: [] });
      return response({});
    });

    await act(async () => root.render(
      <PersonalizedLessonWorkspace contentKind="concept" contentId="piece_safety" />
    ));
    await settle();
    expect(container.textContent).not.toContain("My pieces stay safe");

    const board = container.querySelector('[data-testid="lesson-board"]');
    await act(async () => board.click());
    await settle();
    expect(board.disabled).toBe(true);
    expect(container.textContent).toContain(
      "After Kf3, can Black take your king there?"
    );
    expect(container.textContent).not.toContain("What did you check before choosing");
    const stageRequest = JSON.parse(
      global.fetch.mock.calls.find(([url]) => url.endsWith("/respond"))[1].body
    );
    expect(stageRequest.move).toBe("e2f3");
    expect(stageRequest.reason_choice).toBeUndefined();

    const firstReason = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent.includes("No, the square is safe")
    );
    await act(async () => firstReason.click());
    await settle();
    expect(container.textContent).toContain("What can Black try next?");
    expect(container.textContent).toContain("Correct. The landing square is safe.");
    expect(container.querySelector('[data-testid="lesson-board"]').disabled).toBe(true);

    const secondReason = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent.includes("Black has no immediate capture")
    );
    await act(async () => secondReason.click());
    await settle();

    const answerRequests = global.fetch.mock.calls
      .filter(([url]) => url.endsWith("/respond"))
      .map(([, options]) => JSON.parse(options.body));
    expect(answerRequests[1]).toMatchObject({
      move: "e2f3",
      reason_choice: "no",
      reason_component_id: "destination-safety",
    });
    expect(answerRequests[2]).toMatchObject({
      move: "e2f3",
      reason_choice: "wait",
      reason_component_id: "one-reply",
    });
    expect(container.textContent).toContain("This practice is complete");
  });

  test("asks the server-authored endgame question for the move just played", async () => {
    const endgameSession = {
      ...session,
      lesson: {
        kind: "endgame",
        id: "king_and_pawn/key_squares",
        title: "The Squares Your King Needs",
        rule: "Move your King toward the pawn.",
      },
      current_item: {
        ...session.current_item,
        server_staged_reasoning: true,
        position_idea: "Your King is aiming for a4, b4, or c4.",
        reason_prompt: undefined,
        reason_choices: undefined,
      },
    };
    let respondCount = 0;
    global.fetch.mockImplementation((url) => {
      if (url.endsWith("/start")) return response(endgameSession);
      if (url.endsWith("/respond")) {
        respondCount += 1;
        if (respondCount === 1) {
          return response({
            awaiting_reason: true,
            current_item: {
              ...endgameSession.current_item,
              move_san: "Kc3",
              reason_question: {
                question_id: "endgame:0:c2c3:idea",
                prompt: "What is Kc3 preparing?",
                choices: [
                  { id: "reach_c4", label: "Reach c4, then let the b-pawn follow." },
                  { id: "pawn_leads", label: "Push the pawn first." },
                  { id: "not_sure", label: "I am not sure yet." },
                ],
                progress: { current: 1, total: 1 },
              },
            },
          });
        }
        return response({
          correct: true,
          feedback: "Good. Kc3 prepares c4.",
          reason_components: [{
            correct: true,
            feedback: "Exactly. Kc3 prepares c4.",
          }],
          reasoning_consistent: true,
          earned_state: "can_do_with_help",
          highest_earned_state: "can_do_with_help",
          complete: true,
          current_index: 1,
          total_items: 1,
          next_item: null,
        });
      }
      if (url.includes("/evidence")) return response({ evidence: [] });
      return response({});
    });

    await act(async () => root.render(
      <PersonalizedLessonWorkspace
        contentKind="endgame"
        contentId="king_and_pawn/key_squares"
      />
    ));
    await settle();
    expect(container.textContent).toContain(
      "Your King is aiming for a4, b4, or c4."
    );
    expect(container.textContent).not.toContain("It uses the rule for this ending");

    const board = container.querySelector('[data-testid="lesson-board"]');
    await act(async () => board.click());
    await settle();
    expect(container.textContent).toContain("What is Kc3 preparing?");
    expect(container.textContent).toContain(
      "Reach c4, then let the b-pawn follow."
    );

    const reason = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent.includes("Reach c4")
    );
    await act(async () => reason.click());
    await settle();

    const requests = global.fetch.mock.calls
      .filter(([url]) => url.endsWith("/respond"))
      .map(([, options]) => JSON.parse(options.body));
    expect(requests[0].reason_choice).toBeUndefined();
    expect(requests[1]).toMatchObject({
      reason_choice: "reach_c4",
      reason_component_id: "endgame:0:c2c3:idea",
    });
    expect(container.textContent).toContain("This practice is complete");
  });

  test("an off-lesson endgame move is graded immediately without empty choices", async () => {
    const endgameSession = {
      ...session,
      lesson: {
        kind: "endgame",
        id: "king_and_pawn/key_squares",
        title: "The Squares Your King Needs",
        rule: "Move your King toward the pawn.",
      },
      current_item: {
        ...session.current_item,
        server_staged_reasoning: true,
        position_idea: "Your King is aiming for a4, b4, or c4.",
        reason_prompt: undefined,
        reason_choices: undefined,
      },
    };
    global.fetch.mockImplementation((url) => {
      if (url.endsWith("/start")) return response(endgameSession);
      if (url.endsWith("/respond")) {
        return response({
          correct: false,
          feedback: "That move can still win, but it does not practise today's idea.",
          highest_earned_state: "learning",
          complete: false,
          current_index: 0,
          total_items: 1,
          next_item: endgameSession.current_item,
          next_stage: "contrast",
        });
      }
      if (url.includes("/evidence")) return response({ evidence: [] });
      return response({});
    });

    await act(async () => root.render(
      <PersonalizedLessonWorkspace
        contentKind="endgame"
        contentId="king_and_pawn/key_squares"
      />
    ));
    await settle();
    const board = container.querySelector('[data-testid="lesson-board"]');
    await act(async () => board.click());
    await settle();

    expect(container.textContent).toContain("That move can still win");
    expect(container.textContent).not.toContain("Pick the thought closest");
    expect(container.querySelector('[data-testid="lesson-board"]').disabled).toBe(false);
  });
});
