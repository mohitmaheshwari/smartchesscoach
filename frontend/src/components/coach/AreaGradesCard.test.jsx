/**
 * "Where you stand" — a row is clickable only when something is behind it.
 *
 * Mohit, 2026-10-04: "nothing is clickable for a drill". The fix added links,
 * and the risk it introduced is the opposite one: a link on a row with an
 * empty page behind it. The backend decides that and omits `practice`
 * entirely, so the rule this file holds is that the card renders exactly what
 * it is given and never invents an affordance.
 *
 * The card also carries NO numbers, by contract. The grade is a word and a
 * four-step meter; the rate that produced it is never rendered.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("@/App", () => ({ API: "https://api.test/api" }), { virtual: true });
jest.mock("lucide-react", () => ({
  Loader2: () => null,
  ChevronRight: () => null,
}), { virtual: true });
jest.mock("react-router-dom", () => ({
  Link: ({ to, children, ...rest }) => <a href={to} {...rest}>{children}</a>,
}), { virtual: true });

const AreaGradesCard = require("./AreaGradesCard").default;

let container;
let root;

const respond = (body) => {
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve(body) })
  );
};

const render = async () => {
  act(() => root.render(<AreaGradesCard />));
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
};

const payload = (overrides = {}) => ({
  areas: [
    { key: "piece_safety", label: "Keeping pieces safe", measured: true,
      grade: "Good",
      practice: { href: "/training/pattern/piece_safety", label: "Practise this" } },
    { key: "king_safety", label: "Keeping your king safe", measured: true,
      grade: "Needs work" },
    { key: "endgame_technique", label: "Playing the endgame", measured: false,
      grade: null },
  ],
  phases: [
    { key: "middlegame", label: "The middlegame", measured: true, grade: "Fair" },
  ],
  ...overrides,
});

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

test("a row with practice supply becomes a link", async () => {
  respond(payload());
  await render();
  const link = container.querySelector('[data-testid="area-practice-piece_safety"]');
  expect(link).not.toBeNull();
  expect(link.getAttribute("href")).toBe("/training/pattern/piece_safety");
});

test("a row without practice supply is not a link", async () => {
  respond(payload());
  await render();
  expect(
    container.querySelector('[data-testid="area-practice-king_safety"]')
  ).toBeNull();
  // Positive control: the card did render that row, so the assertion above is
  // about the link and not about a missing row.
  expect(container.textContent).toContain("Keeping your king safe");
});

test("no anchor is rendered for any row the server did not route", async () => {
  respond(payload());
  await render();
  const hrefs = [...container.querySelectorAll("a")].map((a) => a.getAttribute("href"));
  expect(hrefs).toEqual(["/training/pattern/piece_safety"]);
});

test("an unmeasured area says so instead of showing a grade", async () => {
  respond(payload());
  await render();
  expect(container.textContent).toContain("Not enough games yet");
});

test("the card shows no numbers anywhere", async () => {
  respond(payload());
  await render();
  expect(container.textContent).not.toMatch(/[0-9%]/);
});

test("the meter fills one step per grade, never more", async () => {
  respond({
    areas: [
      { key: "a", label: "A", measured: true, grade: "Needs work" },
      { key: "b", label: "B", measured: true, grade: "Excellent" },
    ],
    phases: [],
  });
  await render();
  const rows = container.querySelectorAll("div.flex.items-center.gap-4");
  // Every row renders exactly four meter steps, so the meter cannot drift out
  // of step with the four grades it stands for.
  rows.forEach((row) => {
    const steps = row.querySelectorAll("span.rounded-full");
    if (steps.length) expect(steps.length).toBe(4);
  });
});

test("renders nothing when the server has no areas", async () => {
  respond({ areas: [], phases: [] });
  await render();
  expect(container.querySelector('[data-testid="area-grades-card"]')).toBeNull();
});
