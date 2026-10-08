/**
 * Board sounds, synthesised.
 *
 * Nothing is shipped as an audio file on purpose. Recorded piece sounds carry
 * the same licensing question as piece artwork, and the Web Audio API can make
 * a convincing wooden click from noise — so there is no asset to attribute, no
 * download, and nothing to add to the bundle.
 *
 * Lifted out of LabV2.jsx, where a `useChessSounds` hook has been defining
 * playMoveSound since it was written and never calling it — the move sound
 * existed and could not be heard, and no other surface could import it.
 *
 * The move sound is NOT the 600Hz sine that was in there. A pure tone reads as
 * a notification chime; a piece landing on a board is a short broadband click
 * with a fast decay. This is filtered noise with a ~40ms envelope, which is
 * what that sounds like.
 */

let ctxRef = null;

const getCtx = () => {
  if (typeof window === "undefined") return null;
  const Ctor = window.AudioContext || window.webkitAudioContext;
  if (!Ctor) return null;
  // NOTHING here may throw. 2026-10-08: playForSan runs on every move in
  // every mode, and `new AudioContext()` can throw -- browsers cap the
  // number of contexts (~6 in Chrome) and block construction without a
  // gesture. That exception propagated through click -> playForSan ->
  // makeMove, and because onPieceDrop must return true for a move to stick,
  // the piece snapped back: SOUND BROKE THE BOARD. Audio is never
  // load-bearing, so failure here must be silence, not a dead board.
  try {
    if (!ctxRef) ctxRef = new Ctor();
    // Browsers start the context suspended until a user gesture. A move IS a
    // gesture, so resuming here is allowed and is why the first move is audible.
    if (ctxRef.state === "suspended") ctxRef.resume().catch(() => {});
  } catch {
    ctxRef = null;
    return null;
  }
  return ctxRef;
};

const MUTE_KEY = "chessguru.board_sound_muted";

/** Sound is on by default; the preference is per-browser. */
export const isMuted = () => {
  try {
    return window.localStorage.getItem(MUTE_KEY) === "true";
  } catch {
    // Private mode, blocked storage: audible rather than silently broken.
    return false;
  }
};

export const setMuted = (muted) => {
  try {
    window.localStorage.setItem(MUTE_KEY, muted ? "true" : "false");
  } catch {
    /* preference simply does not persist */
  }
};

/**
 * A piece landing on a wooden board, built from what that actually is:
 *
 *   1. a very short broadband TRANSIENT (the contact), ~6ms, high-passed so
 *      it reads as "tap" and not "hiss"
 *   2. a damped low BODY resonance (the board itself ringing), a sine around
 *      150-260Hz falling slightly as it decays
 *
 * The previous version was a single band-passed noise burst at 1100Hz, which
 * is a thin "tick" -- the sound of a fingernail, not of a piece. Mohit,
 * 2026-10-08: "i hear the sound but don't like it". Two layers is the
 * smallest change that makes it read as wood.
 */
const thock = ({ body, bodyEnd, bodyGain, tap, tapGain, duration }) => {
  const ctx = getCtx();
  if (!ctx || isMuted()) return;
  try {
    const now = ctx.currentTime;

    // --- 1. contact transient -------------------------------------------
    const tapFrames = Math.floor(ctx.sampleRate * 0.006);
    const tapBuf = ctx.createBuffer(1, tapFrames, ctx.sampleRate);
    const tapData = tapBuf.getChannelData(0);
    for (let i = 0; i < tapFrames; i += 1) {
      tapData[i] = (Math.random() * 2 - 1) * Math.exp((-9 * i) / tapFrames);
    }
    const tapSrc = ctx.createBufferSource();
    tapSrc.buffer = tapBuf;
    const tapHp = ctx.createBiquadFilter();
    tapHp.type = "highpass";
    tapHp.frequency.value = tap;
    const tapVol = ctx.createGain();
    tapVol.gain.setValueAtTime(tapGain, now);
    tapVol.gain.exponentialRampToValueAtTime(0.0001, now + 0.03);
    tapSrc.connect(tapHp); tapHp.connect(tapVol); tapVol.connect(ctx.destination);
    tapSrc.start(now); tapSrc.stop(now + 0.04);

    // --- 2. board body ---------------------------------------------------
    const osc = ctx.createOscillator();
    osc.type = "sine";
    osc.frequency.setValueAtTime(body, now);
    osc.frequency.exponentialRampToValueAtTime(bodyEnd, now + duration);
    const lp = ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.value = 1400;
    const vol = ctx.createGain();
    // Percussive envelope: near-instant attack, exponential fall, no tail.
    vol.gain.setValueAtTime(0.0001, now);
    vol.gain.exponentialRampToValueAtTime(bodyGain, now + 0.004);
    vol.gain.exponentialRampToValueAtTime(0.0001, now + duration);
    osc.connect(lp); lp.connect(vol); vol.connect(ctx.destination);
    osc.start(now); osc.stop(now + duration + 0.02);
  } catch {
    /* audio is never load-bearing; a failure must not break a move */
  }
};

