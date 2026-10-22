/**
 * The review queue finds games by game tag (services/game_tags.py), and a tag
 * chip opens the game at the move behind it.
 */
import { createRoot } from "react-dom/client";
import { act } from "react";

import ReviewQueue from "@/pages/ReviewQueue";

jest.mock("@/App", () => ({ API: "http://test/api" }));
jest.mock("@/components/Layout", () => ({ children }) => <div data-testid="layout">{children}</div>);
const mockNavigate = jest.fn();
jest.mock("react-router-dom", () => ({ useNavigate: () => mockNavigate }), { virtual: true });
jest.mock("lucide-react", () => ({ ChevronRight: () => <span />, Flag: () => <span />, Search: () => <span /> }), { virtual: true });

const GAME = {
  game_id: "g1", owner_user_id: "u1", owner_name: "Mohit", opening: "Queen's Pawn Opening",
  result: "win", user_color: "black", opponent: "EddieDawg1971", blunders: 2, mistakes: 3,
  flag_count: 0, game_tags: ["opening_queens_pawn_opening", "user_queen_trapped_opponent_missed", "user_let_off"],
  game_tag_moves: { user_queen_trapped_opponent_missed: [{ move_number: 16, san: "Ng5", side: "you" }] },
};

let container, root;
beforeEach(() => {
  mockNavigate.mockClear();
  global.IS_REACT_ACT_ENVIRONMENT = true;
  global.fetch = jest.fn((url) => {
    let body = {};
    if (url.includes("/reviewer/game-tags")) {
      body = { tags: [{ id: "user_let_off", games: 872 }, { id: "user_queen_trapped_opponent_missed", games: 14 },
        { id: "user_delivered_back_rank_mate", games: 29 }], tagged_games: 2000 };
    } else if (url.includes("/reviewer/owners")) {
      body = { owners: [] };
    } else if (url.includes("/reviewer/games")) {
      body = { games: [GAME], total: 1, page: 1, page_size: 50, has_more: false };
    }
    return Promise.resolve({ ok: true, status: 200, json: async () => body });
  });
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(() => { act(() => root.unmount()); container.remove(); delete global.fetch; });

async function render() {
  await act(async () => root.render(<ReviewQueue user={{}} />));
  await act(async () => { for (let i = 0; i < 10; i += 1) await Promise.resolve(); });
}

const gameCalls = () => global.fetch.mock.calls.map(([u]) => u).filter((u) => u.includes("/reviewer/games"));

test("tags are grouped by kind, rarest first, with their counts", async () => {
  await render();
  const groups = [...container.querySelectorAll("[data-testid='tag-filter-select'] optgroup")];
  expect(groups.map((g) => g.label)).toEqual(["Got away with it, or punished", "Checkmates"]);
  expect([...groups[0].querySelectorAll("option")].map((o) => o.textContent)).toEqual([
    "queen trapped, opponent missed (14)", "let off (872)",
  ]);
  expect(groups[1].querySelector("option").textContent).toBe("delivered back rank mate (29)");
});

test("choosing a tag searches every analysed game for it", async () => {
  await render();
  const select = container.querySelector("[data-testid='tag-filter-select']");
  await act(async () => {
    select.value = "user_queen_trapped_opponent_missed";
    select.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await act(async () => { for (let i = 0; i < 10; i += 1) await Promise.resolve(); });
  const last = gameCalls().pop();
  expect(last).toContain("tags=user_queen_trapped_opponent_missed");
  expect(last).toContain("regenerated_only=false");
  expect(container.querySelector("[data-testid='tag-filter-chip']").textContent)
    .toContain("queen trapped, opponent missed");
});

test("a failed tag request is retried instead of leaving the picker empty", async () => {
  // Mohit, 2026-10-22: a tab opened during a server outage showed "Add a
  // tag (0)" for hours, because the tag list was fetched once and never again.
  jest.useFakeTimers();
  let tagCalls = 0;
  const ok = global.fetch;
  global.fetch = jest.fn((url) => {
    if (url.includes("/reviewer/game-tags")) {
      tagCalls += 1;
      if (tagCalls === 1) return Promise.resolve({ ok: false, status: 504, json: async () => ({}) });
    }
    return ok(url);
  });
  try {
    await render();
    expect(container.querySelector("[data-testid='tag-filter-select'] option").textContent).toBe("Add a tag (0)");
    await act(async () => { jest.advanceTimersByTime(2100); });
    await act(async () => { for (let i = 0; i < 10; i += 1) await Promise.resolve(); });
    expect(tagCalls).toBe(2);
    expect(container.querySelector("[data-testid='tag-filter-select'] option").textContent).toBe("Add a tag (3)");
  } finally {
    jest.useRealTimers();
  }
});

test("a tag chip on a row opens the game at that move", async () => {
  await render();
  const chip = [...container.querySelectorAll("[data-testid='game-tag-chips'] button")]
    .find((b) => b.textContent.startsWith("queen trapped"));
  expect(chip.textContent).toBe("queen trapped, opponent missed · Ng5");
  await act(async () => chip.click());
  expect(mockNavigate).toHaveBeenCalledWith("/lab/game/g1?move=16");
});
