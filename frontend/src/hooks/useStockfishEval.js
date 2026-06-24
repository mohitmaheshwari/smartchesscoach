/**
 * useStockfishEval — client-side Stockfish (WASM) for PWC live captions.
 *
 * docs/pwc_client_eval_scope.md: run Stockfish in the browser (single-threaded +
 * SIMD), time-bounded ~800ms with a depth-12 floor, and feed the eval facts to the
 * /v5/feedback endpoint → the SAME central caption door as review. Zero server
 * Stockfish per live move; instant on any device; no network round-trip for the eval.
 *
 * ── Asset requirement (one-time) ───────────────────────────────────────────
 * This loads a Stockfish worker from `${PUBLIC_URL}/stockfish/stockfish.js`. Add a
 * single-threaded SIMD build there, e.g.:
 *   npm i stockfish.wasm   # then copy its dist into frontend/public/stockfish/
 * or drop a prebuilt stockfish.js + stockfish.wasm into frontend/public/stockfish/.
 * Single-threaded → no COOP/COEP cross-origin-isolation headers needed.
 *
 * Returns: { ready, evalMove } where evalMove(fenBefore, moveSan) resolves to the
 * full fact shape the backend caption pipeline expects (white-POV evals in pawns):
 *   { eval_before, eval_after, cp_loss, best_move, pv_after_best, pv_after_played }
 * or null on failure (caller falls back to the server-eval path).
 */
import { useEffect, useRef, useState, useCallback } from "react";
import { Chess } from "chess.js";

// stockfish.js@10: the WASM worker entry is `stockfish.wasm.js` (it loads
// stockfish.wasm); `stockfish.js` is only the asm.js fallback. Feature-detect per
// the package README — pointing at stockfish.js was why the worker loaded but never
// spoke UCI. 2026-06-24.
const _WASM_OK = typeof WebAssembly === "object" &&
  typeof WebAssembly.validate === "function" &&
  WebAssembly.validate(Uint8Array.of(0x0, 0x61, 0x73, 0x6d, 0x01, 0x00, 0x00, 0x00));
const _SF_BASE = `${process.env.PUBLIC_URL || ""}/stockfish`;
const WORKER_URL = `${_SF_BASE}/${_WASM_OK ? "stockfish.wasm.js" : "stockfish.js"}`;
const MOVETIME_MS = 800;   // time-bounded; depth floats with device speed
const MIN_DEPTH = 12;      // correctness floor (depth_probe.py: harmful <7% at d12)
const PV_LEN = 4;

