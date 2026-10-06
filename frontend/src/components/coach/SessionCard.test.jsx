/**
 * The session card shows a decision, and never a button with nothing behind it.
 * docs/home_session_scope.md
 */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("lucide-react", () => ({ Loader2: () => null, ChevronRight: () => null }), { virtual: true });
jest.mock("react-router-dom", () => ({
  Link: ({ to, children, ...rest }) => <a href={to} {...rest}>{children}</a>,
}), { virtual: true });
jest.mock("react-chessboard", () => ({
  Chessboard: ({ position }) => <div data-testid="board" data-fen={position} />,
}), { virtual: true });

const SessionCard = require("./SessionCard").default;

let container, root;
const respond = (body) => {
  global.fetch = jest.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(body) }));
};
const render = async () => {
  act(() => root.render(<SessionCard />));
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
};

const SESSION = {
  mode: "appreciate",
  why: "good_move",
  headline: "You found something here worth keeping.",
  line: "You gave up material and it was still the best move on the board.",
  fen: "8/8/8/8/8/8/8/K6k w - - 0 1",
  signals: [
    { kind: "improving", label: "tactical oversight" },
    { kind: "working_on", label: "piece safety" },
    { kind: "strength", label: "Low blunder rate" },
  ],
  blocks: [
    { kind: "appreciate", title: "The move you got right", detail: "", minutes: 2, href: "/game/g1" },
    { kind: "improve", title: "piece safety", detail: "Positions from your own games.", minutes: 5, href: "/training/pattern/piece_safety" },
    { kind: "challenge", title: "Unseen positions", detail: "No hints unless you ask.", minutes: 2, href: "/training/find/pin" },
  ],
  minutes: 9,
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

test("shows the coach's decision and the blocks", async () => {
  respond(SESSION);
  await render();
  expect(container.textContent).toContain("You found something here worth keeping.");
  expect(container.querySelector('[data-testid="session-block-improve"]')).not.toBeNull();
  expect(container.querySelector('[data-testid="session-block-challenge"]')).not.toBeNull();
});

test("the three signals render in a fixed order", async () => {
  respond(SESSION);
  await render();
  const text = container.querySelector('[data-testid="session-signals"]').textContent;
  expect(text.indexOf("Improving")).toBeLessThan(text.indexOf("Working on"));
  expect(text.indexOf("Working on")).toBeLessThan(text.indexOf("Strength"));
});

test("a block with no destination is not a link", async () => {
  respond({ ...SESSION, blocks: [{ kind: "challenge", title: "Unseen positions", minutes: 2 }] });
  await render();
  expect(container.querySelector('[data-testid="session-block-challenge"]')).toBeNull();
  expect(container.textContent).toContain("Unseen positions");
});

test("there is no start-session button, because there is no session runner", async () => {
  respond(SESSION);
  await render();
  expect(container.textContent).not.toMatch(/start (today'?s )?session/i);
});

test("the board renders only when the celebration has one", async () => {
  respond(SESSION);
  await render();
  expect(container.querySelector('[data-testid="board"]')).not.toBeNull();
});

test("no board when there is no position", async () => {
  respond({ ...SESSION, fen: null });
  await render();
  expect(container.querySelector('[data-testid="board"]')).toBeNull();
});

test("renders nothing without a headline", async () => {
  respond({});
  await render();
  expect(container.querySelector('[data-testid="session-card"]')).toBeNull();
});

test("minutes are the only number shown", async () => {
  respond(SESSION);
  await render();
  const digits = (container.textContent.match(/[0-9]+/g) || []);
  // every number on the card must be one of the block minute counts
  const minutes = SESSION.blocks.map((b) => String(b.minutes));
  digits.forEach((d) => expect(minutes).toContain(d));
});
