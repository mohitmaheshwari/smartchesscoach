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
 * The verdict is a human one. This page only shows the position and records
 * what Mohit says about it.
 */
import { useState, useEffect, useCallback } from "react";
import { Chess } from "chess.js";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import LichessBoard from "@/components/LichessBoard";
import { Loader2, RefreshCw, Copy } from "lucide-react";

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
    try {
      const qs = cluster ? `?cluster=${encodeURIComponent(cluster)}` : "";
      const res = await fetch(`${API}/admin/geometry-gaps/next${qs}`, {
        credentials: "include",
      });
      if (res.status === 404) {
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

  const arrows = item
    ? [
        sanToArrow(item.fen, item.played_san, "red"),
        sanToArrow(item.fen, item.best_san, "green"),
      ].filter(Boolean)
    : [];

  return (
    <Layout>
      <div className="mx-auto w-full max-w-[1040px] px-4 py-8">
        <header className="mb-6">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">
            Admin · geometry gaps
          </p>
          <h1 className="text-2xl font-semibold">
            Mistakes the board cannot explain yet
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Red is the move that was played. Green is the move the engine
            preferred. Nothing else is drawn, because nothing else is proven.
            Tell me whether a picture here is buildable.
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
        ) : error && !item ? (
          <p className="text-sm text-muted-foreground">{error}</p>
        ) : item ? (
          <div className="grid gap-6 md:grid-cols-[minmax(0,420px)_1fr]">
            <div>
              <LichessBoard
                fen={item.fen}
                orientation={item.side_to_move}
                arrows={arrows}
              />
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
                  placeholder="e.g. draw the line from the rook to the back rank, the king has no escape"
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
