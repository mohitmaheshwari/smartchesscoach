import React, { act } from "react";
import { createRoot } from "react-dom/client";

import { ActiveLessonPanel } from "./OpeningTeachingPanel";


jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("react-router-dom", () => ({ useNavigate: () => jest.fn() }), { virtual: true });


const response = (body) => ({ ok: true, json: () => Promise.resolve(body) });

const deferred = () => {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
};


describe("ActiveLessonPanel teaching-move bridge", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    delete window.validateTeachingMove;
    delete global.fetch;
  });

  const renderPanel = ({ sessionId, onMoveValidated, onLessonComplete }) => act(async () => root.render(
    <ActiveLessonPanel
      lesson={{ lesson_name: "The pin", key_ideas: [] }}
      sessionId={sessionId}
      currentInstruction={null}
      onMoveValidated={onMoveValidated}
      onLessonComplete={onLessonComplete}
      onExitLesson={jest.fn()}
    />
  ));

  test("the board bridge calls the latest handlers when props change", async () => {
    const firstHandler = jest.fn();
    const currentHandler = jest.fn();
    global.fetch = jest.fn(() => Promise.resolve(response({
      correct: true,
      complete: false,
      message: "That keeps the pin.",
    })));

    await renderPanel({
      sessionId: "session-1",
      onMoveValidated: firstHandler,
      onLessonComplete: jest.fn(),
    });
    await renderPanel({
      sessionId: "session-1",
      onMoveValidated: currentHandler,
      onLessonComplete: jest.fn(),
    });

    await act(async () => window.validateTeachingMove("Bb5"));

    expect(firstHandler).not.toHaveBeenCalled();
    expect(currentHandler).toHaveBeenCalledTimes(1);
    expect(JSON.parse(global.fetch.mock.calls[0][1].body)).toEqual({
      session_id: "session-1",
      move: "Bb5",
    });
  });

  test("an in-flight same-session result transfers to the latest handlers", async () => {
    const pendingRequest = deferred();
    const firstHandler = jest.fn();
    const currentHandler = jest.fn();
    global.fetch = jest.fn(() => pendingRequest.promise);

    await renderPanel({
      sessionId: "session-1",
      onMoveValidated: firstHandler,
      onLessonComplete: jest.fn(),
    });

    let pendingValidation;
    await act(async () => {
      pendingValidation = window.validateTeachingMove("Bb5");
      await Promise.resolve();
    });

    await renderPanel({
      sessionId: "session-1",
      onMoveValidated: currentHandler,
      onLessonComplete: jest.fn(),
    });

    pendingRequest.resolve(response({
      correct: true,
      complete: false,
      message: "Transferred response.",
    }));
    await act(async () => pendingValidation);

    expect(firstHandler).not.toHaveBeenCalled();
    expect(currentHandler).toHaveBeenCalledTimes(1);
    expect(container.textContent).toContain("Transferred response.");
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  test("an old session response cannot update or call back into the new lesson", async () => {
    const oldRequest = deferred();
    const oldHandler = jest.fn();
    const currentHandler = jest.fn();
    global.fetch = jest.fn()
      .mockImplementationOnce(() => oldRequest.promise)
      .mockImplementationOnce(() => Promise.resolve(response({
        correct: true,
        complete: false,
        message: "Current lesson response.",
      })));

    await renderPanel({
      sessionId: "session-old",
      onMoveValidated: oldHandler,
      onLessonComplete: jest.fn(),
    });

    let oldValidation;
    await act(async () => {
      oldValidation = window.validateTeachingMove("e4");
      await Promise.resolve();
    });

    await renderPanel({
      sessionId: "session-current",
      onMoveValidated: currentHandler,
      onLessonComplete: jest.fn(),
    });
    await act(async () => window.validateTeachingMove("d4"));

    oldRequest.resolve(response({
      correct: true,
      complete: false,
      message: "Old lesson response.",
    }));
    await act(async () => oldValidation);

    expect(oldHandler).not.toHaveBeenCalled();
    expect(currentHandler).toHaveBeenCalledTimes(1);
    expect(container.textContent).toContain("Current lesson response.");
    expect(container.textContent).not.toContain("Old lesson response.");
  });
});
