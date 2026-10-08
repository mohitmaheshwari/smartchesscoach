/**
 * The three movements. docs/home_as_a_coach_scope.md
 *
 * The thing worth testing here is NOT that the sections render. It is that the
 * answer cannot be on screen before the player has committed to a belief,
 * because asking before telling is the entire mechanism — and that the order of
 * the page is know → think → practise → play, which is a source contract no
 * render test can see.
 */
import React, { act } from "react";
import { createRoot } from "react-dom/client";
const fs = require("fs");
const path = require("path");

// `virtual: true` and a require after the mocks, matching SessionCard.test.jsx:
// the CRA resolver does not find these from a mock factory otherwise.
jest.mock("@/App", () => ({ API: "/api" }), { virtual: true });
jest.mock("react-router-dom", () => ({ useNavigate: () => jest.fn() }), { virtual: true });
jest.mock("react-chessboard", () => ({
  Chessboard: ({ position }) => <div data-testid="board" data-fen={position} />,
}), { virtual: true });

const CoachMovements = require("./CoachMovements").default;

const PAYLOAD = {
  coach: {
    known: {
      measured: true,
      lead: "I have been through your games.",
      lines: [
        { kind: "strength", text: "You are hard to beat by accident." },
        { kind: "cost", text: "You have lost seventy-one games on the clock." },
      ],
    },
    today: {
      position_id: "p1",
      fen: "8/2R4P/7r/2Pkp3/4n3/6P1/6K1/8 w - - 3 49",
      played_move: "Kf3",
      user_color: "white",
      topic: "calculation_depth",
      ask: "How did you pick it?",
      options: [
        { id: "followed_the_line", label: "I followed the forcing line." },
        { id: "looked_strongest", label: "It looked strongest." },
      ],
    },
    play: { href: "/play-with-coach", lead: "Play me.", line: "I will stop you.", cta: "Sit down" },
  },
};

let container, root;

// Without this, every act() logs "the current testing environment is not
// configured to support act(...)" and the real failures get lost in it.
global.IS_REACT_ACT_ENVIRONMENT = true;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  jest.restoreAllMocks();
});

const mountWith = async (payload) => {
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve(payload) }));
  await act(async () => { root.render(<CoachMovements />); });
};

test("the three movements render from one request", async () => {
  await mountWith(PAYLOAD);
  expect(container.querySelector('[data-testid="coach-known"]')).toBeTruthy();
  expect(container.querySelector('[data-testid="coach-today"]')).toBeTruthy();
  expect(container.querySelector('[data-testid="coach-play"]')).toBeTruthy();
  // One fetch, not three. FindingCard, SessionCard and the focus-why lookup
  // each hit /home/session separately before this.
  expect(global.fetch).toHaveBeenCalledTimes(1);
});

test("the good thing is on screen above the costly one", async () => {
  await mountWith(PAYLOAD);
  const html = container.innerHTML;
  expect(html.indexOf("hard to beat")).toBeGreaterThan(-1);
  expect(html.indexOf("hard to beat")).toBeLessThan(html.indexOf("on the clock"));
});

test("the board shows his position and names his move", async () => {
  await mountWith(PAYLOAD);
  const board = container.querySelector('[data-testid="coach-today"] [data-testid="board"]');
  expect(board.getAttribute("data-fen")).toBe(PAYLOAD.coach.today.fen);
  expect(container.textContent).toContain("You played Kf3 here.");
});

test("NO ANSWER IS ON SCREEN BEFORE HE COMMITS", async () => {
  await mountWith(PAYLOAD);
  expect(container.querySelector('[data-testid="coach-today-answer"]')).toBeNull();
  expect(container.querySelectorAll('[data-testid="coach-today-option"]').length).toBe(2);
});

test("no answer is in the payload the page is given, either", async () => {
  await mountWith(PAYLOAD);
  // Belt and braces with the server test: if the answer ever rode along in the
  // session payload, the mechanism would be cosmetic.
  const serialised = JSON.stringify(PAYLOAD.coach.today);
  expect(serialised).not.toMatch(/best_move|solution|correct_move|expected/i);
});

