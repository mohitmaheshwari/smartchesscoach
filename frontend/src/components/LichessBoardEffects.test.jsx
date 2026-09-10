import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { Chessground as mockedChessground } from "chessground";

import LichessBoard from "./LichessBoard";

const mockGround = {
  set: jest.fn(),
  destroy: jest.fn(),
  setAutoShapes: jest.fn(),
};
jest.mock("chessground", () => ({ Chessground: jest.fn() }));
jest.mock("framer-motion", () => ({
  motion: { div: ({ children, ...props }) => <div {...props}>{children}</div> },
}));
jest.mock("./BoardCoordinates", () => () => null);

const START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1";

describe("LichessBoard dynamic controls", () => {
  let container;
  let root;
  let boardApi;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    boardApi = React.createRef();
    mockGround.set.mockReset();
    mockGround.destroy.mockReset();
    mockGround.setAutoShapes.mockReset();
    mockedChessground.mockReset();
    mockedChessground.mockReturnValue(mockGround);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  test("a FEN update preserves the requested movable color", async () => {
    await act(async () => root.render(
      <LichessBoard ref={boardApi} fen={START} movableColor="black" showDests />
    ));
    expect(boardApi.current.getGround()).toBe(mockGround);
    mockGround.set.mockClear();

    await act(async () => root.render(
      <LichessBoard ref={boardApi} fen={AFTER_E4} movableColor="black" showDests />
    ));
    expect(boardApi.current.getGround()).toBe(mockGround);

    expect(mockGround.set).toHaveBeenCalled();
    const update = mockGround.set.mock.calls.at(-1)[0];
    expect(update.fen).toBe(AFTER_E4);
    expect(update.movable.color).toBe("black");
    expect(update.movable.dests.size).toBeGreaterThan(0);
  });

  test("changing showDests updates controls without recreating the board", async () => {
    await act(async () => root.render(
      <LichessBoard ref={boardApi} fen={AFTER_E4} movableColor="black" showDests />
    ));
    mockGround.set.mockClear();
    mockedChessground.mockClear();

    await act(async () => root.render(
      <LichessBoard ref={boardApi} fen={AFTER_E4} movableColor="black" showDests={false} />
    ));

    expect(mockedChessground).not.toHaveBeenCalled();
    const update = mockGround.set.mock.calls.at(-1)[0];
    expect(update.movable.showDests).toBe(false);
    expect(update.movable.dests.size).toBe(0);
  });

  test("variation playback reports completion after its final legal move", async () => {
    jest.useFakeTimers();
    const onStep = jest.fn();
    const onComplete = jest.fn();
    await act(async () => root.render(
      <LichessBoard ref={boardApi} fen={START} />
    ));

    act(() => {
      boardApi.current.playVariation(START, ["e4", "e5"], {
        stepDelayMs: 10,
        onStep,
        onComplete,
      });
      jest.advanceTimersByTime(420);
    });

    expect(onStep).toHaveBeenCalledWith(-1, null);
    expect(onStep).toHaveBeenCalledTimes(3);
    expect(onComplete).toHaveBeenCalledTimes(1);
    jest.useRealTimers();
  });
});
