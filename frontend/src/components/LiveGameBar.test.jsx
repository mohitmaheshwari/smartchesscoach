/**
 * The bar that explains why the app is refusing everything, and the helper
 * that recognises the refusal.
 *
 * The guard shipped 2026-11-25 doing exactly its job, and the rest of the app
 * silently looked broken: Layout's coach-pulse poll asked three endpoints a
 * minute, each came back 403, each was swallowed by `if (res.ok)`, and the
 * player was told nothing. These cover the three things that make the fix
 * honest rather than decorative:
 *
 *   - it recognises a real refusal and nothing else;
 *   - it carries the server's words and a link, and nothing about the board —
 *     the entire reason the guard exists is that no evaluation may reach a
 *     player mid-game;
 *   - it takes itself away when the game is over.
 */

import React, { act } from "react";
import { createRoot } from "react-dom/client";

import LiveGameBar from "./LiveGameBar";
import { readRefusal } from "@/lib/liveGameNotice";

const NOTICE = {
  message:
    "Your game is live, so the coach is quiet. Finish the game and your review opens by itself.",
  open: "/play-with-coach",
  label: "Back to your game",
};

function response({ status = 200, body = {} }) {
  return {
    status,
    ok: status >= 200 && status < 300,
    clone: () => response({ status, body }),
    json: () => Promise.resolve(body),
  };
}

let host;
let root;

async function mount(element) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => {
    root.render(element);
  });
}

const bar = () => host.querySelector('[data-testid="live-game-bar"]');

beforeEach(() => {
  window.history.pushState({}, "", "/home");
  jest.useFakeTimers({ doNotFake: ["nextTick", "queueMicrotask"] });
  global.fetch = jest.fn(() => Promise.resolve(response({ body: {} })));
});

afterEach(async () => {
  if (root) await act(async () => root.unmount());
  jest.useRealTimers();
  jest.restoreAllMocks();
});

describe("recognising the guard's refusal", () => {
  it("reads a real refusal into something sayable", async () => {
    const notice = await readRefusal(
      response({
        status: 403,
        body: {
          detail: "Your game is live, so the coach is quiet.",
          live_lichess_game: true,
          open: "/play-with-coach",
          open_label: "Back to your game",
        },
      })
    );
    expect(notice).toEqual({
      message: "Your game is live, so the coach is quiet.",
      open: "/play-with-coach",
      label: "Back to your game",
    });
  });

  it("ignores a 403 that is not the guard's", async () => {
    expect(
      await readRefusal(response({ status: 403, body: { detail: "Forbidden" } }))
    ).toBeNull();
  });

  it("ignores a 403 that is not even JSON", async () => {
    const bad = {
      status: 403,
      clone: () => ({ json: () => Promise.reject(new Error("not json")) }),
    };
    expect(await readRefusal(bad)).toBeNull();
  });

  it("costs nothing on a normal response", async () => {
    const ok = response({ body: { anything: true } });
    ok.clone = () => {
      throw new Error("a 200 must never be cloned or parsed");
    };
    expect(await readRefusal(ok)).toBeNull();
  });

  it("does not patch the global fetch", async () => {
    // 2026-11-26: the first version wrapped window.fetch so any call anywhere
    // would be caught. It broke identity for everything else holding a
    // reference -- LayoutNotificationEffects reads global.fetch.mock.calls and
    // failed immediately. The poll that was already being refused is a better
    // place to notice than every call in the app.
    const before = global.fetch;
    await readRefusal(response({ status: 403, body: { live_lichess_game: true } }));
    expect(global.fetch).toBe(before);
  });
});

describe("the bar", () => {
  it("shows nothing when there is nothing to say", async () => {
    await mount(<LiveGameBar notice={null} onClear={() => {}} />);
    expect(bar()).toBeNull();
  });

  it("gives somewhere to go, which is the whole point", async () => {
    await mount(<LiveGameBar notice={NOTICE} onClear={() => {}} />);
    expect(bar().textContent).toMatch(/review opens by itself/i);
    const link = host.querySelector('[data-testid="live-game-bar-link"]');
    expect(link.getAttribute("href")).toBe("/play-with-coach");
    expect(link.textContent).toMatch(/back to your game/i);
  });

  it("says nothing about the position", async () => {
    await mount(<LiveGameBar notice={NOTICE} onClear={() => {}} />);
    expect(bar().textContent).not.toMatch(
      /\bcp\b|centipawn|blunder|eval|better move|advantage/i
    );
  });

  it("stays out of the way on the board itself", async () => {
    window.history.pushState({}, "", "/play-with-coach");
    await mount(<LiveGameBar notice={NOTICE} onClear={() => {}} />);
    expect(bar()).toBeNull();
  });

  it("takes itself away once the game is over", async () => {
    let live = true;
    global.fetch = jest.fn(() =>
      Promise.resolve(
        response({
          body: live ? { playing: true, game: { finished: false } } : { playing: false },
        })
      )
    );
    const onClear = jest.fn();
    await mount(<LiveGameBar notice={NOTICE} onClear={onClear} />);

    await act(async () => {
      jest.advanceTimersByTime(8000);
    });
    expect(onClear).not.toHaveBeenCalled();

    live = false;
    await act(async () => {
      jest.advanceTimersByTime(8000);
    });
    expect(onClear).toHaveBeenCalled();
  });

  it("keeps the bar rather than guessing when the check fails", async () => {
    global.fetch = jest.fn(() => Promise.reject(new Error("offline")));
    const onClear = jest.fn();
    await mount(<LiveGameBar notice={NOTICE} onClear={onClear} />);
    await act(async () => {
      jest.advanceTimersByTime(24000);
    });
    expect(onClear).not.toHaveBeenCalled();
    expect(bar()).not.toBeNull();
  });

  it("asks only the endpoint playing is allowed to use", async () => {
    await mount(<LiveGameBar notice={NOTICE} onClear={() => {}} />);
    await act(async () => {
      jest.advanceTimersByTime(8000);
    });
    const asked = global.fetch.mock.calls.map(([url]) => String(url));
    expect(asked).toHaveLength(1);
    expect(asked[0]).toMatch(/\/api\/coach\/play\/live\/state$/);
  });

  it("stops polling when it goes away", async () => {
    await mount(<LiveGameBar notice={NOTICE} onClear={() => {}} />);
    await act(async () => {
      root.render(<LiveGameBar notice={null} onClear={() => {}} />);
    });
    global.fetch.mockClear();
    await act(async () => {
      jest.advanceTimersByTime(40000);
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });
});
