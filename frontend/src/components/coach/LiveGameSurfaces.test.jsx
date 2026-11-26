/**
 * The move list, the captured material and the result card.
 *
 * Two things here are worth guarding beyond "it renders":
 *
 *  - the rating change is Lichess's number. If their export did not answer,
 *    the card must show nothing rather than a computed guess.
 *  - move navigation must stay locked while the game is live. A board that
 *    can show a position other than the live one is one refactor away from
 *    showing an analysed one, which is the thing that gets accounts marked.
 */

import React, { act } from "react";
import { createRoot } from "react-dom/client";

import {
  MoveList,
  MoveNav,
  PlayerCard,
  ResultCard,
  captured,
  clockText,
  replay,
  resultWords,
} from "./LiveGameSurfaces";

async function render(element) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  await act(async () => {
    createRoot(host).render(element);
  });
  return host;
}

describe("replaying the game", () => {
  it("turns Lichess's UCI moves into the notation people read", () => {
    const { sans, fens } = replay("startpos", "e2e4 e7e5 g1f3 b8c6");
    expect(sans).toEqual(["e4", "e5", "Nf3", "Nc6"]);
    expect(fens).toHaveLength(5); // the start, plus one per move
  });

  it("stops at a move it cannot replay instead of throwing", () => {
    const { sans } = replay("startpos", "e2e4 zz9z9z e7e5");
    expect(sans).toEqual(["e4"]);
  });

  it("handles a game that did not start from the initial position", () => {
    const fen = "4k3/8/8/8/8/8/4P3/4K3 w - - 0 1";
    const { sans } = replay(fen, "e2e4");
    expect(sans).toEqual(["e4"]);
  });
});

