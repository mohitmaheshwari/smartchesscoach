/**
 * AdminPositionalReasons — capture a coach's reason for why the good move
 * is good.
 *
 * The machine can check a positional idea and count how often it separates
 * the played move from the best one across the corpus. It cannot reliably
 * invent the idea: of five predicates written in one pass, one fired zero
 * times in 46,655 positions, and there was no way to know which beforehand.
 *
 * So this collects the half the machine is bad at. One position at a time,
 * with the move played and the move that was best, and a box to say why in
 * plain English. Each reason becomes a candidate predicate, which is then
 * measured against the whole corpus before it can reach a user.
 *
 * Positions no existing predicate explains are served first — the rest
 * would only confirm what we already detect.
 *
 * Admin-only; the backend enforces require_admin on every route.
 */
import { useState, useEffect, useCallback } from "react";
import { Chess } from "chess.js";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import LichessBoard from "@/components/LichessBoard";
import { Loader2, SkipForward, Check, RefreshCw } from "lucide-react";

// Resolve SAN on a FEN into an arrow tuple the board understands.
const sanToArrow = (fen, san, color) => {
  if (!fen || !san) return null;
  try {
    const game = new Chess(fen);
    const move = game.move(san, { sloppy: true });
    if (!move) return null;
    return [move.from, move.to, color];
  } catch {
    return null;
  }
};

export default function AdminPositionalReasons() {
  const [position, setPosition] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reason, setReason] = useState("");
  const [label, setLabel] = useState("");
  const [saving, setSaving] = useState(false);
  const [progress, setProgress] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    setReason("");
    setLabel("");
    try {
      const res = await fetch(`${API}/admin/positional-reasons/next`, {
        credentials: "include",
      });
      if (res.status === 404) {
        setPosition(null);
        setError("Queue is empty. Reseed it to continue.");
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setPosition(data);
      setProgress(data.progress || null);
    } catch (e) {
      setError(`Could not load a position: ${e.message}`);
      setPosition(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const submit = async () => {
    if (!position || !reason.trim()) return;
    setSaving(true);
    try {
      const res = await fetch(`${API}/admin/positional-reasons`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          fen: position.fen,
          reason: reason.trim(),
          concept_label: label.trim() || null,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setProgress({ answered: data.answered, total: data.total });
      await load();
    } catch (e) {
      setError(`Could not save: ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  const skip = async () => {
    if (!position) return;
    setSaving(true);
    try {
      await fetch(`${API}/admin/positional-reasons/skip`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ fen: position.fen }),
      });
      await load();
    } finally {
      setSaving(false);
    }
  };

  const arrows = position
    ? [
        sanToArrow(position.fen, position.best_san, "green"),
        sanToArrow(position.fen, position.played_san, "red"),
      ].filter(Boolean)
    : [];

  return (
    <Layout>
      <div className="mx-auto max-w-5xl px-4 py-6">
        <div className="mb-5 flex items-end justify-between gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
              Positional reasons
            </p>
            <h1 className="text-2xl font-semibold">Why is the good move good?</h1>
            <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
              Green is the engine&apos;s move, red is what was played. Say in plain
              English what the green move achieves that the red one gives up. Each
              reason becomes a candidate detector and gets measured against every
              mistake in the corpus before it goes anywhere near a player.
            </p>
          </div>
          {progress && (
            <div className="shrink-0 text-right text-xs text-muted-foreground">
              <div className="text-lg font-semibold text-foreground">
                {progress.answered}
                <span className="text-muted-foreground">/{progress.total}</span>
              </div>
              answered
            </div>
          )}
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-amber-500/40 bg-amber-500/5 px-4 py-3 text-sm">
            {error}
            <Button variant="ghost" size="sm" className="ml-2" onClick={load}>
              <RefreshCw className="mr-1 h-3 w-3" /> Retry
            </Button>
          </div>
        )}

        {loading ? (
          <div className="flex items-center gap-2 py-16 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading a position…
          </div>
        ) : position ? (
          <div className="grid gap-6 md:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
            <div>
              <div className="aspect-square w-full">
                <LichessBoard
                  fen={position.fen}
                  orientation={position.side_to_move === "black" ? "black" : "white"}
                  interactive={false}
                  viewOnly={true}
                  arrows={arrows}
                />
              </div>
              <div className="mt-3 space-y-1 font-mono text-xs text-muted-foreground">
                <div>
                  <span className="text-red-400">played {position.played_san}</span>
                  {"  ·  "}
                  <span className="text-emerald-400">best {position.best_san}</span>
                </div>
                <div>
                  {position.side_to_move} to move · {position.men} pieces ·{" "}
                  {position.cp_loss}cp lost · {position.bucket}
                </div>
                {position.already_explained_by?.length > 0 && (
                  <div className="text-amber-400">
                    already detected by: {position.already_explained_by.join(", ")}
                  </div>
                )}
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">
                  Why is {position.best_san} good here?
                </label>
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  rows={7}
                  autoFocus
                  placeholder={`e.g. ${position.best_san} keeps the bishop in front of their passed pawn, so it can never run. ${position.played_san} gives that square up.`}
                  className="w-full resize-y rounded-lg border border-border bg-background/60 p-3 text-sm outline-none focus:border-primary/60"
                />
                <p className="mt-1 text-[11px] text-muted-foreground">
                  Say what changes on the board, not how big the advantage is. If
                  nothing positional explains it, write that — a &quot;this is just
                  a tactic&quot; is a useful answer.
                </p>
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">
                  Short name for the idea (optional)
                </label>
                <input
                  value={label}
                  onChange={(e) => setLabel(e.target.value)}
                  placeholder="blockade / king activity / rook behind passer"
                  className="w-full rounded-lg border border-border bg-background/60 px-3 py-2 text-sm outline-none focus:border-primary/60"
                />
                <p className="mt-1 text-[11px] text-muted-foreground">
                  Reuse the same name across positions and they group into one
                  candidate detector.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <Button onClick={submit} disabled={saving || !reason.trim()}>
                  {saving ? (
                    <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                  ) : (
                    <Check className="mr-1 h-4 w-4" />
                  )}
                  Save and next
                </Button>
                <Button variant="ghost" onClick={skip} disabled={saving}>
                  <SkipForward className="mr-1 h-4 w-4" />
                  Skip this one
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <p className="py-16 text-muted-foreground">Nothing to show.</p>
        )}
      </div>
    </Layout>
  );
}
