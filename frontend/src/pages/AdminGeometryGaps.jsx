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
  const [copiedPrompt, setCopiedPrompt] = useState(false);
  // Which line is being walked, and how far into it.
  const [line, setLine] = useState(null);
  const [ply, setPly] = useState(0);
  const [denied, setDenied] = useState(false);
  // Two queues on one page. "gaps" asks "can we DRAW this?"; "why" asks
  // "write the sentence we are missing". Mohit, 2026-09-22: "add those
  // positions in geometry-gaps page so i or farhan can help you out" --
  // here because GEOMETRY_REVIEWER_EMAILS is the only gate Farhan holds.
  const [mode, setMode] = useState("gaps");
  const [side, setSide] = useState("");
  const [why, setWhy] = useState("");

  const loadResults = useCallback(async () => {
    try {
      const path =
        mode === "why"
          ? "/admin/geometry-gaps/no-why/results"
          : "/admin/geometry-gaps/results";
      const r = await fetch(`${API}${path}`, {
        credentials: "include",
      });
      if (r.ok) setResults(await r.json());
    } catch {
      /* the tally is a nicety; never block judging on it */
    }
  }, [mode]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    setNotes("");
    setWhy("");
    setLine(null);
    setPly(0);
    setDenied(false);
    try {
      const url =
        mode === "why"
          ? `${API}/admin/geometry-gaps/no-why/next${
              side ? `?side=${encodeURIComponent(side)}` : ""
            }`
          : `${API}/admin/geometry-gaps/next${
              cluster ? `?cluster=${encodeURIComponent(cluster)}` : ""
            }`;
      const res = await fetch(url, { credentials: "include" });
      if (res.status === 403) {
        // Without this the page renders its shell and then sits empty, which
        // is the blank-screen failure twice over. Say so instead.
        setItem(null);
        setDenied(true);
        setError("");
      } else if (res.status === 404) {
        setItem(null);
        setError(
          mode === "why"
            ? "Every caption in the corpus has a why. Nothing left."
            : "Nothing left to rule on in this cluster."
        );
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
  }, [cluster, mode, side, loadResults]);

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

  const submitWhy = async (action) => {
    if (!item || saving) return;
    if (action === "authored" && !why.trim()) return;
    setSaving(true);
    try {
      await fetch(`${API}/admin/geometry-gaps/no-why`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ ...item, action, why: why.trim() }),
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
      // best_san can be absent on a missing-why item (the V5 record does not
      // always carry one). An undefined SAN in the list renders a dead button
      // and truncates the replay, so drop it here rather than downstream.
      return (
        which === "played"
          ? [item.played_san, ...(item.pv_after_played || [])]
          : [item.best_san, ...(item.pv_after_best || [])]
      ).filter(Boolean);
    },
    [item]
  );

  // Everything Claude needs to answer "why was this worse", in one paste.
  // It carries the analyser's own fields -- cognitive_gap, threat, mate_info --
  // which the page had been holding back, so the answer is grounded in what we
  // already decided about the move rather than re-derived from the FEN.
  //
  // The severity bands are included verbatim so the reply uses OUR definition
  // of inaccuracy/mistake/blunder instead of its own.
  const claudePrompt = useCallback(() => {
    if (!item) return "";
    const line = (moves) => (moves && moves.length ? moves.join(" ") : "(none stored)");
    const ev = (v) => (v === null || v === undefined ? "?" : `${(v / 100).toFixed(2)}`);
    return [
      "You are coaching a 600-1500 rated chess player. Explain, in very simple",
      "English, why the move they played was worse than the engine's move.",
      "",
      `Position (FEN): ${item.fen}`,
      `${item.side_to_move || item.side || "unknown side"} to move, move ${item.move_number}`,
      "",
      `They played:   ${item.played_san}`,
      `Engine wants:  ${item.best_san}`,
      `Eval before ${ev(item.eval_before)} -> after ${ev(item.eval_after)} (white's point of view)`,
      `Cost of the move: ${item.cp_loss} centipawns`,
      item.cognitive_gap ? `Our analyser labelled the gap: ${item.cognitive_gap}` : null,
      item.critical_reason ? `Critical reason: ${item.critical_reason}` : null,
      item.threat ? `Threat noted: ${JSON.stringify(item.threat)}` : null,
      item.mate_info ? `Mate info: ${JSON.stringify(item.mate_info)}` : null,
      "",
      `Line after what they played: ${line(movesFor("played"))}`,
      `Line after the engine move:  ${line(movesFor("best"))}`,
      "",
      item.severity ? `We classified this as: ${item.severity}` : null,
      "",
      "Severity bands we use (by player rating):",
      "  under 1000: inaccuracy 150cp, mistake 300cp, blunder 300cp+",
      "  1000-1399:  inaccuracy 75cp,  mistake 200cp, blunder 200cp+",
      "  1400-1799:  inaccuracy 50cp,  mistake 150cp, blunder 150cp+",
      "  1800+:      inaccuracy 30cp,  mistake 100cp, blunder 100cp+",
      "",
      "Answer with:",
      "1. Severity, using the bands above (say which band you assumed). If we",
      "   already classified it above, say whether you agree and why.",
      "2. Why the played move is worse - the actual mechanism on the board,",
      "   not a restatement of the engine line. Name squares and pieces.",
      "3. Why the engine's move is better.",
      "4. One transferable lesson the player could use in another game.",
      "5. The board facts you used, so each claim can be checked.",
      "",
      "Rules: short sentences, common words, no chess jargon. Say whose move",
      "each move in a line is. Do not claim anything the position does not show.",
    ]
      .filter(Boolean)
      .join("\n");
  }, [item, movesFor]);

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
            {mode === "why"
              ? "Blunders that never say why"
              : "Mistakes the board cannot explain yet"}
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {mode === "why"
              ? "Each of these is a real mistake whose caption never explains itself. Write the missing sentence, or say the move needs no coaching. 697 of 5,683 across 500 games."
              : "Click any move to play the line out on the board. The punishment line after the mistake is usually where the real lesson is."}
          </p>
        </header>

        <div className="mb-4 flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded border p-0.5">
            {[
              ["gaps", "Undrawable"],
              ["why", "Missing the why"],
            ].map(([key, label]) => (
              <button
                key={key}
                type="button"
                onClick={() => setMode(key)}
                className={`rounded px-2.5 py-1 text-xs ${
                  mode === key
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          {mode === "gaps" ? (
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
          ) : (
            <select
              className="rounded border bg-background px-2 py-1 text-sm"
              value={side}
              onChange={(e) => setSide(e.target.value)}
            >
              <option value="">Both sides</option>
              <option value="user">Their own moves</option>
              <option value="opponent">Opponent moves (16.8% bare)</option>
            </select>
          )}
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
                <button
                  type="button"
                  className="mt-3 ml-3 inline-flex items-center gap-1 text-xs font-medium text-foreground hover:underline"
                  onClick={() => {
                    navigator.clipboard.writeText(claudePrompt());
                    setCopiedPrompt(true);
                    setTimeout(() => setCopiedPrompt(false), 1600);
                  }}
                >
                  <Copy className="h-3 w-3" />{" "}
                  {copiedPrompt ? "Prompt copied" : "Copy for Claude"}
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

              {mode === "why" ? (
                <>
                  <div className="rounded border border-amber-500/50 bg-amber-500/5 p-3">
                    <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
                      What we say today
                    </div>
                    <p className="mt-1 text-sm">{item.caption}</p>
                    <p className="mt-1 text-[11px] text-muted-foreground">
                      {item.side === "opponent" ? "Opponent" : "Player"} move ·{" "}
                      {item.severity}
                      {typeof item.cp_loss === "number"
                        ? ` · ${item.cp_loss} cp`
                        : ""}
                    </p>
                  </div>

                  <div>
                    <label className="text-sm font-medium" htmlFor="gap-why">
                      Why was this move bad? One or two short sentences.
                    </label>
                    <textarea
                      id="gap-why"
                      className="mt-1 w-full rounded border bg-background p-2 text-sm"
                      rows={4}
                      value={why}
                      onChange={(e) => setWhy(e.target.value)}
                      placeholder="e.g. It leaves the knight on d4 with nothing guarding it, and Qxd4 just takes it."
                    />
                    <p className="mt-1 text-[11px] text-muted-foreground">
                      Very easy English, short sentences. Say what the move
                      gives away, not what to play instead.
                    </p>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <Button
                      onClick={() => submitWhy("authored")}
                      disabled={saving || !why.trim()}
                    >
                      Save this why
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => submitWhy("no_why_needed")}
                      disabled={saving}
                    >
                      Not really a mistake
                    </Button>
                    <Button
                      variant="ghost"
                      onClick={() => submitWhy("skip")}
                      disabled={saving}
                    >
                      Skip
                    </Button>
                  </div>
                </>
              ) : (
                <>
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
                </>
              )}
            </div>
          </div>
        ) : null}

        {mode === "gaps" &&
        results &&
        Object.keys(results.by_cluster || {}).length ? (
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
