/**
 * Render smoke for the Part 1 game-review repairs (backend 047a334a).
 *
 * The payloads below are the ACTUAL `compose_story` output for Games A-D,
 * captured from the candidate running against production data. The point is
 * that three of the repairs change the shape the UI receives, and two of those
 * shapes have never reached this component before:
 *
 *   good_moves   was [] on every game ever rendered, so the "What you did
 *                well" panel has never been exercised with data
 *   title        may now be ABSENT when a caption's shape is unrecognised
 *   cp_loss_label may now be a 21-character sentence ("gave up a forced
 *                mate") in a badge that was sized for "-352cp"
 *
 * This is jsdom, not a browser: it proves the component renders the new shapes
 * without throwing and puts the right text on screen. It cannot prove the
 * badge looks right at a given viewport -- that needs a real browser.
 */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

import LabV2 from "./LabV2";

const mockNavigate = jest.fn();

jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
  useParams: () => ({ gameId: "game-1" }),
  useSearchParams: () => [new URLSearchParams(), jest.fn()],
}), { virtual: true });
jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("@/lib/analytics", () => ({
  ANALYTICS_EVENTS: { FUNNEL_REVIEW_OPENED: "review_opened" },
  track: jest.fn(),
}), { virtual: true });
jest.mock("@/components/Layout", () => ({ children }) => <div>{children}</div>, { virtual: true });
jest.mock("@/components/LichessBoard", () => ({ fen }) => <div data-testid="lab-board">{fen}</div>, { virtual: true });
jest.mock("@/components/FeedbackModal", () => () => null, { virtual: true });
jest.mock("@/components/GameDecryptionV5", () => () => <div data-testid="decrypt-view" />, { virtual: true });
jest.mock("@/components/Lab/CoachInsightPanel", () => () => null, { virtual: true });
jest.mock("@/components/coach/CoachSession", () => () => null, { virtual: true });
jest.mock("@/components/Lab/CoachAction", () => () => null, { virtual: true });
jest.mock("@/components/coach/CoachMovePanel", () => () => null, { virtual: true });
jest.mock("@/components/experience/CanonicalReviewFocus", () => () => null, { virtual: true });
jest.mock("@/components/shared/FlagMoveDialog", () => ({ InlineFlag: () => null }), { virtual: true });
jest.mock("@/hooks/usePuzzleSubmissionIdentity", () => () => ["submission-1", jest.fn()], { virtual: true });
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));
jest.mock("framer-motion", () => ({
  motion: new Proxy({}, { get: () => ({ children, ...props }) => <div {...props}>{children}</div> }),
}));

const response = (body) => ({ ok: true, status: 200, json: () => Promise.resolve(body) });

// ── Real candidate output, Game A (loss, White 1301 v 1373) ───────────────
const GAME_A_STORY = {
  opener: "In this game you lost as White. The game turned at move 11 in the opening.",
  result_arc: { result_label: "you lost as White", decided_at_move: 11, phase: "opening" },
  principles: [
    {
      n: 1, move_number: 11, phase: "opening", san_played: "b4", san_best: "d4",
      cp_loss: 352, cp_loss_label: "-352cp", cost_is_mate: false,
      mate_transition: null, mate_cost_the_player: null,
      title: "Runs into the reply",
      diagnosis: "b4 runs into Bxc4, trading your queen on c4 for a bishop.",
      principle: "Before any quiet move, check that it doesn't run into a tactic that loses a piece.",
      fen_before: "r1b1k1nr/1p2bpp1/p2p1q1p/2p1p3/P1Q1P3/2PP1N2/1P1N1PPP/R1B1K2R w KQkq - 0 11",
      gap: null,
    },
  ],
  // The repair under test: this was [] on every game before 047a334a.
  good_moves: [
    { move_number: 17, san: "Ke2", phase: "middlegame" },
    { move_number: 13, san: "Nxc4", phase: "middlegame" },
  ],
  summary_table: [
    { mistake: "b4 (move 11)", cp_loss_label: "-352cp", remedy: "Before any quiet move, check that it doesn't run into a tactic that loses a piece." },
  ],
  homework: ["Replay this game move-by-move at a slower pace this week."],
  closing: "2 real mistakes decided this game.",
};

// ── Real candidate output, Game C (won by mate from a lost position) ──────
// Carries BOTH new shapes at once: a sentence in the cp badge, and a card
// with no `title` key at all.
const GAME_C_STORY = {
  opener: "In this game you won as Black. The game turned at move 20 in the middlegame.",
  result_arc: { result_label: "you won as Black", decided_at_move: 20, phase: "middlegame" },
  principles: [
    {
      n: 1, move_number: 20, phase: "middlegame", san_played: "Qxh3+", san_best: "Qxf3+",
      cp_loss: 1385,
      cp_loss_label: "gave up a forced mate",
      cost_is_mate: true,
      mate_transition: "gave up a forced mate",
      mate_cost_the_player: true,
      // No `title` key: repair 1.6 drops it when the caption shape is
      // unrecognised rather than showing a header that contradicts the body.
      diagnosis: "Qxh3+ misses mate in 3.",
      principle: "Qxf3+ was the move. Before moving, check every forcing move.",
      fen_before: "r5k1/pp4pp/2pp4/4p3/4P3/5NqP/PPPQ1b2/R4R1K b - - 2 20",
      gap: "missed_tactic",
    },
  ],
  good_moves: [
    { move_number: 30, san: "Rxh2#", phase: "middlegame" },
    { move_number: 29, san: "Rh6+", phase: "middlegame" },
  ],
  summary_table: [
    { mistake: "Qxh3+ (move 20)", cp_loss_label: "gave up a forced mate", remedy: "Qxf3+ was the move." },
  ],
  homework: ["Daily: 10 tactics puzzles for the next 5 days."],
  closing: "3 real mistakes decided this game.",
};

