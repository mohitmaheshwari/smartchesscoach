/**
 * An academy coach on one of a student's games
 * (docs/play_any_line_scope.md, "Coach pages").
 *
 * The game replays move by move, and the coach can move any piece to show
 * the student a line: the board answers with the engine's reply and the same
 * words the student sees on their own review (POST /coach/line/*). "Your" in
 * those words is the student.
 *
 * Staff only, after the parent agreed; the server checks both on every call
 * (routes/academy_games.py).
 */
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Chess } from "chess.js";
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";

import { API } from "@/App";
import Layout from "@/components/Layout";
import LichessBoard from "@/components/LichessBoard";
import LineBoardPanel, { LineBoardHint } from "@/components/review/LineBoardPanel";
import useLineBoard from "@/hooks/useLineBoard";

/** Every position of the game, from its PGN (a FEN header is honoured). */
export function gamePositions(pgn) {
  const g = new Chess();
  g.loadPgn(pgn || "");
  const history = g.history({ verbose: true });
  const start = history.length ? history[0].before : g.fen();
  const positions = [{ fen: start, san: null, from: null, to: null }];
  for (const m of history) positions.push({ fen: m.after, san: m.san, from: m.from, to: m.to });
  return positions;
}

export default function AcademyStudentGame() {
  const { studentId, gameId } = useParams();
  const [state, setState] = useState({ loading: true });
  const [index, setIndex] = useState(0);
  const lb = useLineBoard(gameId);

  useEffect(() => {
    let live = true;
    fetch(`${API}/academy/student/${studentId}/game/${gameId}`, { credentials: "include" })
      .then(async (res) => {
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || "This game could not be opened.");
        return data;
      })
      .then((data) => { if (live) setState({ data }); })
      .catch((err) => { if (live) setState({ error: err.message }); });
    return () => { live = false; };
  }, [studentId, gameId]);

  const positions = useMemo(() => {
    try {
      return state.data ? gamePositions(state.data.pgn) : [];
    } catch {
      return [];
    }
  }, [state.data]);

  const lbExit = lb.exit;
  useEffect(() => { lbExit(); }, [index, lbExit]);
  const lbPrefetch = lb.prefetch;
  const hereFen = positions[index]?.fen;
  useEffect(() => { if (hereFen) lbPrefetch(hereFen); }, [hereFen, lbPrefetch]);

  if (state.loading) return <Layout><p className="p-6 text-sm text-muted-foreground">Opening the game…</p></Layout>;
  if (state.error) {
    return (
      <Layout>
        <div className="mx-auto max-w-3xl p-6 grid gap-3">
          <p>{state.error}</p>
          <Link className="underline" to={`/academy/student/${studentId}`}>Back to the student</Link>
        </div>
      </Layout>
    );
  }

  const data = state.data;
  const here = positions[index] || positions[0];
  const last = positions.length - 1;
  const moveLabel = (i) => {
    if (i === 0) return "Start";
    const n = Math.ceil(i / 2);
    return `${n}${i % 2 === 1 ? "." : "..."} ${positions[i].san}`;
  };

  return (
    <Layout>
      <div className="mx-auto grid w-full max-w-5xl gap-4 px-4 py-6">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h1 className="text-xl font-semibold" data-testid="coach-game-title">
            {data.student_name}{data.opponent_name ? ` vs ${data.opponent_name}` : ""}
          </h1>
          <Link className="text-sm underline" to={`/academy/student/${studentId}`}>Back to {data.student_name}</Link>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="grid gap-3">
            <div className="aspect-square w-full max-w-[500px] mx-auto">
              <LichessBoard
                fen={lb.active ? lb.fen : here.fen}
                orientation={data.user_color === "black" ? "black" : "white"}
                viewOnly={lb.busy}
                onMove={(m) => lb.play(here.fen, m.from, m.to, m.promotion)}
                lastMove={lb.active ? lb.lastMove : (here.from ? [here.from, here.to] : null)}
                arrows={lb.active ? lb.arrows : []}
              />
            </div>
            <div className="flex items-center justify-center gap-2">
              <button className="rounded border p-2" onClick={() => setIndex(0)} disabled={index === 0}
                aria-label="Start"><ChevronsLeft className="w-4 h-4" /></button>
              <button className="rounded border p-2" onClick={() => setIndex(Math.max(0, index - 1))}
                disabled={index === 0} aria-label="Back" data-testid="coach-game-back">
                <ChevronLeft className="w-4 h-4" /></button>
              <span className="min-w-[100px] text-center text-sm text-muted-foreground">{moveLabel(index)}</span>
              <button className="rounded border p-2" onClick={() => setIndex(Math.min(last, index + 1))}
                disabled={index >= last} aria-label="Forward" data-testid="coach-game-forward">
                <ChevronRight className="w-4 h-4" /></button>
              <button className="rounded border p-2" onClick={() => setIndex(last)} disabled={index >= last}
                aria-label="End"><ChevronsRight className="w-4 h-4" /></button>
            </div>
            {lb.active ? <LineBoardPanel lb={lb} gameFen={here.fen} /> : <LineBoardHint />}
          </div>
          <div className="rounded-2xl border bg-card p-4">
            <p className="mb-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">Moves</p>
            <ol className="flex flex-wrap gap-x-2 gap-y-1 font-mono text-sm" data-testid="coach-game-moves">
              {positions.slice(1).map((p, i) => (
                <li key={i}>
                  <button
                    className={`rounded px-1 ${index === i + 1 ? "bg-foreground text-background" : "hover:bg-muted"}`}
                    onClick={() => setIndex(i + 1)}
                  >
                    {i % 2 === 0 ? `${i / 2 + 1}. ` : ""}{p.san}
                  </button>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </div>
    </Layout>
  );
}
