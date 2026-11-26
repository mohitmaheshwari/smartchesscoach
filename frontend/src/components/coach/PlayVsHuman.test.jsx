/**
 * The sealed review panel must hold nothing while the game is live.
 *
 * This is the one frontend rule that protects a real person's Lichess account.
 * The server enforces it structurally (live_play_guard.py refuses the review
 * endpoint mid-game), but a component that *tried* to show something would
 * still be a bug worth catching here, and cheaply.
 *
 * Written in the house style for this repo: createRoot + act, no
 * @testing-library (it is not a dependency).
 */

import React, { act } from "react";
import { createRoot } from "react-dom/client";

import PlayVsHuman from "./PlayVsHuman";

// The board itself is react-chessboard's problem, not ours. Mock it and record
// what position we handed it.
let lastBoardProps = null;
jest.mock("@/components/LichessBoard", () => (props) => {
  lastBoardProps = props;
  return null;
}, { virtual: true });

const LIVE_GAME = {
  playing: true,
  seeking: false,
  game: {
    game_id: "xit0qdzB",
    color: "white",
    fen: "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
    moves: "e2e4",
    status: "started",
    winner: null,
    finished: false,
    our_turn: false,
    white_time_ms: 600000,
    black_time_ms: 594000,
    opponent: { username: "someone", rating: 1521 },
    rated: false,
    speed: "rapid",
    draw_offer_from: null,
    stream_alive: true,
    lichess_url: "https://lichess.org/xit0qdzB",
    started_at: "2026-11-25T19:00:00+00:00",
  },
};

const FINISHED_GAME = {
  playing: true,
  seeking: false,
  game: { ...LIVE_GAME.game, status: "resign", winner: "white", finished: true, our_turn: false },
};

function mockApi(handlers) {
  global.fetch = jest.fn((url) => {
    const path = String(url);
    for (const [fragment, make] of handlers) {
      if (path.includes(fragment)) {
        const { status = 200, body = {} } = make();
        return Promise.resolve({
          ok: status >= 200 && status < 300,
          status,
          json: () => Promise.resolve(body),
        });
      }
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) });
  });
}

async function render(element) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => {
    root.render(element);
  });
  // let the state poll and any follow-up fetch settle
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
  return { host, root };
}

beforeEach(() => {
  lastBoardProps = null;
  jest.useFakeTimers({ doNotFake: ["nextTick", "queueMicrotask"] });
});

afterEach(() => {
  jest.useRealTimers();
  jest.restoreAllMocks();
});

describe("while the Lichess game is live", () => {
  it("shows the sealed panel and no review anywhere", async () => {
    mockApi([
      ["/time-controls", () => ({ body: { options: ["10+0", "10+5"], default: "10+5" } })],
      ["/state", () => ({ body: LIVE_GAME })],
    ]);

    const { host } = await render(<PlayVsHuman onExit={() => {}} />);

    const panel = host.querySelector('[data-testid="live-review-panel"]');
    expect(panel).not.toBeNull();
    expect(panel.textContent).toMatch(/opens the moment this game ends/i);

    // The whole point: no way into a review, and nothing about the position.
    expect(host.querySelector('[data-testid="live-open-review"]')).toBeNull();
    expect(panel.textContent).not.toMatch(/\bcp\b|centipawn|blunder|better move|eval/i);
  });

  it("never asks the server for the review while the game is live", async () => {
    mockApi([
      ["/time-controls", () => ({ body: { options: ["10+5"], default: "10+5" } })],
      ["/state", () => ({ body: LIVE_GAME })],
    ]);

    await render(<PlayVsHuman onExit={() => {}} />);

    const asked = global.fetch.mock.calls.filter(([url]) => String(url).includes("/live/review/"));
    expect(asked).toHaveLength(0);
  });

  it("hands the board our own colour and the current position", async () => {
    mockApi([
      ["/time-controls", () => ({ body: { options: ["10+5"], default: "10+5" } })],
      ["/state", () => ({ body: LIVE_GAME })],
    ]);

    await render(<PlayVsHuman onExit={() => {}} />);

    expect(lastBoardProps).not.toBeNull();
    expect(lastBoardProps.fen).toBe(LIVE_GAME.game.fen);
    expect(lastBoardProps.orientation).toBe("white");
    // Not our turn, so the pieces must not be movable.
    expect(lastBoardProps.interactive).toBe(false);
  });

  it("forces the board's arrow kill-switch on", async () => {
    mockApi([
      ["/time-controls", () => ({ body: { options: ["10+5"], default: "10+5" } })],
      ["/state", () => ({ body: LIVE_GAME })],
    ]);
    await render(<PlayVsHuman onExit={() => {}} />);

    // LichessBoard.disableArrows is documented there as the one place that
    // guarantees no coaching shape can appear whatever an upstream caller
    // forgot. During a live Lichess game it is not optional.
    expect(lastBoardProps.disableArrows).toBe(true);
    expect(lastBoardProps.arrows).toEqual([]);
    expect(lastBoardProps.circles).toEqual([]);
    // A move classification is an engine verdict; it must never be passed.
    expect(lastBoardProps.moveClassification).toBeUndefined();
  });

  it("uses edge coordinates, not a label stamped on all 64 squares", async () => {
    mockApi([
      ["/time-controls", () => ({ body: { options: ["10+5"], default: "10+5" } })],
      ["/state", () => ({ body: LIVE_GAME })],
    ]);
    await render(<PlayVsHuman onExit={() => {}} />);

    // BoardCoordinates labels every square once the board is >=420px, which
    // is right for reading annotations off a review board and clutter on a
    // board you are playing. 2026-11-25: it shipped that way and looked it.
    expect(lastBoardProps.showCoordinates).toBe(false);
    expect(lastBoardProps.edgeCoordinates).toBe(true);
  });
});

