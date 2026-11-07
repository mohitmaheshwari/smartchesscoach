import { act } from "react";
import { createRoot } from "react-dom/client";
import Landing from "./Landing";

const mockNavigate = jest.fn();
const mockTrack = jest.fn();

jest.mock("react-router-dom", () => ({ useNavigate: () => mockNavigate }), { virtual: true });
jest.mock("framer-motion", () => {
  const React = require("react");
  const cache = {};
  const motion = new Proxy({}, {
    get: (_, tag) => {
      if (!cache[tag]) {
        cache[tag] = React.forwardRef(({
          children, initial, animate, exit, transition, whileInView,
          whileHover, whileTap, viewport, ...props
        }, ref) => React.createElement(tag, { ...props, ref }, children));
      }
      return cache[tag];
    },
  });
  return {
    motion,
    AnimatePresence: ({ children }) => children,
    useReducedMotion: () => true,
  };
});
jest.mock("@/App", () => ({ API: "https://api.test/api" }), { virtual: true });
jest.mock("@/lib/analytics", () => ({
  ANALYTICS_EVENTS: {
    FUNNEL_LANDING_VIEWED: "funnel_landing_viewed",
    FUNNEL_LANDING_CTA_CLICKED: "funnel_landing_cta_clicked",
  },
  track: (...args) => mockTrack(...args),
}), { virtual: true });

describe("outcome-led Landing", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    mockNavigate.mockReset();
    mockTrack.mockReset();
    window.sessionStorage.clear();
    global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({ dev_mode: false, signups_open: true }) });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  const renderLanding = async () => {
    await act(async () => root.render(<Landing />));
  };

  test("leads with a measurable personal improvement promise", async () => {
    await renderLanding();

    expect(container.textContent).toContain("Your next rating milestone needs a plan built from your games.");
    expect(container.textContent).toContain("Did the mistake stop happening?");
    expect(container.textContent).toContain("A sample coaching conversation");
    expect(container.textContent).toContain("A sample message from your coach");
    expect(mockTrack).toHaveBeenCalledWith("funnel_landing_viewed");
  });

  test("preserves public pricing and legal destinations", async () => {
    await renderLanding();

    for (const href of ["/pricing", "/terms", "/privacy", "/refund", "/contact"]) {
      expect(container.querySelector(`a[href="${href}"]`)).not.toBeNull();
    }
  });

  test("starts the plan through auth and preserves the welcome destination", async () => {
    await renderLanding();
    global.fetch.mockResolvedValueOnce({ ok: true, json: async () => ({}) });

    await act(async () => {
      container.querySelector('[data-testid="hero-cta-button"]').dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(window.sessionStorage.getItem("post_auth_redirect")).toBe("/welcome");
    expect(global.fetch).toHaveBeenCalledWith(
      "https://api.test/api/auth/google/login?redirect_to=%2Fwelcome",
      { credentials: "include" }
    );
    expect(mockNavigate).toHaveBeenCalledWith("/login?redirect_to=%2Fwelcome");
    expect(mockTrack).toHaveBeenCalledWith("funnel_landing_cta_clicked", { source: "hero" });
  });

  test("speaks to parents and coaches, states the belief and promises nothing", async () => {
    await renderLanding();
    const section = container.querySelector("#families");
    expect(section.textContent).toContain("Many parents choose chess for their child\u2019s brain development.");
    expect(section.textContent).toContain("the thinking habits behind it, week by week");
    expect(section.textContent.toLowerCase()).not.toMatch(/improves|boosts|guarantee|iq\b/);
  });

  test.each([
    ["families-parent-button", "families_parent"],
    ["families-coach-button", "families_coach"],
  ])("%s goes to sign-up and then to the academy page", async (testId, source) => {
    await renderLanding();
    await act(async () => {
      container.querySelector(`[data-testid="${testId}"]`).dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(window.sessionStorage.getItem("post_auth_redirect")).toBe("/academy");
    expect(mockNavigate).toHaveBeenCalledWith("/login?signup=1&redirect_to=%2Facademy");
    expect(mockTrack).toHaveBeenCalledWith("funnel_landing_cta_clicked", { source });
  });

  test("the family buttons ask for an invite while sign-ups are closed", async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({ signups_open: false }) });
    await renderLanding();
    await act(async () => {
      container.querySelector('[data-testid="families-coach-button"]').dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(mockNavigate).toHaveBeenCalledWith("/invite?from=families_coach");
    expect(window.sessionStorage.getItem("post_auth_redirect")).toBeNull();
  });
});
