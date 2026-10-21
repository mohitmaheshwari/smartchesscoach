/**
 * The story at the top of the review: every row is a move the player can
 * open, and it stays invisible when there is nothing to say.
 */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

import GameStoryPanel from "./GameStoryPanel";

jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
const mockTrack = jest.fn();
jest.mock("@/lib/analytics", () => ({
  ANALYTICS_EVENTS: { GAME_STORY_LINE_OPENED: "game_story_line_opened" },
  track: (...args) => mockTrack(...args),
}), { virtual: true });

const STORY = {
  schema_version: "game_story.v3",
  moments_showable: [
    { id: "located_turn", polarity: "negative", move_san: "Kg3", move_number: 32,
      display_name: "This is where the game got away.", display_detail: null },
    { id: "found_best_in_critical", polarity: "positive", move_san: "b4", move_number: 39,
      display_name: "Found the best move when it mattered",
      display_detail: "The position was sharp and the strongest move was the one played." },
  ],
  spans: [
    { id: "bs_rooks", display_name: "Their rooks worked together and yours did not." },
  ],
};

function mock(status, body) {
  global.fetch = jest.fn(() => Promise.resolve({
    ok: status === 200, status, json: () => Promise.resolve(body),
  }));
}

describe("GameStoryPanel", () => {
  let container, root;

  beforeEach(() => {
    mockTrack.mockClear();
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

  async function render(props) {
    await act(async () => root.render(<GameStoryPanel gameId="g1" {...props} />));
    await act(async () => { for (let i = 0; i < 8; i += 1) await Promise.resolve(); });
  }

  test("it reads the story for this game", async () => {
    mock(200, STORY);
    await render();
    expect(global.fetch.mock.calls[0][0]).toBe("https://api.test/games/g1/story");
    const rows = container.querySelectorAll("[data-testid='game-story-moment']");
    expect(rows).toHaveLength(2);
    expect(rows[0].textContent).toContain("Kg3");
    expect(rows[0].textContent).toContain("This is where the game got away");
    expect(container.textContent).toContain("Their rooks worked together and yours did not.");
  });

  test("tapping a row opens that move and is recorded", async () => {
    mock(200, STORY);
    const onOpenMove = jest.fn();
    await render({ onOpenMove });
    await act(async () => container.querySelectorAll("[data-testid='game-story-moment']")[1].click());
    expect(onOpenMove).toHaveBeenCalledWith(STORY.moments_showable[1]);
    expect(mockTrack).toHaveBeenCalledWith("game_story_line_opened", expect.objectContaining({
      source: "review", content_id: "found_best_in_critical", position_index: 1,
    }));
  });

  test("a moment with no move is not shown, since it cannot be opened", async () => {
    mock(200, { ...STORY, moments_showable: [{ ...STORY.moments_showable[0], move_san: null }] });
    await render();
    expect(container.querySelectorAll("[data-testid='game-story-moment']")).toHaveLength(0);
  });

  test("an empty story renders nothing", async () => {
    mock(200, { moments_showable: [], spans: [] });
    await render();
    expect(container.textContent).toBe("");
  });

  test("a failed request renders nothing and never throws", async () => {
    global.fetch = jest.fn(() => Promise.reject(new Error("offline")));
    await render();
    expect(container.textContent).toBe("");
  });

  test("rows are titles, so none ends in a full stop", async () => {
    mock(200, STORY);
    await render();
    const rows = [...container.querySelectorAll("[data-testid='game-story-moment']")];
    expect(rows[0].textContent).toContain("This is where the game got away");
    expect(rows[0].textContent).not.toContain("got away.");
  });

  test("no number reaches the player except inside a move", async () => {
    mock(200, STORY);
    await render();
    expect(container.textContent.replace(/Kg3|b4/g, "")).not.toMatch(/\d/);
  });
});
