/**
 * The search screen may look alive, but everything it states must be true.
 *
 * The reference design we were shown (Chessiro) says "Searching among 127,643
 * users". Lichess publishes no online-player count — /api/count and
 * /api/users/online are 404, /api/status is API-version info, and the figures
 * on their homepage are per-tournament — so any number of that shape on our
 * screen would be invented. This file pins that it never appears, alongside
 * the ordinary checks that the real details are shown.
 */

import React, { act } from "react";
import { createRoot } from "react-dom/client";

import LiveSearchBoard from "./LiveSearchBoard";

jest.mock("@/components/LichessBoard", () => () => null, { virtual: true });

async function render(element) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  await act(async () => {
    createRoot(host).render(element);
  });
  return host;
}

const ME = { username: "bhutramohit", rating: 1424 };

describe("while searching", () => {
  it("shows the player's real Lichess handle, rating and pool", async () => {
    const host = await render(
      <LiveSearchBoard
        timeControl="10+0"
        rated
        waited={12}
        me={ME}
        opponent={null}
        onCancel={() => {}}
      />
    );

    expect(host.querySelector('[data-testid="search-me"]').textContent).toBe("bhutramohit");
    expect(host.textContent).toContain("1424");
    expect(host.textContent).toMatch(/Rated · 10\+0 · on Lichess/);
    expect(host.querySelector('[data-testid="search-elapsed"]').textContent).toBe("12s");
    expect(host.querySelector('[data-testid="search-headline"]').textContent).toBe(
      "Finding an opponent"
    );
  });

  it("invents no population count", async () => {
    const host = await render(
      <LiveSearchBoard timeControl="10+0" rated waited={3} me={ME} opponent={null} onCancel={() => {}} />
    );

    // Nothing of the shape "searching among 127,643 users" / "12,000 players".
    expect(host.textContent).not.toMatch(/\d[\d,]{3,}\s*(users|players|online)/i);
    expect(host.textContent).not.toMatch(/searching among/i);
  });

  it("says casual when the seek is casual, not whatever was selected last", async () => {
    const host = await render(
      <LiveSearchBoard timeControl="15+10" rated={false} waited={0} me={ME} opponent={null} onCancel={() => {}} />
    );
    expect(host.textContent).toMatch(/Casual · 15\+10 · on Lichess/);
  });

  it("offers a way out", async () => {
    let cancelled = false;
    const host = await render(
      <LiveSearchBoard
        timeControl="10+0"
        rated
        waited={5}
        me={ME}
        opponent={null}
        onCancel={() => {
          cancelled = true;
        }}
      />
    );
    await act(async () => {
      host
        .querySelector('[data-testid="live-cancel-seek"]')
        .dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(cancelled).toBe(true);
  });
});

describe("the moment an opponent is found", () => {
  it("names the real opponent and drops the timer", async () => {
    const host = await render(
      <LiveSearchBoard
        timeControl="10+0"
        rated
        waited={30}
        me={ME}
        opponent={{ username: "someone", rating: 1521 }}
        onCancel={() => {}}
      />
    );

    expect(host.querySelector('[data-testid="search-headline"]').textContent).toBe(
      "Opponent found"
    );
    expect(host.querySelector('[data-testid="search-opponent"]').textContent).toBe("someone");
    expect(host.textContent).toContain("1521");
    // The search is over, so the stopwatch must not keep ticking at them.
    expect(host.querySelector('[data-testid="search-elapsed"]')).toBeNull();
    // And no cancel button for a search that already succeeded.
    expect(host.querySelector('[data-testid="live-cancel-seek"]')).toBeNull();
  });
});
