/**
 * Every player's Home carries the two lines about the player himself
 * (docs/home_behaviour_and_clock_scope.md), only when the server found them.
 */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

import HomeCoachLines from "./HomeCoachLines";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

jest.mock("@/App", () => ({ API: "/api" }), { virtual: true });
jest.mock("lucide-react", () => new Proxy({}, { get: () => () => <span /> }), { virtual: true });
jest.mock("@/components/Home/BetweenGamesPanel", () => ({
  CoachLine: ({ testId, line }) => (line?.headline ? <div data-testid={testId}>{line.headline} {line.detail}</div> : null),
}), { virtual: true });

async function render(body) {
  global.fetch = jest.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(body) }));
  const host = document.createElement("div");
  document.body.appendChild(host);
  await act(async () => { createRoot(host).render(<HomeCoachLines />); });
  return host;
}

afterEach(() => { document.body.innerHTML = ""; delete global.fetch; });

test("shows the clock advice from /home/coach-lines", async () => {
  const host = await render({
    behaviour: null,
    clock_advice: { headline: "Your 3+2 games go badly, mostly on the clock.",
                    detail: "Your 5+3 games go better. Play 5+3 instead." },
  });
  expect(global.fetch.mock.calls[0][0]).toBe("/api/home/coach-lines");
  expect(host.querySelector('[data-testid="between-games-clock"]').textContent).toContain("Play 5+3 instead.");
  expect(host.querySelector('[data-testid="between-games-behaviour"]')).toBeNull();
});

test("renders nothing when neither line was found", async () => {
  const host = await render({ behaviour: null, clock_advice: null });
  expect(host.querySelector('[data-testid="home-coach-lines"]')).toBeNull();
});
