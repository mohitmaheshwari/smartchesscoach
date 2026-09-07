import React, { act } from "react";
import { createRoot } from "react-dom/client";

import PlateauBreakerDashboard from "./PlateauBreakerDashboard";
import PlateauBreakerReview from "./PlateauBreakerReview";


let mockGameId = "game-1";
let mockBlocker = { type: "piece_safety" };
const mockNavigate = jest.fn();

jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
  useParams: () => ({ gameId: mockGameId }),
  useLocation: () => ({ state: { blocker: mockBlocker } }),
}), { virtual: true });
jest.mock("@/components/Layout", () => ({ children }) => <div>{children}</div>, { virtual: true });
jest.mock("@/components/LichessBoard", () => () => <div>board</div>, { virtual: true });
jest.mock("@/components/ClickableLine", () => () => <div>line</div>, { virtual: true });
jest.mock("@/components/streak", () => ({ MistakeFreeStreak: () => <div>streak</div> }), { virtual: true });
jest.mock("@/components/patterns/YourPatterns", () => () => <div>patterns</div>, { virtual: true });


const response = (body) => ({ ok: true, json: () => Promise.resolve(body) });


describe("identity-scoped page loads", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    mockGameId = "game-1";
    mockBlocker = { type: "piece_safety" };
    mockNavigate.mockReset();
    localStorage.clear();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    delete global.fetch;
  });

  const flush = () => act(async () => {
    await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });

  test("dashboard loads once per user id, not per user object", async () => {
    global.fetch = jest.fn((url) => {
      if (url.includes("/coach/deep-memory")) {
        return Promise.resolve(response({ games_analyzed: 3, identity: { blunder_taxonomy: {} } }));
      }
      if (url.includes("/games?")) return Promise.resolve(response({ games: [] }));
      if (url.includes("/streak/status")) return Promise.resolve(response({}));
      throw new Error(`Unexpected URL ${url}`);
    });

    await act(async () => root.render(
      <PlateauBreakerDashboard user={{ user_id: "student-1" }} />
    ));
    await flush();
    expect(global.fetch).toHaveBeenCalledTimes(3);

    await act(async () => root.render(
      <PlateauBreakerDashboard user={{ user_id: "student-1", name: "same player" }} />
    ));
    await flush();
    expect(global.fetch).toHaveBeenCalledTimes(3);

    await act(async () => root.render(
      <PlateauBreakerDashboard user={{ user_id: "student-2" }} />
    ));
    await flush();
    expect(global.fetch).toHaveBeenCalledTimes(6);
    expect(global.fetch.mock.calls.slice(3).map(([url]) => url)).toEqual([
      "https://api.test/coach/deep-memory?user_id=student-2",
      "https://api.test/games?user_id=student-2&limit=10",
      "https://api.test/streak/status?user_id=student-2",
    ]);
  });

  test("review reloads for game, blocker, or user identity changes", async () => {
    global.fetch = jest.fn((url) => {
      if (url.includes("/games/")) return Promise.resolve(response({ user_color: "white" }));
      if (url.includes("/analysis/")) {
        return Promise.resolve(response({ stockfish_analysis: { move_evaluations: [] } }));
      }
      if (url.includes("/coach/patterns/for-mistake/")) return Promise.resolve(response({}));
      if (url.includes("/coach/deep-memory")) {
        return Promise.resolve(response({ identity: { blunder_taxonomy: { by_type: {} } } }));
      }
      throw new Error(`Unexpected URL ${url}`);
    });

    await act(async () => root.render(
      <PlateauBreakerReview user={{ user_id: "student-1" }} />
    ));
    await flush();
    expect(global.fetch).toHaveBeenCalledTimes(4);

    await act(async () => root.render(
      <PlateauBreakerReview user={{ user_id: "student-1", name: "same player" }} />
    ));
    await flush();
    expect(global.fetch).toHaveBeenCalledTimes(4);

    mockBlocker = { type: "king_safety" };
    await act(async () => root.render(
      <PlateauBreakerReview user={{ user_id: "student-1" }} />
    ));
    await flush();
    expect(global.fetch).toHaveBeenCalledTimes(8);
    expect(global.fetch.mock.calls[6][0]).toBe(
      "https://api.test/coach/patterns/for-mistake/king_safety"
    );

    await act(async () => root.render(
      <PlateauBreakerReview user={{ user_id: "student-2" }} />
    ));
    await flush();
    expect(global.fetch).toHaveBeenCalledTimes(12);
    expect(global.fetch.mock.calls[11][0]).toBe(
      "https://api.test/coach/deep-memory?user_id=student-2"
    );

    mockGameId = "game-2";
    await act(async () => root.render(
      <PlateauBreakerReview user={{ user_id: "student-2" }} />
    ));
    await flush();
    expect(global.fetch).toHaveBeenCalledTimes(16);
    expect(global.fetch.mock.calls[12][0]).toBe("https://api.test/games/game-2");
  });
});