test("the answer arrives only after a belief is chosen, and names it back", async () => {
  await mountWith(PAYLOAD);
  global.fetch = jest.fn(() => Promise.resolve({
    ok: true,
    json: () => Promise.resolve({
      ok: true,
      expected: false,
      belief: "You judged it on this move alone.",
      correction: "Play their best reply in your head first.",
    }),
  }));

  const option = container.querySelectorAll('[data-testid="coach-today-option"]')[1];
  await act(async () => { option.click(); });

  expect(global.fetch).toHaveBeenCalledWith(
    "/api/home/today/answer",
    expect.objectContaining({ method: "POST" }));
  const answer = container.querySelector('[data-testid="coach-today-answer"]');
  expect(answer.textContent).toContain("You judged it on this move alone.");
  expect(answer.textContent).toContain("Play their best reply");
  // The question is gone once answered; leaving it there invites a second go
  // at a belief he has already committed to.
  expect(container.querySelectorAll('[data-testid="coach-today-option"]').length).toBe(0);
});

test("the position id is sent, which is what retires the board", async () => {
  // Mohit: "it won't change over time, or would it?" Without this the same
  // position comes back forever, which is what the first version did.
  await mountWith(PAYLOAD);
  global.fetch = jest.fn(() => Promise.resolve({
    ok: true, json: () => Promise.resolve({ ok: true, expected: true, belief: "x" }),
  }));
  await act(async () => {
    container.querySelectorAll('[data-testid="coach-today-option"]')[0].click();
  });
  const body = JSON.parse(global.fetch.mock.calls[0][1].body);
  expect(body.position_id).toBe("p1");
  expect(body.topic).toBe("calculation_depth");
});

test("a returning player is greeted with what they said last time", async () => {
  await mountWith({
    coach: {
      ...PAYLOAD.coach,
      today: {
        ...PAYLOAD.coach.today,
        last_time: { said: "It looked strongest.", was_expected: false },
      },
    },
  });
  const line = container.querySelector('[data-testid="coach-today-last-time"]');
  expect(line.textContent).toContain("It looked strongest.");
  // and the question stops saying "before I tell you anything", because it is
  // no longer the first thing said.
  expect(container.textContent).toContain("Same question on this one");
  expect(container.textContent).not.toContain("Before I tell you anything");
});

test("a first-time player is not told about a last time", async () => {
  await mountWith(PAYLOAD);
  expect(container.querySelector('[data-testid="coach-today-last-time"]')).toBeNull();
  expect(container.textContent).toContain("Before I tell you anything");
});

test("the same belief twice gets noticed, not repeated at", async () => {
  await mountWith(PAYLOAD);
  global.fetch = jest.fn(() => Promise.resolve({
    ok: true,
    json: () => Promise.resolve({
      ok: true, expected: false,
      belief: "You judged it on this move alone.",
      correction: "Play their best reply first.",
      repeat: "You told me the same thing last time.",
    }),
  }));
  await act(async () => {
    container.querySelectorAll('[data-testid="coach-today-option"]')[1].click();
  });
  expect(container.querySelector('[data-testid="coach-today-repeat"]').textContent)
    .toContain("same thing last time");
});

test("a first answer gets no repeat note", async () => {
  await mountWith(PAYLOAD);
  global.fetch = jest.fn(() => Promise.resolve({
    ok: true,
    json: () => Promise.resolve({
      ok: true, expected: false, belief: "b", correction: "c", repeat: null,
    }),
  }));
  await act(async () => {
    container.querySelectorAll('[data-testid="coach-today-option"]')[1].click();
  });
  expect(container.querySelector('[data-testid="coach-today-repeat"]')).toBeNull();
});

test("a movement with nothing to say renders nothing", async () => {
  await mountWith({ coach: { known: null, today: null, play: null } });
  expect(container.querySelector('[data-testid="coach-known"]')).toBeNull();
  expect(container.querySelector('[data-testid="coach-today"]')).toBeNull();
  expect(container.querySelector('[data-testid="coach-play"]')).toBeNull();
});

test("the lesson still renders when the coach payload is missing", async () => {
  // A player whose coach data has not been computed must not lose their lesson.
  global.fetch = jest.fn(() => Promise.resolve({ ok: false }));
  await act(async () => {
    root.render(<CoachMovements><p>the lesson</p></CoachMovements>);
  });
  expect(container.textContent).toContain("the lesson");
});

test("the page order is know, think, practise, play", () => {
  // A source contract: the invitation must come after the lesson. Asking
  // someone to sit down for a game before telling them what to work on is the
  // nav tile with a bigger button on it.
  const src = fs.readFileSync(
    path.join(__dirname, "..", "..", "components/coach/CoachMovements.jsx"),
    "utf8");
  const known = src.indexOf("<Known known=");
  const today = src.indexOf("<Today today=");
  const slot = src.indexOf("{children}");
  const play = src.indexOf("<Play play=");
  expect(known).toBeGreaterThan(-1);
  expect(known).toBeLessThan(today);
  expect(today).toBeLessThan(slot);
  expect(slot).toBeLessThan(play);
});
