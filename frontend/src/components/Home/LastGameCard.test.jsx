/**
 * The card must never put an engine figure in front of the player, and it
 * must be invisible when there is nothing to say — a 204 is the honest empty
 * state, not an error to apologise for.
 */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

import LastGameCard from "./LastGameCard";

jest.mock("react-router-dom", () => ({ useNavigate: () => jest.fn() }), { virtual: true });
jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("lucide-react", () => ({
  ChevronRight: () => <span />, Clock3: () => <span data-testid="clock-icon" />,
}), { virtual: true });

const CARD = {
  state: "clock",
  headline: "You outplayed them. The clock ended it.",
  detail: "You were the steadier player here and your flag fell with the game still yours.",
  decided_by: "clock",
  turning_point_is_theirs: true,
  game_id: "g1",
  result: "lost",
  turning_point: {
    move_number: 13,
    san: "Bxd4",
    whose: "theirs",
    fen_before: "r1bq1rk1/ppp2pp1/3b3p/8/2BpQ3/3PB2P/PPP2PP1/R3K2R w KQ - 0 13",
    board_orientation: "black",
    cost: 492,
  },
  measured: { his_mean_cp: 44, their_mean_cp: 79, his_blunders: 0, their_blunders: 1, depth: 12 },
};

function mock(status, body) {
  global.fetch = jest.fn(() => Promise.resolve({
    ok: status === 200, status,
    json: () => Promise.resolve(body),
  }));
}

describe("LastGameCard", () => {
  let container, root;

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

  async function render() {
    await act(async () => root.render(<LastGameCard />));
    await act(async () => { for (let i = 0; i < 12; i += 1) await Promise.resolve(); });
  }

  test("renders the sentence and the position", async () => {
    mock(200, CARD);
    await render();
    expect(container.textContent).toContain("You outplayed them. The clock ended it.");
    expect(container.textContent).toContain("They played");
    expect(container.textContent).toContain("Bxd4");
    expect(container.querySelector("[role='img']")).toBeTruthy();
  });

  test("no engine figure reaches the screen", async () => {
    mock(200, CARD);
    await render();
    const text = container.textContent;
    for (const n of ["44", "79", "492", "centipawn", "cp", "depth"]) {
      expect(text.toLowerCase()).not.toContain(String(n).toLowerCase());
    }
  });

  test("the clock badge appears only for the clock state", async () => {
    mock(200, CARD);
    await render();
    expect(container.querySelector("[data-testid='clock-icon']")).toBeTruthy();

    await act(async () => root.unmount());
    container.innerHTML = "";
    root = createRoot(container);
    mock(200, { ...CARD, state: "outplayed", decided_by: "clock",
      headline: "They held together better than you did." });
    await render();
    expect(container.querySelector("[data-testid='clock-icon']")).toBeNull();
  });

  test("a 204 renders nothing at all", async () => {
    mock(204, null);
    await render();
    expect(container.querySelector("[data-testid='last-game-card']")).toBeNull();
    expect(container.textContent).toBe("");
  });

  test("a failed request never breaks Home", async () => {
    global.fetch = jest.fn(() => Promise.reject(new Error("offline")));
    await render();
    expect(container.textContent).toBe("");
  });

  test("the board is turned to the side he played", async () => {
    mock(200, CARD);
    await render();
    const squares = container.querySelectorAll("[role='img'] > div");
    expect(squares.length).toBe(64);
  });
});
