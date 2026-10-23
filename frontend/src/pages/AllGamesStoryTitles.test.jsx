import React, { act } from "react";
import { createRoot } from "react-dom/client";

import AllGames from "./AllGames";

const mockNavigate = jest.fn();

jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}), { virtual: true });
jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("@/components/Layout", () => ({ children }) => <div>{children}</div>, { virtual: true });
jest.mock("@/components/curriculum/CurriculumStateStrip", () => () => null, { virtual: true });
jest.mock("@/lib/personalCurriculum", () => ({
  CURRICULUM_ROUTES: { home: "/home" },
}), { virtual: true });
jest.mock("framer-motion", () => ({
  motion: new Proxy({}, {
    get: () => ({ children, ...props }) => <div {...props}>{children}</div>,
  }),
}));

const reply = (body) => ({
  ok: true,
  status: 200,
  json: () => Promise.resolve(body),
});

// The games list shows each game's saved title and its rarest readable tags
// (services/game_tags.py, via /lab-coach-pick coaching.all_games).
describe("All games rows carry the game's title and tags", () => {
  let container;
  let root;

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

  test("a row shows its title and tag chips", async () => {
    global.fetch = jest.fn((url) => {
      if (url.endsWith("/lab-coach-pick")) {
        return Promise.resolve(reply({
          coaching: {
            all_games: [{
              game_id: "g1", opponent: "EddieDawg1971", result: "W", platform: "chess.com",
              story_title: "They missed chances, you won",
              story_tags: [
                { id: "user_queen_trapped_opponent_missed", label: "queen trapped, opponent missed" },
                { id: "reached_rook_endgame", label: "reached rook endgame" },
              ],
            }],
          },
        }));
      }
      if (url.endsWith("/game-review/recommendation")) {
        return Promise.resolve(reply({ enabled: false, status: "disabled", prescription: null }));
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    await act(async () => root.render(<AllGames user={{ user_id: "u1" }} />));
    await act(async () => { for (let i = 0; i < 8; i += 1) await Promise.resolve(); });
    expect(container.querySelector("[data-testid='game-row-title']").textContent)
      .toBe("They missed chances, you won");
    const chips = [...container.querySelectorAll("[data-testid='game-row-tags'] span")].map((s) => s.textContent);
    expect(chips).toEqual(["queen trapped, opponent missed", "reached rook endgame"]);
  });
});
