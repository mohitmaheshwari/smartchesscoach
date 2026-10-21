/**
 * The card must never put an engine figure in front of the player, and it
 * must be invisible when there is nothing to say — a 204 is the honest empty
 * state, not an error to apologise for.
 */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

import LastGameCard from "./LastGameCard";

const mockNavigate = jest.fn();
jest.mock("react-router-dom", () => ({ useNavigate: () => mockNavigate }), { virtual: true });
jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("lucide-react", () => ({
  ChevronRight: () => <span />, Clock3: () => <span data-testid="clock-icon" />,
}), { virtual: true });

// The board is the same react-chessboard the section below it uses, so the
// test records what the card ASKS it to draw rather than counting squares.
const boardProps = [];
jest.mock("react-chessboard", () => ({
  Chessboard: (props) => {
    boardProps.push(props);
    return <div data-testid="board" />;
  },
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
    boardProps.length = 0;
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
    expect(container.querySelector("[data-testid='board']")).toBeTruthy();
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

  test("the board shows the position before the move, turned to his side", async () => {
    mock(200, CARD);
    await render();
    expect(boardProps).toHaveLength(1);
    expect(boardProps[0].position).toBe(CARD.turning_point.fen_before);
    // He was Black in this fixture; showing it from White's side would put
    // the moment he is being asked to look at upside down.
    expect(boardProps[0].boardOrientation).toBe("black");
    expect(boardProps[0].arePiecesDraggable).toBe(false);
  });

  test("it draws the move it names", async () => {
    // Mohit 2026-10-17, on a card showing 4...Bd6 -- the position BEFORE
    // the move, so every black piece was still on its home square and the
    // only sign of the move was the sentence underneath: "look, bd6 here,
    // look at board, it doesn't make sense."
    mock(200, { ...CARD, turning_point: { ...CARD.turning_point, from: "c5", to: "d4" } });
    await render();
    expect(boardProps[0].customArrows).toEqual([["c5", "d4", "#b45309"]]);
    expect(Object.keys(boardProps[0].customSquareStyles)).toEqual(["c5", "d4"]);
  });

  test("a card with no squares draws no arrow rather than a wrong one", async () => {
    mock(200, CARD);                       // fixture carries no from/to
    await render();
    expect(boardProps[0].customArrows).toEqual([]);
    expect(boardProps[0].customSquareStyles).toEqual({});
  });

  test("it is drawn with the page's own board, not one of its own", async () => {
    mock(200, CARD);
    await render();
    // The first cut drew a board out of unicode glyphs and a text-shadow
    // outline, which is what "UX sucks" was about.
    expect(container.querySelector("[data-testid='board']")).toBeTruthy();
    expect(container.textContent).not.toContain("♚");
  });

  // ─── The game story on the card (docs/game_story_on_screen_scope.md) ───

  const STORY_CARD = {
    ...CARD,
    state: "outplayed",
    headline: "They held together better than you did.",
    detail: "They gave you less to work with than you gave them.",
    chosen_by: "last_game",
    review_url: "/game/g1",
    board: {
      source: "story",
      fen_before: "8/p4p2/1p2p3/2p1k1p1/8/2P2KP1/PP3P1P/8 w - - 4 32",
      san: "Kg3",
      from: "f2",
      to: "g3",
      board_orientation: "white",
    },
    story_lines: [
      { kind: "moment", polarity: "negative", san: "Kg3", text: "This is where the game got away." },
      { kind: "moment", polarity: "positive", san: "b4", text: "Found the best move when it mattered" },
      { kind: "stretch", polarity: "negative", san: null, text: "Their rooks worked together and yours did not." },
    ],
  };

  test("it shows the story lines, each located by its move", async () => {
    mock(200, STORY_CARD);
    await render();
    const lines = [...container.querySelectorAll("[data-testid='last-game-story-line']")];
    expect(lines.map((l) => l.textContent)).toEqual([
      "Kg3This is where the game got away.",
      "b4Found the best move when it mattered",
      "Their rooks worked together and yours did not.",
    ]);
  });

  test("the board and the first line point at the same move", async () => {
    mock(200, STORY_CARD);
    await render();
    expect(boardProps[0].position).toBe(STORY_CARD.board.fen_before);
    expect(boardProps[0].customArrows).toEqual([["f2", "g3", "#b45309"]]);
    // Not "It is where the game turned": that sentence belongs to the
    // both-sides turning point, which is not what the board shows here.
    expect(container.textContent).toContain("You played Kg3 here.");
    expect(container.textContent).not.toContain("It is where the game turned");
  });

  test("no number reaches the player except inside a move", async () => {
    mock(200, STORY_CARD);
    await render();
    const story = container.querySelector("[data-testid='last-game-story']").textContent;
    const withoutMoves = story.replace(/Kg3|b4/g, "");
    expect(withoutMoves).not.toMatch(/\d/);
  });

  test("a game the coach picked says so, and opens the pick's review", async () => {
    mockNavigate.mockClear();
    mock(200, { ...STORY_CARD, chosen_by: "coach_pick",
      review_url: "/game/g1?prescription=grp_1&resume=-1" });
    await render();
    expect(container.textContent).toContain("A game worth reviewing");
    expect(container.textContent).not.toContain("Your last game");
    await act(async () => container.querySelector("button").click());
    expect(mockNavigate).toHaveBeenCalledWith("/game/g1?prescription=grp_1&resume=-1");
  });

  test("the ledger story's title heads the lines when there is one", async () => {
    mock(200, { ...STORY_CARD, story_title: "A win with narrow escapes" });
    await render();
    const story = container.querySelector("[data-testid='last-game-story']");
    expect(story.textContent).toContain("A win with narrow escapes");
    expect(story.textContent).not.toContain("What this game left you");
  });

  test("a card without a story renders as it always did", async () => {
    mock(200, CARD);
    await render();
    expect(container.querySelector("[data-testid='last-game-story']")).toBeNull();
    expect(container.textContent).toContain("Your last game");
  });
});
