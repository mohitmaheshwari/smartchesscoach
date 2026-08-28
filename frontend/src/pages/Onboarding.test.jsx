import { act } from "react";
import { createRoot } from "react-dom/client";
import Onboarding from "./Onboarding";


const mockNavigate = jest.fn();

jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}), { virtual: true });
jest.mock("@/App", () => ({ API: "https://api.test/api" }), { virtual: true });
jest.mock("@/lib/analytics", () => ({
  ANALYTICS_EVENTS: { FUNNEL_FIRST_AHA: "funnel_first_aha" },
  track: jest.fn(),
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
    global.fetch = jest.fn((url) => {
      if (url.endsWith("/auth/me")) return Promise.resolve(response({}, false));
      if (url.endsWith("/settings/link-account")) {
        return Promise.resolve(response({ assessed_rating: 1210, games_analyzed: 12 }));
      }
      if (url.endsWith("/settings/profile")) return Promise.resolve(response({ message: "saved" }));
      if (url.endsWith("/games/sync")) return Promise.resolve(response({ synced: 12 }));
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
    expect(container.textContent).toContain("Calibrate Your Profile");

    click("focus-tactics");
    click("motivation-improve");
    click("complete-onboarding-btn");
    await flush();

    expect(mockNavigate).toHaveBeenCalledWith("/game/game_123");
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
});
