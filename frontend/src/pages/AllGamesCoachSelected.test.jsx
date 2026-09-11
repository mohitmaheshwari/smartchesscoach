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

const prescription = {
  schema_version: "coach_selected_game_review.v1",
  enabled: true,
  status: "recommended",
  review_states: { g1: "recommended" },
  prescription: {
    prescription_id: "p1",
    state: "recommended",
    game: {
      game_id: "g1",
      opponent: "AnandFan",
      result: "Lost",
      opening: "Italian Game",
    },
    reason: {
      headline: "I picked this game for your current lesson.",
      body: "It puts your lesson inside one real decision.",
    },
    chapters: [{
      event_id: "e1",
      label: "What was possible here",
      headline: "Your rook needed one more check.",
      explanation: "The queen could take it.",
      move_number: 14,
    }],
    review_url: "/game/g1?prescription=p1&resume=-1",
  },
};

describe("coach-selected Game Review", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    mockNavigate.mockReset();
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    delete global.fetch;
  });

  test("shows why the coach selected the game and starts it before navigating", async () => {
    global.fetch = jest.fn((url, options = {}) => {
      if (url.endsWith("/lab-coach-pick")) {
        return Promise.resolve(reply({
          coaching: {
            all_games: [{
              game_id: "g1",
              opponent: "AnandFan",
              result: "L",
              platform: "chess.com",
            }],
          },
        }));
      }
      if (url.endsWith("/game-review/recommendation") && !options.method) {
        return Promise.resolve(reply(prescription));
      }
      if (url.endsWith("/game-review/recommendation/p1/start")) {
        return Promise.resolve(reply({
          ...prescription,
          status: "started",
          prescription: {
            ...prescription.prescription,
            state: "started",
          },
        }));
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    await act(async () => root.render(<AllGames user={{ user_id: "u1" }} />));
    await act(async () => {
      for (let i = 0; i < 8; i += 1) await Promise.resolve();
    });

    expect(container.textContent).toContain("This is the game I want to study with you.");
    expect(container.textContent).toContain("I picked this game for your current lesson.");
    expect(container.textContent).toContain("What was possible here");
    expect(container.textContent).toContain("Coach’s pick");

    const start = Array.from(container.querySelectorAll("button"))
      .find((button) => button.textContent.includes("Review this with me"));
    await act(async () => start.click());
    await act(async () => {
      for (let i = 0; i < 5; i += 1) await Promise.resolve();
    });

    expect(global.fetch).toHaveBeenCalledWith(
      "https://api.test/game-review/recommendation/p1/start",
      { method: "POST", credentials: "include" },
    );
    expect(mockNavigate).toHaveBeenCalledWith(
      "/game/g1?prescription=p1&resume=-1",
    );
  });

  test("keeps the existing archive when the personal selector is disabled", async () => {
    global.fetch = jest.fn((url) => {
      if (url.endsWith("/lab-coach-pick")) {
        return Promise.resolve(reply({
          coaching: {
            all_games: [{
              game_id: "legacy-g1",
              opponent: "Opponent",
              result: "W",
              platform: "chess.com",
            }],
          },
        }));
      }
      return Promise.resolve(reply({
        enabled: false,
        status: "disabled",
        prescription: null,
      }));
    });

    await act(async () => root.render(<AllGames user={{ user_id: "u2" }} />));
    await act(async () => {
      for (let i = 0; i < 8; i += 1) await Promise.resolve();
    });

    expect(container.textContent).toContain("Let’s find the moment worth understanding.");
    expect(container.textContent).toContain("Won");
    expect(container.querySelector("[data-testid='coach-selected-review']")).toBeNull();
  });

  test("does not substitute the old selector when the recommendation fails", async () => {
    global.fetch = jest.fn((url) => {
      if (url.endsWith("/lab-coach-pick")) {
        return Promise.resolve(reply({
          coaching: {
            all_games: [{
              game_id: "archive-g1",
              opponent: "Opponent",
              result: "W",
              platform: "chess.com",
            }],
          },
        }));
      }
      return Promise.resolve({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ detail: "unavailable" }),
      });
    });

    await act(async () => root.render(<AllGames user={{ user_id: "u3" }} />));
    await act(async () => {
      for (let i = 0; i < 8; i += 1) await Promise.resolve();
    });

    expect(container.textContent).toContain("I could not load the right game just now.");
    expect(container.textContent).not.toContain("Let’s find the moment worth understanding.");
    expect(container.textContent).toContain("Won");
  });
});
