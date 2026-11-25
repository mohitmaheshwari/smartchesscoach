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
  ResultCard,
  captured,
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
