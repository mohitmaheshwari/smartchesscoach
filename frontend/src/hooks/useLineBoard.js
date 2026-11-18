/**
 * Play any line on the review board (docs/play_any_line_scope.md).
 *
 * The student moves a piece from a position of the game; the server answers
 * with the engine's reply and words (POST /coach/line/move). When the move is
 * a mistake, the why button's sentence is asked for separately
 * (POST /coach/line/why) so the reply never waits for it.
 *
 * The game line is never touched: the line lives here until "Back to the
 * game".
 */
import { useCallback, useRef, useState } from "react";
import { Chess } from "chess.js";

import { API } from "@/App";

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

export default function useLineBoard(gameId) {
  // steps: [{ moves_before, student, reply, count_text, why, why_state, arrows, fen_after }]
  const [startFen, setStartFen] = useState(null);
  const [steps, setSteps] = useState([]);
  const [pendingFen, setPendingFen] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  // Every request carries a token; an answer to an older line is dropped.
  const token = useRef(0);

  const active = startFen !== null;
  const last = steps.length ? steps[steps.length - 1] : null;
  const fen = pendingFen || (last ? last.fen_after : startFen);

  const movesSoFar = useCallback((list) => {
    const out = [];
    for (const s of list) {
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

  const request = useCallback(async (base, list, san, optimisticFen) => {
    const myToken = ++token.current;
    const movesBefore = movesSoFar(list);
    setBusy(true);
    setError(null);
    setPendingFen(optimisticFen || null);
    try {
      const data = await post("/coach/line/move", {
        game_id: gameId, start_fen: base, moves: movesBefore, move: san,
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
      setPendingFen(null);
      setError(e.message);
    } finally {
      if (token.current === myToken) setBusy(false);
    }
  }, [gameId, movesSoFar, askWhy]);

  /** The student dropped a piece. `gameFen` is the game position on the board. */
  const play = useCallback((gameFen, from, to, promotion) => {
    if (busy) return false;
    const base = active ? startFen : gameFen;
    const list = active ? steps : [];
    const here = active ? fen : gameFen;
    let move = null;
    try {
      const board = new Chess(here);
      move = board.move({ from, to, promotion: promotion || "q" });
      if (!move) return false;
      if (!active) setStartFen(gameFen);
      request(base, list, move.san, board.fen());
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
    if (!active) setStartFen(gameFen);
    request(base, list, null, null);
  }, [busy, active, startFen, steps, request]);

  const back = useCallback(() => {
    token.current += 1;
    setBusy(false);
    setPendingFen(null);
    setError(null);
    setSteps((prev) => prev.slice(0, -1));
  }, []);

  const exit = useCallback(() => {
    token.current += 1;
    setBusy(false);
    setPendingFen(null);
    setError(null);
    setSteps([]);
    setStartFen(null);
  }, []);

  const arrows = pendingFen ? [] : (last ? last.arrows : []);
  const lastMove = (() => {
    if (pendingFen || !last) return null;
    const uci = (last.reply && last.reply.uci) || last.student.uci;
    return uci ? [uci.slice(0, 2), uci.slice(2, 4)] : null;
  })();

  return {
    active, fen, steps, busy, error, arrows, lastMove,
    line: movesSoFar(steps),
    play, best, back, exit,
  };
}
