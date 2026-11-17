/**
 * "Before your next game" carries how he played as a person in the last game
 * and which clock to play, each only when the player file says it is true
 * (docs/home_behaviour_and_clock_scope.md).
 */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

import BetweenGamesPanel from "./BetweenGamesPanel";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

jest.mock("react-router-dom", () => ({
  Link: ({ to, children, ...rest }) => <a href={to} {...rest}>{children}</a>,
}), { virtual: true });
jest.mock("lucide-react", () => new Proxy({}, { get: () => () => <span /> }), { virtual: true });

let mockFile = null;
jest.mock("@/lib/coachFile", () => ({ useCoachFile: () => mockFile }), { virtual: true });
jest.mock("@/components/coachfile/CoachFileBlocks", () => ({
  LastGameRepeat: () => null,
  PlayPositions: () => null,
  SittingNote: () => null,
}), { virtual: true });

function render() {
  const host = document.createElement("div");
  document.body.appendChild(host);
  act(() => { createRoot(host).render(<BetweenGamesPanel />); });
  return host;
}

afterEach(() => { document.body.innerHTML = ""; mockFile = null; });

test("shows the behaviour line and the clock advice in the server's words", () => {
  mockFile = {
    enabled: true, state: "ready",
    behaviour: { headline: "You were winning, and then one mistake brought another.",
                 detail: "After a mistake, stop. Look at their best reply before your next move." },
    clock_advice: { headline: "Your 3+2 games go badly, mostly on the clock.",
                    detail: "Your 5+3 games go better. Play 5+3 instead." },
  };
  const host = render();
  expect(host.querySelector('[data-testid="between-games-behaviour"]').textContent)
    .toContain("You were winning, and then one mistake brought another.");
  expect(host.querySelector('[data-testid="between-games-clock"]').textContent)
    .toContain("Play 5+3 instead.");
});

test("says nothing when neither was found", () => {
  mockFile = { enabled: true, state: "ready", behaviour: null, clock_advice: null };
  const host = render();
  expect(host.querySelector('[data-testid="between-games-panel"]')).toBeNull();
});
