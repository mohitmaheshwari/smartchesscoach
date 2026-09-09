/**
 * A clock focus must never render the puzzle surface.
 *
 * /training/pattern/time_collapse showed "No puzzles for Calculate the Reply
 * yet", an empty board and "Nothing to solve here right now", while Progress
 * called time discipline the player's number one focus. The focus was correct
 * -- 144 of 783 games lost on the clock -- but puzzles cannot train clock use,
 * so there was nothing to show. Reported live 2026-09-09.
 *
 * See docs/time_management_practice_scope.md.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";

const mockNavigate = jest.fn();
let mockPattern = "time_collapse";

jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
  useSearchParams: () => [new URLSearchParams(""), jest.fn()],
  useParams: () => ({ pattern: mockPattern }),
  Link: ({ children }) => children,
}), { virtual: true });

jest.mock("@/App", () => ({ API: "https://api.test/api" }), { virtual: true });
jest.mock("framer-motion", () => ({
  motion: new Proxy({}, { get: () => ({ children }) => children }),
}), { virtual: true });
jest.mock("@/components/LichessBoard", () => ({
  __esModule: true, default: () => null,
}), { virtual: true });
jest.mock("@/components/training/PICPieceSafetyLesson", () => ({
  __esModule: true, default: () => null,
}), { virtual: true });
jest.mock("@/components/training/CanonicalTrainingAssignment", () => ({
  __esModule: true, default: () => null,
}), { virtual: true });
jest.mock("@/components/training/DifficultySelector", () => ({
  __esModule: true, default: () => null,
}), { virtual: true });
jest.mock("@/components/training/PersonalizedLessonWorkspace", () => ({
  __esModule: true, default: () => null,
}), { virtual: true });
jest.mock("@/hooks/useMoveCaption", () => ({
  __esModule: true, default: () => ({}),
}), { virtual: true });

const PrescribedTraining = require("./PrescribedTraining").default;

let container;
let root;

const profile = {
  eligible: true,
  games_with_clock_data: 55,
  timeout_losses: 14,
  timeout_loss_rate_pct: 25.5,
  sample: "timeout_losses",
  sample_size: 14,
  pct_clock_by_move_10: 42.8,
  pct_clock_by_move_20: 76.7,
  avg_longest_think_seconds: 67,
  worst_think_seconds: 141,
  long_thinks_per_game: 0.8,
  longest_think_phase: { moves_1_10: 3, moves_11_20: 6, moves_21_30: 4, moves_31_plus: 1 },
  burn_moments: [{ game_id: "g1", move_number: 7, seconds: 141, lost_on_time: true }],
};

beforeEach(() => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  window.posthog = { capture: jest.fn() };
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve(profile) })
  );
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  delete window.posthog;
  delete global.fetch;
  mockPattern = "time_collapse";
});

const render = async () => {
  act(() => root.render(<PrescribedTraining user={{ id: "u1" }} />));
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
};

test("a clock focus shows the time profile, not a puzzle board", async () => {
  await render();
  expect(container.querySelector('[data-testid="time-profile-panel"]')).not.toBeNull();
  expect(container.textContent).not.toContain("No puzzle available");
  expect(container.textContent).not.toContain("Calculate the Reply");
  expect(container.textContent).not.toContain("Nothing to solve here right now");
});

test("it reports the player's own clock numbers", async () => {
  await render();
  expect(container.textContent).toContain("42.8%");
  expect(container.textContent).toContain("76.7%");
  expect(container.textContent).toContain("14");
  expect(container.textContent).toContain("2m 21s"); // 141s worst think
});

test("it stays silent when there is not enough clock data", async () => {
  global.fetch = jest.fn(() =>
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve({
        eligible: false, reason: "not_enough_clock_data",
        games_with_clock_data: 2, games_needed: 5,
      }),
    })
  );
  await render();
  expect(container.textContent).toContain("enough games with clock data");
  expect(container.textContent).not.toContain("42.8%");
});

test("a board pattern still uses the puzzle surface", async () => {
  mockPattern = "piece_safety";
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve({ puzzles: [], pool_thin: true }) })
  );
  await render();
  expect(container.querySelector('[data-testid="time-profile-panel"]')).toBeNull();
});
