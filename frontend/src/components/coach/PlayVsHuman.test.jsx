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
jest.mock("react-chessboard", () => ({
  Chessboard: (props) => {
    lastBoardProps = props;
    return null;
  },
}), { virtual: true });

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
    expect(lastBoardProps.position).toBe(LIVE_GAME.game.fen);
    expect(lastBoardProps.boardOrientation).toBe("white");
    // Not our turn, so the pieces must not be draggable.
    expect(lastBoardProps.arePiecesDraggable).toBe(false);
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

    expect(host.querySelector('[data-testid="live-open-review"]')).toBeNull();
    expect(
      host.querySelector('[data-testid="live-review-panel"]').textContent
    ).toMatch(/analysing/i);
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
