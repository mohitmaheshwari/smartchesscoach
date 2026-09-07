import React, { act } from "react";
import { createRoot } from "react-dom/client";

import MistakeFreeStreak from "./MistakeFreeStreak";
import PreGameStreakPopup from "./PreGameStreakPopup";


jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("framer-motion", () => ({
  AnimatePresence: ({ children }) => <>{children}</>,
  motion: { div: ({ children }) => <div>{children}</div> },
}), { virtual: true });
jest.mock("@/components/ui/card", () => ({
  Card: ({ children }) => <div>{children}</div>,
  CardContent: ({ children }) => <div>{children}</div>,
}), { virtual: true });
jest.mock("@/components/ui/button", () => ({
  Button: ({ children }) => <button>{children}</button>,
}), { virtual: true });


describe("streak load effect boundaries", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
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

  test("dashboard streak reloads for a new user, not an unrelated rerender", async () => {
    await act(async () => root.render(<MistakeFreeStreak userId="student-1" />));
    expect(global.fetch).toHaveBeenCalledTimes(1);

    await act(async () => root.render(<MistakeFreeStreak userId="student-1" />));
    expect(global.fetch).toHaveBeenCalledTimes(1);

    await act(async () => root.render(<MistakeFreeStreak userId="student-2" />));
    expect(global.fetch).toHaveBeenCalledTimes(2);
    expect(global.fetch.mock.calls[1][0]).toContain("student-2");
  });

  test("pregame streak loads only when opened and reloads for a new user", async () => {
    await act(async () => root.render(
      <PreGameStreakPopup userId="student-1" isOpen={false} />
    ));
    expect(global.fetch).not.toHaveBeenCalled();

    await act(async () => root.render(
      <PreGameStreakPopup userId="student-1" isOpen />
    ));
    expect(global.fetch).toHaveBeenCalledTimes(1);

    await act(async () => root.render(
      <PreGameStreakPopup userId="student-1" isOpen />
    ));
    expect(global.fetch).toHaveBeenCalledTimes(1);

    await act(async () => root.render(
      <PreGameStreakPopup userId="student-2" isOpen />
    ));
    expect(global.fetch).toHaveBeenCalledTimes(2);
    expect(global.fetch.mock.calls[1][0]).toContain("student-2");
  });
});
