import React, { act } from "react";
import { createRoot } from "react-dom/client";

import CoachPanel from "./CoachPanel";


jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("framer-motion", () => ({
  motion: { div: ({ children, ...props }) => {
    const domProps = { ...props };
    delete domProps.initial;
    delete domProps.animate;
    delete domProps.transition;
    return <div {...domProps}>{children}</div>;
  } },
}));


const response = (body) => ({ ok: true, json: () => Promise.resolve(body) });

const deferred = () => {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
};


describe("CoachPanel position effects", () => {
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
    delete global.fetch;
  });

  const flush = () => act(async () => {
    await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });

  const renderPanel = (fen) => act(async () => root.render(
    <CoachPanel
      sessionId="session-1"
      fen={fen}
      isPlayerTurn
      openingKey="ruy-lopez"
    />
  ));

  test("uses the current opening response to decide whether candidates are needed", async () => {
    let guideCount = 0;
    global.fetch = jest.fn((url) => {
      if (url.endsWith("/opening-guide")) {
        guideCount += 1;
        return Promise.resolve(response(guideCount === 1
          ? { is_in_book: true, hint: "Keep developing." }
          : { is_in_book: false, hint: "Now choose a plan." }));
      }
      if (url.endsWith("/candidates")) {
        return Promise.resolve(response({
          candidates: [{ move: "Nf3", idea: "Bring another piece into the game." }],
        }));
      }
      if (url.endsWith("/read-position")) {
        return Promise.resolve(response({ features: [] }));
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    await renderPanel("fen-in-book");
    await flush();
    expect(global.fetch.mock.calls.filter(([url]) => url.endsWith("/candidates"))).toHaveLength(0);
    expect(container.textContent).toContain("Keep developing.");

    await renderPanel("fen-off-book");
    await flush();
    expect(global.fetch.mock.calls.filter(([url]) => url.endsWith("/candidates"))).toHaveLength(1);
    expect(container.textContent).toContain("Now choose a plan.");
    expect(container.textContent).toContain("Your best options");
  });

  test("a late response for an old position cannot fetch or display old advice", async () => {
    const oldGuide = deferred();
    let guideCount = 0;
    global.fetch = jest.fn((url) => {
      if (url.endsWith("/opening-guide")) {
        guideCount += 1;
        if (guideCount === 1) return oldGuide.promise;
        return Promise.resolve(response({ is_in_book: false, hint: "Current-position advice." }));
      }
      if (url.endsWith("/candidates")) {
        return Promise.resolve(response({ candidates: [{ move: "e4", idea: "Take the center." }] }));
      }
      if (url.endsWith("/read-position")) {
        return Promise.resolve(response({ features: [] }));
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    await renderPanel("fen-old");
    await renderPanel("fen-current");
    await flush();
    expect(container.textContent).toContain("Current-position advice.");

    oldGuide.resolve(response({ is_in_book: false, hint: "Old-position advice." }));
    await flush();

    expect(container.textContent).toContain("Current-position advice.");
    expect(container.textContent).not.toContain("Old-position advice.");
    expect(global.fetch.mock.calls.filter(([url]) => url.endsWith("/candidates"))).toHaveLength(1);
  });
});
