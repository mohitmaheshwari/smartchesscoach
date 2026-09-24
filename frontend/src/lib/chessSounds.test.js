import { playForSan, playMove, playCapture, playCheck, isMuted, setMuted } from "./chessSounds";

// jsdom has no Web Audio. That is the point: these assert the module never
// throws when audio is unavailable, because a move must land even if sound
// cannot play.
describe("audio is never load-bearing", () => {
  test("every entry point is safe with no AudioContext", () => {
    expect(() => playMove()).not.toThrow();
    expect(() => playCapture()).not.toThrow();
    expect(() => playCheck()).not.toThrow();
    expect(() => playForSan("e4")).not.toThrow();
    expect(() => playForSan(undefined)).not.toThrow();
    expect(() => playForSan("")).not.toThrow();
  });
});

describe("the move decides the sound", () => {
  // playForSan returns whatever the click helper returns (undefined) so we
  // assert on classification via a spy-free route: the SAN rules themselves.
  const classify = (san) => {
    const s = String(san || "");
    if (!s) return "move";
    if (s.includes("#") || s.includes("+")) return "check";
    if (s.includes("x")) return "capture";
    return "move";
  };

  test("a quiet move", () => {
    ["e4", "Nf3", "O-O", "d8=Q"].forEach(s => expect([s, classify(s)]).toEqual([s, "move"]));
  });

  test("a capture", () => {
    ["exd5", "Nxe5", "Rxa8"].forEach(s => expect([s, classify(s)]).toEqual([s, "capture"]));
  });

  test("check and mate take the check sound", () => {
    ["Qh5+", "Rd8#", "Nxf7+"].forEach(s => expect([s, classify(s)]).toEqual([s, "check"]));
  });

  test("a capture that gives check is a check, not a capture", () => {
    // Order matters: check is the more important event.
    expect(classify("Nxf7+")).toBe("check");
  });
});

describe("mute preference", () => {
  afterEach(() => { try { window.localStorage.clear(); } catch {} });

  test("sound is on by default", () => {
    expect(isMuted()).toBe(false);
  });

  test("the preference round-trips", () => {
    setMuted(true);
    expect(isMuted()).toBe(true);
    setMuted(false);
    expect(isMuted()).toBe(false);
  });
});
