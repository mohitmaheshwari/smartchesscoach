/**
 * AdminReasonJudge — blind human judging of two model explanations.
 *
 * The first Fable-versus-Opus comparison had Opus grading Fable. The
 * mechanical claim checks ran against a real board so those stand, but
 * "is this reason true, and would it help a 900" was one model judging
 * another, which Mohit called out as unsound.
 *
 * So this puts a human in the loop, and shows both answers anonymously.
 * Which model sits in slot A is fixed by hashing the position, so it is
 * stable across reloads and cannot be learned. The models are revealed
 * only after the vote is stored.
 */
import { useState, useEffect, useCallback } from "react";
import { Chess } from "chess.js";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import LichessBoard from "@/components/LichessBoard";
import { Loader2, RefreshCw, Copy } from "lucide-react";

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

export default function AdminReasonJudge() {
  const [item, setItem] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notes, setNotes] = useState("");
  const [aTrue, setATrue] = useState(null);
  const [bTrue, setBTrue] = useState(null);
  const [reveal, setReveal] = useState(null);
  const [saving, setSaving] = useState(false);
  const [tally, setTally] = useState(null);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    setReveal(null);
    setNotes("");
    setATrue(null);
    setBTrue(null);
    try {
      const res = await fetch(`${API}/admin/reason-judge/next`, { credentials: "include" });
      if (res.status === 404) {
        setItem(null);
        setError("All positions judged. Results are below.");
      } else if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      } else {
        setItem(await res.json());
      }
      const r2 = await fetch(`${API}/admin/reason-judge/results`, { credentials: "include" });
      if (r2.ok) setTally(await r2.json());
    } catch (e) {
      setError(`Could not load: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const vote = async (better) => {
    if (!item) return;
    setSaving(true);
    try {
      const res = await fetch(`${API}/admin/reason-judge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          fen: item.fen,
          better,
          a_is_true: aTrue,
          b_is_true: bTrue,
          notes: notes.trim() || null,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setReveal(data.reveal);
    } catch (e) {
      setError(`Could not save: ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  const copyFen = async () => {
    if (!item) return;
    try {
      await navigator.clipboard.writeText(item.fen);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  const arrows = item
    ? [
        sanToArrow(item.fen, item.best_san, "green"),
        sanToArrow(item.fen, item.played_san, "red"),
      ].filter(Boolean)
    : [];

  const answerCard = (a, isTrue, setTrue) => (
    <div key={a.slot} className="rounded-xl border border-border bg-card/60 p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-semibold">
          Explanation {a.slot}
          {reveal && (
            <span className="ml-2 rounded bg-primary/15 px-2 py-0.5 text-[11px] font-normal text-primary">
              {reveal[a.slot]}
            </span>
          )}
        </span>
        <span className="text-[11px] text-muted-foreground">
          {a.concept_label} · {a.is_positional ? "positional" : "tactical"}
        </span>
      </div>
      <p className="text-sm leading-relaxed">{a.reason}</p>
      {a.checkable_claims?.length > 0 && (
        <ul className="mt-3 space-y-1 border-t border-border/60 pt-2 text-[12px] text-muted-foreground">
          {a.checkable_claims.map((c, i) => (
            <li key={i}>· {c}</li>
          ))}
        </ul>
      )}
      <div className="mt-3 flex items-center gap-2 text-xs">
        <span className="text-muted-foreground">Is this true of the board?</span>
        <Button
          size="sm"
          variant={isTrue === true ? "default" : "outline"}
          onClick={() => setTrue(true)}
        >
          True
        </Button>
        <Button
          size="sm"
          variant={isTrue === false ? "default" : "outline"}
          onClick={() => setTrue(false)}
        >
          False
        </Button>
      </div>
    </div>
  );

  return (
    <Layout>
      <div className="mx-auto max-w-6xl px-4 py-6">
        <div className="mb-5 flex items-end justify-between gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
              Blind judging
            </p>
            <h1 className="text-2xl font-semibold">Which explanation is right?</h1>
            <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
              Two models explained the same position. You cannot see which is
              which until you vote. Green is the engine&apos;s move, red is what
              was played. Judge whether each explanation is <em>true of this
              board</em> first, and which one you would rather show a 900-rated
              player second.
            </p>
          </div>
          {item?.progress && (
            <div className="shrink-0 text-right text-xs text-muted-foreground">
              <div className="text-lg font-semibold text-foreground">
                {item.progress.judged}
                <span className="text-muted-foreground">/{item.progress.total}</span>
              </div>
              judged
            </div>
          )}
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-amber-500/40 bg-amber-500/5 px-4 py-3 text-sm">
            {error}
            <Button variant="ghost" size="sm" className="ml-2" onClick={load}>
              <RefreshCw className="mr-1 h-3 w-3" /> Reload
            </Button>
          </div>
        )}

        {loading ? (
          <div className="flex items-center gap-2 py-16 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading…
          </div>
        ) : item ? (
          <div className="grid gap-6 lg:grid-cols-[minmax(0,340px)_minmax(0,1fr)]">
            <div>
              <div className="aspect-square w-full">
                <LichessBoard
                  fen={item.fen}
                  orientation={item.side_to_move === "black" ? "black" : "white"}
                  interactive={false}
                  viewOnly={true}
                  arrows={arrows}
                />
              </div>
              <div className="mt-3 space-y-1 font-mono text-xs text-muted-foreground">
                <div>
                  <span className="text-red-400">played {item.played_san}</span>
                  {"  ·  "}
                  <span className="text-emerald-400">best {item.best_san}</span>
                </div>
                <div>
                  {item.side_to_move} to move · {item.men} pieces · {item.cp_loss}cp ·{" "}
                  {item.bucket}
                </div>
              </div>
              <Button variant="outline" size="sm" className="mt-3" onClick={copyFen}>
                <Copy className="mr-1 h-3 w-3" />
                {copied ? "Copied" : "Copy FEN"}
              </Button>
            </div>

            <div className="space-y-4">
              <div className="grid gap-3 md:grid-cols-2">
                {item.answers.map((a) =>
                  a.slot === "A"
                    ? answerCard(a, aTrue, setATrue)
                    : answerCard(a, bTrue, setBTrue)
                )}
              </div>

              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                placeholder="Anything either explanation missed, or the reason you would actually give…"
                className="w-full resize-y rounded-lg border border-border bg-background/60 p-3 text-sm outline-none focus:border-primary/60"
              />

              {reveal ? (
                <div className="flex items-center gap-3">
                  <span className="text-sm text-muted-foreground">
                    A was <strong className="text-foreground">{reveal.A}</strong>, B was{" "}
                    <strong className="text-foreground">{reveal.B}</strong>.
                  </span>
                  <Button onClick={load}>Next position</Button>
                </div>
              ) : (
                <div className="flex flex-wrap items-center gap-2">
                  <Button onClick={() => vote("A")} disabled={saving}>
                    A is better
                  </Button>
                  <Button onClick={() => vote("B")} disabled={saving}>
                    B is better
                  </Button>
                  <Button variant="outline" onClick={() => vote("TIE")} disabled={saving}>
                    Equally good
                  </Button>
                  <Button variant="ghost" onClick={() => vote("NEITHER")} disabled={saving}>
                    Both wrong
                  </Button>
                </div>
              )}
            </div>
          </div>
        ) : null}

        {tally && tally.judged > 0 && (
          <div className="mt-8 rounded-xl border border-border bg-card/40 p-4">
            <p className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
              Your verdicts so far ({tally.judged})
            </p>
            <div className="flex flex-wrap gap-4 text-sm">
              {Object.entries(tally.wins || {}).map(([k, v]) => (
                <span key={k}>
                  <span className="font-semibold">{v}</span>{" "}
                  <span className="text-muted-foreground">{k}</span>
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
}
