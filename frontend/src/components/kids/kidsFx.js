/**
 * Sound and sparkle for the kids look. Every sound is made by the browser
 * (Web Audio), so there are no files; every effect is drawn on one canvas.
 * All of it is optional: no audio, no canvas or reduced motion just means quiet.
 */
import { starMarkup } from "@/components/kids/KidsArt";

const MUTE_KEY = "chessguru.kids_muted";
let actx = null;
let muted = (() => { try { return localStorage.getItem(MUTE_KEY) === "1"; } catch { return false; } })();

export function isMuted() { return muted; }
export function setMuted(value) {
  muted = !!value;
  try { localStorage.setItem(MUTE_KEY, muted ? "1" : "0"); } catch { /* private mode: not remembered */ }
}

function reducedMotion() {
  try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch { return false; }
}

function audio() {
  if (muted) return null;
  try {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    actx = actx || new AC();
    if (actx.state === "suspended") actx.resume();
    return actx;
  } catch { return null; }
}

function tone(freq, dur = 0.12, type = "sine", gain = 0.16, when = 0) {
  const a = audio();
  if (!a) return;
  const t = a.currentTime + when;
  const o = a.createOscillator();
  const g = a.createGain();
  o.type = type;
  o.frequency.setValueAtTime(freq, t);
  g.gain.setValueAtTime(0, t);
  g.gain.linearRampToValueAtTime(gain, t + 0.015);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  o.connect(g).connect(a.destination);
  o.start(t);
  o.stop(t + dur + 0.02);
}

const SCALE = [523, 587, 659, 698, 784, 880, 988, 1047];
export const sfx = {
  pop: () => tone(520, 0.08, "triangle", 0.12),
  found: (n) => { tone(SCALE[n % 8], 0.16, "triangle", 0.15); tone(SCALE[n % 8] * 2, 0.1, "sine", 0.05, 0.02); },
  wrong: () => { tone(220, 0.18, "sine", 0.14); tone(185, 0.22, "sine", 0.1, 0.08); },
  right: () => { tone(659, 0.14, "triangle", 0.14); tone(988, 0.22, "triangle", 0.14, 0.1); },
  star: () => [1047, 1319, 1568, 2093].forEach((f, i) => tone(f, 0.14, "sine", 0.1, i * 0.06)),
  slide: () => { tone(330, 0.09, "triangle", 0.08); tone(392, 0.09, "triangle", 0.06, 0.05); },
  fanfare: () => [[523, 0], [659, 0.12], [784, 0.24], [1047, 0.4], [784, 0.58], [1047, 0.7]]
    .forEach(([f, w]) => { tone(f, 0.24, "triangle", 0.14, w); tone(f / 2, 0.24, "sine", 0.06, w); }),
};

// ---------------------------------------------------------------- particles
let canvas = null;
let ctx = null;
let parts = [];
let raf = null;

function ensureCanvas() {
  if (canvas && document.body.contains(canvas)) return ctx;
  if (/jsdom/i.test(navigator.userAgent || "")) return null;  // tests: no canvas to draw on
  try {
    canvas = document.createElement("canvas");
    canvas.className = "kids-fx";
    canvas.setAttribute("aria-hidden", "true");
    document.body.appendChild(canvas);
    ctx = canvas.getContext("2d");
    const size = () => {
      const r = window.devicePixelRatio || 1;
      canvas.width = window.innerWidth * r;
      canvas.height = window.innerHeight * r;
      if (ctx) ctx.setTransform(r, 0, 0, r, 0, 0);
    };
    size();
    window.addEventListener("resize", size);
  } catch { ctx = null; }
  return ctx;
}