describe("once the game is over", () => {
  it("asks where the review is and offers it when ready", async () => {
    mockApi([
      ["/time-controls", () => ({ body: { options: ["10+5"], default: "10+5" } })],
      ["/state", () => ({ body: FINISHED_GAME })],
      [
        "/live/review/",
        () => ({
          body: { ready: true, imported: true, game_id: "our-uuid", review_url: "/game/our-uuid" },
        }),
      ],
    ]);

    const { host } = await render(<PlayVsHuman onExit={() => {}} />);

    const link = host.querySelector('[data-testid="live-open-review"]');
    expect(link).not.toBeNull();
    expect(link.getAttribute("href")).toBe("/game/our-uuid");
  });

  it("says the analysis is still running rather than offering a dead link", async () => {
    mockApi([
      ["/time-controls", () => ({ body: { options: ["10+5"], default: "10+5" } })],
      ["/state", () => ({ body: FINISHED_GAME })],
      ["/live/review/", () => ({ body: { ready: false, imported: true } })],
    ]);

    const { host } = await render(<PlayVsHuman onExit={() => {}} />);

    // Once the game is over the sealed panel is replaced by the result card,
    // which carries the review button (or says why it is not ready yet).
    expect(host.querySelector('[data-testid="live-open-review"]')).toBeNull();
    expect(
      host.querySelector('[data-testid="live-result-card"]').textContent
    ).toMatch(/analysing/i);
  });
});

