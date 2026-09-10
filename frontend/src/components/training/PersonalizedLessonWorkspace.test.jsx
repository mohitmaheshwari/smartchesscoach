import { act } from "react";
import { createRoot } from "react-dom/client";
import PersonalizedLessonWorkspace from "./PersonalizedLessonWorkspace";

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
    expect(container.textContent).toContain("Now I want to see whether the same thought appears");
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
    expect(container.textContent).toContain("You found the idea");
  });
});