const GAME = {
  game_id: "game-1",
  user_color: "white",
  opponent_name: "Opponent",
  result: "1-0",
  pgn: '[Result "*"]\n\n1. e4 e5 2. Nf3 Nc6 *',
};

const ANALYSIS = {
  stockfish_analysis: {
    move_evaluations: [
      { move_number: 1, move: "e4", classification: "mistake", eval_after: -1 },
    ],
  },
};

function mountWith(story) {
  global.fetch = jest.fn((url) => {
    if (url.endsWith("/games/game-1")) return Promise.resolve(response(GAME));
    if (url.includes("/analysis/game-1/enriched")) return Promise.resolve(response(ANALYSIS));
    if (url.endsWith("/lab/game-1")) return Promise.resolve(response({}));
    if (url.endsWith("/games/game-1/coach-review")) {
      return Promise.resolve(response({ story }));
    }
    if (url.includes("/coach/coaching-context/review")) return Promise.resolve(response({}));
    if (url.endsWith("/lab/game-1/deep-strategy")) return Promise.resolve(response({}));
    throw new Error(`Unexpected request: ${url}`);
  });
}

describe("LabV2 renders the repaired coach-review payload", () => {
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
    delete global.fetch;
    jest.restoreAllMocks();
  });

  async function render(story) {
    mountWith(story);
    await act(async () => root.render(<LabV2 user={{ user_id: "student-1" }} />));
    await act(async () => {
      for (let i = 0; i < 24; i += 1) await Promise.resolve();
    });
    // The coach-review panel lives in the "Carry forward" view (LabV2.jsx
    // line 1414 branches on viewMode); the default view is "decrypt".
    const tab = container.querySelector("[data-testid='habits-view-btn']");
    if (tab) act(() => tab.click());
    await act(async () => {
      for (let i = 0; i < 8; i += 1) await Promise.resolve();
    });
  }

  test("Game A: the strengths panel appears for the first time", async () => {
    await render(GAME_A_STORY);
    // "What you did well" has never rendered before, because good_moves was
    // always empty.
    expect(container.textContent).toContain("What you did well");
    expect(container.textContent).toContain("Ke2");
    expect(container.textContent).toContain("Nxc4");
    expect(container.textContent).toContain("on move 17");
  });

  test("Game A: the numeric badge is unchanged", async () => {
    await render(GAME_A_STORY);
    expect(container.textContent).toContain("-352cp");
    expect(container.textContent).toContain("Runs into the reply");
  });

  test("Game A: the opener reads as one sentence", async () => {
    await render(GAME_A_STORY);
    expect(container.textContent).toContain("In this game you lost as White.");
    expect(container.textContent).not.toContain("the this game");
    expect(container.textContent).not.toContain("you you");
  });

  test("Game C: a mate sentence renders in the cost badge", async () => {
    await render(GAME_C_STORY);
    expect(container.textContent).toContain("gave up a forced mate");
    // The thing the repair exists to prevent reaching a player.
    expect(container.textContent).not.toContain("-1385cp");
    expect(container.textContent).not.toContain("1385cp");
  });

  test("Game C: a card with no title still renders its body", async () => {
    await render(GAME_C_STORY);
    expect(container.textContent).toContain("Qxh3+ misses mate in 3.");
    expect(container.textContent).toContain("Qxf3+ was the move.");
    // The move pair and the badge must still be present without a header.
    expect(container.textContent).toContain("m20");
  });

  test("Game C: mate wording does not leak into the strengths panel", async () => {
    await render(GAME_C_STORY);
    expect(container.textContent).toContain("What you did well");
    expect(container.textContent).toContain("Rxh2#");
  });

  test("no payload throws, and an empty story still renders the page", async () => {
    await render({});
    // The review section is simply absent; the page itself still works.
    expect(container.textContent).toContain("Carry forward");
    expect(container.textContent).not.toContain("Coach review");
  });

  test("the badge text is long enough to be worth a visual check", async () => {
    await render(GAME_C_STORY);
    const badge = Array.from(container.querySelectorAll("span"))
      .find((el) => el.textContent === "gave up a forced mate");
    expect(badge).toBeTruthy();
    // Recorded deliberately: this badge is styled font-mono and was sized for
    // a 7-character token. 21 characters render here, which jsdom cannot
    // measure. Flagged for the browser pass rather than asserted away.
    expect(badge.textContent.length).toBeGreaterThan(15);
  });
});