describe("the seek we actually send", () => {
  // 2026-11-25: the first version sent casual 10+5 and sat in a quiet pool for
  // a minute while Chessiro paired the same player in seconds at 10+0. The
  // pool you ask for is the whole feature working or not.
  it("defaults to a rated 10+0 game, the busiest pool", async () => {
    mockApi([
      [
        "/time-controls",
        () => ({
          body: { options: ["10+0", "10+5", "15+10"], default: "10+0", default_rated: true },
        }),
      ],
      ["/state", () => ({ body: { playing: false, seeking: false } })],
      ["/seek", () => ({ body: { seeking: true } })],
    ]);

    const { host } = await render(<PlayVsHuman onExit={() => {}} />);
    const button = host.querySelector('[data-testid="live-find-opponent"]');
    expect(button).not.toBeNull();

    await act(async () => {
      button.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const seek = global.fetch.mock.calls.find(([url]) => String(url).includes("/live/seek"));
    expect(seek).toBeDefined();
    expect(JSON.parse(seek[1].body)).toEqual({ time_control: "10+0", rated: true });
  });

  it("sends casual only when the player actually picks it", async () => {
    mockApi([
      [
        "/time-controls",
        () => ({ body: { options: ["10+0"], default: "10+0", default_rated: true } }),
      ],
      ["/state", () => ({ body: { playing: false, seeking: false } })],
      ["/seek", () => ({ body: { seeking: true } })],
    ]);

    const { host } = await render(<PlayVsHuman onExit={() => {}} />);
    await act(async () => {
      host
        .querySelector('[data-testid="live-rated-casual"]')
        .dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await act(async () => {
      host
        .querySelector('[data-testid="live-find-opponent"]')
        .dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const seek = global.fetch.mock.calls.find(([url]) => String(url).includes("/live/seek"));
    expect(JSON.parse(seek[1].body).rated).toBe(false);
  });

  it("says plainly that rated moves their real Lichess rating", async () => {
    mockApi([
      [
        "/time-controls",
        () => ({ body: { options: ["10+0"], default: "10+0", default_rated: true } }),
      ],
      ["/state", () => ({ body: { playing: false, seeking: false } })],
    ]);
    const { host } = await render(<PlayVsHuman onExit={() => {}} />);
    expect(host.textContent).toMatch(/counts on your Lichess rating/i);
  });
});

describe("the lobby, before a seek is sent", () => {
  // 2026-11-26: the first version was a 440px column of form controls floating
  // at the top of an empty page -- no board, nothing to look at, on a screen
  // whose whole job is to make someone want to press one button.
  const LOBBY = [
    [
      "/time-controls",
      () => ({
        body: {
          options: ["10+0", "10+5", "15+10"],
          default: "10+0",
          default_rated: true,
          me: { username: "bhutramohit", rating: 1437 },
        },
      }),
    ],
    ["/state", () => ({ body: { playing: false, seeking: false } })],
  ];

  it("shows a board before a single choice is made", async () => {
    mockApi(LOBBY);
    await render(<PlayVsHuman onExit={() => {}} />);

    expect(lastBoardProps).not.toBeNull();
    expect(lastBoardProps.fen).toMatch(/^rnbqkbnr\/pppppppp/);
    // Nothing on it is playable or annotated: it is a picture of chess.
    expect(lastBoardProps.interactive).toBe(false);
    expect(lastBoardProps.disableArrows).toBe(true);
  });

  it("says who you will be playing as, with your real handle", async () => {
    mockApi(LOBBY);
    const { host } = await render(<PlayVsHuman onExit={() => {}} />);

    const card = host.querySelector('[data-testid="live-me"]');
    expect(card).not.toBeNull();
    expect(card.textContent).toMatch(/bhutramohit/);
    expect(card.textContent).toMatch(/1437/);
  });

  it("spells out what each time control actually means", async () => {
    mockApi(LOBBY);
    const { host } = await render(<PlayVsHuman onExit={() => {}} />);

    expect(host.querySelector('[data-testid="live-tc-10+0"]').textContent).toMatch(
      /10 min/
    );
    expect(host.querySelector('[data-testid="live-tc-10+5"]').textContent).toMatch(
      /10 min \+ 5s a move/
    );
    // No speed class: Lichess's Bullet/Blitz/Rapid thresholds are a table we
    // have not checked, so the screen does no classifying.
    expect(host.querySelector('[data-testid="live-tc-15+10"]').textContent).not.toMatch(
      /rapid|blitz|bullet/i
    );
  });

  it("names the chosen control on the button you are about to press", async () => {
    mockApi(LOBBY);
    const { host } = await render(<PlayVsHuman onExit={() => {}} />);

    const button = host.querySelector('[data-testid="live-find-opponent"]');
    expect(button.textContent).toMatch(/Find an opponent · 10\+0/);

    await act(async () => {
      host
        .querySelector('[data-testid="live-tc-15+10"]')
        .dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(
      host.querySelector('[data-testid="live-find-opponent"]').textContent
    ).toMatch(/Find an opponent · 15\+10/);
  });

  it("leaves out the account card rather than inventing a handle", async () => {
    mockApi([
      ["/time-controls", () => ({ body: { options: ["10+0"], default: "10+0" } })],
      ["/state", () => ({ body: { playing: false, seeking: false } })],
    ]);
    const { host } = await render(<PlayVsHuman onExit={() => {}} />);

    expect(host.querySelector('[data-testid="live-me"]')).toBeNull();
    expect(host.querySelector('[data-testid="live-find-opponent"]')).not.toBeNull();
  });
});

describe("when the account cannot play yet", () => {
  it("asks for the one-time Lichess permission instead of failing silently", async () => {
    mockApi([
      ["/time-controls", () => ({ body: { options: ["10+5"], default: "10+5" } })],
      [
        "/state",
        () => ({
          status: 409,
          body: {
            detail: {
              reason: "needs_board_play_scope",
              message: "Reconnect your Lichess account once to let ChessGuru make your moves.",
            },
          },
        }),
      ],
    ]);

    const { host } = await render(<PlayVsHuman onExit={() => {}} />);

    expect(host.textContent).toMatch(/Reconnect your Lichess account once/i);
    expect(host.textContent).toMatch(/never suggest moves/i);
  });
});
