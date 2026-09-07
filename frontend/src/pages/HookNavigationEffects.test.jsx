import React, { act } from "react";
import { createRoot } from "react-dom/client";

import CoachReplay from "./CoachReplay";
import DiagnosticPuzzles from "./DiagnosticPuzzles";


let mockNavigate = jest.fn();

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
    mockNavigate = jest.fn();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    delete global.fetch;
  });

  const deferred = () => {
    let resolve;
    const promise = new Promise((done) => { resolve = done; });
    return { promise, resolve };
  };

  const flush = () => act(async () => {
    await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });

  test("CoachReplay keeps one load and uses the latest router identity on failure", async () => {
    const request = deferred();
    global.fetch = jest.fn(() => request.promise);
    const firstNavigate = mockNavigate;
    await act(async () => root.render(<CoachReplay user={{ user_id: "student-1" }} />));

    expect(global.fetch).toHaveBeenCalledTimes(1);
    const latestNavigate = jest.fn();
    mockNavigate = latestNavigate;
    await act(async () => root.render(<CoachReplay user={{ user_id: "student-1" }} />));
    expect(global.fetch).toHaveBeenCalledTimes(1);

    request.resolve({ ok: false });
    await flush();
    expect(firstNavigate).not.toHaveBeenCalled();
    expect(latestNavigate).toHaveBeenCalledWith("/game/game-1", { replace: true });
  });

  test("DiagnosticPuzzles starts once and uses the latest router identity on 401", async () => {
    const request = deferred();
    global.fetch = jest.fn(() => request.promise);
    const firstNavigate = mockNavigate;
    await act(async () => root.render(<DiagnosticPuzzles />));

    expect(global.fetch).toHaveBeenCalledTimes(1);
    const latestNavigate = jest.fn();
    mockNavigate = latestNavigate;
    await act(async () => root.render(<DiagnosticPuzzles />));
    expect(global.fetch).toHaveBeenCalledTimes(1);

    request.resolve({ ok: false, status: 401 });
    await flush();
    expect(firstNavigate).not.toHaveBeenCalled();
    expect(latestNavigate).toHaveBeenCalledWith(
      "/login?redirect_to=%2Fdiagnostic"
    );
  });
});
