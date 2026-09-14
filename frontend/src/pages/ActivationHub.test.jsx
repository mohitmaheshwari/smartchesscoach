import { act } from "react";
import { createRoot } from "react-dom/client";
import ActivationHub from "./ActivationHub";


const mockNavigate = jest.fn();

jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}), { virtual: true });
jest.mock("@/App", () => ({ API: "https://api.test/api" }), { virtual: true });
jest.mock("@/lib/analytics", () => ({
  ANALYTICS_EVENTS: { FUNNEL_ACTIVATION_CTA: "funnel_activation_cta" },
  track: jest.fn(),
}), { virtual: true });


describe("ActivationHub", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    mockNavigate.mockReset();
    // Two different requests leave this page, and they are not the same story.
    // /onboarding/status decides whether the hub renders at all (an activated
    // user is redirected instead, so it deliberately renders nothing until the
    // answer arrives). The profile save is the one that must NEVER block a
    // button. Resolve the first, leave the second pending -- which is exactly
    // what these tests are about.
    global.fetch = jest.fn((url) => {
      if (String(url).includes("/onboarding/status")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ needs_onboarding: true }),
        });
      }
      return new Promise(() => {});
    });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  // async act so the status check settles and the hub actually renders.
  const renderHub = () => act(async () => { root.render(<ActivationHub />); });
  const click = (testId) => act(() => {
    container.querySelector(`[data-testid="${testId}"]`).dispatchEvent(
      new MouseEvent("click", { bubbles: true })
    );
  });

  test("opens diagnostic immediately even while profile save is pending", async () => {
    await renderHub();

    click("hub-diagnostic");

    expect(mockNavigate).toHaveBeenCalledWith("/diagnostic", {
      state: { fromActivationHub: true },
    });
    expect(global.fetch).toHaveBeenCalledWith(
      "https://api.test/api/settings/profile",
      expect.objectContaining({ method: "POST", keepalive: true })
    );
  });

  // --- the level question has to be ON the screen the player actually sees ---
  //
  // It was built for players with no chess.com or Lichess account, and it was
  // put on /onboarding -- which is reachable only through the "Already play on
  // Chess.com or Lichess?" link. So the one question written for people
  // without an account was shown only to people who had one, and a new player
  // went into the diagnostic with no rating at all behind the selection.

  test("asks where the player is with chess, before either door", async () => {
    await renderHub();

    for (const value of ["learning_moves", "know_rules", "plays_regularly",
                         "experienced"]) {
      expect(
        container.querySelector(`[data-testid="hub-self-level-${value}"]`)
      ).not.toBeNull();
    }

    // Order matters: clicking a door navigates away immediately, so an answer
    // rendered below the doors would arrive too late to pick the tier.
    const html = container.innerHTML;
    expect(html.indexOf('hub-self-level-learning_moves'))
      .toBeLessThan(html.indexOf('hub-diagnostic'));
  });

  test("sends the chosen level with the profile save", async () => {
    await renderHub();

    click("hub-self-level-plays_regularly");
    click("hub-diagnostic");

    const call = global.fetch.mock.calls.find(
      ([url]) => String(url).includes("/settings/profile")
    );
    expect(JSON.parse(call[1].body)).toEqual(
      expect.objectContaining({ self_assessed_level: "plays_regularly" })
    );
  });

  test("neither door is gated on answering it", async () => {
    // Optional by design. A question that blocks the value action would cost
    // more than the tier it buys -- the hub exists because 32% of arrivals
    // were dead on arrival.
    await renderHub();

    click("hub-diagnostic");

    expect(mockNavigate).toHaveBeenCalledWith("/diagnostic", {
      state: { fromActivationHub: true },
    });
    const call = global.fetch.mock.calls.find(
      ([url]) => String(url).includes("/settings/profile")
    );
    expect(JSON.parse(call[1].body).self_assessed_level).toBeNull();
  });

  // --- the connect option is offered well, but not offered first ------------
  //
  // Real games are the strongest coaching evidence and a bare text link
  // undersold that. But the hub exists because leading with the account ask
  // left 32% of signups dead on arrival, so a stronger affordance must not
  // become a higher position.

  test("offers connecting real games as a card, not a bare link", async () => {
    await renderHub();

    const connect = container.querySelector('[data-testid="hub-connect"]');
    expect(connect).not.toBeNull();
    expect(connect.textContent).toMatch(/Chess\.com or Lichess/);
    // A card states the benefit; a link just points somewhere.
    expect(connect.textContent).toMatch(/games you already played/);
  });

  test("keeps both no-account doors above the connect card", async () => {
    await renderHub();

    const html = container.innerHTML;
    expect(html.indexOf('hub-diagnostic')).toBeLessThan(html.indexOf('hub-connect'));
    expect(html.indexOf('hub-play')).toBeLessThan(html.indexOf('hub-connect'));
  });

  test("connecting does not mark the user activated on the way out", async () => {
    // Activation is finished in Onboarding, once an account is verified and
    // its games import. Someone who opens this and backs out is not activated,
    // so the hub must not complete onboarding for them.
    await renderHub();

    click("hub-connect");

    expect(mockNavigate).toHaveBeenCalledWith("/onboarding");
    const saved = global.fetch.mock.calls.filter(
      ([url]) => String(url).includes("/settings/profile")
    );
    expect(saved).toHaveLength(0);
  });

  test("opens Coach Play immediately even while profile save is pending", async () => {
    await renderHub();

    click("hub-play");

    expect(mockNavigate).toHaveBeenCalledWith("/play-with-coach", {
      state: { fromActivationHub: true },
    });
  });
});
