/**
 * "How your chess is going" — the bars, and the context the bars were missing.
 *
 * docs/chances_not_games_scope.md
 *
 * Mohit, 2026-10-06: the first build shipped the ratio and none of the context,
 * so the card said "about half" without saying half of what, against when, or
 * going which way. The habit lines are that context and they stand on their own:
 * a player with too few chances to rate can still be told how regular they have
 * been this month.
 */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("lucide-react", () => ({
  Loader2: () => null,
  ChevronRight: () => null,
}), { virtual: true });
jest.mock("react-router-dom", () => ({
  Link: ({ to, children, ...rest }) => <a href={to} {...rest}>{children}</a>,
}), { virtual: true });

const ChancesCard = require("./ChancesCard").default;

let container;
let root;

const respond = (body) => {
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve(body) })
  );
};

const render = async () => {
  act(() => root.render(<ChancesCard />));
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
};

const HABITS = {
  measured: true,
  lines: [
    { kind: "week", line: "About the same as your usual week." },
    { kind: "rhythm", line: "You have played on most days this month." },
    {
      kind: "results",
      line: "Your results fall away as a session goes on, but your eye for tactics does not.",
      next: "Something other than spotting things is going wrong late in a sitting.",
    },
  ],
};

const FULL = {
  measured: true,
  headline: "You take about half of what the board offers you.",
  chances: 4346,
  took: 2302,
  share: 0.53,
  shapes: [
    { shape: "free_piece", label: "free material", share: 0.83, chances: 880, judgeable: true },
    { shape: "skewer", label: "skewers", share: 0.42, chances: 1071, judgeable: true },
    { shape: "force_the_king", label: "forcing the king", share: 0, chances: 1, judgeable: false },
  ],
  weakest: { shape: "skewer", label: "skewers" },
  weakest_line: "Lining pieces up is what costs you.",
  practice: { href: "/training/find/skewer", label: "Practise skewers" },
  habits: HABITS,
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

test("shows the headline, the bars and the context together", async () => {
  respond(FULL);
  await render();
  expect(container.textContent).toContain("about half of what the board offers");
  expect(container.textContent).toContain("About the same as your usual week.");
  expect(container.textContent).toContain("most days this month");
  expect(container.textContent).toContain("Lining pieces up");
});

test("a shape with too few chances gets no bar", async () => {
  respond(FULL);
  await render();
  // free material and skewers are judgeable; forcing the king is not.
  expect(container.textContent).toContain("free material");
  expect(container.textContent).toContain("skewers");
  expect(container.textContent).not.toContain("forcing the king");
});

test("the habits render even when there are too few chances to rate", async () => {
  // A player can be told how regular they have been before we can rate them.
  respond({ measured: false, reason: "not enough chances watched yet", habits: HABITS });
  await render();
  expect(container.querySelector('[data-testid="chances-card"]')).not.toBeNull();
  expect(container.textContent).toContain("most days this month");
  expect(container.textContent).not.toContain("what the board offers");
});

test("renders nothing when there is neither a rating nor a habit", async () => {
  respond({ measured: false, reason: "not enough chances watched yet" });
  await render();
  expect(container.querySelector('[data-testid="chances-card"]')).toBeNull();
});

test("the practice link is only rendered when the server sent one", async () => {
  respond({ ...FULL, practice: null });
  await render();
  expect(container.querySelector('[data-testid="chances-practice"]')).toBeNull();
  // positive control: it does render when present
  jest.resetAllMocks();
  act(() => root.unmount());
  container.remove();
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  respond(FULL);
  await render();
  expect(container.querySelector('[data-testid="chances-practice"]')).not.toBeNull();
});

test("no number reaches the page, though the payload carries counts", async () => {
  respond(FULL);
  await render();
  // chances: 4346 and took: 2302 are in the payload and must not be printed.
  expect(container.textContent).not.toMatch(/[0-9]/);
});
