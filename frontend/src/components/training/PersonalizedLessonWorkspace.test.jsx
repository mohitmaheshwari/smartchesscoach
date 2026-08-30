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
    side_to_move: "White",
    move_number: 18,
    diagnosis_kind: "piece_in_danger",
    prompt: "One of your pieces can be taken. Find a move that saves it or answers the attack.",
    reason_prompt: "Which piece needs your attention first?",
    reason_choices: [
      { id: "piece_in_danger:d4", label: "My knight on d4 can be taken." },
      { id: "piece_in_danger:e4", label: "My pawn on e4 can be taken." },
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
          message: "Your knight on d4 is attacked by the bishop on a7.",
          highlight_squares: ["d4", "a7"],
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

  test("requires a reason, records requested help, and reports only proved state", async () => {
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
    expect(board.disabled).toBe(true);
    expect(container.textContent).toContain("This is the one idea in your current coaching plan");
    expect(container.textContent).toContain("White to move · before move 18 · from your game");
    expect(container.textContent).toContain("First identify the piece in danger");

    const showHelp = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent.includes("Show it on the board")
    );
    await act(async () => showHelp.click());
    await settle();
    expect(container.textContent).toContain("Your knight on d4 is attacked by the bishop on a7");

    const reason = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent.includes("My knight on d4 can be taken")
    );
    act(() => reason.click());
    expect(board.disabled).toBe(false);
    expect(container.textContent).toContain("Now make a move that saves the piece");

    await act(async () => board.click());
    await settle();

    const helpCall = global.fetch.mock.calls.find(([url]) => url.endsWith("/help"));
    const answerCall = global.fetch.mock.calls.find(([url]) => url.endsWith("/respond"));
    expect(JSON.parse(helpCall[1].body).action).toBe("show_on_board");
    expect(JSON.parse(answerCall[1].body).reason_choice).toBe("piece_in_danger:d4");
    expect(container.textContent).toContain("Can do alone");
    expect(container.textContent).toContain("I have not yet seen you use it in a game");
    expect(container.textContent).toContain("Remembered laterNot measured");
    expect(container.textContent).not.toContain("Reliable");
  });
});
