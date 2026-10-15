/**
 * The step machine is the risky part of this page: nothing may be revealed
 * until all six answers exist, a played move must stay on the board, and a
 * second drag must not add a move on top of the first.
 */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

import ReplyCheck from "./ReplyCheck";

let lastBoardProps = null;

jest.mock("react-chessboard", () => ({
  Chessboard: (props) => {
    lastBoardProps = props;
    return <div data-testid="board" data-fen={props.position} />;
  },
}), { virtual: true });
jest.mock("@/components/Layout", () => ({ children }) => <div>{children}</div>, { virtual: true });
jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("sonner", () => ({ toast: { error: jest.fn(), success: jest.fn() } }));

// 3a41fb4c move 28: Black is in check from Qc7; only Qxc7 holds.
const ITEM = {
  position_id: "3a41fb4c:28",
  game_id: "3a41fb4c", move_number: 28, platform: "lichess", date: "2026-08-31",
  to_move: "black",
  fen: "4r3/2Q3kp/5np1/p3rp2/2q5/P1PR4/6PP/3R1K2 b - - 0 28",
  preceding_moves: ["26.Kf1", "27.Qxb7"],
  side_to_move_in_check: true, checking_squares: ["c7"],
  all_legal_moves: ["Kf8", "Kg8", "Kh6", "Kh8", "Nd7", "Qf7", "Qxc7", "R5e7", "R8e7"],
  n_legal: 9,
};

const posted = [];

function mockFetch() {
  global.fetch = jest.fn((url, opts) => {
    if (url.endsWith("/coach/reply-check/packet"))
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ count: 1, items: [ITEM] }) });
    if (url.endsWith("/coach/reply-check/responses"))
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ responses: [] }) });
    if (url.endsWith("/coach/reply-check/response")) {
      posted.push(JSON.parse(opts.body));
      return Promise.resolve({ ok: true, json: () => Promise.resolve({
        recorded: true,
        derived: { move_graded: "R8e7", move_holds: false, move_holds_at_every_depth: false,
                   move_branch_prepared: true, reply_names_the_capture: true,
                   reply_as_damaging_as_best: true, reply_not_sure: false,
                   revised: false, pending_verification: false },
      }) });
    }
    if (url.includes("/coach/reply-check/evidence/"))
      return Promise.resolve({ ok: true, json: () => Promise.resolve({
        n_moves_that_hold: 1, accept_moves: ["Qxc7"], one_move_only_wording_permitted: true,
        reply_evidence_by_candidate_move: {
          R8e7: { engine_top_replies: [{ reply: "Qxc4", eval_after_reply_his_pov: -406 }],
                  punishing_replies: ["Qxc4"] },
        },
      }) });
    throw new Error("unexpected " + url);
  });
}

describe("ReplyCheck", () => {
  let container, root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    posted.length = 0;
    lastBoardProps = null;
    mockFetch();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    delete global.fetch;
  });

  async function mount() {
    await act(async () => root.render(<ReplyCheck user={{ user_id: "u1" }} />));
    await act(async () => { for (let i = 0; i < 20; i += 1) await Promise.resolve(); });
  }

  const click = async (text) => {
    const btn = Array.from(container.querySelectorAll("button"))
      .find((b) => b.textContent.trim() === text);
    if (!btn) throw new Error(`no button "${text}" — have: ` +
      Array.from(container.querySelectorAll("button")).map((b) => b.textContent.trim()).join(" | "));
    await act(async () => btn.click());
  };
  const drop = async (from, to) => {
    await act(async () => { lastBoardProps.onPieceDrop(from, to); });
  };

  test("shows the position and the check, and nothing else", async () => {
    await mount();
    expect(container.textContent).toContain("Black to move");
    expect(container.textContent).toContain("in check from c7");
    expect(container.textContent).toContain("Do you recognise this position?");
    // no evaluation, no answer, no hint
    expect(container.textContent).not.toContain("Qxc7");
    expect(global.fetch.mock.calls.some((c) => String(c[0]).includes("/evidence/"))).toBe(false);
  });

  test("a legal move sticks to the board; an illegal one is refused", async () => {
    await mount();
    await click("No");
    expect(lastBoardProps.arePiecesDraggable).toBe(true);

    let accepted;
    await act(async () => { accepted = lastBoardProps.onPieceDrop("c4", "c7"); }); // Qxc7
    expect(accepted).toBe(true);
    expect(container.textContent).toContain("Qxc7");
    // the move stays on the board, and the board locks so a second drag
    // cannot stack another move on top
    expect(lastBoardProps.position).not.toBe(ITEM.fen);
    expect(lastBoardProps.arePiecesDraggable).toBe(false);
  });

  test("an illegal drop is rejected and nothing is recorded", async () => {
    await mount();
    await click("No");
    let accepted;
    await act(async () => { accepted = lastBoardProps.onPieceDrop("a5", "a1"); });
    expect(accepted).toBe(false);
    expect(lastBoardProps.position).toBe(ITEM.fen);
  });

  test("the full six answers are recorded, and only then is evidence fetched", async () => {
    await mount();
    await click("No");
    await drop("e8", "e7");              // R8e7
    await click("Lock it in");
    await drop("c7", "c4");              // Qxc4, their reply
    await click("Lock it in");
    await click("losing");               // how do you rate it now
    await click("losing");               // and after their reply

    // still nothing revealed
    expect(global.fetch.mock.calls.some((c) => String(c[0]).includes("/evidence/"))).toBe(false);

    await click("Keep my move and record");
    await act(async () => { for (let i = 0; i < 20; i += 1) await Promise.resolve(); });

    expect(posted).toHaveLength(1);
    expect(posted[0]).toMatchObject({
      position_id: "3a41fb4c:28",
      recognised: "no",
      intended_move: "R8e7",
      expected_reply: "Qxc4",
      assessment_now: "losing",
      assessment_after_predicted_reply: "losing",
    });
    expect(global.fetch.mock.calls.some((c) => String(c[0]).includes("/evidence/"))).toBe(true);
    expect(container.textContent).toContain("Qxc4");
    expect(container.textContent).toContain("How did you pick it?");
  });

  test("not sure is a recordable answer for the reply", async () => {
    await mount();
    await click("No");
    await drop("c4", "c7");
    await click("Lock it in");
    await click("Not sure");
    // "not sure" is accepted and the sitting carries on
    await click("winning");
    expect(container.textContent).toContain("And after their reply, whatever it turns out to be?");
  });
});
