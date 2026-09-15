import React, { act } from "react";
import { createRoot } from "react-dom/client";

import UnifiedCoachPanel from "./UnifiedCoachPanel";
const mockNavigate = jest.fn();
const mockInvalidate = jest.fn();
jest.mock("@/lib/personalCurriculum", () => ({ invalidatePersonalCurriculum: () => mockInvalidate() }));

jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}), { virtual: true });
jest.mock("@/components/ui/button", () => ({
  Button: ({ children, ...props }) => <button {...props}>{children}</button>,
}), { virtual: true });
jest.mock("lucide-react", () => new Proxy({}, {
  get: () => (props) => <span {...props} />,
}));


describe("UnifiedCoachPanel", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    mockNavigate.mockReset();
    mockInvalidate.mockReset();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  const renderPanel = (overrides = {}) => {
    const props = {
      gameMode: "coach",
      coachingContext: {
        primary_focus: {
          label: "Piece safety",
          instruction_text: "Before moving, check what can take your piece.",
        },
      },
      activeMoment: null,
      stripMoment: null,
      pendingMove: null,
      isPlayerTurn: true,
      isCoachThinking: false,
      gameOver: false,
      gameResult: null,
      summary: null,
      canExplainLastMove: true,
      helpAnswer: null,
      helpLoading: false,
      onAskCoach: jest.fn(),
      onDismissHelp: jest.fn(),
      onTryAnother: jest.fn(),
      onPlayAnyway: jest.fn(),
      onNewGame: jest.fn(),
      ...overrides,
    };
    act(() => root.render(<UnifiedCoachPanel {...props} />));
    return props;
  };

  test("a critical moment has two immediate, explicit exits", () => {
    const props = renderPanel({
      activeMoment: {
        text: "Qh5 leaves your queen open to Nxh5.",
        instruction: "Check every reply before you commit.",
      },
      pendingMove: { san: "Qh5" },
    });

    act(() => {
      container.querySelector('[data-testid="unified-try-another"]').click();
      container.querySelector('[data-testid="unified-play-anyway"]').click();
    });

    expect(props.onTryAnother).toHaveBeenCalledTimes(1);
    expect(props.onPlayAnyway).toHaveBeenCalledTimes(1);
    expect(container.textContent).not.toMatch(/tap clock/i);
  });

  test("play mode stays explicitly silent even if a moment is supplied", () => {
    renderPanel({
      gameMode: "play",
      activeMoment: { text: "This must not leak." },
      pendingMove: { san: "Qh5" },
    });

    expect(container.textContent).toContain("Your game. No hints.");
    expect(container.textContent).not.toContain("This must not leak.");
    expect(
      container.querySelector('[data-testid="unified-play-anyway"]')
    ).toBeNull();
  });

  test("a postgame practice label without a destination cannot secretly start a game", () => {
    const props = renderPanel({
      gameOver: true,
      gameResult: "loss",
      summary: {
        has_data: true,
        pattern_verdict: {
          message: "You protected your pieces more often, but missed one late check.",
          detail: "Keep the same scan for the full game.",
          cta_label: "Practise this check",
        },
      },
    });

    expect(container.textContent).toMatch(/protected your pieces/i);
    const buttons = container.querySelectorAll("button");
    expect(buttons).toHaveLength(1);
    expect(buttons[0].textContent).toBe("Play another game");
    act(() => buttons[0].click());
    expect(props.onNewGame).toHaveBeenCalledTimes(1);
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  test("postgame prefers the unified focus story and canonical next action", () => {
    const props = renderPanel({
      gameOver: true,
      summary: {
        has_data: true,
        coach_summary: "Legacy summary that should not win.",
        unified_summary: {
          focus_label: "Piece safety",
          story: "Your piece safety work showed up in 1 verified moment today.",
          detail: "Moving the bishop leaves your knight on e5 undefended.",
          next_action: {
            label: "Practise this check",
            href: "/training/pattern/piece_safety",
          },
        },
      },
    });

    expect(container.textContent).toContain("Today’s work: Piece safety");
    expect(container.textContent).toContain("1 verified moment");
    expect(container.textContent).not.toContain("Legacy summary");
    expect(container.querySelectorAll("button")).toHaveLength(1);
    act(() => container.querySelector('button').click());
    expect(mockNavigate).toHaveBeenCalledWith('/training/pattern/piece_safety');
    expect(props.onNewGame).not.toHaveBeenCalled();
  });

  test("a partial unified action never lends its label to another destination", () => {
    renderPanel({ gameOver: true, summary: {
      unified_summary: { next_action: { label: 'Learn an endgame' } },
      pattern_verdict: { cta_label: 'Review this game', cta_href: '/game/example' },
    } });
    expect(container.querySelector('button').textContent).toBe('Review this game');
    act(() => container.querySelector('button').click());
    expect(mockNavigate).toHaveBeenCalledWith('/game/example');
  });

  test("game end and arriving summary each invalidate the old coaching plan", () => {
    renderPanel();
    expect(mockInvalidate).not.toHaveBeenCalled();
    renderPanel({ gameOver: true });
    expect(mockInvalidate).toHaveBeenCalledTimes(1);
    renderPanel({ gameOver: true, summary: { has_data: true } });
    expect(mockInvalidate).toHaveBeenCalledTimes(2);
  });

  test("ask coach opens two bounded no-typing actions", () => {
    const props = renderPanel();

    act(() => container.querySelector('[data-testid="unified-ask-coach"]').click());
    const actions = container.querySelector('[data-testid="unified-help-actions"]');
    expect(actions.textContent).toContain("Explain their move");
    expect(actions.textContent).toContain("Remind me what to check");
    expect(actions.querySelectorAll("button").length).toBeLessThanOrEqual(3);

    act(() => actions.querySelector("button").click());
    expect(props.onAskCoach).toHaveBeenCalledWith("explain_last_move");
  });

  test("a help answer owns the panel without stacking an idle prompt", () => {
    const props = renderPanel({
      helpAnswer: {
        answer: "Their rook moved to e8 and now protects the pawn on e6.",
      },
    });

    expect(container.textContent).toContain("Coach’s answer");
    expect(container.textContent).toContain("Their rook moved to e8");
    expect(container.textContent).not.toContain("Your turn. Take your time.");
    act(() => Array.from(container.querySelectorAll("button"))
      .find((button) => button.textContent === "Got it").click());
    expect(props.onDismissHelp).toHaveBeenCalledTimes(1);
  });
});
