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

  test("opens Coach Play immediately even while profile save is pending", async () => {
    await renderHub();

    click("hub-play");

    expect(mockNavigate).toHaveBeenCalledWith("/play-with-coach", {
      state: { fromActivationHub: true },
    });
  });
});
