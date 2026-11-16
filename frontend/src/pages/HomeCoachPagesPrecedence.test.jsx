/**
 * The coach-pages Home wins over the curriculum Home.
 *
 * 2026-11-16: prod enables the personal curriculum for admin and super_admin,
 * and HomePageNew returned CurriculumHome before it reached the coach-pages
 * branch, so the owner's own account (super_admin, in the coach-pages flag)
 * never saw the plan while every player viewed through view-as did. This
 * renders the page as that account, both ways round.
 */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("react-router-dom", () => ({
  useNavigate: () => jest.fn(),
  Link: ({ children }) => <span>{children}</span>,
}), { virtual: true });
jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("framer-motion", () => ({
  motion: new Proxy({}, { get: () => ({ children }) => <div>{children}</div> }),
}), { virtual: true });
jest.mock("@/lib/analytics", () => ({
  ANALYTICS_EVENTS: {}, track: () => {}, trackCurriculum: () => {},
}), { virtual: true });
jest.mock("@/lib/motion", () => ({
  pageEnter: {}, staggerContainer: {}, staggerItem: {}, fadeInUp: {}, scaleIn: {},
}), { virtual: true });
// The curriculum is ON, as it is on prod for admins.
jest.mock("@/lib/personalCurriculum", () => ({
  loadPersonalCurriculum: () => Promise.resolve({ enabled: true }),
}), { virtual: true });
jest.mock("@/components/Layout", () => ({ children }) => <div>{children}</div>, { virtual: true });
jest.mock("@/components/coach/ChancesCard", () => () => <div />, { virtual: true });
jest.mock("@/components/coach/CoachMovements", () => ({ children }) => <div>{children}</div>, { virtual: true });
jest.mock("@/components/experience/CanonicalFocusRail", () => () => <div />, { virtual: true });
jest.mock("@/components/HomeLoadingSkeleton", () => () => <div />, { virtual: true });
jest.mock("lucide-react", () => new Proxy({}, { get: () => () => <span /> }), { virtual: true });
jest.mock("@/components/Home/LastGameCard", () => () => <div />, { virtual: true });
jest.mock("@/components/Home/BetweenGamesPanel", () => () => <div />, { virtual: true });
jest.mock("@/components/curriculum/CurriculumHome", () => () => (
  <div data-testid="curriculum-home-sentinel" />
), { virtual: true });
jest.mock("@/components/Home/CoachPlanCard", () => () => (
  <div data-testid="coach-plan-sentinel" />
), { virtual: true });

import HomePageNew from "./HomePageNew";

describe("coach pages over the curriculum home", () => {
  let container, root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    global.IntersectionObserver = class {
      observe() {} unobserve() {} disconnect() {}
    };
    global.fetch = jest.fn((url) => {
      const body = String(url).includes("/home/dashboard-v2") ? { games_analyzed: 31, games_imported: 62 } : {};
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
    });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    delete global.fetch;
  });

  async function render(user) {
    await act(async () => root.render(<HomePageNew user={user} />));
    await act(async () => { for (let i = 0; i < 25; i += 1) await Promise.resolve(); });
  }

  test("a super-admin in the coach-pages flag sees the coach plan, not the curriculum home", async () => {
    await render({ role: "super_admin", email: "owner@test", coach_pages: true });
    expect(container.querySelector("[data-testid='coach-plan-sentinel']")).toBeTruthy();
    expect(container.querySelector("[data-testid='curriculum-home-sentinel']")).toBeNull();
  });

  test("an admin without the coach pages still gets the curriculum home", async () => {
    await render({ role: "super_admin", email: "owner@test", coach_pages: false });
    expect(container.querySelector("[data-testid='curriculum-home-sentinel']")).toBeTruthy();
    expect(container.querySelector("[data-testid='coach-plan-sentinel']")).toBeNull();
  });
});
