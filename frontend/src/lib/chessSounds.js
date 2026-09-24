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
  if (!ctxRef) ctxRef = new Ctor();
  // Browsers start the context suspended until a user gesture. A move IS a
  // gesture, so resuming here is allowed and is why the first move is audible.
  if (ctxRef.state === "suspended") ctxRef.resume().catch(() => {});
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

/** A short noise burst through a band-pass — a piece landing on wood. */
const click = ({ freq, duration, gain, decay }) => {
  const ctx = getCtx();
  if (!ctx || isMuted()) return;
  try {
    const frames = Math.floor(ctx.sampleRate * duration);
    const buffer = ctx.createBuffer(1, frames, ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < frames; i += 1) {
      // Noise shaped by an exponential decay: the percussive part.
      data[i] = (Math.random() * 2 - 1) * Math.exp((-decay * i) / frames);
    }
    const src = ctx.createBufferSource();
    src.buffer = buffer;

    const band = ctx.createBiquadFilter();
    band.type = "bandpass";
    band.frequency.value = freq;
    band.Q.value = 1.1;

    const vol = ctx.createGain();
    vol.gain.setValueAtTime(gain, ctx.currentTime);
    vol.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);

    src.connect(band);
    band.connect(vol);
    vol.connect(ctx.destination);
    src.start();
    src.stop(ctx.currentTime + duration);
  } catch {
    /* audio is never load-bearing; a failure must not break a move */
  }
};

/** A quiet move. */
export const playMove = () =>
  click({ freq: 1100, duration: 0.045, gain: 0.16, decay: 22 });

/** A capture: lower and a touch fuller, so the two are distinguishable. */
export const playCapture = () =>
  click({ freq: 700, duration: 0.07, gain: 0.22, decay: 16 });

/** Check: the same click with a short tone over it, still not an alarm. */
export const playCheck = () => {
  click({ freq: 900, duration: 0.05, gain: 0.18, decay: 20 });
  const ctx = getCtx();
  if (!ctx || isMuted()) return;
  try {
    const osc = ctx.createOscillator();
    const vol = ctx.createGain();
    osc.type = "triangle";
    osc.frequency.setValueAtTime(660, ctx.currentTime);
    vol.gain.setValueAtTime(0.0001, ctx.currentTime);
    vol.gain.exponentialRampToValueAtTime(0.08, ctx.currentTime + 0.012);
    vol.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.16);
    osc.connect(vol);
    vol.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.17);
  } catch {
    /* ignore */
  }
};

/**
 * Pick the sound from the move itself, so callers do not each re-derive it.
 * `san` is the move in algebraic notation.
 */
export const playForSan = (san) => {
  const s = String(san || "");
  if (!s) return playMove();
  if (s.includes("#") || s.includes("+")) return playCheck();
  if (s.includes("x")) return playCapture();
  return playMove();
};

export default playForSan;
