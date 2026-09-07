import React, { act } from "react";
import { createRoot } from "react-dom/client";

import PostGameLesson from "@/components/PostGameLesson";
import PostLossRecovery from "./PostLossRecovery";


let mockGameId;
const mockNavigate = jest.fn();

jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
  useParams: () => ({ gameId: mockGameId }),
}), { virtual: true });
jest.mock("@/components/Layout", () => ({ children }) => <div>{children}</div>, { virtual: true });
jest.mock("@/components/CoachBoard", () => () => <div>board</div>, { virtual: true });


const deferred = () => {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
};

const failedResponse = () => ({ ok: false, json: () => Promise.resolve({}) });


describe("effect-owned page loads", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    mockGameId = undefined;
    mockNavigate.mockReset();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    delete global.fetch;
  });

  const flush = () => act(async () => {
    await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });

  test("post-game analysis loads once per session after completion", async () => {
    const first = deferred();
    const second = deferred();
    global.fetch = jest.fn()
      .mockImplementationOnce(() => first.promise)
      .mockImplementationOnce(() => second.promise);

    await act(async () => root.render(
      <PostGameLesson sessionId="session-1" result="draw" onPlayAgain={() => {}} />
    ));
    expect(global.fetch).toHaveBeenCalledTimes(1);

    first.resolve(failedResponse());
    await flush();
    expect(global.fetch).toHaveBeenCalledTimes(1);

    await act(async () => root.render(
      <PostGameLesson sessionId="session-2" result="draw" onPlayAgain={() => {}} />
    ));
    expect(global.fetch).toHaveBeenCalledTimes(2);
    expect(JSON.parse(global.fetch.mock.calls[1][1].body)).toEqual({ session_id: "session-2" });

    second.resolve(failedResponse());
    await flush();
    expect(global.fetch).toHaveBeenCalledTimes(2);
  });

  test("post-loss recovery skips a missing game and loads once per game", async () => {
    const first = deferred();
    const second = deferred();
    global.fetch = jest.fn()
      .mockImplementationOnce(() => first.promise)
      .mockImplementationOnce(() => second.promise);

    await act(async () => root.render(<PostLossRecovery user={{ user_id: "student-1" }} />));
    expect(global.fetch).not.toHaveBeenCalled();

    mockGameId = "game-1";
    await act(async () => root.render(<PostLossRecovery user={{ user_id: "student-1" }} />));
    expect(global.fetch).toHaveBeenCalledTimes(1);

    first.resolve(failedResponse());
    await flush();
    expect(global.fetch).toHaveBeenCalledTimes(1);

    mockGameId = "game-2";
    await act(async () => root.render(<PostLossRecovery user={{ user_id: "student-1" }} />));
    expect(global.fetch).toHaveBeenCalledTimes(2);
    expect(global.fetch.mock.calls[1][0]).toBe("https://api.test/reflect/v1/post-loss/game-2");

    second.resolve(failedResponse());
    await flush();
    expect(global.fetch).toHaveBeenCalledTimes(2);
  });
});
