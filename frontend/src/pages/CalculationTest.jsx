/**
 * Showing your working.
 *
 * docs/calculation_test_scope.md.
 *
 * THE BOARD DOES NOT MOVE. That is the whole exercise. If the pieces follow
 * your clicks you are looking at the position, not calculating it, and the test
 * measures nothing it was built to measure. So the board stays on the starting
 * position and the line builds up as text beside it.
 *
 * Clicking rather than typing, because the audience is 600-1500 and asking
 * someone to write "Qxd3+" from memory tests their notation, not their chess.
 * Two clicks name a move; a hidden chess.js game validates it and produces the
 * notation.
 *
 * The line has no fixed length. Mohit, 2026-10-01: "calculation can be more
 * than one step too, right?" You stop when you are ready, and how deep the
 * position runs is shown, because stopping short and going wrong are different
 * failures.
 */

import { useState, useEffect, useMemo, useCallback } from "react";
import { Chess } from "chess.js";
import { API } from "@/App";
import Layout from "@/components/Layout";
import LichessBoard from "@/components/LichessBoard";
import { Button } from "@/components/ui/button";
import { Loader2, Undo2, RotateCcw } from "lucide-react";

const ENDINGS = [
  { key: "winning", label: "I am winning" },
  { key: "level", label: "About level" },
  { key: "losing", label: "I am worse" },
];

