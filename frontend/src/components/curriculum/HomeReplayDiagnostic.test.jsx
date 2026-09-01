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
          reason_prompt: "What did you pay attention to before moving?",
          reason_choices: [
            { id: "keeps_piece_safe", label: "I checked what could be taken." },
            { id: "not_sure", label: "I am not sure yet." },
          ],
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
    expect(container.textContent).toContain("What did you pay attention to");
    expect(container.textContent).toContain("I checked what could be taken.");
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
        },
      },
    };
    act(() => root.render(
      <HomeReplayDiagnostic diagnostic={diagnostic} onNavigate={jest.fn()} />
    ));

    expect(container.textContent).toContain("not improvement in your games yet");
    expect(container.textContent).toContain("watching mode");
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
