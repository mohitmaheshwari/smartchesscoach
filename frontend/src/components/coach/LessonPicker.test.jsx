import { act } from "react";
import { createRoot } from "react-dom/client";
import LessonPicker from "./LessonPicker";

jest.mock("../../App", () => ({ API: "https://api.test/api" }));

const response = (body, ok = true) => Promise.resolve({
  ok,
  json: () => Promise.resolve(body),
});

describe("LessonPicker", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    global.fetch = jest.fn((url, options = {}) => {
      if (url.endsWith("/catalog")) {
        return response({
          traps: [
            { key: "white-trap", name: "White trap", trap_for: "white", difficulty: "beginner" },
            { key: "black-trap", name: "Black trap", trap_for: "black", difficulty: "beginner" },
          ],
          opening_ideas: [
            { key: "white-plan", name: "White opening plan", plan_for: "white", difficulty: "intermediate" },
            { key: "black-plan", name: "Black opening plan", plan_for: "black", difficulty: "intermediate" },
          ],
          endgames: [],
        });
      }
      if (url.endsWith("/start") && options.method === "POST") {
        return response({ lesson_type: "opening_plan", teaching_fen: "fen" });
      }
      return response({}, false);
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    delete global.fetch;
  });

  const settle = async () => {
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });
  };

  test("keeps opening plans separate from forced traps and starts the canonical lesson type", async () => {
    const onStartLesson = jest.fn();
    await act(async () => {
      root.render(
        <LessonPicker
          sessionId="session-1"
          userColor="white"
          onStartLesson={onStartLesson}
          onClose={() => {}}
        />
      );
    });
    await settle();

    expect(container.querySelector('[data-testid="trap-white-trap"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="trap-black-trap"]')).toBeNull();
    expect(container.textContent).not.toContain("White opening plan");

    await act(async () => {
      container.querySelector('[data-testid="tab-opening_ideas"]').click();
    });
    expect(container.textContent).toContain("White opening plan");
    expect(container.textContent).not.toContain("Black opening plan");

    await act(async () => {
      container.querySelector('[data-testid="opening-idea-white-plan"]').click();
    });
    await settle();

    const startCall = global.fetch.mock.calls.find(([url]) => url.endsWith("/start"));
    expect(JSON.parse(startCall[1].body)).toMatchObject({
      session_id: "session-1",
      lesson_type: "opening_plan",
      lesson_key: "white-plan",
    });
    expect(onStartLesson).toHaveBeenCalledWith({
      lesson_type: "opening_plan",
      teaching_fen: "fen",
    });
  });
});
