import { act } from "react";
import { createRoot } from "react-dom/client";
import UnifiedProgress, { buildProgressView } from "./UnifiedProgress";

const mockNavigate = jest.fn();
const mockLoadPersonalCurriculum = jest.fn();

jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}), { virtual: true });
jest.mock("react-chessboard", () => ({
  Chessboard: ({ position }) => <div data-testid="evidence-board">{position}</div>,
}));
jest.mock("@/components/Layout", () => ({ children }) => <div>{children}</div>);
jest.mock("@/App", () => ({ API: "https://api.test/api" }));
jest.mock("@/lib/analytics", () => ({
  ANALYTICS_EVENTS: { PROGRESS_VIEWED: "progress_viewed" },
  trackCurriculum: jest.fn(),
}));
jest.mock("@/lib/motion", () => ({
  fadeInUp: {},
  revealOnScroll: {},
  staggerContainer: {},
}));
jest.mock("@/lib/personalCurriculum", () => ({
  loadPersonalCurriculum: (...args) => mockLoadPersonalCurriculum(...args),
}));

const curriculum = {
  enabled: true,
  decision: {
    primary: {
      title: "Piece safety",
      destination: {
        href: "/training?personalized=1&kind=concept&lesson=piece_safety",
      },
    },
  },
};

const observation = (overrides = {}) => ({
  game_id: "game-3",
  ply: 4,
  move_number: 2,
  fen: "4k3/8/8/8/8/8/3R4/4K3 w - - 0 1",
  move_uci: "d2d7",
  move_san: "Rd7",
  piece: "rook",
  destination: "d7",
  outcome: "miss",
  opponent: "Opponent",
  ...overrides,
});

const journey = (overrides = {}) => ({
  enabled: true,
  paused: false,
  focus: { focus_kind: "piece_safety/destination_safety_exact" },
  practice: {
    lesson_evidence_events: 2,
    completed: true,
    changes_transfer_verdict: false,
  },
  transfer: {
    verdict: "improved",
    message: "You have now handled this decision in later unassisted games.",
  },
  steps: {
    baseline_frozen: true,
    home_focus_served: true,
    lesson_completed: true,
    later_unassisted_opportunity: true,
  },
  evidence_examples: {
    before: observation(),
    recent: observation({
      game_id: "game-4",
      outcome: "handled",
      opponent: "Recent opponent",
    }),
  },
  ...overrides,
});

describe("UnifiedProgress evidence experience", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    mockNavigate.mockReset();
    mockLoadPersonalCurriculum.mockReset();
    mockLoadPersonalCurriculum.mockResolvedValue(curriculum);
    global.fetch = jest.fn();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    delete global.fetch;
  });

  test("leads with later-game proof and shows only exact owned boards", async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(journey()),
    });

    await act(async () => {
      root.render(<UnifiedProgress user={{ user_id: "user-1" }} />);
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(container.textContent).toContain(
      "This lesson is beginning to hold in your games."
    );
    expect(container.textContent).toContain(
      "You have now handled this decision in later unassisted games."
    );
    expect(container.querySelectorAll('[data-testid="evidence-board"]')).toHaveLength(2);
    expect(container.textContent).toContain(
      "This time, your rook stayed safe on d7."
    );
    expect(container.textContent).toContain(
      "Practice is recorded, but it never changes the real-game verdict by itself."
    );
    expect(container.textContent).not.toContain("Our one focus right now");
    expect(container.textContent).not.toContain("Practise this with me");
    expect(container.textContent).not.toMatch(/\d+%/);

    act(() => container.querySelector('article button').click());
    expect(mockNavigate).toHaveBeenCalledWith("/game/game-3");
  });

  test("does not invent game evidence while waiting for transfer", async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(journey({
        transfer: {
          verdict: "insufficient_evidence",
          message:
            "Practice is recorded. I need to see the same decision in a later unassisted game before I can judge improvement.",
        },
        steps: {
          baseline_frozen: true,
          home_focus_served: true,
          lesson_completed: true,
          later_unassisted_opportunity: false,
        },
        evidence_examples: { before: null, recent: null },
      })),
    });

    await act(async () => {
      root.render(<UnifiedProgress user={{ user_id: "user-1" }} />);
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(container.textContent).toContain(
      "You understand this in practice. I can’t call it improvement yet."
    );
    expect(container.querySelector('[data-testid="progress-evidence-empty"]')).not.toBeNull();
    expect(container.textContent).toContain(
      "I won’t fill this space with a vaguely similar position."
    );

    act(() => {
      container
        .querySelector('[data-testid="progress-next-action"]')
        .click();
    });
    expect(mockNavigate).toHaveBeenCalledWith("/import");
  });
});

describe("buildProgressView", () => {
  test("keeps a later miss active and routes to its actual game", () => {
    const view = buildProgressView({
      curriculum,
      journey: journey({
        transfer: {
          verdict: "still_recurring",
          message: "The same decision appeared again in a later game.",
        },
        evidence_examples: {
          before: observation(),
          recent: observation({ game_id: "game with spaces", outcome: "miss" }),
        },
      }),
    });

    expect(view.headline).toBe("The old mistake showed up again.");
    expect(view.action.href).toBe("/game/game%20with%20spaces");
  });

  test("sends unfinished practice back to the canonical lesson", () => {
    const view = buildProgressView({
      curriculum,
      journey: journey({
        practice: { lesson_evidence_events: 0, completed: false },
        transfer: { verdict: "insufficient_evidence" },
      }),
    });

    expect(view.headline).toBe("First, show me you understand the idea.");
    expect(view.action.href).toBe(
      "/training?personalized=1&kind=concept&lesson=piece_safety"
    );
  });

  test("preserves a neutral saved state when the pilot is paused", () => {
    const view = buildProgressView({
      curriculum,
      journey: {
        enabled: false,
        paused: true,
        message:
          "Your lesson and progress are saved. Your coach is preparing the next step.",
      },
    });

    expect(view.headline).toBe("Nothing you learned has disappeared.");
    expect(view.body).toContain("progress are saved");
  });

  test("makes no improvement claim outside canonical complete-coaching evidence", () => {
    const view = buildProgressView({
      curriculum,
      journey: { enabled: false, paused: false },
    });

    expect(view.headline).toBe("I’m not ready to claim a change yet.");
    expect(view.body).toContain("I would only be guessing");
  });
});