export default function CalculationTest() {
  const [positions, setPositions] = useState([]);
  const [index, setIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [reason, setReason] = useState("");
  const [moves, setMoves] = useState([]);          // SAN, alternating
  const [from, setFrom] = useState(null);
  const [ending, setEnding] = useState("");
  const [result, setResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const position = positions[index] || null;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API}/calculation-test/positions?count=3`, {
          credentials: "include",
        });
        const data = await res.json();
        if (cancelled) return;
        setPositions(data.positions || []);
        setReason(data.reason || "");
      } catch (e) {
        if (!cancelled) setError("Could not load a position.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // The hidden game. It follows the entered line so moves can be validated and
  // named, and it is never what the board shows.
  const shadow = useMemo(() => {
    if (!position?.fen) return null;
    const game = new Chess(position.fen);
    for (const san of moves) {
      try { game.move(san, { sloppy: true }); } catch { break; }
    }
    return game;
  }, [position?.fen, moves]);

  const sideToMove = useMemo(() => {
    if (!position?.fen) return null;
    const start = new Chess(position.fen).turn();
    return moves.length % 2 === 0 ? start : (start === "w" ? "b" : "w");
  }, [position?.fen, moves]);

  const startSide = useMemo(
    () => (position?.fen ? new Chess(position.fen).turn() : "w"),
    [position?.fen]
  );

  const onSquareClick = useCallback((square) => {
    if (!shadow || result) return;
    setError("");
    if (!from) { setFrom(square); return; }
    if (from === square) { setFrom(null); return; }
    try {
      const probe = new Chess(shadow.fen());
      const made = probe.move({ from, to: square, promotion: "q" });
      if (made) {
        setMoves((prev) => [...prev, made.san]);
        setFrom(null);
        return;
      }
    } catch { /* fall through */ }
    // Not a legal move from there — treat the click as a new starting square.
    setFrom(square);
  }, [from, shadow, result]);

  const submit = async () => {
    if (!position || moves.length === 0) return;
    setSubmitting(true);
    setError("");
    try {
      const res = await fetch(`${API}/calculation-test/submit`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          position_id: position.position_id,
          moves,
          verdict: ending || null,
        }),
      });
      if (!res.ok) throw new Error(String(res.status));
      setResult(await res.json());
    } catch (e) {
      setError("Could not check that line. Try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const nextPosition = () => {
    setIndex((i) => i + 1);
    setMoves([]); setFrom(null); setEnding(""); setResult(null); setError("");
  };

  if (loading) {
    return (
      <Layout>
        <div className="flex justify-center py-20">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      </Layout>
    );
  }

  if (!position) {
    return (
      <Layout>
        <div className="mx-auto max-w-xl px-4 py-16 text-center">
          <h1 className="text-xl font-semibold">Nothing to work out yet</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {reason || "Play a few more games and we will find you a position."}
          </p>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="mx-auto max-w-5xl px-4 py-8">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">
          Showing your working
        </p>
        <h1 className="mt-1 text-2xl font-semibold">
          Work out the line without moving the pieces
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          This is from one of your own games. You played{" "}
          <strong>{position.you_played}</strong> and there was something better.
          Click the squares to show your move, then their best answer, then
          yours — as far as you can see. The board will not move.
          {position.needs_half_moves
            ? ` This one runs about ${position.needs_half_moves} half-moves.`
            : ""}
        </p>

        <div className="mt-6 grid gap-6 md:grid-cols-[minmax(0,420px)_1fr]">
          <div>
            <LichessBoard
              fen={position.fen}
              orientation={startSide === "w" ? "white" : "black"}
              selectionOnly
              showCoordinates={false}
              onSquareClick={onSquareClick}
              highlights={from ? [from] : []}
            />
            {!result && (
              <p className="mt-2 text-xs text-muted-foreground">
                {from
                  ? `From ${from} — now click where it goes.`
                  : `Click the piece that moves. It is ${
                      sideToMove === startSide ? "your" : "their"
                    } turn in your line.`}
              </p>
            )}
          </div>

          <div className="space-y-4">
            <div className="rounded-lg border p-4">
              <p className="text-sm font-medium">Your line</p>
              {moves.length === 0 ? (
                <p className="mt-2 text-sm text-muted-foreground">
                  Nothing yet.
                </p>
              ) : (
                <ol className="mt-2 space-y-1 font-mono text-sm">
                  {moves.map((san, i) => (
                    <li key={`${san}-${i}`}>
                      <span className="mr-2 text-xs font-sans text-muted-foreground">
                        {i % 2 === 0 ? "you" : "them"}
                      </span>
                      {san}
                    </li>
                  ))}
                </ol>
              )}
              {!result && moves.length > 0 && (
                <div className="mt-3 flex gap-2">
                  <Button variant="outline" size="sm"
                          onClick={() => { setMoves((m) => m.slice(0, -1)); setFrom(null); }}>
                    <Undo2 className="mr-1 h-3 w-3" /> Take back
                  </Button>
                  <Button variant="ghost" size="sm"
                          onClick={() => { setMoves([]); setFrom(null); }}>
                    <RotateCcw className="mr-1 h-3 w-3" /> Start again
                  </Button>
                </div>
              )}
            </div>

            {!result && (
              <div className="rounded-lg border p-4">
                <p className="text-sm font-medium">And then?</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {ENDINGS.map((e) => (
                    <Button key={e.key} size="sm"
                            variant={ending === e.key ? "default" : "outline"}
                            onClick={() => setEnding(e.key)}>
                      {e.label}
                    </Button>
                  ))}
                </div>
                <Button className="mt-4" disabled={moves.length === 0 || submitting}
                        onClick={submit}>
                  {submitting ? (
                    <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Checking</>
                  ) : "Check my line"}
                </Button>
                {error && <p className="mt-2 text-sm text-muted-foreground">{error}</p>}
              </div>
            )}

            {result && <Verdict result={result} onNext={nextPosition}
                                hasNext={index + 1 < positions.length} />}
          </div>
        </div>
      </div>
    </Layout>
  );
}

function Verdict({ result, onNext, hasNext }) {
  const plies = result.plies || [];
  const broke = plies.find((p) => p.verdict && p.verdict !== "sound");
  // "Your line holds up until that move" is nonsense when the FIRST move is
  // the wrong one -- nothing held up.
  const brokeAtStart = broke && broke.ply === 1;
  const works = result.sound_continuation || [];
  return (
    <div className="rounded-lg border p-4" data-testid="verdict">
      <p className="text-sm font-medium">How that line held up</p>
      <ol className="mt-2 space-y-1 font-mono text-sm">
        {plies.map((p) => (
          <li key={p.ply} className={p.verdict === "sound" ? "" : "text-amber-700 dark:text-amber-400"}>
            <span className="mr-2 text-xs font-sans text-muted-foreground">{p.by}</span>
            {p.move}
            {p.verdict !== "sound" && p.best ? (
              <span className="ml-2 text-xs font-sans">— {p.best} was the move</span>
            ) : null}
          </li>
        ))}
      </ol>
      <p className="mt-3 text-sm">
        {brokeAtStart
          ? "That first move does not work here."
          : broke
            ? "Your line holds up to that point, then it goes wrong."
            : result.stopped_early
              ? "Everything you gave was right. There was more to see past where you stopped."
              : "That is the line."}
      </p>
      {works.length > 0 && (
        <div className="mt-3 rounded-md bg-muted/50 p-3">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            What works instead
          </p>
          <p className="mt-1 font-mono text-sm">{works.join("  ")}</p>
        </div>
      )}
      {result.judged_the_end && result.judged_the_end.right === false && (
        <p className="mt-1 text-sm text-muted-foreground">
          You read the end as {result.judged_the_end.said}; it is{" "}
          {result.judged_the_end.actually}.
        </p>
      )}
      {hasNext && (
        <Button className="mt-4" onClick={onNext}>Next position</Button>
      )}
    </div>
  );
}
