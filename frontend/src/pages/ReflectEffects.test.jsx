import React, { act } from "react";
import { createRoot } from "react-dom/client";

import Reflect from "./Reflect";

jest.mock("react-router-dom", () => ({ useNavigate: () => jest.fn() }), { virtual: true });
jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("@/components/Layout", () => ({ children }) => <div>{children}</div>, { virtual: true });
jest.mock("@/components/CoachBoard", () => {
  const ReactModule = require("react");
  return ReactModule.forwardRef(({ position }, _ref) => {
    return <div data-testid="reflect-board">{position}</div>;
  });
}, { virtual: true });
jest.mock("@/components/FeedbackModal", () => () => null, { virtual: true });
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));
jest.mock("framer-motion", () => ({
  motion: new Proxy({}, { get: () => ({ children, ...props }) => <div {...props}>{children}</div> }),
  AnimatePresence: ({ children }) => <>{children}</>,
}));

const response = (body) => ({ ok: true, status: 200, json: () => Promise.resolve(body) });
const deferred = () => {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
};
const games = [
  { game_id: "game-1", opponent_name: "First", user_color: "white", result: "loss", time_control: "10+0" },
  { game_id: "game-2", opponent_name: "Second", user_color: "black", result: "loss", time_control: "10+0" },
];
const moment = (number, userMove, bestMove) => ({
  move_number: number,
  type: "mistake",
  fen: "8/8/8/8/8/8/4K3/6k1 w - - 0 1",
  user_move: userMove,
  best_move: bestMove,
  eval_change: -1,
});

describe("Reflect game and moment ownership", () => {
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
    jest.restoreAllMocks();
  });

  const flush = async () => {
    await act(async () => {
      for (let i = 0; i < 16; i += 1) await Promise.resolve();
    });
  };

  const switchToSecondGame = () => {
    const dots = [...container.querySelectorAll("button")]
      .filter((button) => button.className.includes("w-2 h-2"));
    expect(dots).toHaveLength(2);
    act(() => dots[1].click());
  };

  const commonResponse = (url) => {
    if (url.endsWith("/reflect/v1/profile")) return Promise.resolve(response({}));
    if (url.endsWith("/reflect/pending")) return Promise.resolve(response({ games }));
    if (url.includes("/contextual-tags")) return Promise.resolve(response({ tags: [] }));
    if (url.includes("/quick-tags")) return Promise.resolve(response({ tags: [] }));
    if (url.includes("/time-context")) return Promise.resolve(response({ clock_state: "normal" }));
    if (url.includes("/intent-hypotheses")) return Promise.resolve(response({ hypotheses: [] }));
    return null;
  };

  test("a late prior-game explanation cannot replace the current moment", async () => {
    const oldExplanation = deferred();
    global.fetch = jest.fn((url, options = {}) => {
      const common = commonResponse(url);
      if (common) return common;
      if (url.endsWith("/reflect/game/game-1/moments")) {
        return Promise.resolve(response({ moments: [moment(1, "Kd3", "Kf3")] }));
      }
      if (url.endsWith("/reflect/game/game-2/moments")) {
        return Promise.resolve(response({ moments: [moment(2, "Ke3", "Kd3")] }));
      }
      if (url.endsWith("/reflect/explain-moment")) {
        const body = JSON.parse(options.body);
        return body.user_move === "Kd3"
          ? oldExplanation.promise
          : Promise.resolve(response({ impact: "NEW IMPACT", better_plan: "NEW PLAN" }));
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    await act(async () => root.render(<Reflect user={{ user_id: "student-1" }} />));
    await flush();
    expect(container.textContent).toContain("Move 1");

    switchToSecondGame();
    await flush();
    expect(container.textContent).toContain("Move 2");
    expect(container.textContent).toContain("NEW IMPACT");

    oldExplanation.resolve(response({ impact: "OLD IMPACT", better_plan: "OLD PLAN" }));
    await flush();
    expect(container.textContent).toContain("NEW IMPACT");
    expect(container.textContent).not.toContain("OLD IMPACT");
  });

  test("a late prior-game moments list cannot replace the selected game", async () => {
    const oldMoments = deferred();
    global.fetch = jest.fn((url) => {
      const common = commonResponse(url);
      if (common) return common;
      if (url.endsWith("/reflect/game/game-1/moments")) return oldMoments.promise;
      if (url.endsWith("/reflect/game/game-2/moments")) {
        return Promise.resolve(response({ moments: [moment(2, "Ke3", "Kd3")] }));
      }
      if (url.endsWith("/reflect/explain-moment")) {
        return Promise.resolve(response({ impact: "SECOND GAME", better_plan: "Stay current" }));
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    await act(async () => root.render(<Reflect user={{ user_id: "student-1" }} />));
    await flush();
    switchToSecondGame();
    await flush();
    expect(container.textContent).toContain("Move 2");

    oldMoments.resolve(response({ moments: [moment(1, "Kd3", "Kf3")] }));
    await flush();
    expect(container.textContent).toContain("Move 2");
    expect(container.textContent).not.toContain("Move 1");
  });
});
