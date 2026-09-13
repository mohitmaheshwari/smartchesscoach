import React, { act } from "react";
import { createRoot } from "react-dom/client";

import UnifiedCoachPanel from "./UnifiedCoachPanel";

jest.mock("react-router-dom", () => ({
  useNavigate: () => jest.fn(),
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

  test("postgame shows one story and one next action", () => {
    renderPanel({
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
    expect(buttons[0].textContent).toContain("Practise this check");
  });
});
