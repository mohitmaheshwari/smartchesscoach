import React, { act } from "react";
import { createRoot } from "react-dom/client";

import LineBoardPanel, { LineBoardHint } from "./LineBoardPanel";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const step = (over = {}) => ({
  student: { san: "Qxa8", uci: "f3a8", text: "Qxa8 is fine. It takes their rook on a8.", class: "good" },
  reply: { san: "Bc6", uci: "b5c6", text: "Bc6 attacks your queen." },
  count_text: null,
  why: null,
  why_state: "none",
  arrows: [],
  fen_after: "",
  ...over,
});

const lb = (over = {}) => ({
  active: true, steps: [step()], busy: false, error: null,
  back: jest.fn(), best: jest.fn(), exit: jest.fn(),
  ...over,
});

let container;
let root;
beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

const byId = (id) => container.querySelector(`[data-testid="${id}"]`);

test("shows the student's move and the reply in words", () => {
  act(() => root.render(<LineBoardPanel lb={lb()} gameFen="x" />));
  expect(byId("line-student").textContent).toBe("Qxa8 is fine. It takes their rook on a8.");
  expect(byId("line-reply").textContent).toBe("Bc6 attacks your queen.");
});

test("the reply is not said twice when the why sentence names it", () => {
  const s = step({
    student: { san: "Qf3", uci: "d1f3", text: "Qf3 is a mistake: Bxa6 was better.", class: "blunder" },
    reply: { san: "Bxb5", uci: "a6b5", text: "Bxb5 takes your bishop on b5." },
    why: "After Qf3, Bxb5 takes your bishop on b5, and nothing can take back.",
    why_state: "done",
  });
  act(() => root.render(<LineBoardPanel lb={lb({ steps: [s] })} gameFen="x" />));
  expect(byId("line-why")).not.toBeNull();
  expect(byId("line-reply")).toBeNull();
});

test("the controls call back, best and exit", () => {
  const l = lb();
  act(() => root.render(<LineBoardPanel lb={l} gameFen="start-fen" />));
  act(() => byId("line-back").click());
  act(() => byId("line-best").click());
  act(() => byId("line-exit").click());
  expect(l.back).toHaveBeenCalled();
  expect(l.best).toHaveBeenCalledWith("start-fen");
  expect(l.exit).toHaveBeenCalled();
});

test("the hint tells the player the board takes moves", () => {
  act(() => root.render(<LineBoardHint />));
  expect(byId("line-hint").textContent).toBe("Move any piece to try your own idea.");
});