describe("captured material", () => {
  it("is empty at the start", () => {
    const { advantage, white, black } = captured(
      "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    );
    expect(white).toEqual([]);
    expect(black).toEqual([]);
    expect(advantage).toBe(0);
  });

  it("counts what each side has taken, and who is ahead", () => {
    // Black is missing a queen; White is missing a knight.
    const { white, black, advantage } = captured(
      "rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/R1BQKBNR w KQkq - 0 1"
    );
    expect(white).toEqual(["q"]);      // what White has captured
    expect(black).toEqual(["n"]);      // what Black has captured
    expect(advantage).toBe(9 - 3);     // queen minus knight
  });
});

describe("how the result reads", () => {
  it("names the way the game ended", () => {
    expect(resultWords({ status: "mate", winner: "white" }, "white")).toEqual({
      headline: "You won",
      reason: "by checkmate",
    });
    expect(resultWords({ status: "resign", winner: "black" }, "white")).toEqual({
      headline: "You lost",
      reason: "by resignation",
    });
    expect(resultWords({ status: "outoftime", winner: "white" }, "black")).toEqual({
      headline: "You lost",
      reason: "on time",
    });
    expect(resultWords({ status: "draw", winner: null }, "white").headline).toBe("Draw");
  });

  it("falls back to the raw status rather than inventing a reason", () => {
    expect(resultWords({ status: "weirdNewStatus", winner: "white" }, "white").reason).toBe(
      "weirdNewStatus"
    );
  });
});

describe("the result card", () => {
  const base = { status: "mate", winner: "white", our_rating: 1437, our_rating_diff: 6 };

  it("shows Lichess's rating and the change", async () => {
    const host = await render(
      <ResultCard game={base} ourColor="white" review={null} onNewGame={() => {}} />
    );
    expect(host.querySelector('[data-testid="live-result-headline"]').textContent).toBe(
      "You won"
    );
    expect(host.textContent).toContain("by checkmate");
    expect(host.querySelector('[data-testid="live-new-rating"]').textContent).toBe("1437");
    expect(host.querySelector('[data-testid="live-rating-diff"]').textContent).toBe("↑ 6");
  });

  it("shows a loss as a loss, with the drop", async () => {
    const host = await render(
      <ResultCard
        game={{ ...base, winner: "black", our_rating: 1424, our_rating_diff: -7 }}
        ourColor="white"
        review={null}
        onNewGame={() => {}}
      />
    );
    expect(host.querySelector('[data-testid="live-result-headline"]').textContent).toBe(
      "You lost"
    );
    expect(host.querySelector('[data-testid="live-rating-diff"]').textContent).toBe("↓ 7");
  });

  it("shows no rating line at all when Lichess did not tell us", async () => {
    const host = await render(
      <ResultCard
        game={{ status: "mate", winner: "white" }}
        ourColor="white"
        review={null}
        onNewGame={() => {}}
      />
    );
    expect(host.querySelector('[data-testid="live-new-rating"]')).toBeNull();
    expect(host.querySelector('[data-testid="live-rating-diff"]')).toBeNull();
    // and no invented number anywhere on the card
    expect(host.textContent).not.toMatch(/↑|↓|±/);
  });

  it("offers the review only once it is actually ready", async () => {
    const pending = await render(
      <ResultCard game={base} ourColor="white" review={{ imported: true, ready: false }} onNewGame={() => {}} />
    );
    expect(pending.querySelector('[data-testid="live-open-review"]')).toBeNull();
    expect(pending.querySelector('[data-testid="live-review-pending"]').textContent).toMatch(
      /analysing/i
    );

    const ready = await render(
      <ResultCard
        game={base}
        ourColor="white"
        review={{ ready: true, review_url: "/game/abc" }}
        onNewGame={() => {}}
      />
    );
    expect(ready.querySelector('[data-testid="live-open-review"]').getAttribute("href")).toBe(
      "/game/abc"
    );
  });
});

describe("move navigation", () => {
  it("is locked while the game is live", async () => {
    const host = await render(
      <MoveNav ply={4} total={4} onSeek={() => {}} enabled={false} />
    );
    expect(host.querySelector('[data-testid="live-nav-prev"]').disabled).toBe(true);
    expect(host.querySelector('[data-testid="live-nav-start"]').disabled).toBe(true);
  });

  it("walks back and forth once the game is over", async () => {
    const seen = [];
    const host = await render(
      <MoveNav ply={4} total={6} onSeek={(p) => seen.push(p)} enabled />
    );
    for (const id of ["live-nav-start", "live-nav-prev", "live-nav-next", "live-nav-end"]) {
      await act(async () => {
        host
          .querySelector(`[data-testid="${id}"]`)
          .dispatchEvent(new MouseEvent("click", { bubbles: true }));
      });
    }
    expect(seen).toEqual([0, 3, 5, 6]);
  });

  it("will not walk past either end", async () => {
    const seen = [];
    const host = await render(<MoveNav ply={0} total={2} onSeek={(p) => seen.push(p)} enabled />);
    await act(async () => {
      host
        .querySelector('[data-testid="live-nav-next"]')
        .dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(seen).toEqual([1]);
  });
});

describe("the move list", () => {
  it("pairs the moves by turn", async () => {
    const host = await render(
      <MoveList sans={["e4", "e5", "Nf3"]} ply={3} onSeek={() => {}} canSeek />
    );
    const text = host.querySelector('[data-testid="live-move-list"]').textContent;
    expect(text).toContain("1");
    expect(text).toContain("e4");
    expect(text).toContain("e5");
    expect(text).toContain("Nf3");
  });

  it("is not clickable while the game is live", async () => {
    const seen = [];
    const host = await render(
      <MoveList sans={["e4", "e5"]} ply={2} onSeek={(p) => seen.push(p)} canSeek={false} />
    );
    const buttons = host.querySelectorAll("button");
    buttons.forEach((b) => expect(b.disabled).toBe(true));
    expect(seen).toEqual([]);
  });
});

/**
 * The clock.
 *
 * Lichess sends a reading with each board update and nothing in between, so a
 * clock drawn straight from the 1.5s poll lurches and then sits frozen through
 * a long think. These tests are about the two halves of the fix: subtract the
 * age the server reports for a reading, then run it down locally until the next
 * one. The failure they catch is a clock that looks live and is not -- in a
 * 10+0 game that is the difference between "I have time" and flagging.
 */
describe("the clock", () => {
  beforeEach(() => {
    jest.useFakeTimers({ doNotFake: ["nextTick", "queueMicrotask"] });
  });
  afterEach(() => {
    jest.useRealTimers();
  });

  const mount = async (props) => {
    const host = document.createElement("div");
    document.body.appendChild(host);
    const root = createRoot(host);
    await act(async () => {
      root.render(<PlayerCard testId="p" name="Someone" pieces={[]} {...props} />);
    });
    const shown = () => host.querySelector('[data-testid="p-clock"]');
    const rerender = async (next) => {
      await act(async () => {
        root.render(<PlayerCard testId="p" name="Someone" pieces={[]} {...next} />);
      });
    };
    const advance = async (ms) => {
      await act(async () => {
        jest.advanceTimersByTime(ms);
      });
    };
    return { shown, rerender, advance };
  };

  it("formats the way a chess clock does, with tenths under ten seconds", () => {
    expect(clockText(600000)).toBe("10:00");
    expect(clockText(65000)).toBe("1:05");
    expect(clockText(10000)).toBe("0:10");
    expect(clockText(9400)).toBe("0:09.4");
    expect(clockText(0)).toBe("0:00.0");
    expect(clockText(null)).toBe("—:—");
  });

  it("subtracts the age of the reading instead of drawing a stale number", async () => {
    // 10:00 as measured two seconds ago is 9:58 now. Drawing 10:00 here is the
    // lurch: the next poll would drop it to 9:56.
    const { shown } = await mount({ clockMs: 600000, clockAgeMs: 2000, running: true });
    expect(shown().textContent).toBe("9:58");
  });

  it("runs down between readings, with no new data at all", async () => {
    const { shown, advance } = await mount({
      clockMs: 600000,
      clockAgeMs: 0,
      running: true,
    });
    expect(shown().textContent).toBe("10:00");

    await advance(3000);
    expect(shown().textContent).toBe("9:57");

    await advance(4000);
    expect(shown().textContent).toBe("9:53");
  });

  it("leaves the other player's clock exactly where it was", async () => {
    const { shown, advance } = await mount({
      clockMs: 600000,
      clockAgeMs: 2000,
      running: false,
    });
    // Not their move, so no time has come off THEIR clock during those two
    // seconds. The age belongs to whoever is on move. Subtracting it here
    // was the bug: it showed 9:58 for a player who still has all 10:00.
    expect(shown().textContent).toBe("10:00");
    await advance(8000);
    expect(shown().textContent).toBe("10:00");
  });

  it("holds the idle clock still across polls, as the reading goes stale", async () => {
    // The regression that reached a live game. clock_age_ms grows with every
    // poll while nobody moves, so subtracting it from the idle side stepped
    // that clock down once per poll. It is not a smooth tick -- no interval
    // runs for a stopped clock -- but on screen it is indistinguishable from
    // one, and both clocks ran down together.
    const { shown, rerender } = await mount({
      clockMs: 600000,
      clockAgeMs: 0,
      running: false,
    });
    expect(shown().textContent).toBe("10:00");

    for (const age of [700, 1500, 2400, 3300, 5000]) {
      await rerender({ clockMs: 600000, clockAgeMs: age, running: false });
      expect(shown().textContent).toBe("10:00");
    }
  });

  it("still corrects for a stale reading on the side that IS running", async () => {
    // The fix must not throw away the correction where it belongs, or the
    // running clock lurches backwards on every poll.
    const { shown, rerender } = await mount({
      clockMs: 600000,
      clockAgeMs: 2000,
      running: true,
    });
    expect(shown().textContent).toBe("9:58");
    await rerender({ clockMs: 600000, clockAgeMs: 5000, running: true });
    expect(shown().textContent).toBe("9:55");
  });

  it("re-anchors on every new reading, so our drift lives one poll at most", async () => {
    const { shown, rerender, advance } = await mount({
      clockMs: 600000,
      clockAgeMs: 0,
      running: true,
    });
    await advance(5000);
    expect(shown().textContent).toBe("9:55");

    // Lichess now says 8:20. Whatever we had counted down to is discarded.
    await rerender({ clockMs: 500000, clockAgeMs: 0, running: true });
    expect(shown().textContent).toBe("8:20");
    await advance(2000);
    expect(shown().textContent).toBe("8:18");
  });

  it("follows an increment upward rather than refusing to go up", async () => {
    // A 10+5 game adds five seconds after the move. Lichess's reading already
    // includes it, so the clock must be allowed to rise.
    const { shown, rerender } = await mount({
      clockMs: 300000,
      clockAgeMs: 0,
      running: false,
    });
    expect(shown().textContent).toBe("5:00");
    await rerender({ clockMs: 305000, clockAgeMs: 0, running: false });
    expect(shown().textContent).toBe("5:05");
  });

  // 30 seconds at a 100ms tick is 300 renders inside act(), which genuinely
  // takes longer than Jest's 5s default on a loaded machine. The assertion is
  // unchanged; only the budget is honest about what the test does.
  it("stops at zero rather than counting into negative time", async () => {
    const { shown, advance } = await mount({
      clockMs: 3000,
      clockAgeMs: 0,
      running: true,
    });
    await advance(30000);
    expect(shown().textContent).toBe("0:00.0");
  }, 20000);

  it("goes urgent while it is running, not only when a poll happens to land", async () => {
    const { shown, advance } = await mount({
      clockMs: 35000,
      clockAgeMs: 0,
      running: true,
    });
    expect(shown().className).not.toMatch(/rose/);
    await advance(6000);
    expect(shown().textContent).toBe("0:29");
    expect(shown().className).toMatch(/rose/);
  });

  it("says nothing rather than zero when there is no reading yet", async () => {
    const { shown, advance } = await mount({ clockMs: null, running: true });
    expect(shown().textContent).toBe("—:—");
    await advance(5000);
    expect(shown().textContent).toBe("—:—");
  });

  it("clears its interval when the clock stops, rather than leaking one", async () => {
    // A clock per card per game, left running for the rest of the session, is
    // the kind of leak nothing on screen reveals.
    const started = jest.spyOn(global, "setInterval");
    const cleared = jest.spyOn(global, "clearInterval");

    const { rerender } = await mount({ clockMs: 600000, clockAgeMs: 0, running: true });
    const ours = started.mock.results.map((r) => r.value);
    expect(ours.length).toBeGreaterThan(0);

    await rerender({ clockMs: 600000, clockAgeMs: 0, running: false });
    const releasedIds = cleared.mock.calls.map(([id]) => id);
    for (const id of ours) expect(releasedIds).toContain(id);
  });
});
