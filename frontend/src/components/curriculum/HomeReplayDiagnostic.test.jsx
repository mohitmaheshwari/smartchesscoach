import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import HomeReplayDiagnostic from "./HomeReplayDiagnostic";

jest.mock("@/App", () => ({ API: "/api" }));
jest.mock("@/components/LichessBoard", () => {
  const ReactModule = require("react");
  return ReactModule.forwardRef(function FakeBoard({ onMove, interactive }, ref) {
    ReactModule.useImperativeHandle(ref, () => ({
      highlightSquares: jest.fn(),
      clearArrows: jest.fn(),
    }));
    return (
      <button
        type="button"
        data-testid="fake-board"
        disabled={!interactive}
        onClick={() => onMove?.({ from: "d1", to: "a1" })}
      >
        board
      </button>
    );
  });
});

const activeDiagnostic = {
  enabled: true,
  state: "active",
  session: {
    session_id: "s1",
    status: "active",
    current_index: 0,
    total_items: 2,
    awaiting_reason: false,
    current_item: {
      item_id: "diagnostic-position-1",
      fen: "3rk3/8/8/8/8/8/8/3QK3 w - - 0 1",
      orientation: "white",
      prompt: "What would you play here?",
      source_label: "A position from one of your games",
    },
  },
};

describe("HomeReplayDiagnostic", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    window.posthog = { capture: jest.fn() };
    global.fetch = jest.fn();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    delete window.posthog;
    delete global.fetch;
  });

  test("initial position hides lesson identity, reason options and answers", () => {
    act(() => root.render(
      <HomeReplayDiagnostic diagnostic={activeDiagnostic} onNavigate={jest.fn()} />
    ));

    expect(container.textContent).toContain("What would you play now?");
    expect(container.textContent).not.toContain("Piece safety");
    expect(container.textContent).not.toContain("keeps every piece safe");
    expect(container.textContent).not.toContain("It leaves my pieces protected");
    expect(container.textContent).not.toContain("best move");
  });

  test("move is submitted before reflection choices appear", async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        awaiting_reason: true,
        current_index: 0,
        current_item: {
          ...activeDiagnostic.session.current_item,
          move_san: "Qa1",
          reason_question: {
            question_id: "incoming-threat-1",
            prompt: "Which piece attacked your queen on d1?",
            choices: [
              { id: "a", label: "The rook on d8." },
              { id: "b", label: "No piece attacked it." },
            ],
            progress: { current: 1, total: 3 },
          },
        },
      }),
    });

    act(() => root.render(
      <HomeReplayDiagnostic diagnostic={activeDiagnostic} onNavigate={jest.fn()} />
    ));
    await act(async () => {
      container.querySelector('[data-testid="fake-board"]').click();
    });

    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(JSON.parse(global.fetch.mock.calls[0][1].body)).toMatchObject({
      session_id: "s1",
      move: "d1a1",
    });
    expect(container.textContent).toContain("Which piece attacked your queen on d1?");
    expect(container.textContent).toContain("Question 1 of 3");
    expect(container.textContent).toContain("The rook on d8.");
  });

  test("one reason answer opens only the next board question", async () => {
    global.fetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          awaiting_reason: true,
          current_index: 0,
          current_item: {
            ...activeDiagnostic.session.current_item,
            move_san: "Qa1",
            reason_question: {
              question_id: "threat-1",
              prompt: "What attacked your queen on d1?",
              choices: [{ id: "a", label: "The rook on d8." }],
              progress: { current: 1, total: 2 },
            },
          },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          awaiting_reason: true,
          current_index: 0,
          current_item: {
            ...activeDiagnostic.session.current_item,
            move_san: "Qa1",
            reason_question: {
              question_id: "destination-2",
              prompt: "Can Black win your queen on a1 immediately?",
              choices: [{ id: "b", label: "No, it is safe on a1." }],
              progress: { current: 2, total: 2 },
            },
          },
        }),
      });

    act(() => root.render(
      <HomeReplayDiagnostic diagnostic={activeDiagnostic} onNavigate={jest.fn()} />
    ));
    await act(async () => {
      container.querySelector('[data-testid="fake-board"]').click();
    });
    const firstChoice = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent.includes("The rook on d8.")
    );
    await act(async () => firstChoice.click());

    const body = JSON.parse(global.fetch.mock.calls[1][1].body);
    expect(body).toMatchObject({
      session_id: "s1",
      move: "d1a1",
      reason_choice: "a",
      reason_component_id: "threat-1",
    });
    expect(container.textContent).toContain("Can Black win your queen on a1 immediately?");
    expect(container.textContent).toContain("Question 2 of 2");
    expect(container.querySelector('[data-testid="fake-board"]').disabled).toBe(true);
  });

  test("connection summary is persisted before the transfer board opens", async () => {
    const diagnostic = {
      enabled: true,
      state: "connection",
      session: {
        session_id: "s1",
        awaiting_continue: true,
        position_summary: {
          eyebrow: "Connection understood",
          title: "You saw the whole connection.",
          move_san: "R3d2",
          demonstrated: [
            { kind: "incoming_threat", text: "The queen on c2 attacked both rooks." },
            { kind: "one_recapture_calculation", text: "After Qxd2, Rxd2 answers the capture." },
          ],
          missing: [],
          principle: "Before you move an attacked piece, check the square it lands on and calculate one reply.",
        },
      },
    };
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        session_id: "s1",
        current_index: 1,
        total_items: 2,
        awaiting_continue: false,
        awaiting_reason: false,
        current_item: activeDiagnostic.session.current_item,
      }),
    });

    act(() => root.render(
      <HomeReplayDiagnostic diagnostic={diagnostic} onNavigate={jest.fn()} />
    ));
    expect(container.textContent).toContain("You saw the whole connection.");
    expect(container.textContent).toContain("After Qxd2, Rxd2 answers the capture.");
    expect(container.textContent).toContain("calculate one reply");
    expect(container.querySelector('[data-testid="fake-board"]')).toBeNull();

    const continueButton = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent.includes("Try a different-looking position")
    );
    await act(async () => continueButton.click());
    expect(global.fetch.mock.calls[0][0]).toBe(
      "/api/training/personalized/diagnostic/continue"
    );
    expect(container.querySelector('[data-testid="fake-board"]')).not.toBeNull();
  });

  test("an unsupported move is reset without inventing a question", async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        measurement_status: "unmeasured",
        retry_move: true,
        awaiting_reason: false,
        message: "I cannot verify that explanation with this lesson yet. Try another move.",
        current_index: 0,
        current_item: activeDiagnostic.session.current_item,
      }),
    });
    act(() => root.render(
      <HomeReplayDiagnostic diagnostic={activeDiagnostic} onNavigate={jest.fn()} />
    ));
    await act(async () => {
      container.querySelector('[data-testid="fake-board"]').click();
    });

    expect(container.textContent).toContain("cannot verify that explanation");
    expect(container.textContent).not.toContain("Choose what you actually saw");
    expect(container.querySelector('[data-testid="fake-board"]').disabled).toBe(false);
  });

  test("result explicitly refuses to call two positions real-game improvement", () => {
    const diagnostic = {
      enabled: true,
      state: "result",
      session: {
        diagnostic_result: {
          conclusion: "controlled_transfer",
          real_game_evidence: "not_measured",
          separate_soundness_issue: false,
          component_outcomes: {
            incoming_threat: { asked: 2, demonstrated: 2 },
            destination_safety: { asked: 2, demonstrated: 1 },
          },
        },
      },
    };
    act(() => root.render(
      <HomeReplayDiagnostic diagnostic={diagnostic} onNavigate={jest.fn()} />
    ));

    expect(container.textContent).toContain("not improvement in your games yet");
    expect(container.textContent).toContain("watching mode");
    expect(container.textContent).toContain("Threat recognized");
    expect(container.textContent).toContain("Landing square checked");
  });

  test("a verified later miss replaces the watching copy without claiming clean-game success", () => {
    const diagnostic = {
      enabled: true,
      state: "later_miss",
      session: {
        diagnostic_result: {
          conclusion: "controlled_transfer",
          real_game_evidence: "missed",
          separate_soundness_issue: false,
        },
      },
    };
    act(() => root.render(
      <HomeReplayDiagnostic diagnostic={diagnostic} onNavigate={jest.fn()} />
    ));

    expect(container.textContent).toContain("It returned in a real game");
    expect(container.textContent).toContain("stronger evidence than a puzzle score");
    expect(container.textContent).not.toContain("you improved");
  });
});
