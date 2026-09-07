import { act } from "react";
import { createRoot } from "react-dom/client";
import Onboarding from "./Onboarding";


const mockNavigate = jest.fn();
const mockTrack = jest.fn();

jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}), { virtual: true });
jest.mock("@/App", () => ({ API: "https://api.test/api" }), { virtual: true });
jest.mock("@/lib/analytics", () => ({
  ANALYTICS_EVENTS: {
    FUNNEL_FIRST_AHA: "funnel_first_aha",
    FUNNEL_IMPORT_DONE: "funnel_import_done",
  },
  track: (...args) => mockTrack(...args),
}), { virtual: true });
jest.mock("@/components/InstantDNA", () => () => null, { virtual: true });


const response = (body, ok = true) => ({
  ok,
  json: () => Promise.resolve(body),
});


describe("Onboarding", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    mockNavigate.mockReset();
    mockTrack.mockReset();
    global.fetch = jest.fn((url) => {
      if (url.endsWith("/auth/me")) return Promise.resolve(response({}, false));
      if (url.endsWith("/settings/link-account")) {
        return Promise.resolve(response({ assessed_rating: 1210, games_analyzed: 12 }));
      }
      if (url.endsWith("/settings/profile")) return Promise.resolve(response({ message: "saved" }));
      if (url.endsWith("/import-games")) return Promise.resolve(response({ imported: 12, total_found: 12 }));
      if (url.endsWith("/journey/first-aha")) {
        return Promise.resolve(response({ game_id: "game_123", was_loss: true }));
      }
      return Promise.resolve(response({}, false));
    });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  const flush = () => act(async () => {
    await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
  const byTestId = (testId) => container.querySelector(`[data-testid="${testId}"]`);
  const click = (testId) => act(() => {
    byTestId(testId).dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
  const change = (testId, value) => act(() => {
    const input = byTestId(testId);
    const setter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      "value"
    ).set;
    setter.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });

  test("verifies through ChessGuru, advances, and opens the first game", async () => {
    await act(async () => root.render(<Onboarding />));

    change("chesscom-input", "ExamplePlayer");
    click("verify-chesscom-btn");
    await flush();

    expect(container.textContent).toContain("Account verified");

    expect(global.fetch).toHaveBeenCalledWith(
      "https://api.test/api/settings/link-account",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        body: JSON.stringify({ platform: "chess.com", username: "exampleplayer" }),
      })
    );
    expect(global.fetch.mock.calls.some(([url]) => url.includes("api.chess.com"))).toBe(false);

    click("step1-continue-btn");
    expect(container.textContent).toContain("What do you want from your chess?");

    click("focus-tactics");
    click("motivation-improve");
    click("complete-onboarding-btn");
    await flush();

    expect(global.fetch).toHaveBeenCalledWith(
      "https://api.test/api/import-games",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        body: JSON.stringify({ platform: "chess.com", username: "exampleplayer" }),
      })
    );
    expect(global.fetch.mock.calls.some(([url]) => url.endsWith("/games/sync"))).toBe(false);
    const importCall = global.fetch.mock.calls.findIndex(([url]) => url.endsWith("/import-games"));
    const profileCall = global.fetch.mock.calls.findIndex(([url]) => url.endsWith("/settings/profile"));
    expect(importCall).toBeGreaterThan(-1);
    expect(profileCall).toBeGreaterThan(importCall);
    expect(mockTrack).toHaveBeenCalledWith("funnel_import_done", {
      source: "onboarding",
      status: "new_games",
      total_items: 12,
    });
    expect(mockNavigate).toHaveBeenCalledWith("/game/game_123");
  });

  test("stops visibly and emits no completion when game import fails", async () => {
    global.fetch = jest.fn((url) => {
      if (url.endsWith("/auth/me")) return Promise.resolve(response({}, false));
      if (url.endsWith("/settings/link-account")) {
        return Promise.resolve(response({ assessed_rating: 1210 }));
      }
      if (url.endsWith("/settings/profile")) return Promise.resolve(response({ message: "saved" }));
      if (url.endsWith("/import-games")) {
        return Promise.resolve(response({ detail: "Chess.com is temporarily unavailable" }, false));
      }
      if (url.endsWith("/journey/first-aha")) {
        return Promise.resolve(response({ game_id: "must_not_open" }));
      }
      return Promise.resolve(response({}, false));
    });

    await act(async () => root.render(<Onboarding />));
    change("chesscom-input", "ExamplePlayer");
    click("verify-chesscom-btn");
    await flush();
    click("step1-continue-btn");
    click("focus-tactics");
    click("motivation-improve");
    click("complete-onboarding-btn");
    await flush();

    expect(container.textContent).toContain("Chess.com is temporarily unavailable");
    expect(mockTrack).not.toHaveBeenCalledWith("funnel_import_done", expect.anything());
    expect(global.fetch.mock.calls.some(([url]) => url.endsWith("/settings/profile"))).toBe(false);
    expect(mockNavigate).not.toHaveBeenCalledWith("/game/must_not_open");
  });

  test("does not mark an account verified when the backend rejects it", async () => {
    global.fetch = jest.fn((url) => {
      if (url.endsWith("/auth/me")) return Promise.resolve(response({}, false));
      return Promise.resolve(response({ detail: "Chess.com username not found" }, false));
    });

    await act(async () => root.render(<Onboarding />));
    change("chesscom-input", "missing-player");
    click("verify-chesscom-btn");
    await flush();

    expect(container.textContent).toContain("Chess.com username not found");
    expect(container.textContent).not.toContain("Account verified");
    expect(byTestId("step1-continue-btn").disabled).toBe(true);
  });

  test("restores a previously verified account as a retryable import after reload", async () => {
    global.fetch = jest.fn((url) => {
      if (url.endsWith("/auth/me")) {
        return Promise.resolve(response({ chess_com_username: "SavedPlayer" }));
      }
      return Promise.resolve(response({}, false));
    });

    await act(async () => root.render(<Onboarding />));
    await flush();

    expect(byTestId("chesscom-input").value).toBe("SavedPlayer");
    expect(container.textContent).toContain("Account verified");
    expect(byTestId("step1-continue-btn").disabled).toBe(false);
    expect(mockNavigate).not.toHaveBeenCalledWith("/training");
  });

  test("treats an already-current account as a successful import boundary", async () => {
    global.fetch = jest.fn((url) => {
      if (url.endsWith("/auth/me")) return Promise.resolve(response({}, false));
      if (url.endsWith("/settings/link-account")) {
        return Promise.resolve(response({ assessed_rating: 1210 }));
      }
      if (url.endsWith("/import-games")) {
        return Promise.resolve(response({ imported: 0, total_found: 20 }));
      }
      if (url.endsWith("/settings/profile")) return Promise.resolve(response({ message: "saved" }));
      if (url.endsWith("/journey/first-aha")) {
        return Promise.resolve(response({ game_id: "existing_game", was_loss: false }));
      }
      return Promise.resolve(response({}, false));
    });

    await act(async () => root.render(<Onboarding />));
    change("chesscom-input", "ExistingPlayer");
    click("verify-chesscom-btn");
    await flush();
    click("step1-continue-btn");
    click("focus-tactics");
    click("motivation-improve");
    click("complete-onboarding-btn");
    await flush();

    expect(mockTrack).toHaveBeenCalledWith("funnel_import_done", {
      source: "onboarding",
      status: "already_current",
      total_items: 0,
    });
    expect(mockNavigate).toHaveBeenCalledWith("/game/existing_game");
  });

  test("imports every account verified in the onboarding session", async () => {
    global.fetch = jest.fn((url, options = {}) => {
      if (url.endsWith("/auth/me")) return Promise.resolve(response({}, false));
      if (url.endsWith("/settings/link-account")) {
        return Promise.resolve(response({ assessed_rating: 1210 }));
      }
      if (url.endsWith("/import-games")) {
        const { platform } = JSON.parse(options.body);
        return Promise.resolve(response({ imported: platform === "chess.com" ? 3 : 2 }));
      }
      if (url.endsWith("/settings/profile")) return Promise.resolve(response({ message: "saved" }));
      if (url.endsWith("/journey/first-aha")) {
        return Promise.resolve(response({ game_id: "dual_account_game", was_loss: true }));
      }
      return Promise.resolve(response({}, false));
    });

    await act(async () => root.render(<Onboarding />));
    change("chesscom-input", "ChessPlayer");
    click("verify-chesscom-btn");
    await flush();
    change("lichess-input", "LichessPlayer");
    click("verify-lichess-btn");
    await flush();
    click("step1-continue-btn");
    click("focus-tactics");
    click("motivation-improve");
    click("complete-onboarding-btn");
    await flush();

    const importBodies = global.fetch.mock.calls
      .filter(([url]) => url.endsWith("/import-games"))
      .map(([, options]) => JSON.parse(options.body));
    expect(importBodies).toEqual([
      { platform: "chess.com", username: "chessplayer" },
      { platform: "lichess", username: "lichessplayer" },
    ]);
    expect(mockTrack).toHaveBeenCalledWith("funnel_import_done", {
      source: "onboarding",
      status: "new_games",
      total_items: 5,
    });
  });
});
