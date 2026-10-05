/**
 * The thinking card says words, never a score, and only about habits that can
 * separate one player from another.
 *
 * REPLACES ThinkingScoreCardUnmeasured.test.jsx, which guarded a real bug: three
 * of the five habits produced no data until 2026-09-24, and the card turned a
 * null score into a confident 0 and an empty bar — "you are terrible at this",
 * about something never observed. That guarantee is now structural rather than
 * tested: no score is rendered at all, and the server only ever sends a line for
 * a habit whose score is a number below its cut. The tests below hold the rules
 * that replaced it.
 */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

import ThinkingScoreCard from "./ThinkingScoreCard";

jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("lucide-react", () => ({ Loader2: () => null }), { virtual: true });

let container;
let root;

const respond = (body) => {
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve(body) })
  );
};

const render = async () => {
  act(() => root.render(<ThinkingScoreCard />));
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
};

const card = (lines) => ({
  has_data: true,
  overall_score: 84.6,
  card: {
    schema_version: "thinking_habits_card.v1",
    measured: lines.length > 0,
    lines,
  },
});

const THREAT = {
  habit: "threat_awareness",
  headline: "You are moving before you look at their threats.",
  body: "Most of your mistakes come right after their move changed something.",
  next: "Before each move, ask what their last move attacked.",
};

beforeEach(() => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  jest.resetAllMocks();
});

test("renders the habit that is at an end", async () => {
  respond(card([THREAT]));
  await render();
  expect(
    container.querySelector('[data-testid="thinking-habit-threat_awareness"]')
  ).not.toBeNull();
  expect(container.textContent).toContain("their last move attacked");
});

test("shows no number, even though the payload still carries a score", async () => {
  respond(card([THREAT]));
  await render();
  // The endpoint keeps overall_score for older readers. It must not reach the
  // page: this card was the only one on /progress rendering a number.
  expect(container.textContent).not.toMatch(/[0-9]/);
});

test("renders nothing when no habit is at an end", async () => {
  respond(card([]));
  await render();
  expect(
    container.querySelector('[data-testid="thinking-score-card"]')
  ).toBeNull();
  // Silence, not reassurance: a cheerful line off a saturated measure is the
  // mistake the balanced behaviour sentence made.
  expect(container.textContent).not.toMatch(/fine|good|well done|great/i);
});

test("renders nothing when the server sends no card at all", async () => {
  respond({ has_data: false });
  await render();
  expect(
    container.querySelector('[data-testid="thinking-score-card"]')
  ).toBeNull();
});

test("a second habit is rendered with its own headline", async () => {
  const verify = {
    habit: "move_verification",
    headline: "You commit to a move before checking it.",
    body: "The move that looks strongest often stops looking strong.",
    next: "Play their best reply in your head before you touch it.",
  };
  respond(card([THREAT, verify]));
  await render();
  expect(
    container.querySelector('[data-testid="thinking-habit-move_verification"]')
  ).not.toBeNull();
  expect(container.textContent).toContain("commit to a move before checking it");
});
