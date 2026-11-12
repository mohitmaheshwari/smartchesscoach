/**
 * Read aloud: the coach's words, spoken by the browser, for a child who does not
 * read yet. docs/first_steps_scope.md, "Presentation". No files and no service:
 * the browser's own speech. On or off is remembered. No voice just means quiet.
 */
const KEY = "chessguru.room_read_aloud";
let on = (() => { try { return localStorage.getItem(KEY) === "1"; } catch { return false; } })();

export function readAloudOn() { return on; }
export function setReadAloud(value) {
  on = !!value;
  try { localStorage.setItem(KEY, on ? "1" : "0"); } catch { /* private mode: not remembered */ }
  if (!on) stopSpeaking();
}

function pickVoice(synth) {
  const voices = synth.getVoices ? synth.getVoices() : [];
  const lang = (v) => String(v.lang || "").toLowerCase();
  return voices.find((v) => lang(v) === "en-in")
    || voices.find((v) => lang(v) === "en-gb")
    || voices.find((v) => lang(v).startsWith("en"))
    || null;
}

export function stopSpeaking() {
  try { if (window.speechSynthesis) window.speechSynthesis.cancel(); } catch { /* quiet is fine */ }
}

/** Say `text`, replacing whatever was being said. */
export function speak(text) {
  if (!on || !text) return;
  try {
    const synth = window.speechSynthesis;
    if (!synth || typeof window.SpeechSynthesisUtterance !== "function") return;
    synth.cancel();
    const u = new window.SpeechSynthesisUtterance(String(text));
    const voice = pickVoice(synth);
    if (voice) { u.voice = voice; u.lang = voice.lang; }
    u.rate = 0.95;
    synth.speak(u);
  } catch { /* quiet is fine */ }
}