/** A quiet move: a soft knock. */
const _playMove_raw = () =>
  thock({ body: 190, bodyEnd: 120, bodyGain: 0.26, tap: 2600, tapGain: 0.1, duration: 0.085 });

/** A capture: heavier and a touch longer, so the two are distinguishable. */
const _playCapture_raw = () =>
  thock({ body: 150, bodyEnd: 92, bodyGain: 0.34, tap: 1900, tapGain: 0.17, duration: 0.125 });

/** Check: the knock, then a clear two-note rise. Attention, not alarm. */
const _playCheck_raw = () => {
  thock({ body: 190, bodyEnd: 130, bodyGain: 0.24, tap: 2600, tapGain: 0.1, duration: 0.08 });
  const ctx = getCtx();
  if (!ctx || isMuted()) return;
  try {
    const now = ctx.currentTime;
    [[660, 0.055], [880, 0.12]].forEach(([f, at]) => {
      const osc = ctx.createOscillator();
      const vol = ctx.createGain();
      osc.type = "triangle";
      osc.frequency.setValueAtTime(f, now + at);
      vol.gain.setValueAtTime(0.0001, now + at);
      vol.gain.exponentialRampToValueAtTime(0.075, now + at + 0.012);
      vol.gain.exponentialRampToValueAtTime(0.0001, now + at + 0.13);
      osc.connect(vol); vol.connect(ctx.destination);
      osc.start(now + at); osc.stop(now + at + 0.15);
    });
  } catch {
    /* ignore */
  }
};

/**
 * A move that cost material. Deliberately NOT an alarm: a dull low knock and
 * a short fall, so it reads as "that one hurt" rather than a buzzer. Mohit's
 * rule is undramatic coaching -- the sound must not be the loudest thing
 * that happens when a 900 hangs a piece.
 */
const _playBlunder_raw = () => {
  thock({ body: 120, bodyEnd: 70, bodyGain: 0.3, tap: 1200, tapGain: 0.12, duration: 0.16 });
  const ctx = getCtx();
  if (!ctx || isMuted()) return;
  try {
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const vol = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(300, now + 0.04);
    osc.frequency.exponentialRampToValueAtTime(165, now + 0.34);
    vol.gain.setValueAtTime(0.0001, now + 0.04);
    vol.gain.exponentialRampToValueAtTime(0.06, now + 0.07);
    vol.gain.exponentialRampToValueAtTime(0.0001, now + 0.36);
    osc.connect(vol); vol.connect(ctx.destination);
    osc.start(now + 0.04); osc.stop(now + 0.38);
  } catch {
    /* ignore */
  }
};

/**
 * Pick the sound from the move itself, so callers do not each re-derive it.
 * `san` is the move in algebraic notation.
 */
const _playForSan_raw = (san) => {
  const s = String(san || "");
  if (!s) return playMove();
  if (s.includes("#") || s.includes("+")) return playCheck();
  if (s.includes("x")) return playCapture();
  return playMove();
};

const _safe = (fn) => (...args) => {
  try {
    return fn(...args);
  } catch {
    return undefined;
  }
};

export const playMove = _safe(_playMove_raw);
export const playCapture = _safe(_playCapture_raw);
export const playCheck = _safe(_playCheck_raw);
export const playBlunder = _safe(_playBlunder_raw);
export const playForSan = _safe(_playForSan_raw);

export default playForSan;
