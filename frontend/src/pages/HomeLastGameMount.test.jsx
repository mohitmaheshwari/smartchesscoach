/**
 * Where the last-game card is mounted.
 *
 * It was first wired inside HomePageNew's `!hasGames` branch -- the page a
 * player sees BEFORE they have imported anything -- so the one audience that
 * can have a last game was the one audience that could never see the card.
 * Every test passed, because the tests rendered the card and never the page.
 *
 * So this renders the page, both ways round. "Mounted" and "reaching a
 * person" are different claims and only the second one is worth making.
 */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("react-router-dom", () => ({
  useNavigate: () => jest.fn(),
  Link: ({ children }) => <span>{children}</span>,
}), { virtual: true });
jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("framer-motion", () => ({
  motion: new Proxy({}, { get: () => ({ children, ...p }) => <div {...{}}>{children}</div> }),
}), { virtual: true });
jest.mock("@/lib/analytics", () => ({
  ANALYTICS_EVENTS: {}, track: () => {}, trackCurriculum: () => {},
}), { virtual: true });
jest.mock("@/lib/motion", () => ({
  pageEnter: {}, staggerContainer: {}, staggerItem: {}, fadeInUp: {}, scaleIn: {},
}), { virtual: true });
jest.mock("@/lib/personalCurriculum", () => ({
  loadPersonalCurriculum: () => Promise.resolve({ enabled: false }),
}), { virtual: true });
jest.mock("@/components/Layout", () => ({ children }) => <div>{children}</div>, { virtual: true });
jest.mock("@/components/coach/ChancesCard", () => () => <div />, { virtual: true });
jest.mock("@/components/coach/CoachMovements", () => ({ children }) => <div>{children}</div>, { virtual: true });
jest.mock("@/components/experience/CanonicalFocusRail", () => () => <div />, { virtual: true });
jest.mock("@/components/curriculum/CurriculumHome", () => () => <div />, { virtual: true });
jest.mock("@/components/HomeLoadingSkeleton", () => () => <div />, { virtual: true });
jest.mock("lucide-react", () => new Proxy({}, { get: () => () => <span /> }), { virtual: true });

// The card itself is a sentinel here: this test is about where it is mounted.
jest.mock("@/components/Home/LastGameCard", () => () => (
  <div data-testid="last-game-card-sentinel" />
), { virtual: true });

import HomePageNew from "./HomePageNew";

function fetchReturning(dashboard) {
  return jest.fn((url) => {
    const body = String(url).includes("/home/dashboard-v2") ? dashboard : {};
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
  });
}

describe("the last-game card's mount on Home", () => {
  let container, root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    // jsdom has no IntersectionObserver and the page uses one to track which
    // section is on screen.
    global.IntersectionObserver = class {
      observe() {} unobserve() {} disconnect() {}
    };
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    delete global.fetch;
  });

  async function render() {
    await act(async () => root.render(<HomePageNew />));
    await act(async () => { for (let i = 0; i < 25; i += 1) await Promise.resolve(); });
  }

  test("a player with games sees it", async () => {
    global.fetch = fetchReturning({ games_analyzed: 31, games_imported: 62 });
    await render();
    expect(container.querySelector("[data-testid='last-game-card-sentinel']")).toBeTruthy();
  });

  test("a player with no games is not shown a card about a game", async () => {
    global.fetch = fetchReturning({ games_analyzed: 0, games_imported: 0 });
    await render();
    expect(container.querySelector("[data-testid='last-game-card-sentinel']")).toBeNull();
  });
});
