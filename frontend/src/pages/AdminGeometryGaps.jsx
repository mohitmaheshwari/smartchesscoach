/**
 * AdminGeometryGaps - the mistakes the board cannot explain yet.
 *
 * Mohit 2026-09-17: "if you find any puzzles you don't [know] the answer for
 * in arrow and captions, send them to me and I will tell you if it is
 * buildable."
 *
 * Two pictures ship today - a check that adds a second attacker, and what a
 * blunder gave away - and together they cover 58.3% of user mistakes, up from
 * 0%. Everything else lands here instead of being guessed at, because drawing
 * an arrow on a position with no tactical shape is how the clutter started.
 *
 * Both engine lines are playable on the board, because the punishment line is
 * usually where the lesson actually lives. Mohit, on a position whose caption
 * could only say Qxd6 was worse than cxd6: "the punishment line tells us the
 * problem that we are missing." The line answers it - 24.Nc4 hits the queen on
 * d6 with tempo - and that is a rule you can carry to the next game.
 *
 * The verdict is a human one. This page shows the position and records what
 * Mohit says about it; it never guesses one.
 */
import { useState, useEffect, useCallback, useMemo } from "react";
import { Chess } from "chess.js";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import LichessBoard from "@/components/LichessBoard";
import { Loader2, RefreshCw, Copy, RotateCcw } from "lucide-react";

const CLUSTER_LABEL = {
  quiet_positional_move: "Quiet positional move",
  best_move_capture_not_priceable: "Best move was a capture we cannot price",
  already_decided: "Position already decided",
  played_capture_not_punished: "Played a capture that was not punished",
  best_move_checks_wins_nothing: "Best move checks, wins nothing",
  best_move_is_mate: "Best move is mate",
};

const sanToArrow = (fen, san, color) => {
  if (!fen || !san) return null;
  try {
    const game = new Chess(fen);
    const move = game.move(san, { sloppy: true });
    return move ? [move.from, move.to, color] : null;
  } catch {
    return null;
  }
};

