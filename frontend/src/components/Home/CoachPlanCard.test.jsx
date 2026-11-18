/**
 * The plan card, from the 2026-11-16 live read (Mohit: "look at text,
 * completely meaningless"): an opening step must show the board it talks
 * about, "See where it happened" must open where it happened, a warning sign
 * ending in "?" must not print "?.", and the trained step must not say
 * "Same as before" beside "Waiting for games".
 */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

import CoachPlanCard from "./CoachPlanCard";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

jest.mock("@/lib/analytics", () => ({ ANALYTICS_EVENTS: new Proxy({}, { get: (_t, k) => k }), track: jest.fn() }), { virtual: true });
jest.mock("react-router-dom", () => ({
  useNavigate: () => jest.fn(),
  Link: ({ to, children, ...rest }) => <a href={to} {...rest}>{children}</a>,
}), { virtual: true });
jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("lucide-react", () => new Proxy({}, { get: () => () => <span /> }), { virtual: true });

const boardProps = [];
jest.mock("react-chessboard", () => ({
  Chessboard: (props) => {
    boardProps.push(props);
    return <div data-testid="board" />;
  },
}), { virtual: true });

let mockFile = null;
jest.mock("@/lib/coachFile", () => ({ useCoachFile: () => mockFile, playFrom: jest.fn() }), { virtual: true });
jest.mock("@/components/coachfile/CoachFileBlocks", () => {
  const { Chessboard } = jest.requireMock("react-chessboard");
  return {
    PLAYED: "#b45309",
    BETTER: "#047857",
    Board: ({ fen, arrows }) => <Chessboard position={fen} customArrows={arrows} />,
  };
}, { virtual: true });

const FEN = "rnbqk1nr/ppp1ppbp/3p2p1/8/2BPP3/5N2/PPP2PPP/RNBQK2R b KQkq - 1 4";

const PLAN = {
  read: ["What costs you most: not answering an attack on the king."],
  stake: { low: 25, high: 51 },
  check: { state: "waiting", title: "Waiting for games", words: "Not enough new games to tell yet." },
  steps: [
    {
      kind: "habit", key: "habit:k", title: "Not answering an attack on the king",
      do: "Every move, count his pieces near your king.", training: true, this_week: true,
      state: "same", state_title: "Same as before",
      sign: { title: "Who is near my king?", text: "Ask what he is threatening there." },
      stake: { high: 51 },
      work: { learn: { url: "/training/pattern/king_safety", text: "Learn it." }, find: [], play: [], target: "Use your rule." },
    },
    {
      kind: "opening", key: "opening:black:g6 Bg7:Bg4", title: "Your opening as Black",
      do: "You keep reaching this position and playing the orange move. The green move is better.",
      san: "Bg4", better_san: "Nf6", fen: FEN, side: "black",
      played_from: "c8", played_to: "g4", better_from: "g8", better_to: "f6",
      learn_url: "/learn", stake: { high: 25 },
      work: { find: [{ ref: "g0:4", url: "/game/g0?move=4" }] },
    },
  ],
};

let root;
let host;
beforeEach(() => {
  boardProps.length = 0;
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
});
afterEach(() => {
  act(() => root.unmount());
  host.remove();
});

function render(plan = PLAN) {
  mockFile = { enabled: true, state: "ready", plan, notation: true, week: { done: {} } };
  act(() => root.render(<CoachPlanCard />));
}

test("the opening step draws its own position with both moves", () => {
  render();
  expect(boardProps).toHaveLength(1);
  expect(boardProps[0].position).toBe(FEN);
  expect(boardProps[0].customArrows.map((a) => [a[0], a[1]])).toEqual([["c8", "g4"], ["g8", "f6"]]);
});

test("'See where it happened' opens the game, not the general learn page", () => {
  render();
  const link = [...host.querySelectorAll("a")].find((a) => a.textContent === "See where it happened");
  expect(link.getAttribute("href")).toBe("/game/g0?move=4");
});

test("a warning sign ending in a question mark gets no extra full stop", () => {
  render();
  expect(host.textContent).toContain("Who is near my king? Ask what");
  expect(host.textContent).not.toContain("?.");
});

test("the trained step shows 'Since you started' and not a second, contradicting state", () => {
  render();
  expect(host.textContent).toContain("Since you started: Waiting for games. Not enough new games to tell yet.");
  expect(host.textContent).not.toContain("Same as before");
});
