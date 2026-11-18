/**
 * Stockfish 17.1 (lite, single-threaded) in the browser, for the line board
 * (docs/play_any_line_scope.md, section 10).
 *
 * Why: the reply and the arrows should come at once, like an analysis board,
 * not after a round trip to a busy server. The engine runs in a Web Worker;
 * the server only writes the words.
 *
 * One worker for the whole page, started on first use. One search at a time:
 * a new search stops the one running. Results are cached by position, so the
 * position on the board can be searched in the background while the student
 * thinks, and their move then needs only one more search.
 *
 * Scores are centipawns from the side to move; a mate is +-(10000 - n), the
 * same shape the server uses.
 */
import { useCallback, useEffect, useState } from "react";

export const ENGINE_NAME = "sf17.1-lite";
export const MOVETIME_MS = 800;   // measured 2026-11-18: same verdict as depth 16 on the server
const WORKER_URL = `${process.env.PUBLIC_URL || ""}/stockfish17/stockfish-17.1-lite-single-03e3232.js`;
const CACHE_MAX = 64;

let worker = null;
let state = "idle";            // idle | starting | ready | failed
let readyWaiters = [];
let current = null;            // { key, resolve, lines, depth, onInfo }
let queue = Promise.resolve();
const cache = new Map();
const listeners = new Set();

function notify() { listeners.forEach((fn) => fn(state)); }

function parseInfo(line) {
  if (!line.startsWith("info") || line.indexOf(" pv ") < 0) return null;
  if (line.includes(" lowerbound") || line.includes(" upperbound")) return null;
  const mp = Number((line.match(/ multipv (\d+)/) || [0, 1])[1]);
  const depth = Number((line.match(/ depth (\d+)/) || [0, 0])[1]);
  const cp = line.match(/ score cp (-?\d+)/);
  const mate = line.match(/ score mate (-?\d+)/);
  let score = null;
  if (cp) score = Number(cp[1]);
  else if (mate) { const n = Number(mate[1]); score = n > 0 ? 10000 - n : -10000 - n; }
  const pv = line.split(" pv ")[1].trim().split(/\s+/);
  return { mp, depth, score, pv };
}

function onLine(line) {
  if (line === "uciok") {
    worker.postMessage("setoption name Hash value 32");
    worker.postMessage("isready");
    return;
  }
  if (line === "readyok" && state === "starting") {
    state = "ready";
    readyWaiters.forEach((r) => r(true));
    readyWaiters = [];
    notify();
    return;
  }
  if (!current) return;
  const info = parseInfo(line);
  if (info) {
    current.lines[info.mp] = { score: info.score, pv: info.pv, depth: info.depth };
    current.depth = Math.max(current.depth, info.depth);
    if (current.onInfo && info.mp === 1) current.onInfo({ ...current.lines[1] });
    return;
  }
  if (line.startsWith("bestmove")) {
    const done = current;
    current = null;
    done.resolve({ lines: done.lines, depth: done.depth });
  }
}

function start() {
  if (state !== "idle") return;
  if (typeof Worker !== "function" || typeof WebAssembly !== "object") {
    state = "failed";
    notify();
    return;
  }
  state = "starting";
  notify();
  try {
    worker = new Worker(WORKER_URL);
    worker.onmessage = (e) => String(e.data).split("\n").forEach((l) => l && onLine(l.trim()));
    worker.onerror = () => {
      state = "failed";
      readyWaiters.forEach((r) => r(false));
      readyWaiters = [];
      if (current) { current.resolve(null); current = null; }
      notify();
    };
    worker.postMessage("uci");
  } catch {
    state = "failed";
    notify();
  }
}

function whenReady() {
  if (state === "ready") return Promise.resolve(true);
  if (state === "failed") return Promise.resolve(false);
  start();
  return new Promise((resolve) => {
    readyWaiters.push(resolve);
    setTimeout(() => resolve(state === "ready"), 8000);
  });
}

/**
 * Search `fen`. Resolves {lines: {1: {score, pv, depth}, 2: ...}, depth} or
 * null when the engine is not available. `onInfo` sees the best line grow.
 */
export function analyse(fen, { multipv = 1, movetime = MOVETIME_MS, onInfo } = {}) {
  const key = `${fen.split(" ").slice(0, 4).join(" ")}|${multipv}|${movetime}`;
  if (cache.has(key)) return Promise.resolve(cache.get(key));
  const run = queue.then(async () => {
    if (cache.has(key)) return cache.get(key);
    if (!(await whenReady())) return null;
    const result = await new Promise((resolve) => {
      current = { key, resolve, lines: {}, depth: 0, onInfo };
      worker.postMessage("stop");
      worker.postMessage(`setoption name MultiPV value ${multipv}`);
      worker.postMessage(`position fen ${fen}`);
      worker.postMessage(`go movetime ${movetime}`);
      // A search that never reports back must not hang the board: give up and
      // let the server engine answer instead.
      setTimeout(() => {
        if (current && current.resolve === resolve) {
          current = null;
          worker.postMessage("stop");
          resolve(null);
        }
      }, movetime + 4000);
    });
    if (result && result.lines[1]) {
      cache.set(key, result);
      if (cache.size > CACHE_MAX) cache.delete(cache.keys().next().value);
    }
    return result;
  });
  queue = run.catch(() => null);
  return run;
}

/** The page's view of the engine: its state, and `analyse`. */
export default function useBrowserEngine() {
  const [engineState, setEngineState] = useState(state);
  useEffect(() => {
    listeners.add(setEngineState);
    start();
    return () => listeners.delete(setEngineState);
  }, []);
  const run = useCallback((fen, opts) => analyse(fen, opts), []);
  return { state: engineState, analyse: run };
}
