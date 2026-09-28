/**
 * Same symptom, opposite prescriptions.
 *
 * A knowledge gap sends the player to positions of that shape. A looking habit
 * must NOT send him to more of the same puzzles -- more repetitions of an idea
 * he already knows trains nothing. If both layers ever produced the same drill,
 * separating them would have bought nothing.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("@/App", () => ({ API: "https://api.test/api" }), { virtual: true });
jest.mock("@/components/ui/card", () => ({
  Card: ({ children, ...rest }) => <div {...rest}>{children}</div>,
  CardContent: ({ children }) => <div>{children}</div>,
  CardHeader: ({ children }) => <div>{children}</div>,
  CardTitle: ({ children }) => <div>{children}</div>,
}), { virtual: true });
jest.mock("lucide-react", () => ({ Loader2: () => null }), { virtual: true });
jest.mock("react-router-dom", () => ({
  Link: ({ to, children, ...rest }) => <a href={to} {...rest}>{children}</a>,
}), { virtual: true });

const TacticalEyeCard = require("./TacticalEyeCard").default;

let container;
let root;

const KNOWLEDGE = {
  measured: true,
  layer: "knowledge",
  headline: "Your eye has not learned this shape yet.",
  body: "Chances come up more often than you take them, and you are giving yourself time.",
  next: "Next: positions where forks are waiting.",
  drill: { href: "/training/pattern/missed_tactic", label: "Find the shape" },
};

const ATTENTION = {
  measured: true,
  layer: "attention",
  headline: "You play quickly. Let us find out if that is costing you.",
  body: "Chances come up more often than you take them, and you are a fast mover in general. Whether the two are connected, we do not know yet.",
  next: "Next: the same positions, but take your time on each one.",
  drill: { href: "/training/safety", label: "Practise the check" },
};

const respond = (body) => {
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve(body) })
  );
};

const render = async () => {
  act(() => root.render(<TacticalEyeCard />));
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
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
  delete global.fetch;
});

test("the knowledge layer sends the player to the shape", async () => {
  respond(KNOWLEDGE);
  await render();
  const drill = container.querySelector('[data-testid="tactical-eye-drill"]');
  expect(drill.getAttribute("href")).toBe("/training/pattern/missed_tactic");
});

test("the attention layer does NOT send him to more of the same puzzles", async () => {
  respond(ATTENTION);
  await render();
  const drill = container.querySelector('[data-testid="tactical-eye-drill"]');
  expect(drill.getAttribute("href")).not.toContain("/training/pattern/");
  expect(drill.getAttribute("href")).toBe("/training/safety");
});

test("the attention card offers a hypothesis, never a cause", async () => {
  /** The verdict comes from GENERAL tempo, and measured across 42 players
   *  mistakes are LESS rushed than ordinary moves, so a causal claim is not
   *  supported. */
  respond(ATTENTION);
  await render();
  const text = container.textContent.toLowerCase();
  expect(text).toContain("we do not know yet");
  expect(text).not.toContain("that is why");
  expect(text).not.toContain("stopping to check is");
});

test("no number ever reaches the page", async () => {
  respond(KNOWLEDGE);
  await render();
  expect(container.textContent).not.toMatch(/\d/);
});

test("a player who finds them gets no card", async () => {
  respond({ measured: false, reason: "no tactical gap" });
  await render();
  expect(container.querySelector('[data-testid="tactical-eye-card"]')).toBeNull();
});

test("an unmeasured player gets no card rather than a hedged one", async () => {
  respond({ measured: false, reason: "not enough tactical chances watched yet" });
  await render();
  expect(container.querySelector('[data-testid="tactical-eye-card"]')).toBeNull();
});

test("a failed request costs the page nothing", async () => {
  global.fetch = jest.fn(() => Promise.reject(new Error("offline")));
  await render();
  expect(container.querySelector('[data-testid="tactical-eye-card"]')).toBeNull();
});
