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
    expect(onOpenMove).toHaveBeenCalledWith({ move_number: 39, move_san: "b4", side: "you" });
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

  // ─── The ledger story (docs/game_story_by_phase_scope.md v2) ───

  const PLAN_STORY = {
    ...STORY,
    plan: {
      type: { id: "narrow_escapes", title: "A win with narrow escapes" },
      chapters: [
        { id: "start", title: "The start", lines: [
          { kind: "opening", side: "you", san: null, polarity: "neutral",
            text: "You came out of the Queen's Pawn Opening with the better position." },
        ] },
        { id: "middle", title: "The middle", lines: [
          { kind: "your_mistake", side: "you", san: "Ng5", move_number: 16, polarity: "negative",
            text: "Ng5 nearly cost you your queen. After Rh1, she would have had no safe square. They played f4 instead." },
          { kind: "their_mistake", side: "them", san: "f4", move_number: 17, polarity: "positive",
            text: "They went wrong with f4, and you found a good answer: Bxc3." },
        ] },
        { id: "finish", title: "The finish", lines: [
          { kind: "finish", side: null, san: null, polarity: "neutral",
            text: "From there you stayed well ahead, and they resigned." },
        ] },
      ],
      lesson: { id: "let_off", text: "Your opponent let you off more than once." },
      coach_notes: [
        { kind: "your_mistake", side: "you", san: "Ng5", move_number: 16, polarity: "negative",
          text: "Best was Bxc3. After Rh1, every square your queen could reach was covered. They played f4." },
      ],
    },
  };

  test("the plan is told as a title and three chapters", async () => {
    mock(200, PLAN_STORY);
    await render();
    expect(container.querySelector("[data-testid='game-story-title']").textContent).toBe("A win with narrow escapes");
    const text = container.textContent;
    expect(text).toContain("The start");
    expect(text).toContain("The middle");
    expect(text).toContain("The finish");
    expect(text).toContain("Ng5 nearly cost you your queen.");
    expect(container.querySelector("[data-testid='game-story-lesson']").textContent)
      .toContain("Your opponent let you off more than once.");
    // The earlier moment list is not shown beside the plan.
    expect(container.querySelectorAll("[data-testid='game-story-moment']")).toHaveLength(0);
  });

  test("the written title leads, with the story type above it and the teaching below", async () => {
    mock(200, { ...PLAN_STORY, headline: {
      title: "They missed chances, you won",
      teaching: "You won partly because they missed chances you gave them.",
      source: "llm",
    } });
    await render();
    expect(container.querySelector("[data-testid='game-story-title']").textContent)
      .toBe("They missed chances, you won");
    expect(container.querySelector("[data-testid='game-story-teaching']").textContent)
      .toContain("missed chances you gave them");
    expect(container.textContent).toContain("A win with narrow escapes");
  });

  test("a line about their move opens THEIR move", async () => {
    mock(200, PLAN_STORY);
    const onOpenMove = jest.fn();
    await render({ onOpenMove });
    const buttons = [...container.querySelectorAll("button[data-testid='game-story-line']")];
    const theirLine = buttons.find((b) => b.textContent.includes("They went wrong with f4"));
    await act(async () => theirLine.click());
    expect(onOpenMove).toHaveBeenCalledWith({ move_number: 17, move_san: "f4", side: "them" });
  });

  test("a line with no move is text, not a button", async () => {
    mock(200, PLAN_STORY);
    await render();
    const plain = [...container.querySelectorAll("div[data-testid='game-story-line']")];
    expect(plain.map((d) => d.textContent)).toEqual(expect.arrayContaining([
      expect.stringContaining("You came out of the Queen's Pawn Opening"),
    ]));
  });

  test("coach notes are the same moments as study notes", async () => {
    mock(200, PLAN_STORY);
    await render();
    await act(async () => container.querySelector("[data-testid='game-story-mode-coach']").click());
    const notes = container.querySelectorAll("[data-testid='game-story-coach-note']");
    expect(notes).toHaveLength(1);
    expect(notes[0].textContent).toContain("Best was Bxc3.");
  });

  test("the plan has no number outside a move", async () => {
    mock(200, PLAN_STORY);
    await render();
    const stripped = container.textContent.replace(/\b(?:[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8][+#]?)/g, "");
    expect(stripped).not.toMatch(/\d/);
  });
});
