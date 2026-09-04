import { act } from "react";
import { createRoot } from "react-dom/client";
import CurriculumStateStrip from "./CurriculumStateStrip";
import { resetPersonalCurriculumRequestsForTests } from "../../lib/personalCurriculum";

const mockNavigate = jest.fn();

jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}), { virtual: true });
jest.mock("../../App", () => ({ API: "https://api.test/api" }));

describe("CurriculumStateStrip", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    resetPersonalCurriculumRequestsForTests();
    mockNavigate.mockReset();
    global.fetch = jest.fn(() => Promise.resolve({
      ok: true,
      json: () => Promise.resolve({
        enabled: true,
        decision: {
          primary: {
            state: "can_do_alone",
            title: "Piece safety",
            destination: { href: "/training?personalized=1&kind=concept&lesson=piece_safety" },
          },
        },
      }),
    }));
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    delete global.fetch;
  });

  test("shows the shared state without inventing application or retention", async () => {
    await act(async () => {
      root.render(<CurriculumStateStrip user={{ user_id: "u1" }} surface="progress" />);
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(container.textContent).toContain("Can do alone");
    expect(container.textContent).toContain("We’re still making this feel natural");
    expect(container.textContent).toContain("I’ll watch for it the next time you play");
    expect(container.textContent).not.toContain("measured");
    expect(container.textContent).not.toContain("Reliable");

    act(() => container.querySelector("button").click());
    expect(mockNavigate).toHaveBeenCalledWith(
      "/training?personalized=1&kind=concept&lesson=piece_safety"
    );
  });

  test("shows the server-owned transfer verdict instead of inferring from practice", async () => {
    global.fetch.mockImplementation((url) => Promise.resolve({
      ok: true,
      json: () => Promise.resolve(
        url.endsWith("/progress/complete-coaching")
          ? {
              enabled: true,
              transfer: {
                verdict: "still_recurring",
                message: "The same decision appeared again in a later game, so this stays in your plan.",
              },
            }
          : {
              enabled: true,
              decision: {
                primary: {
                  state: "can_do_alone",
                  title: "Piece safety",
                  destination: { href: "/training?personalized=1&kind=concept&lesson=piece_safety" },
                },
              },
            }
      ),
    }));

    await act(async () => {
      root.render(<CurriculumStateStrip user={{ user_id: "u1" }} surface="progress" />);
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });

    const verdict = container.querySelector('[data-testid="phase8-transfer-verdict"]');
    expect(verdict).not.toBeNull();
    expect(verdict.textContent).toContain("same decision appeared again");
    expect(verdict.textContent).not.toContain("practice means improved");
  });
});
