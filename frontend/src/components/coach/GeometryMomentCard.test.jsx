import { act } from "react";
import { createRoot } from "react-dom/client";
import GeometryMomentCard from "./GeometryMomentCard";

jest.mock("@/App", () => ({ API: "https://example.test/api" }), { virtual: true });


const MOMENT = {
  event_id: "geometry-event-1",
  eyebrow: "You missed it",
  prompt: "Which two pieces now share one attack?",
  explanation: "Nc7+ attacks the rook on a8 and king on e8 together.",
  lesson: "Two L-jumps can meet on one square.",
  arrows: [["c7", "a8"], ["c7", "e8"]],
  revealed: false,
};


describe("GeometryMomentCard", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    global.fetch = jest.fn();
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    jest.restoreAllMocks();
  });

  test("keeps the answer hidden until one complete reveal response arrives", async () => {
    const onReveal = jest.fn();
    const onDismiss = jest.fn();
    global.fetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          moment: { ...MOMENT, revealed: true },
        }),
      })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ success: true }) });

    act(() => root.render(
      <GeometryMomentCard
        moment={MOMENT}
        sessionId="coach-session-1"
        onReveal={onReveal}
        onDismiss={onDismiss}
      />
    ));

    expect(container.textContent).toContain(MOMENT.prompt);
    expect(container.textContent).not.toContain(MOMENT.explanation);
    expect(container.textContent).not.toContain("Coach thinking");

    await act(async () => {
      container.querySelector("button").dispatchEvent(
        new MouseEvent("click", { bubbles: true })
      );
    });

    expect(global.fetch).toHaveBeenCalledWith(
      "https://example.test/api/coach/play/geometry-moment/respond",
      expect.objectContaining({
        body: JSON.stringify({
          session_id: "coach-session-1",
          event_id: "geometry-event-1",
          action: "reveal",
        }),
      })
    );
    expect(container.textContent).toContain(MOMENT.explanation);
    expect(container.textContent).toContain(MOMENT.lesson);
    expect(onReveal).toHaveBeenCalledWith({ ...MOMENT, revealed: true });

    await act(async () => {
      container.querySelector("button").dispatchEvent(
        new MouseEvent("click", { bubbles: true })
      );
    });
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });
});
