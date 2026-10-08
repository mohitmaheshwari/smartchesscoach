/**
 * Sound must never break a move.
 *
 * 2026-10-08: playForSan was hoisted to run on EVERY move in every mode.
 * getCtx() called `new AudioContext()` outside any try, and browsers cap the
 * number of contexts and block construction without a gesture. The throw
 * propagated through click -> playForSan -> makeMove, and because
 * onPieceDrop must return true for a move to stick, the piece snapped back:
 * Mohit could not move at all. These tests pin the contract that every
 * exported sound swallows its own failure.
 */
import { playMove, playCapture, playCheck, playBlunder, playForSan } from "./chessSounds";

const ALL = { playMove, playCapture, playCheck, playBlunder, playForSan };

describe("audio is never load-bearing", () => {
  afterEach(() => { jest.restoreAllMocks(); });

  it("survives an AudioContext constructor that throws", () => {
    window.AudioContext = function () { throw new Error("blocked by browser"); };
    window.webkitAudioContext = window.AudioContext;
    for (const [name, fn] of Object.entries(ALL)) {
      expect(() => fn("Qxf7#")).not.toThrow(`${name} must not throw`);
    }
  });

  it("survives no AudioContext at all", () => {
    delete window.AudioContext;
    delete window.webkitAudioContext;
    for (const fn of Object.values(ALL)) {
      expect(() => fn("e4")).not.toThrow();
    }
  });

  it("survives localStorage throwing (private mode)", () => {
    jest.spyOn(window.localStorage.__proto__, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    for (const fn of Object.values(ALL)) {
      expect(() => fn("Bxc3")).not.toThrow();
    }
  });

  it("playForSan tolerates junk input", () => {
    for (const bad of [null, undefined, 42, {}, [], ""]) {
      expect(() => playForSan(bad)).not.toThrow();
    }
  });
});
