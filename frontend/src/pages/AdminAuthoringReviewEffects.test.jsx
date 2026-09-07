import React, { act } from "react";
import { createRoot } from "react-dom/client";

import AdminAuthoringReview from "./AdminAuthoringReview";

jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("@/components/LichessBoard", () => () => <div data-testid="board" />, { virtual: true });
jest.mock("react-router-dom", () => ({
  Link: ({ children }) => <span>{children}</span>,
  useNavigate: () => jest.fn(),
}), { virtual: true });

const response = (body = {}) => ({
  ok: true,
  statusText: "OK",
  json: () => Promise.resolve(body),
});
const item = (id) => ({
  feedback_id: id,
  game_id: `game-${id}`,
  move_number: 5,
  move_san: "Nf3",
  auto_gate_verdict: "REJECT",
  suggested_caption: `Suggestion ${id}`,
  coaching_text: `Original ${id}`,
  diagnostics: {},
});
const flush = () => act(async () => {
  await Promise.resolve();
  await new Promise((done) => setTimeout(done, 0));
});

describe("AdminAuthoringReview queue advancement", () => {
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
  });

  test("successful actions advance exactly one current queue item", async () => {
    global.fetch = jest.fn()
      .mockResolvedValueOnce(response({ items: [item("one"), item("two")], total: 2 }))
      .mockResolvedValueOnce(response());

    await act(async () => root.render(<AdminAuthoringReview />));
    await flush();
    expect(container.textContent).toContain("one");

    const approve = [...container.querySelectorAll("button")]
      .find((button) => button.textContent.includes("Approve"));
    await act(async () => {
      approve.click();
      await Promise.resolve();
    });

    expect(container.textContent).toContain("two");
    expect(container.textContent).toContain("2 / 2 loaded");
    expect(global.fetch).toHaveBeenLastCalledWith(
      "https://api.test/admin/authoring/one/approve",
      expect.objectContaining({ method: "POST" })
    );
  });
});