function loop() {
  if (raf || !ctx) return;
  const step = () => {
    ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
    parts = parts.filter((p) => p.life > 0 && p.y < window.innerHeight + 40);
    for (const p of parts) {
      p.vy += p.g; p.x += p.vx; p.y += p.vy; p.life -= p.decay; p.rot += p.vr;
      ctx.save();
      ctx.globalAlpha = Math.max(0, Math.min(1, p.life * 1.4));
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot);
      ctx.fillStyle = p.c;
      if (p.kind === "paper") ctx.fillRect(-p.r / 2, -p.r, p.r, p.r * 2);
      else if (p.kind === "star") {
        ctx.beginPath();
        for (let k = 0; k < 10; k += 1) {
          const rr = k % 2 ? p.r * 0.45 : p.r * 1.2;
          const an = (k * Math.PI) / 5;
          ctx.lineTo(Math.cos(an) * rr, Math.sin(an) * rr);
        }
        ctx.fill();
      } else { ctx.beginPath(); ctx.arc(0, 0, p.r, 0, Math.PI * 2); ctx.fill(); }
      ctx.restore();
    }
    if (parts.length) raf = window.requestAnimationFrame(step);
    else { raf = null; ctx.clearRect(0, 0, window.innerWidth, window.innerHeight); }
  };
  raf = window.requestAnimationFrame(step);
}

const COLORS = ["#ffc23d", "#ff7a59", "#2fbf83", "#7fd0e6", "#ffffff"];
export function burst(x, y, n = 18) {
  if (reducedMotion() || !ensureCanvas()) return;
  for (let i = 0; i < n; i += 1) {
    const a = Math.random() * Math.PI * 2;
    const s = 2 + Math.random() * 5;
    parts.push({ x, y, vx: Math.cos(a) * s, vy: Math.sin(a) * s - 2, g: 0.18, life: 1, decay: 0.018 + Math.random() * 0.02,
      r: 3 + Math.random() * 4, c: COLORS[i % COLORS.length], kind: Math.random() < 0.4 ? "star" : "dot", rot: Math.random() * 6, vr: 0.1 });
  }
  loop();
}

export function confetti() {
  if (reducedMotion() || !ensureCanvas()) return;
  const colors = [...COLORS, "#d94f6a"];
  for (let i = 0; i < 160; i += 1) {
    parts.push({ x: Math.random() * window.innerWidth, y: -20 - Math.random() * window.innerHeight * 0.5,
      vx: (Math.random() - 0.5) * 2, vy: 2 + Math.random() * 3, g: 0.03, life: 1, decay: 0.004 + Math.random() * 0.003,
      r: 5 + Math.random() * 5, c: colors[i % colors.length], kind: "paper", rot: Math.random() * 6, vr: (Math.random() - 0.5) * 0.3 });
  }
  loop();
}

export function centerOf(el) {
  const r = el.getBoundingClientRect();
  return [r.left + r.width / 2, r.top + r.height / 2];
}

/** A star flies from `fromEl` to the star counter, then the counter bumps. */
export function flyStar(fromEl, onLand) {
  const pill = document.getElementById("kids-starpill");
  if (!pill || !fromEl || reducedMotion() || !document.body.animate) { if (onLand) onLand(); return; }
  const [x0, y0] = centerOf(fromEl);
  const [x1, y1] = centerOf(pill.querySelector("svg") || pill);
  const s = document.createElement("div");
  s.className = "kids-flystar";
  s.innerHTML = `<svg viewBox="0 0 100 100" width="34" height="34">${starMarkup()}</svg>`;
  document.body.appendChild(s);
  const mx = (x0 + x1) / 2 + 60;
  const my = Math.min(y0, y1) - 80;
  const anim = s.animate([
    { transform: `translate(${x0 - 17}px, ${y0 - 17}px) scale(1.3)` },
    { transform: `translate(${mx - 17}px, ${my - 17}px) scale(1.6) rotate(180deg)`, offset: 0.45 },
    { transform: `translate(${x1 - 17}px, ${y1 - 17}px) scale(.8) rotate(360deg)` },
  ], { duration: 850, easing: "cubic-bezier(.5,0,.3,1)" });
  anim.onfinish = () => {
    s.remove();
    pill.classList.remove("bump");
    void pill.offsetWidth;
    pill.classList.add("bump");
    sfx.star();
    burst(x1, y1, 10);
    if (onLand) onLand();
  };
}
