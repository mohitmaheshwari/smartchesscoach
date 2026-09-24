/**
 * A habit we never measured must not be rendered as a score of zero.
 *
 * Three of the five thinking habits produced no data at all until 2026-09-24 -
 * they read a field that does not exist, so nothing was ever attributed to
 * them. The backend now sends current_score: null with measured: false. The
 * card used `habitData?.current_score || 0`, which turned that into a
 * confident 0 and an empty bar: "you are terrible at this", about something we
 * never observed.
 */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

import ThinkingScoreCard from "./ThinkingScoreCard";

jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }) => {
      const domProps = { ...props };
      delete domProps.initial;
      delete domProps.animate;
      delete domProps.exit;
      delete domProps.transition;
      return <div {...domProps}>{children}</div>;
    },
  },
  AnimatePresence: ({ children }) => <>{children}</>,
}));

const habit = (score, measured) => ({
  current_score: score,
  previous_score: null,
  change: null,
  measured,
  trend: "insufficient_data",
});

const payload = (overrides = {}) => ({
  has_data: true,
  overall_score: 72,
  overall_trend: "stable",
  overall_change: null,
  games_analyzed: 9,
  explanation: "Based on your recent games.",
  recommendations: [],
  habit_progress: {
    threat_awareness: habit(72, true),
    move_verification: habit(64, true),
    tactical_vision: habit(null, false),
    king_safety: habit(null, false),
    patience: habit(null, false),
  },
  ...overrides,
});

let container;
let root;

const mount = async (body) => {
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve(body) })
  );
  container = document.createElement("div");
  document.body.appendChild(container);
  await act(async () => {
    root = createRoot(container);
    root.render(<ThinkingScoreCard />);
  });
  await act(async () => {});
};

afterEach(async () => {
  if (root) {
    await act(async () => root.unmount());
    root = null;
  }
  if (container) {
    container.remove();
    container = null;
  }
  jest.resetAllMocks();
});

const expandHabits = async () => {
  const btn = Array.from(container.querySelectorAll("button")).find((b) =>
    /show all/i.test(b.textContent)
  );
  if (btn) {
    await act(async () => {
      btn.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
  }
};

test("measured habits fill the default view, not the unmeasured ones", async () => {
  await mount(payload());

  // The card shows 3 habits by default. Those slots must go to habits we
  // actually measured - a null score sorting as 0 used to put all three
  // unmeasured ones on top, so the card said "Not enough data yet" three
  // times and hid the real numbers.
  const text = container.textContent;
  expect(text).toContain("72");
  expect(text).toContain("64");
  expect(
    container.querySelector('[data-testid="habit-unmeasured-patience"]')
  ).toBeNull();
});

test("unmeasured habits say so instead of showing 0", async () => {
  await mount(payload());
  await expandHabits();

  for (const key of ["tactical_vision", "king_safety", "patience"]) {
    const el = container.querySelector(`[data-testid="habit-unmeasured-${key}"]`);
    expect(el).not.toBeNull();
    expect(el.textContent).toMatch(/not enough data/i);
  }
  // and none of them rendered a fake zero
  expect(container.textContent).not.toMatch(/0(?=\s*(%|$))/);
});

test("a null overall score renders a dash, not NaN", async () => {
  await mount(payload({ overall_score: null }));

  expect(container.textContent).not.toContain("NaN");
  await expandHabits();
  expect(
    container.querySelector('[data-testid="habit-unmeasured-patience"]')
  ).not.toBeNull();
});
