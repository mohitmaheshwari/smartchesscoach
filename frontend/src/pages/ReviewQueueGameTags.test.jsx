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
      body = { tags: [{ id: "user_let_off", games: 872 }, { id: "user_queen_trapped_opponent_missed", games: 14 }], tagged_games: 2000 };
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

test("tags are offered rarest first, with their counts", async () => {
  await render();
  const options = [...container.querySelectorAll("[data-testid='tag-filter-select'] option")].map((o) => o.textContent);
  expect(options[1]).toBe("queen trapped, opponent missed (14)");
  expect(options[2]).toBe("let off (872)");
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

test("a tag chip on a row opens the game at that move", async () => {
  await render();
  const chip = [...container.querySelectorAll("[data-testid='game-tag-chips'] button")]
    .find((b) => b.textContent.startsWith("queen trapped"));
  expect(chip.textContent).toBe("queen trapped, opponent missed · Ng5");
  await act(async () => chip.click());
  expect(mockNavigate).toHaveBeenCalledWith("/lab/game/g1?move=16");
});
