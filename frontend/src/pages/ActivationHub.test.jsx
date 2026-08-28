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
    global.fetch = jest.fn(() => new Promise(() => {}));
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  const renderHub = () => act(() => root.render(<ActivationHub />));
  const click = (testId) => act(() => {
    container.querySelector(`[data-testid="${testId}"]`).dispatchEvent(
      new MouseEvent("click", { bubbles: true })
    );
  });

  test("opens diagnostic immediately even while profile save is pending", () => {
    renderHub();

    click("hub-diagnostic");

    expect(mockNavigate).toHaveBeenCalledWith("/diagnostic", {
      state: { fromActivationHub: true },
    });
    expect(global.fetch).toHaveBeenCalledWith(
      "https://api.test/api/settings/profile",
      expect.objectContaining({ method: "POST", keepalive: true })
    );
  });

  test("opens Coach Play immediately even while profile save is pending", () => {
    renderHub();

    click("hub-play");

    expect(mockNavigate).toHaveBeenCalledWith("/play-with-coach", {
      state: { fromActivationHub: true },
    });
  });
});
