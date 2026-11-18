/**
 * Today's tasks on Home (docs/daily_coach_plan_scope.md): the server's list,
 * ticked as he opens tasks, and a week row that never counts misses.
 */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

import DayCard from "./DayCard";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

jest.mock("@/App", () => ({ API: "/api" }), { virtual: true });
jest.mock("@/lib/coachFile", () => ({ playFrom: jest.fn() }), { virtual: true });
jest.mock("react-router-dom", () => ({
  Link: ({ to, children, onClick, ...rest }) => <a href={to} onClick={(e) => { e.preventDefault(); onClick && onClick(e); }} {...rest}>{children}</a>,
  useNavigate: () => jest.fn(),
}), { virtual: true });
jest.mock("lucide-react", () => new Proxy({}, { get: () => (props) => <span aria-label={props["aria-label"]} /> }), { virtual: true });

const DAY = {
  enabled: true, state: "ready", day: "2026-11-18", size: "normal", sizes: ["short", "normal", "long"], all_done: false,
  tasks: [
    { id: "fix:find:g2:20", slot: "fix", action: "open", title: "Find the better move in one of your games.", text: "This week's step: x.", url: "/game/g2?move=20", done: false },
    { id: "theme:pin", slot: "new", action: "puzzles", title: "Pin", text: "A piece cannot move.", url: "/training/theme/theme-pin?count=6&from=today", count: 6, done: false },
    { id: "play:clock:5+3", slot: "play", action: "games", title: "Two games at 5+3.", text: "Your 5+3 games go better.", done: true },
  ],
  week: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((label, i) => ({ day: `d${i}`, label, state: i === 0 ? "done" : "none", today: i === 2 })),
};

async function render(body) {
  global.fetch = jest.fn((url) => Promise.resolve({ ok: true, json: () => Promise.resolve(String(url).includes("/tick") ? { ok: true } : body) }));
  const host = document.createElement("div");
  document.body.appendChild(host);
  await act(async () => { createRoot(host).render(<DayCard />); });
  return host;
}

afterEach(() => { document.body.innerHTML = ""; delete global.fetch; });

test("shows the server's tasks in order, with the browser's time zone in the request", async () => {
  const host = await render(DAY);
  expect(global.fetch.mock.calls[0][0]).toMatch(/^\/api\/daily-plan\?tz=/);
  const slots = [...host.querySelectorAll("li")].map((li) => li.getAttribute("data-testid"));
  expect(slots).toEqual(["day-task-fix", "day-task-new", "day-task-play"]);
  expect(host.textContent).toContain("Two games at 5+3.");
  expect(host.textContent).not.toMatch(/missed/i);
});

test("opening a task that is done by opening ticks it; a puzzle task waits for its proof", async () => {
  const host = await render(DAY);
  await act(async () => { host.querySelector('[data-testid="day-task-new"] a').click(); });
  expect(global.fetch.mock.calls.some(([url]) => String(url).includes("/daily-plan/tick"))).toBe(false);
  await act(async () => { host.querySelector('[data-testid="day-task-fix"] a').click(); });
  const tick = global.fetch.mock.calls.find(([url]) => String(url).includes("/daily-plan/tick"));
  expect(JSON.parse(tick[1].body).task_id).toBe("fix:find:g2:20");
  expect(host.querySelector('[data-testid="day-task-fix"] [aria-label="done"]')).not.toBeNull();
});

test("renders nothing for a player without the coach pages", async () => {
  const host = await render({ enabled: false });
  expect(host.querySelector('[data-testid="day-card"]')).toBeNull();
});