export default function AdminGeometryGaps() {
  const [item, setItem] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [results, setResults] = useState(null);
  const [cluster, setCluster] = useState("");
  const [copied, setCopied] = useState(false);
  // Which line is being walked, and how far into it.
  const [line, setLine] = useState(null);
  const [ply, setPly] = useState(0);
  const [denied, setDenied] = useState(false);

  const loadResults = useCallback(async () => {
    try {
      const r = await fetch(`${API}/admin/geometry-gaps/results`, {
        credentials: "include",
      });
      if (r.ok) setResults(await r.json());
    } catch {
      /* the tally is a nicety; never block judging on it */
    }
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    setNotes("");
    setLine(null);
    setPly(0);
    setDenied(false);
    try {
      const qs = cluster ? `?cluster=${encodeURIComponent(cluster)}` : "";
      const res = await fetch(`${API}/admin/geometry-gaps/next${qs}`, {
        credentials: "include",
      });
      if (res.status === 403) {
        // Without this the page renders its shell and then sits empty, which
        // is the blank-screen failure twice over. Say so instead.
        setItem(null);
        setDenied(true);
        setError("");
      } else if (res.status === 404) {
        setItem(null);
        setError("Nothing left to rule on in this cluster.");
      } else if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      } else {
        setItem(await res.json());
      }
    } catch (e) {
      setItem(null);
      setError(String(e.message || e));
    } finally {
      setLoading(false);
      loadResults();
    }
  }, [cluster, loadResults]);

  useEffect(() => {
    load();
  }, [load]);

  const rule = async (verdict) => {
    if (!item || saving) return;
    setSaving(true);
    try {
      await fetch(`${API}/admin/geometry-gaps`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ ...item, verdict, notes }),
      });
      await load();
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setSaving(false);
    }
  };

  // A line is the move itself followed by the engine's continuation.
  const movesFor = useCallback(
    (which) => {
      if (!item) return [];
      return which === "played"
        ? [item.played_san, ...(item.pv_after_played || [])]
        : [item.best_san, ...(item.pv_after_best || [])];
    },
    [item]
  );

  // Replay from the original FEN every time rather than mutating a board we
  // keep around: a single illegal SAN then truncates the line instead of
  // corrupting every later position.
  const view = useMemo(() => {
    const base = { fen: item?.fen || null, arrow: null };
    if (!item || !line || ply < 1) return base;
    try {
      const game = new Chess(item.fen);
      let last = null;
      for (const san of movesFor(line).slice(0, ply)) {
        const made = game.move(san, { sloppy: true });
        if (!made) break;
        last = made;
      }
      return {
        fen: game.fen(),
        arrow: last
          ? [last.from, last.to, line === "played" ? "red" : "green"]
          : null,
      };
    } catch {
      return base;
    }
  }, [item, line, ply, movesFor]);

  const step = (which, index) => {
    setLine(which);
    setPly(index + 1);
  };

  const arrows = useMemo(() => {
    if (!item) return [];
    if (view.arrow) return [view.arrow];
    return [
      sanToArrow(item.fen, item.played_san, "red"),
      sanToArrow(item.fen, item.best_san, "green"),
    ].filter(Boolean);
  }, [item, view]);

  const renderLine = (which, label, colorClass) => {
    const moves = movesFor(which);
    if (!moves.length) return null;
    // The position is mid-game, so number from the real move number and keep
    // Black-to-move lines reading "23...Qxd6" rather than a fake "1.".
    const startNumber = item.move_number || 1;
    const blackToMove = item.side_to_move === "black";
    return (
      <div className="rounded-lg border p-3">
        <p className={`text-xs font-semibold uppercase tracking-wide ${colorClass}`}>
          {label}
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-1">
          {moves.map((san, i) => {
            const whiteMove = blackToMove ? i % 2 === 1 : i % 2 === 0;
            const number = startNumber + Math.floor((blackToMove ? i + 1 : i) / 2);
            const active = line === which && ply === i + 1;
            return (
              <span key={`${which}-${i}-${san}`} className="flex items-center">
                {whiteMove ? (
                  <span className="mr-1 text-xs text-muted-foreground">
                    {number}.
                  </span>
                ) : i === 0 ? (
                  <span className="mr-1 text-xs text-muted-foreground">
                    {number}...
                  </span>
                ) : null}
                <button
                  type="button"
                  onClick={() => step(which, i)}
                  className={`rounded px-1.5 py-0.5 font-mono text-sm hover:bg-muted ${
                    active ? "bg-foreground text-background" : ""
                  }`}
                >
                  {san}
                </button>
              </span>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <Layout>
      <div className="mx-auto w-full max-w-[1100px] px-4 py-8">
        <header className="mb-6">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">
            Admin · geometry gaps
          </p>
          <h1 className="text-2xl font-semibold">
            Mistakes the board cannot explain yet
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Click any move to play the line out on the board. The punishment
            line after the mistake is usually where the real lesson is.
          </p>
        </header>

        <div className="mb-4 flex flex-wrap items-center gap-2">
          <select
            className="rounded border bg-background px-2 py-1 text-sm"
            value={cluster}
            onChange={(e) => setCluster(e.target.value)}
          >
            <option value="">All clusters</option>
            {Object.entries(CLUSTER_LABEL).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
          <Button variant="outline" size="sm" onClick={load} disabled={loading}>
            <RefreshCw className="mr-1 h-3 w-3" /> Skip
          </Button>
          {results ? (
            <span className="text-xs text-muted-foreground">
              {results.total} ruled so far
            </span>
          ) : null}
        </div>

        {loading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Finding a position...
          </div>
        ) : denied ? (
          <div className="rounded-lg border p-6" data-testid="geometry-gaps-denied">
            <p className="font-medium">You do not have access to this review queue.</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Ask Mohit to add your account, then reload this page.
            </p>
          </div>
        ) : error && !item ? (
          <p className="text-sm text-muted-foreground">{error}</p>
        ) : item ? (
          <div className="grid gap-6 md:grid-cols-[minmax(0,420px)_1fr]">
            <div>
              <LichessBoard
                fen={view.fen}
                orientation={item.side_to_move}
                arrows={arrows}
              />
              {line ? (
                <button
                  type="button"
                  onClick={() => {
                    setLine(null);
                    setPly(0);
                  }}
                  className="mt-2 inline-flex items-center gap-1 text-xs text-muted-foreground hover:underline"
                >
                  <RotateCcw className="h-3 w-3" /> Back to the position
                </button>
              ) : null}
            </div>
            <div className="space-y-4">
              <div className="rounded-lg border p-4">
                <p className="text-sm">
                  <span className="text-muted-foreground">Played</span>{" "}
                  <strong className="text-red-600">{item.played_san}</strong>
                  {"  ·  "}
                  <span className="text-muted-foreground">
                    Engine preferred
                  </span>{" "}
                  <strong className="text-green-600">{item.best_san}</strong>
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  move {item.move_number} · -{item.cp_loss}cp ·{" "}
                  {item.side_to_move} to move
                </p>
                <p className="mt-2 text-sm">
                  <span className="rounded bg-amber-100 px-2 py-0.5 text-amber-900">
                    {CLUSTER_LABEL[item.cluster] || item.cluster}
                  </span>
                </p>
                <button
                  type="button"
                  className="mt-3 inline-flex items-center gap-1 text-xs text-muted-foreground hover:underline"
                  onClick={() => {
                    navigator.clipboard.writeText(item.fen);
                    setCopied(true);
                    setTimeout(() => setCopied(false), 1200);
                  }}
                >
                  <Copy className="h-3 w-3" /> {copied ? "Copied" : "Copy FEN"}
                </button>
                <p className="mt-2 break-all font-mono text-[11px] text-muted-foreground">
                  {item.fen}
                </p>
              </div>

              {renderLine(
                "played",
                "What happened after the mistake",
                "text-red-600"
              )}
              {renderLine("best", "What the engine wanted", "text-green-600")}

              <div>
                <label className="text-sm font-medium" htmlFor="gap-notes">
                  What should the arrows show here?
                </label>
                <textarea
                  id="gap-notes"
                  className="mt-1 w-full rounded border bg-background p-2 text-sm"
                  rows={4}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="e.g. the knight hits the queen with tempo - draw a5 to the queen's square"
                />
              </div>

              <div className="flex flex-wrap gap-2">
                <Button onClick={() => rule("buildable")} disabled={saving}>
                  Buildable
                </Button>
                <Button
                  variant="outline"
                  onClick={() => rule("not_buildable")}
                  disabled={saving}
                >
                  Not buildable
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => rule("unsure")}
                  disabled={saving}
                >
                  Unsure
                </Button>
              </div>
            </div>
          </div>
        ) : null}

        {results && Object.keys(results.by_cluster || {}).length ? (
          <section className="mt-10">
            <h2 className="text-sm font-semibold">Ruled so far</h2>
            <table className="mt-2 w-full text-sm">
              <tbody>
                {Object.entries(results.by_cluster).map(([key, counts]) => (
                  <tr key={key} className="border-t">
                    <td className="py-1 pr-4">{CLUSTER_LABEL[key] || key}</td>
                    <td className="py-1 text-muted-foreground">
                      {Object.entries(counts)
                        .map(([v, n]) => `${v}: ${n}`)
                        .join("  ·  ")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        ) : null}
      </div>
    </Layout>
  );
}
