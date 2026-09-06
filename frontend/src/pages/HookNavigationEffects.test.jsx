import React, { act } from "react";
import { createRoot } from "react-dom/client";

import CoachReplay from "./CoachReplay";
import DiagnosticPuzzles from "./DiagnosticPuzzles";


const mockNavigate = jest.fn();

jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
  useParams: () => ({ gameId: "game-1" }),
}), { virtual: true });
jest.mock("@/components/Layout", () => ({ children }) => <div>{children}</div>, { virtual: true });
jest.mock("@/components/LichessBoard", () => () => <div data-testid="board" />, { virtual: true });


describe("navigation-dependent load effects", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    mockNavigate.mockClear();
    global.fetch = jest.fn(() => new Promise(() => {}));
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    delete global.fetch;
  });

  test("CoachReplay does not duplicate its load on an unrelated rerender", async () => {
    await act(async () => root.render(<CoachReplay user={{ user_id: "student-1" }} />));

    expect(global.fetch).toHaveBeenCalledTimes(1);
    await act(async () => root.render(<CoachReplay user={{ user_id: "student-1" }} />));

    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  test("DiagnosticPuzzles does not duplicate its start on an unrelated rerender", async () => {
    await act(async () => root.render(<DiagnosticPuzzles />));

    expect(global.fetch).toHaveBeenCalledTimes(1);
    await act(async () => root.render(<DiagnosticPuzzles />));

    expect(global.fetch).toHaveBeenCalledTimes(1);
  });
});
