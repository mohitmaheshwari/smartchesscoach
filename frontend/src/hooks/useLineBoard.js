/**
 * Play any line on the review board (docs/play_any_line_scope.md).
 *
 * The student moves a piece from a position of the game. Stockfish in the
 * browser (useBrowserEngine, section 10) finds the reply at once and the
 * board plays it; the server then writes the words for both moves
 * (POST /coach/line/move with the browser's numbers, no server engine). When
 * the browser engine is not available, the server engine answers instead.
 * A mistake also gets the why button's sentence (POST /coach/line/why), which
 * stays on the server and arrives later.
 *
 * The game line is never touched: the line lives here until "Back to the
 * game".
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Chess } from "chess.js";

import { API } from "@/App";
import useBrowserEngine, { ENGINE_NAME } from "@/hooks/useBrowserEngine";

async function post(path, body) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  let data = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }
  if (!res.ok) {
    const msg = (data && data.detail) || "The coach could not answer that move.";
    throw new Error(typeof msg === "string" ? msg : "The coach could not answer that move.");
  }
  return data;
}

export const ARROW_COLOR = { blue: "blue", red: "red" };

const uciArrow = (uci, color) => [uci.slice(0, 2), uci.slice(2, 4), color];

/** The browser's numbers in the shape POST /coach/line/move takes. */
export function clientEvalFrom(before, after) {
  const b1 = before?.lines?.[1];
  if (!b1 || !b1.pv?.length || b1.score == null) return null;
  const a1 = after?.lines?.[1];
  return {
    engine: ENGINE_NAME,
    best: b1.pv[0],
    best_cp: b1.score,
    second_cp: before.lines[2]?.score ?? null,
    after_cp: a1 ? a1.score : null,
    pv_after: a1 ? a1.pv.slice(0, 12) : [],
    depth_before: before.depth,
    depth_after: after ? after.depth : null,
  };
}

