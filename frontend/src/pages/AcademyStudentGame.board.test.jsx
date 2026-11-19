/**
 * The board contract: LichessBoard plays the move itself and calls onMove
 * with ONE object {from, to, san, ...}. A handler written for three arguments
 * (from, to, promotion) received the object as `from`, so no move was ever
 * sent (2026-11-19, the line board's first live day). This drives the page the
 * way the real board does.
 */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("react-router-dom", () => ({
  Link: ({ children }) => <a>{children}</a>,
  useParams: () => ({ studentId: "s1", gameId: "g1" }),
}), { virtual: true });
jest.mock("@/App", () => ({ API: "http://test/api" }));
jest.mock("@/components/Layout", () => ({ children }) => <div>{children}</div>);
let boardProps = null;
jest.mock("@/components/LichessBoard", () => (props) => { boardProps = props; return null; });

import AcademyStudentGame from "./AcademyStudentGame";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

test("a move from the board reaches the server", async () => {
  const calls = [];
  global.fetch = jest.fn(async (url, opts) => {
    calls.push({ url, body: opts && opts.body ? JSON.parse(opts.body) : null });
    if (String(url).endsWith("/academy/student/s1/game/g1")) {
      return { ok: true, json: async () => ({ game_id: "g1", pgn: "1. e4 e5 *", user_color: "white", student_name: "A" }) };
    }
    return { ok: true, json: async () => ({ student: { san: "Nf3", text: "Nf3 is fine." }, reply: null, arrows: [], fen_after: "x", needs_why: false }) };
  });
  const el = document.createElement("div");
  document.body.appendChild(el);
  const root = createRoot(el);
  await act(async () => { root.render(<AcademyStudentGame />); });
  await act(async () => { await Promise.resolve(); });
  expect(boardProps).not.toBeNull();
  // The real board's call shape: one object.
  await act(async () => { boardProps.onMove({ from: "e2", to: "e4", san: "e4", fen: "x" }); });
  await act(async () => { await new Promise((r) => setTimeout(r, 50)); });
  const sent = calls.find((c) => String(c.url).endsWith("/coach/line/move"));
  expect(sent).toBeTruthy();
  expect(sent.body.move).toBe("e4");
  act(() => root.unmount());
});
