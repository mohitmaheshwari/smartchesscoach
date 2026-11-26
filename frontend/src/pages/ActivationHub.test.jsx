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
  const el = (testId) => container.querySelector(`[data-testid="${testId}"]`);
  const click = (testId) => act(() => {
    el(testId).dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
  const savedProfileCalls = () => global.fetch.mock.calls.filter(
    ([url]) => String(url).includes("/settings/profile")
  );

  // The flow is: why you came -> do you play online -> where we start.
  const toAccountStep = async () => { await renderHub(); click("hub-motivation-improve"); };
  const toStartStep = async () => { await toAccountStep(); click("hub-no-account"); };

  // --- the order Mohit asked for, 2026-11-26 ------------------------------
  //
  // "We should first pull up user reason for joining, once they join us, if
  // they have an online account, and then the third section."

  test("asks why you came first, and nothing else", async () => {
    await renderHub();

    expect(el("hub-step").textContent).toBe("Step 1 of 3");
    expect(el("hub-motivation-improve")).not.toBeNull();
    // Not the account, and not the doors -- one question at a time.
    expect(el("hub-connect")).toBeNull();
    expect(el("hub-diagnostic")).toBeNull();
    expect(el("hub-play")).toBeNull();
  });

  test("asks about an online account second, after the reason", async () => {
    await toAccountStep();

    expect(el("hub-step").textContent).toBe("Step 2 of 3");
    expect(el("hub-connect")).not.toBeNull();
    expect(el("hub-diagnostic")).toBeNull();
  });

  test("offers the two ways to start third", async () => {
    await toStartStep();

    expect(el("hub-step").textContent).toBe("Step 3 of 3");
    expect(el("hub-diagnostic")).not.toBeNull();
    expect(el("hub-play")).not.toBeNull();
  });

  test("keeps the reason the player gave", async () => {
    await toStartStep();

    click("hub-diagnostic");

    expect(JSON.parse(savedProfileCalls()[0][1].body)).toEqual(
      expect.objectContaining({ player_motivation: "improve" })
    );
  });

  test("you can decline to give a reason and still go on", async () => {
    await renderHub();

    click("hub-skip-motivation");

    expect(el("hub-step").textContent).toBe("Step 2 of 3");
  });

  test("you can go back and change an answer", async () => {
    await toAccountStep();

    click("hub-back");

    expect(el("hub-step").textContent).toBe("Step 1 of 3");
    expect(el("hub-motivation-improve")).not.toBeNull();
  });

  // --- the account ask must never become a wall again ---------------------
  //
  // docs/activation_hub_scope.md:9 -- 32% of signups were dead on arrival
  // because onboarding demanded a chess account BEFORE delivering any value.
  // Step 2 asks; it must never require. These two are that guarantee, and
  // they replace the old "keep both doors above the connect card", which
  // said the same thing back when everything shared one screen.

  test("the account step can always be passed in one tap", async () => {
    await toAccountStep();

    const skip = el("hub-no-account");
    expect(skip).not.toBeNull();
    // Equally weighted, not a hidden escape: same card shape as the connect
    // option, and it says what happens instead.
    expect(skip.className).toMatch(/w-full/);
    expect(skip.textContent).toMatch(/Not yet/);
  });

  test("both doors are reachable without ever connecting an account", async () => {
    await toStartStep();

    click("hub-diagnostic");

    expect(mockNavigate).toHaveBeenCalledWith("/diagnostic", {
      state: { fromActivationHub: true },
    });
    // Nothing on the way here demanded an account.
    expect(mockNavigate).not.toHaveBeenCalledWith("/onboarding");
  });

  test("the first screen never mentions linking an account", async () => {
    // The wall was not only a required field -- it was the first thing a new
    // player saw. Asking on screen one, even softly, rebuilds the impression.
    await renderHub();

    expect(container.textContent).not.toMatch(/Chess\.com|Lichess|connect/i);
  });

  // --- the doors still work the moment they are pressed -------------------

  test("opens diagnostic immediately even while profile save is pending", async () => {
    await toStartStep();

    click("hub-diagnostic");

    expect(mockNavigate).toHaveBeenCalledWith("/diagnostic", {
      state: { fromActivationHub: true },
    });
    expect(global.fetch).toHaveBeenCalledWith(
      "https://api.test/api/settings/profile",
      expect.objectContaining({ method: "POST", keepalive: true })
    );
  });

  test("opens Coach Play immediately even while profile save is pending", async () => {
    await toStartStep();

    click("hub-play");

    expect(mockNavigate).toHaveBeenCalledWith("/play-with-coach", {
      state: { fromActivationHub: true },
    });
    expect(global.fetch).toHaveBeenCalledWith(
      "https://api.test/api/settings/profile",
      expect.objectContaining({ method: "POST", keepalive: true })
    );
  });

  // --- the level question has to be ON the screen the player actually sees -
  //
  // It was built for players with no chess.com or Lichess account, and it was
  // put on /onboarding -- reachable only through the "Already play on
  // Chess.com or Lichess?" link. So the one question written for people
  // without an account was shown only to people who had one. It now sits on
  // step 3, which is reached precisely by saying you have no account.

  test("asks where the player is with chess, before either door", async () => {
    await toStartStep();

    for (const value of ["learning_moves", "know_rules", "plays_regularly",
                         "experienced"]) {
      expect(el(`hub-self-level-${value}`)).not.toBeNull();
    }

    // Order matters: clicking a door navigates away immediately, so an answer
    // rendered below the doors would arrive too late to pick the tier.
    const html = container.innerHTML;
    expect(html.indexOf('hub-self-level-learning_moves'))
      .toBeLessThan(html.indexOf('hub-diagnostic'));
  });

  test("sends the chosen level with the profile save", async () => {
    await toStartStep();

    click("hub-self-level-plays_regularly");
    click("hub-diagnostic");

    expect(JSON.parse(savedProfileCalls()[0][1].body)).toEqual(
      expect.objectContaining({ self_assessed_level: "plays_regularly" })
    );
  });

  test("neither door is gated on answering it", async () => {
    // Optional by design. A question that blocks the value action would cost
    // more than the tier it buys -- the hub exists because 32% of arrivals
    // were dead on arrival.
    await toStartStep();

    click("hub-diagnostic");

    expect(mockNavigate).toHaveBeenCalledWith("/diagnostic", {
      state: { fromActivationHub: true },
    });
    expect(JSON.parse(savedProfileCalls()[0][1].body).self_assessed_level).toBeNull();
  });

  // --- the connect option is offered well -------------------------------

  test("offers connecting real games as a card, not a bare link", async () => {
    await toAccountStep();

    const connect = el("hub-connect");
    expect(connect).not.toBeNull();
    expect(connect.textContent).toMatch(/Chess\.com or Lichess/);
    // A card states the benefit; a link just points somewhere.
    expect(connect.textContent).toMatch(/games you already played/);
  });

  test("connecting does not mark the user activated on the way out", async () => {
    // Activation is finished in Onboarding, once an account is verified and
    // its games import. Someone who opens this and backs out is not activated,
    // so the hub must not complete onboarding for them.
    await toAccountStep();

    click("hub-connect");

    expect(mockNavigate).toHaveBeenCalledWith("/onboarding");
    expect(savedProfileCalls()).toHaveLength(0);
  });

  // --- the hierarchy has to be visible, not just ordered ------------------
  //
  // Codex built an elevated card -- gradient, lifted shadow, lime arrow --
  // and put it on "connect your account", which would have inverted the
  // hub's whole reason for existing. The craft was right and the placement
  // was wrong, so the treatment moved to the action that IS primary.

  test("the primary action carries the elevated treatment", async () => {
    await toStartStep();

    const primary = el("hub-diagnostic");
    expect(primary.className).toMatch(/rounded-2xl/);
    expect(primary.className).toMatch(/border-2/);
  });

  test("the connect card is not dressed as THE action", async () => {
    // Now on its own step, so it cannot be compared in one DOM with the
    // primary. The rule it has to keep is the same: connecting is an offer,
    // never the headline.
    await toAccountStep();

    const connect = el("hub-connect");
    expect(connect.className).not.toMatch(/border-2/);
    expect(connect.textContent).not.toMatch(/recommended/i);
  });

  test("every action is reachable and visible without a mouse", async () => {
    // An arrow that only appears on hover does not exist for keyboard or
    // touch users, and a control with no focus ring cannot be tabbed to
    // visibly.
    await toAccountStep();
    for (const id of ["hub-connect", "hub-no-account"]) {
      expect(el(id).className).toMatch(/focus-visible:ring-2/);
    }
    expect(container.innerHTML).not.toMatch(/opacity-0 group-hover:opacity-100/);

    click("hub-no-account");
    for (const id of ["hub-diagnostic", "hub-play"]) {
      expect(el(id).className).toMatch(/focus-visible:ring-2/);
    }
    expect(container.innerHTML).not.toMatch(/opacity-0 group-hover:opacity-100/);
  });

  test("every tappable thing clears the 44px floor", async () => {
    // Phone first. These were 34-38px tall on one screen before the split.
    await renderHub();
    expect(el("hub-motivation-improve").className).toMatch(/min-h-\[44px\]/);
    expect(el("hub-skip-motivation").className).toMatch(/min-h-\[44px\]/);

    click("hub-motivation-improve");
    expect(el("hub-back").className).toMatch(/min-h-\[44px\]/);

    click("hub-no-account");
    expect(el("hub-self-level-know_rules").className).toMatch(/min-h-\[44px\]/);
  });
});
