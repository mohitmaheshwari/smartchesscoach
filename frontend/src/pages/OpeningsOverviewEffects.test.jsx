import React, { act } from "react";
import { createRoot } from "react-dom/client";

import OpeningsOverview from "./OpeningsOverview";

jest.mock("react-router-dom", () => ({
  useNavigate: () => jest.fn(),
  useSearchParams: () => [new URLSearchParams(), jest.fn()],
}), { virtual: true });
jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("@/components/Layout", () => ({ children }) => <div>{children}</div>, { virtual: true });
jest.mock("@/components/LichessBoard", () => () => <div>Board</div>, { virtual: true });
jest.mock("@/lib/analytics", () => ({
  ANALYTICS_EVENTS: { EXPLORE_OPENED: "explore_opened" },
  trackCurriculum: jest.fn(),
}), { virtual: true });
jest.mock("framer-motion", () => ({
  motion: { div: ({ children, ...props }) => <div {...props}>{children}</div> },
  AnimatePresence: ({ children }) => <>{children}</>,
}));

const response = (body) => ({ ok: true, json: () => Promise.resolve(body) });
const deferred = () => { let resolve; const promise = new Promise((done) => { resolve = done; }); return { promise, resolve }; };

describe("OpeningsOverview account-owned loading", () => {
  let container;
  let root;

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

  const flush = () => act(async () => { await Promise.resolve(); await new Promise((done) => setTimeout(done, 0)); });

  test("a late profile from the prior account cannot replace the current repertoire", async () => {
    const oldProfile = deferred();
    let profileCount = 0;
    global.fetch = jest.fn((url) => {
      if (url.endsWith("/openings/repertoire")) return Promise.resolve(response({ white_repertoire: [], black_repertoire: [] }));
      if (url.endsWith("/training/opening-progress")) return Promise.resolve(response({ progress: [] }));
      if (url.endsWith("/openings/profile")) {
        profileCount += 1;
        return profileCount === 1
          ? oldProfile.promise
          : Promise.resolve(response({ total_analyzed_games: 22, white: {}, black: {}, recurring_deviations: [] }));
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    await act(async () => root.render(<OpeningsOverview user={{ user_id: "old-user" }} />));
    await act(async () => root.render(<OpeningsOverview user={{ user_id: "current-user" }} />));
    await flush();
    expect(container.textContent).toContain("Your Repertoire (22 games)");

    oldProfile.resolve(response({ total_analyzed_games: 3, white: {}, black: {}, recurring_deviations: [] }));
    await flush();

    expect(container.textContent).toContain("Your Repertoire (22 games)");
    expect(container.textContent).not.toContain("Your Repertoire (3 games)");
    expect(profileCount).toBe(2);
  });

  test("a failed new-account load cannot reveal the prior account's repertoire", async () => {
    let requestCount = 0;
    global.fetch = jest.fn((url) => {
      const generation = Math.floor(requestCount / 3);
      requestCount += 1;
      if (generation > 0) return Promise.resolve({ ok: false });
      if (url.endsWith("/openings/repertoire")) {
        return Promise.resolve(response({ white_repertoire: [], black_repertoire: [] }));
      }
      if (url.endsWith("/training/opening-progress")) {
        return Promise.resolve(response({ progress: [] }));
      }
      if (url.endsWith("/openings/profile")) {
        return Promise.resolve(response({
          total_analyzed_games: 7,
          white: {},
          black: {},
          recurring_deviations: [],
        }));
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    await act(async () => root.render(<OpeningsOverview user={{ user_id: "old-user" }} />));
    await flush();
    expect(container.textContent).toContain("Your Repertoire (7 games)");

    await act(async () => root.render(<OpeningsOverview user={{ user_id: "current-user" }} />));
    await flush();

    expect(requestCount).toBe(6);
    expect(container.textContent).not.toContain("Your Repertoire (7 games)");
    expect(container.querySelector("[data-testid='your-repertoire-card']")).toBeNull();
  });
});
