import { createRoot } from "react-dom/client";
import { act } from "react";
import FirstStepsClass, { parseFen } from "@/pages/FirstStepsClass";

let mockParams = {};
jest.mock("react-router-dom", () => ({ useParams: () => mockParams }), { virtual: true });
jest.mock("@/App", () => ({ API: "http://test/api" }));

const SESSION = {
  session_id: "cls_1", kind: "class", class_id: "rook", title: "The rook", index: 1, count: 7,
  parts: ["Warm-up", "Today's idea", "Practice", "Practice", "Play it", "Play it", "Check"], stars: 1,
  current: { id: "rook-lines", part: "Today's idea", kind: "tap_reach", fen: "8/8/8/8/3R4/8/8/8 w - - 0 1",
             say: "The rook goes in straight lines.", sub: "Tap every square it can reach.",
             total: 14, found: ["d5"], wrong: 0, finished: false },
};

let container; let root;
beforeEach(() => { container = document.createElement("div"); document.body.appendChild(container); root = createRoot(container); });
afterEach(() => { act(() => root.unmount()); container.remove(); delete global.fetch; });

function reply(body, ok = true) {
  return Promise.resolve({ ok, status: ok ? 200 : 409, json: async () => body });
}

async function flush() { await act(async () => { await Promise.resolve(); await Promise.resolve(); }); }

test("fen squares are read the right way up", () => {
  const p = parseFen("8/8/8/8/3R4/8/8/k6K w - - 0 1");
  expect(p.d4).toEqual({ type: "r", white: true });
  expect(p.a1).toEqual({ type: "k", white: false });
  expect(p.h1).toEqual({ type: "k", white: true });
});

test("a new child is asked three questions first", async () => {
  mockParams = { token: "tok" };
  global.fetch = jest.fn(() => reply({ child_name: "Aarav", placed: false, open: null, classes: [], all_done: false }));
  await act(async () => { root.render(<FirstStepsClass />); });
  await flush();
  expect(container.textContent).toContain("Hi Aarav!");
  expect(container.textContent).toContain("three quick questions");
  expect(global.fetch.mock.calls[0][0]).toBe("http://test/api/academy/class/tok");
});

test("a tap is sent to the server and its words are shown", async () => {
  mockParams = { token: "tok" };
  const after = { ...SESSION, current: { ...SESSION.current, wrong: 1 } };
  global.fetch = jest.fn()
    .mockImplementationOnce(() => reply({ child_name: "Aarav", placed: true, open: SESSION, classes: [] }))
    .mockImplementationOnce(() => reply({ result: { outcome: "wrong", kind: "like_bishop",
      say: "That's a diagonal. The rook can't go that way. That's how the bishop moves!" }, session: after }));
  await act(async () => { root.render(<FirstStepsClass />); });
  await flush();
  expect(container.textContent).toContain("1 of 14 squares found");
  const e5 = container.querySelector("[data-sq=e5]");
  await act(async () => { e5.click(); });
  await flush();
  const [url, init] = global.fetch.mock.calls[1];
  expect(url).toBe("http://test/api/academy/class/tok/answer");
  expect(JSON.parse(init.body)).toEqual({ session_id: "cls_1", item_id: "rook-lines", answer: { square: "e5" } });
  expect(container.textContent).toContain("That's how the bishop moves!");
});

test("a move is a piece tap then a square tap", async () => {
  mockParams = { token: "tok" };
  const move = { ...SESSION, current: { id: "mate-test", part: "Check", kind: "move_goal", test: true,
    fen: "k7/8/1K6/8/8/8/8/7R w - - 0 1", say: "Show me what you learnt.", sub: "Find checkmate in one move.",
    wrong: 0, finished: false } };
  global.fetch = jest.fn()
    .mockImplementationOnce(() => reply({ child_name: "Aarav", placed: true, open: move, classes: [] }))
    .mockImplementationOnce(() => reply({ result: { outcome: "right", say: "Perfect. You can checkmate!" },
      session: { ...move, current: { ...move.current, finished: true, solved: true } } }));
  await act(async () => { root.render(<FirstStepsClass />); });
  await flush();
  await act(async () => { container.querySelector("[data-sq=h1]").click(); });
  await act(async () => { container.querySelector("[data-sq=h8]").click(); });
  await flush();
  expect(JSON.parse(global.fetch.mock.calls[1][1].body).answer).toEqual({ move: "h1h8" });
  expect(container.textContent).toContain("Perfect. You can checkmate!");
  expect([...container.querySelectorAll("button")].some((b) => b.textContent === "Next")).toBe(true);
});

test("a class link before consent says a parent must agree", async () => {
  mockParams = { token: "tok" };
  global.fetch = jest.fn(() => reply({ detail: "A parent needs to agree first. Ask your coach for the link." }, false));
  await act(async () => { root.render(<FirstStepsClass />); });
  await flush();
  expect(container.textContent).toContain("A parent needs to agree first.");
});