export default function useLineBoard(gameId) {
  const engine = useBrowserEngine();
  // steps: [{ student, reply, count_text, why, why_state, arrows, fen_after, provisional }]
  const [startFen, setStartFen] = useState(null);
  const [steps, setSteps] = useState([]);
  const [pendingFen, setPendingFen] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [hint, setHint] = useState(false);
  const [hintArrow, setHintArrow] = useState(null);
  // Every request carries a token; an answer to an older line is dropped.
  const token = useRef(0);
  const usable = engine.state !== "failed";

  const active = startFen !== null;
  const last = steps.length ? steps[steps.length - 1] : null;
  const fen = pendingFen || (last ? last.fen_after : startFen);

  const movesSoFar = useCallback((list) => {
    const out = [];
    for (const s of list) {
      if (s.provisional) continue;
      out.push(s.student.san);
      if (s.reply) out.push(s.reply.san);
    }
    return out;
  }, []);

  const askWhy = useCallback((myToken, base, movesBefore, san, index) => {
    post("/coach/line/why", { game_id: gameId, start_fen: base, moves: movesBefore, move: san })
      .then((data) => {
        if (token.current !== myToken) return;
        setSteps((prev) => prev.map((s, i) => (i === index
          ? { ...s, why: data && data.found ? data.text : null, why_state: "done" }
          : s)));
      })
      .catch(() => {
        if (token.current !== myToken) return;
        setSteps((prev) => prev.map((s, i) => (i === index ? { ...s, why_state: "done" } : s)));
      });
  }, [gameId]);

  /** The browser's search for this move: before (MultiPV 2) and after. */
  const browserSearch = useCallback(async (hereFen, san) => {
    if (!usable) return null;
    const before = await engine.analyse(hereFen, { multipv: 2 });
    if (!before || !before.lines[1]) return null;
    const board = new Chess(hereFen);
    let move;
    try {
      move = san ? board.move(san) : board.move({
        from: before.lines[1].pv[0].slice(0, 2), to: before.lines[1].pv[0].slice(2, 4),
        promotion: before.lines[1].pv[0][4] || undefined,
      });
    } catch {
      return null;
    }
    if (!move) return null;
    const afterFen = board.fen();
    const after = board.isGameOver() ? null : await engine.analyse(afterFen, { multipv: 1 });
    return { before, after, move, afterFen };
  }, [engine, usable]);

  const request = useCallback(async (base, list, san, hereFen, optimisticFen) => {
    const myToken = ++token.current;
    const movesBefore = movesSoFar(list);
    setBusy(true);
    setError(null);
    setHintArrow(null);
    setPendingFen(optimisticFen || null);
    try {
      const found = await browserSearch(hereFen, san);
      if (token.current !== myToken) return;
      let clientEval = null;
      if (found) {
        clientEval = clientEvalFrom(found.before, found.after);
        // Show the reply on the board at once; the words follow.
        const replyUci = found.after?.lines?.[1]?.pv?.[0];
        if (replyUci) {
          const b = new Chess(found.afterFen);
          let reply = null;
          try {
            reply = b.move({ from: replyUci.slice(0, 2), to: replyUci.slice(2, 4), promotion: replyUci[4] });
          } catch {
            reply = null;
          }
          if (reply) {
            setPendingFen(null);
            setSteps([...list, {
              provisional: true,
              student: { san: found.move.san, uci: found.move.from + found.move.to, text: null },
              reply: { san: reply.san, uci: replyUci, text: null },
              arrows: [uciArrow(found.move.from + found.move.to, "blue"), uciArrow(replyUci, "red")],
              fen_after: b.fen(),
              why_state: "none",
            }]);
          }
        }
      }
      const data = await post("/coach/line/move", {
        game_id: gameId, start_fen: base, moves: movesBefore,
        move: san || (found ? found.move.san : null),
        client_eval: clientEval,
      });
      if (token.current !== myToken) return;
      const step = {
        student: data.student,
        reply: data.reply,
        count_text: data.count_text,
        arrows: (data.arrows || []).map((a) => [a.from, a.to, ARROW_COLOR[a.color] || "red"]),
        fen_after: data.fen_after,
        why: null,
        why_state: data.needs_why ? "loading" : "none",
      };
      const index = list.length;
      setSteps([...list, step]);
      setPendingFen(null);
      if (data.needs_why) askWhy(myToken, base, movesBefore, data.student.san, index);
    } catch (e) {
      if (token.current !== myToken) return;
      setSteps(list);
      setPendingFen(null);
      setError(e.message);
    } finally {
      if (token.current === myToken) setBusy(false);
    }
  }, [gameId, movesSoFar, askWhy, browserSearch]);

  /** The student dropped a piece. `gameFen` is the game position on the board. */
  const play = useCallback((gameFen, from, to, promotion) => {
    if (busy) return false;
    const base = active ? startFen : gameFen;
    const list = active ? steps : [];
    const here = active ? fen : gameFen;
    try {
      const board = new Chess(here);
      const move = board.move({ from, to, promotion: promotion || "q" });
      if (!move) return false;
      if (!active) setStartFen(gameFen);
      request(base, list, move.san, here, board.fen());
      return true;
    } catch {
      return false;
    }
  }, [busy, active, startFen, steps, fen, request]);

  /** "Best move here": the engine's best is played as the student's move. */
  const best = useCallback((gameFen) => {
    if (busy) return;
    const base = active ? startFen : gameFen;
    const list = active ? steps : [];
    const here = active ? fen : gameFen;
    if (!active) setStartFen(gameFen);
    request(base, list, null, here, null);
  }, [busy, active, startFen, steps, fen, request]);

  const back = useCallback(() => {
    token.current += 1;
    setBusy(false);
    setPendingFen(null);
    setError(null);
    setHintArrow(null);
    setSteps((prev) => prev.slice(0, -1));
  }, []);

  const exit = useCallback(() => {
    token.current += 1;
    setBusy(false);
    setPendingFen(null);
    setError(null);
    setHintArrow(null);
    setSteps([]);
    setStartFen(null);
  }, []);

  /** Search a position in the background, so the student's move there is quick. */
  const prefetchFen = useRef(null);
  const prefetch = useCallback((positionFen) => {
    if (!usable || !positionFen) return;
    prefetchFen.current = positionFen;
    // Let the board settle: a player stepping through moves fast only pays
    // for the position they stop on.
    setTimeout(() => {
      if (prefetchFen.current === positionFen) engine.analyse(positionFen, { multipv: 2 });
    }, 250);
  }, [engine, usable]);

  // While a line is open, the position after the reply is searched at once,
  // and, with "Show best move" on, its best move is drawn as it is found.
  useEffect(() => {
    if (!active || busy || !fen || !usable) return undefined;
    let live = true;
    const hintToken = token.current;
    engine.analyse(fen, {
      multipv: 2,
      onInfo: (line) => {
        if (live && hint && token.current === hintToken && line.pv?.[0]) {
          setHintArrow(uciArrow(line.pv[0], "green"));
        }
      },
    }).then((res) => {
      if (live && hint && token.current === hintToken && res?.lines?.[1]?.pv?.[0]) {
        setHintArrow(uciArrow(res.lines[1].pv[0], "green"));
      }
    });
    return () => { live = false; };
  }, [active, busy, fen, hint, usable, engine]);

  useEffect(() => { if (!hint) setHintArrow(null); }, [hint]);

  const baseArrows = pendingFen ? [] : (last ? last.arrows : []);
  const arrows = hint && hintArrow ? [...baseArrows, hintArrow] : baseArrows;
  const lastMove = (() => {
    if (pendingFen || !last) return null;
    const uci = (last.reply && last.reply.uci) || last.student.uci;
    return uci ? [uci.slice(0, 2), uci.slice(2, 4)] : null;
  })();

  return {
    active, fen, steps, busy, error, arrows, lastMove,
    hint, setHint, engineState: engine.state,
    line: movesSoFar(steps),
    play, best, back, exit, prefetch,
  };
}