export function useStockfishEval() {
  const workerRef = useRef(null);
  const readyRef = useRef(false);
  const pendingRef = useRef(null); // { resolve, info: {depth,scoreCp,mate,pv}, sideToMoveWhite }
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let worker;
    try {
      worker = new Worker(WORKER_URL);
    } catch (e) {
      // No asset / unsupported → hook stays not-ready; caller uses server fallback.
      console.warn("[useStockfishEval] worker init failed:", e);
      return;
    }
    workerRef.current = worker;

    // Surface worker-level failures (wasm load error, script error) — without this
    // a broken engine fails silently. 2026-06-24 debug.
    worker.onerror = (e) => {
      console.error("[useStockfishEval] worker error:", e?.message || e?.filename || e);
    };
    worker.onmessageerror = (e) => console.error("[useStockfishEval] message error:", e);

    let _dbgLines = 0; // log the handshake (first ~25 lines) so we can see the protocol
    worker.onmessage = (ev) => {
      const line = typeof ev.data === "string" ? ev.data : ev.data?.data || "";
      if (_dbgLines < 25) { console.log("[useStockfishEval] <<", JSON.stringify(ev.data)?.slice(0, 120)); _dbgLines++; }
      if (!line) return;
      if (line === "uciok") {
        worker.postMessage("setoption name Use NNUE value true");
        worker.postMessage("setoption name Threads value 1");
        worker.postMessage("isready");
        return;
      }
      if (line === "readyok") {
        readyRef.current = true;
        setReady(true);
        console.log("[useStockfishEval] engine ready (client-side WASM eval active)");
        return;
      }
      const p = pendingRef.current;
      if (!p) return;
      if (line.startsWith("info ") && line.includes(" pv ")) {
        const depthM = line.match(/ depth (\d+)/);
        const cpM = line.match(/ score cp (-?\d+)/);
        const mateM = line.match(/ score mate (-?\d+)/);
        const pvM = line.match(/ pv (.+)$/);
        if (pvM) {
          p.info = {
            depth: depthM ? parseInt(depthM[1], 10) : 0,
            scoreCp: cpM ? parseInt(cpM[1], 10) : null,
            mate: mateM ? parseInt(mateM[1], 10) : null,
            pv: pvM[1].trim().split(/\s+/),
          };
        }
        return;
      }
      if (line.startsWith("bestmove")) {
        const bm = line.split(/\s+/)[1];
        const resolve = p.resolve;
        const info = p.info || {};
        pendingRef.current = null;
        resolve({ bestmoveUci: bm, ...info });
      }
    };

    worker.postMessage("uci");
    return () => {
      try { worker.postMessage("quit"); worker.terminate(); } catch (_) {}
      workerRef.current = null;
      readyRef.current = false;
    };
  }, []);

  // Analyze a single FEN; resolves {bestmoveUci, depth, scoreCp, mate, pv}. White-POV
  // conversion is done by the caller (we know whose turn it is from the FEN).
  const analyze = useCallback((fen) => {
    return new Promise((resolve) => {
      const worker = workerRef.current;
      if (!worker || !readyRef.current) { resolve(null); return; }
      const sideToMoveWhite = fen.split(" ")[1] !== "b";
      pendingRef.current = { resolve, info: null, sideToMoveWhite };
      worker.postMessage("ucinewgame");
      worker.postMessage(`position fen ${fen}`);
      worker.postMessage(`go movetime ${MOVETIME_MS}`);
      // safety timeout — if the worker never answers, don't hang the move flow.
      setTimeout(() => {
        if (pendingRef.current && pendingRef.current.resolve === resolve) {
          pendingRef.current = null;
          resolve(null);
        }
      }, MOVETIME_MS + 1500);
    });
  }, []);

  // White-POV centipawns from a UCI score (which is side-to-move POV).
  const toWhiteCp = (r, sideToMoveWhite) => {
    if (!r) return null;
    let cp;
    if (r.mate != null) cp = r.mate > 0 ? 10000 : -10000; // mate → clamp, mover POV
    else if (r.scoreCp != null) cp = r.scoreCp;
    else return null;
    return sideToMoveWhite ? cp : -cp; // flip to white POV
  };

  const uciPvToSan = (fen, pvUci) => {
    const out = [];
    try {
      const c = new Chess(fen);
      for (const u of (pvUci || []).slice(0, PV_LEN)) {
        const mv = c.move({ from: u.slice(0, 2), to: u.slice(2, 4), promotion: u.slice(4) || undefined });
        if (!mv) break;
        out.push(mv.san);
      }
    } catch (_) {}
    return out;
  };

  /**
   * evalMove — full fact shape for a played move, for /v5/feedback.
   * White-POV evals in PAWNS (the endpoint multiplies by 100).
   */
  const evalMove = useCallback(async (fenBefore, moveSan) => {
    if (!readyRef.current) return null;
    let fenAfter, moverWhite;
    try {
      const c = new Chess(fenBefore);
      moverWhite = c.turn() === "w";
      const mv = c.move(moveSan);
      if (!mv) return null;
      fenAfter = c.fen();
    } catch (_) {
      return null;
    }

    const before = await analyze(fenBefore);
    const after = await analyze(fenAfter);
    if (!before || !after) return null;
    if ((before.depth || 0) < MIN_DEPTH && (after.depth || 0) < MIN_DEPTH) {
      // never reached the correctness floor → let the server path handle it
      return null;
    }

    const evalBeforeWhiteCp = toWhiteCp(before, fenBefore.split(" ")[1] !== "b");
    const evalAfterWhiteCp = toWhiteCp(after, fenAfter.split(" ")[1] !== "b");
    if (evalBeforeWhiteCp == null || evalAfterWhiteCp == null) return null;

    // cp_loss from the MOVER's perspective.
    const moverBefore = moverWhite ? evalBeforeWhiteCp : -evalBeforeWhiteCp;
    const moverAfter = moverWhite ? evalAfterWhiteCp : -evalAfterWhiteCp;
    const cpLoss = Math.max(0, Math.round(moverBefore - moverAfter));

    // best move SAN (from the before-position analysis).
    let bestSan = null;
    try {
      const c = new Chess(fenBefore);
      if (before.bestmoveUci && before.bestmoveUci !== "(none)") {
        const mv = c.move({
          from: before.bestmoveUci.slice(0, 2),
          to: before.bestmoveUci.slice(2, 4),
          promotion: before.bestmoveUci.slice(4) || undefined,
        });
        bestSan = mv ? mv.san : null;
      }
    } catch (_) {}

    const facts = {
      eval_before: Math.round(evalBeforeWhiteCp) / 100, // pawns, white-POV
      eval_after: Math.round(evalAfterWhiteCp) / 100,
      cp_loss: cpLoss,
      best_move: bestSan,
      pv_after_best: uciPvToSan(fenBefore, before.pv),
      pv_after_played: uciPvToSan(fenAfter, after.pv),
    };
    console.log(`[useStockfishEval] ${moveSan} -> best ${bestSan}, cp_loss ${cpLoss}, depth ${before.depth}/${after.depth} (client eval)`);
    return facts;
  }, [analyze]);

  return { ready, evalMove };
}

export default useStockfishEval;
