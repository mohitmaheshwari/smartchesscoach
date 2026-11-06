/**
 * The room's one sound: wood on wood. Made by the browser, so there are no files.
 * Off is remembered. No audio just means quiet.
 */
const KEY = "chessguru.room_sound_off";
let actx = null;
let off = (() => { try { return localStorage.getItem(KEY) === "1"; } catch { return false; } })();

export function soundOff() { return off; }
export function setSoundOff(value) {
  off = !!value;
  try { localStorage.setItem(KEY, off ? "1" : "0"); } catch { /* private mode: not remembered */ }
}

export function woodClick(hard = false) {
  if (off) return;
  try {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    actx = actx || new AC();
    if (actx.state === "suspended") actx.resume();
    const n = Math.floor(actx.sampleRate * 0.05);
    const buffer = actx.createBuffer(1, n, actx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < n; i += 1) data[i] = (Math.random() * 2 - 1) * Math.exp(-i / (n * 0.12));
    const source = actx.createBufferSource();
    const filter = actx.createBiquadFilter();
    const gain = actx.createGain();
    source.buffer = buffer;
    filter.type = "bandpass";
    filter.frequency.value = hard ? 900 : 1500;
    filter.Q.value = 1.2;
    gain.gain.value = hard ? 0.9 : 0.55;
    source.connect(filter).connect(gain).connect(actx.destination);
    source.start();
  } catch { /* quiet is fine */ }
}
