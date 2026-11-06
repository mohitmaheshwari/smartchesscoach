import { createRoot } from "react-dom/client";
import { act } from "react";
import FirstStepsClass from "@/pages/FirstStepsClass";

let mockParams = {};
jest.mock("react-router-dom", () => ({ useParams: () => mockParams }), { virtual: true });
jest.mock("@/App", () => ({ API: "http://test/api" }));
// The real board is covered elsewhere; here each square is a plain button.
jest.mock("@/components/LichessBoard", () => (props) => (
  <div data-testid="board" data-fen={props.fen} data-marks={JSON.stringify(props.highlights || [])}>
    {["e5", "h1", "h8"].map((s) => (
      <button key={s} type="button" data-sq={s} onClick={() => props.onSquareClick && props.onSquareClick(s)}>{s}</button>
    ))}
  </div>
));

const SESSION = {
  session_id: "cls_1", kind: "class", class_id: "rook", title: "The rook", index: 1, count: 7,
  parts: ["Warm-up", "Today's idea", "Practice", "Practice", "Play it", "Play it", "Check"], stars: 1,
  current: { id: "rook-lines", part: "Today's idea", kind: "tap_reach", fen: "8/8/8/8/3R4/8/8/8 w - - 0 1",
             say: "The rook goes in straight lines.", sub: "Show every square it can reach.",
             total: 14, found: ["d5"], wrong: 0, finished: false },
};

let container; let root;
beforeEach(() => { container = document.createElement("div"); document.body.appendChild(container); root = createRoot(container); });
afterEach(() => { act(() => root.unmount()); container.remove(); delete global.fetch; });

function reply(body, ok = true) {
  return Promise.resolve({ ok, status: ok ? 200 : 409, json: async () => body });
}

async function flush() { await act(async () => { await Promise.resolve(); await Promise.resolve(); }); }

test("a new child is asked three questions first", async () => {
  mockParams = { token: "tok" };
  global.fetch = jest.fn(() => reply({ child_name: "Aarav", placed: false, open: null, classes: [], all_done: false }));
  await act(async () => { root.render(<FirstStepsClass />); });
  await flush();
  expect(container.textContent).toContain("Hello Aarav.");
  expect(container.textContent).toContain("Three quick questions");
  expect(global.fetch.mock.calls[0][0]).toBe("http://test/api/academy/class/tok");
});

test("the path shows every class with the next one open", async () => {
  mockParams = { token: "tok" };
  global.fetch = jest.fn(() => reply({ child_name: "Aarav", placed: true, open: null, next: { id: "bishop", title: "The bishop" },
    classes: [{ id: "rook", title: "The rook", passed: true }, { id: "bishop", title: "The bishop", passed: false }, { id: "queen", title: "The queen", passed: false }] }));
  await act(async () => { root.render(<FirstStepsClass />); });
  await flush();
  const text = container.textContent;
  expect(text).toContain("Aarav's path");
  expect(text).toContain("Complete");
  expect(text).toContain("Locked");
  expect(container.querySelector("[data-testid=board]").dataset.fen).toContain("3B4");
});

test("a tap is sent to the server and its words are shown", async () => {
  mockParams = { token: "tok" };
  const after = { ...SESSION, current: { ...SESSION.current, wrong: 1 } };
  global.fetch = jest.fn()
    .mockImplementationOnce(() => reply({ child_name: "Aarav", placed: true, open: SESSION, classes: [] }))
    .mockImplementationOnce(() => reply({ result: { outcome: "wrong", kind: "like_bishop",
      say: "That's a diagonal. The rook can't go that way. That is how the bishop moves." }, session: after }));
  await act(async () => { root.render(<FirstStepsClass />); });
  await flush();
  expect(container.textContent).toContain("1 of 14 squares found");
  expect(JSON.parse(container.querySelector("[data-testid=board]").dataset.marks)).toEqual([{ square: "d5", kind: "found" }]);
  await act(async () => { container.querySelector("[data-sq=e5]").click(); });
  await flush();
  const [url, init] = global.fetch.mock.calls[1];
  expect(url).toBe("http://test/api/academy/class/tok/answer");
  expect(JSON.parse(init.body)).toEqual({ session_id: "cls_1", item_id: "rook-lines", answer: { square: "e5" } });
  expect(container.textContent).toContain("That is how the bishop moves.");
});

test("a move is a piece tap then a square tap, and the right move plays on the board", async () => {
  mockParams = { token: "tok" };
  const move = { ...SESSION, current: { id: "mate-test", part: "Check", kind: "move_goal", test: true,
    fen: "k7/8/1K6/8/8/8/8/7R w - - 0 1", say: "Check your understanding", sub: "Find checkmate in one move.",
    wrong: 0, finished: false } };
  global.fetch = jest.fn()
    .mockImplementationOnce(() => reply({ child_name: "Aarav", placed: true, open: move, classes: [] }))
    .mockImplementationOnce(() => reply({ result: { outcome: "right", say: "Correct. You can give checkmate.",
      fen_after: "k6R/8/1K6/8/8/8/8/8 b - - 1 1" }, session: { ...move, current: { ...move.current, finished: true, solved: true } } }));
  await act(async () => { root.render(<FirstStepsClass />); });
  await flush();
  await act(async () => { container.querySelector("[data-sq=h1]").click(); });
  await act(async () => { container.querySelector("[data-sq=h8]").click(); });
  await flush();
  expect(JSON.parse(global.fetch.mock.calls[1][1].body).answer).toEqual({ move: "h1h8" });
  expect(container.textContent).toContain("Correct. You can give checkmate.");
  expect(container.querySelector("[data-testid=board]").dataset.fen).toContain("k6R");
  expect([...container.querySelectorAll("button")].some((b) => b.textContent === "Continue")).toBe(true);
});

test("a finished class shows the facts, with no celebration words", async () => {
  mockParams = { token: "tok" };
  const finished = { ...SESSION, current: { ...SESSION.current, finished: true } };
  global.fetch = jest.fn()
    .mockImplementationOnce(() => reply({ child_name: "Aarav", placed: true, open: finished, classes: [] }))
    .mockImplementationOnce(() => reply({ ...SESSION, current: null, finished_at: "now",
      summary: { say: "Aarav now knows how the rook moves.", passed: true, steps: 7, first_try: 5, parent: "Today Aarav learnt how the rook moves." } }));
  await act(async () => { root.render(<FirstStepsClass />); });
  await flush();
  await act(async () => { [...container.querySelectorAll("button")].find((b) => b.textContent === "Continue").click(); });
  await flush();
  const text = container.textContent;
  expect(text).toContain("The rook, complete.");
  expect(text).toContain("Right first time");
  expect(text).toContain("For a parent: Today Aarav learnt how the rook moves.");
});

test("a class link before consent says a parent must agree", async () => {
  mockParams = { token: "tok" };
  global.fetch = jest.fn(() => reply({ detail: "A parent needs to agree first. Ask your coach for the link." }, false));
  await act(async () => { root.render(<FirstStepsClass />); });
  await flush();
  expect(container.textContent).toContain("A parent needs to agree first.");
});
