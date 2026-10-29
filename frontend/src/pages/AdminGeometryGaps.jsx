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

// What the board decided about Claude's reason, in the words the page uses.
// "not probeable" is NOT a refutation: it means the only thing that could be
// scored was the null move, so nothing about the reason itself was tested.
const JUDGE_LABEL = {
  confirmed: "confirmed by the board",
  refuted: "refuted by the board",
  not_probeable: "could not be put to the board",
  cannot_test: "nothing to test",
};

// One probe's numbers, in the engine's own units. A relation shows the two
// groups the judge compared; a placement or a pass shows what it recovered.
const probeNumbers = (p) => {
  if (!p) return "";
  if (p.kind === "relation") {
    const top = (xs) => (Array.isArray(xs) ? xs : [])
      .map((x) => (Array.isArray(x) ? x[0] : x))
      .sort((a, b) => b - a)
      .slice(0, 3)
      .map((n) => (n > 0 ? `+${n}` : `${n}`))
      .join(" ");
    return `break ${top(p.break) || "—"} · keep ${top(p.keep) || "—"}`;
  }
  if (p.kind === "placement" || p.kind === "pass") {
    if (typeof p.recovers !== "number") return p.why || "";
    const share = typeof p.share === "number" && Math.abs(p.share) <= 1000 ? ` (${p.share}%)` : "";
    return `recovers ${p.recovers > 0 ? "+" : ""}${p.recovers} of ${p.cost ?? "?"}${share}`;
  }
  return "";
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
  // Fourth queue. Mohit, 2026-10-29: "add a section on claude reason for
  // those positions too, so I can verify them right there." `judge` filters
  // by what the board said about the reason.
  const [judge, setJudge] = useState("");
  // Play your own move and ask the engine what it answers. Mohit, 2026-09-30:
  // "if I play a move on the board, can you give me stockfish response for
  // that move, so I really know why the move I play doesn't work?" The two
  // stored lines only cover the move played and the move the engine wanted;
  // the question a reviewer actually has is usually about a third move.
  const [probeFen, setProbeFen] = useState(null);
  const [probeMoves, setProbeMoves] = useState([]);
  const [probe, setProbe] = useState(null);
  const [probing, setProbing] = useState(false);
  const [probeError, setProbeError] = useState("");

  const loadResults = useCallback(async () => {
    try {
      const path =
        mode === "why"
          ? "/admin/geometry-gaps/no-why/results"
          : mode === "claude"
          ? "/admin/geometry-gaps/claude-reasons/results"
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
          : mode === "claude"
          ? `${API}/admin/geometry-gaps/claude-reasons/next${
              judge ? `?judge=${encodeURIComponent(judge)}` : ""
            }`
          : mode === "unexplained"
          ? `${API}/admin/geometry-gaps/unexplained/next${
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
            : mode === "unexplained"
            ? "Every blunder has an explanation now. Nothing left."
            : mode === "claude"
            ? "Every reason in this set has been ruled on."
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
  }, [cluster, mode, side, judge, loadResults]);

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

  // The third queue asks a different question -- "what IS the lesson" -- so
  // it posts a lesson, not a why, and "there is no lesson here" is a real
  // answer rather than a skip.
  const submitLesson = async (action, reason) => {
    if (!item || saving) return;
    if (action === "lesson" && !why.trim()) return;
    setSaving(true);
    try {
      await fetch(`${API}/admin/geometry-gaps/unexplained`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ ...item, action, reason, lesson: why.trim() }),
      });
      await load();
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setSaving(false);
    }
  };

  const submitWhy = async (action, reason) => {
    if (!item || saving) return;
    if (action === "authored" && !why.trim()) return;
    setSaving(true);
    try {
      await fetch(`${API}/admin/geometry-gaps/no-why`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ ...item, action, reason, why: why.trim() }),
      });
      await load();
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setSaving(false);
    }
  };

  // The fourth queue records whether a human agrees with the reason the board
  // confirmed. The note is the reviewer's own reason, when it differs.
  const submitClaude = async (verdict) => {
    if (!item || saving) return;
    setSaving(true);
    try {
      await fetch(`${API}/admin/geometry-gaps/claude-reasons`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ key: item.key, verdict, note: why.trim() }),
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

  const clearProbe = useCallback(() => {
    setProbeFen(null);
    setProbeMoves([]);
    setProbe(null);
    setProbeError("");
  }, []);

  const step = (which, index) => {
    clearProbe();
    setLine(which);
    setPly(index + 1);
  };

  // Ask the engine what it answers. `/analyze-position` is cached server side,
  // so walking a line back and forth is cheap after the first look.
  const askEngine = useCallback(async (fen) => {
    setProbing(true);
    setProbeError("");
    try {
      const res = await fetch(`${API}/analyze-position`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fen, depth: 18 }),
      });
      if (!res.ok) throw new Error(`engine returned ${res.status}`);
      const data = await res.json();
      setProbe({
        cp: data?.evaluation?.centipawns ?? null,
        mate: data?.evaluation?.mate_in ?? null,
        bestSan: data?.best_move?.san || null,
        pv: Array.isArray(data?.pv) ? data.pv : [],
        depth: data?.depth ?? null,
      });
    } catch (e) {
      setProbe(null);
      setProbeError("Could not reach the engine. Try that move again.");
    } finally {
      setProbing(false);
    }
  }, []);

  const handleProbeMove = useCallback((move) => {
    if (!move?.fen) return;
    // `line` and `ply` are deliberately left alone. probeFen already wins on
    // the board, and keeping them means the line buttons still show where the
    // reviewer branched off -- which is the thing they are trying to
    // understand when they start playing moves of their own.
    setProbeFen(move.fen);
    setProbeMoves((prev) => [...prev, { san: move.san, fen: move.fen }]);
    askEngine(move.fen);
  }, [askEngine]);

  // A fresh position is a fresh question.
  useEffect(() => { clearProbe(); }, [item?.key, clearProbe]);

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
              : mode === "claude"
              ? "Claude's reason, judged by the board"
              : "Mistakes the board cannot explain yet"}
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {mode === "why"
              ? "Each of these is a real mistake whose caption never explains itself. Write the missing sentence, or say the move needs no coaching. 697 of 5,683 across 500 games."
              : mode === "claude"
              ? "The 61 moves out of 320 where the why button had nothing to say. For each: the reason Claude would give, and what happened when that reason was tested on the board. Say whether you agree."
              : "Click any move to play the line out on the board. The punishment line after the mistake is usually where the real lesson is."}
          </p>
        </header>

        <div className="mb-4 flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded border p-0.5">
            {[
              ["gaps", "Undrawable"],
              ["why", "Missing the why"],
              // The residue: blunders the engine's line cannot explain and
              // no board family covers. 69 of 2,383 flagged moves over 100
              // games. Mohit 2026-10-10: "we already have geometrty-gaps
              // page, we shuld hae put in there ... may bea seperat tab".
              ["unexplained", "No explanation"],
              // Claude's reason for each silent position, with the board's
              // verdict on it. Mohit 2026-10-29: "so I can verify them
              // right there."
              ["claude", "Claude's reasons"],
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
          ) : mode === "claude" ? (
            <select
              className="rounded border bg-background px-2 py-1 text-sm"
              value={judge}
              onChange={(e) => setJudge(e.target.value)}
            >
              <option value="">Every verdict</option>
              {Object.entries(JUDGE_LABEL).map(([key, label]) => (
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
                fen={probeFen || view.fen}
                orientation={item.side_to_move}
                arrows={probeFen ? [] : arrows}
                onMove={handleProbeMove}
              />
              {/* The hint stays put. An earlier version swapped it for the
                  Back button as soon as a line was stepped, so the affordance
                  vanished exactly when a reviewer most wants it -- Mohit,
                  2026-09-30: "this stops working when we start clicking the
                  line". Dragging worked the whole time; nothing said so. */}
              <p className="mt-2 text-xs text-muted-foreground">
                Drag a piece to try a move from this position and see what the
                engine answers. That works here, part-way down a line, or after
                your own moves.
              </p>
              {line || probeFen ? (
                <button
                  type="button"
                  onClick={() => {
                    setLine(null);
                    setPly(0);
                    clearProbe();
                  }}
                  className="mt-1 inline-flex items-center gap-1 text-xs text-muted-foreground hover:underline"
                >
                  <RotateCcw className="h-3 w-3" /> Back to the position
                </button>
              ) : null}
              {probeFen ? (
                <div className="mt-3 rounded-lg border p-3 text-sm">
                  <p className="text-xs text-muted-foreground">
                    You played{" "}
                    <span className="font-mono text-foreground">
                      {probeMoves.map((m) => m.san).join(" ")}
                    </span>
                  </p>
                  {probing ? (
                    <p className="mt-2 flex items-center gap-2 text-muted-foreground">
                      <Loader2 className="h-3 w-3 animate-spin" /> Asking the engine
                    </p>
                  ) : probeError ? (
                    <p className="mt-2 text-muted-foreground">{probeError}</p>
                  ) : probe ? (
                    <div className="mt-2 space-y-1">
                      <p>
                        <span className="text-muted-foreground">Engine answers</span>{" "}
                        <strong className="font-mono">{probe.bestSan || "—"}</strong>
                      </p>
                      <p>
                        <span className="text-muted-foreground">Position is now</span>{" "}
                        <strong className="font-mono">
                          {probe.mate != null
                            ? `mate in ${Math.abs(probe.mate)}`
                            : probe.cp == null
                              ? "—"
                              : `${probe.cp > 0 ? "+" : ""}${(probe.cp / 100).toFixed(2)}`}
                        </strong>
                        <span className="text-muted-foreground">
                          {" "}(from White&rsquo;s side)
                        </span>
                      </p>
                      {probe.pv?.length ? (
                        <p className="font-mono text-xs text-muted-foreground">
                          {probe.pv.slice(0, 10).join(" ")}
                        </p>
                      ) : null}
                    </div>
                  ) : null}
                </div>
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
                    {CLUSTER_LABEL[item.cluster] || item.cluster || item.bucket}
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

              {mode === "claude" ? (
                <>
                  <div
                    className="rounded border border-violet-500/50 bg-violet-500/5 p-3"
                    data-testid="claude-reason"
                  >
                    <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
                      Claude&rsquo;s reason
                      {item.bucket ? ` · ${item.bucket}` : ""}
                    </div>
                    <p className="mt-1 text-sm">{item.reason}</p>
                    <p className="mt-1 text-[11px] text-muted-foreground">
                      The board says:{" "}
                      <strong className="text-foreground">
                        {JUDGE_LABEL[item.judge_overall] || item.judge_overall || "?"}
                      </strong>
                      {typeof item.cp_loss === "number"
                        ? ` · ${item.cp_loss} cp on a fresh depth-18 search`
                        : ""}
                      {item.grade_fresh ? ` · ${item.grade_fresh}` : ""}
                    </p>
                  </div>

                  {Array.isArray(item.probes) && item.probes.length ? (
                    <div className="rounded-lg border p-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        Put to the board
                      </p>
                      <table className="mt-2 w-full text-sm">
                        <tbody>
                          {item.probes.map((p, i) => (
                            <tr key={`${i}-${p.label}`} className="border-t align-top">
                              <td className="py-1 pr-3">
                                {p.label}
                                <div className="text-[11px] text-muted-foreground">{p.kind}</div>
                              </td>
                              <td className="py-1 pr-3 font-mono text-xs text-muted-foreground">
                                {probeNumbers(p)}
                              </td>
                              <td className="py-1 text-xs whitespace-nowrap">{p.verdict}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      <p className="mt-2 text-[11px] text-muted-foreground">
                        Numbers are centipawns recovered when that one thing is
                        changed on the board. A relation shows squares that break
                        it against squares that keep it; if both recover the same,
                        the relation was not the cause.
                      </p>
                    </div>
                  ) : null}

                  <div>
                    <label className="text-sm font-medium" htmlFor="gap-claude-note">
                      Your reason, if it differs
                    </label>
                    <textarea
                      id="gap-claude-note"
                      className="mt-1 w-full rounded border bg-background p-2 text-sm"
                      rows={3}
                      value={why}
                      onChange={(e) => setWhy(e.target.value)}
                      placeholder="e.g. It is really about the bishop pair, not the square."
                    />
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <Button onClick={() => submitClaude("agree")} disabled={saving}>
                      Agree
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => submitClaude("disagree")}
                      disabled={saving}
                    >
                      Disagree
                    </Button>
                    <Button
                      variant="ghost"
                      onClick={() => submitClaude("unsure")}
                      disabled={saving}
                    >
                      Not sure
                    </Button>
                    {results && typeof results.in_set === "number" ? (
                      <span className="self-center text-xs text-muted-foreground">
                        {results.total} of {results.in_set} ruled
                      </span>
                    ) : null}
                  </div>
                </>
              ) : mode === "unexplained" ? (
                <>
                  <div className="rounded border border-sky-500/50 bg-sky-500/5 p-3">
                    <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
                      Nothing can explain this one
                    </div>
                    <p className="mt-1 text-sm">{item.question}</p>
                    <p className="mt-1 text-[11px] text-muted-foreground">
                      {item.side === "opponent" ? "Opponent" : "Player"} move
                      {typeof item.cp_loss === "number"
                        ? ` · ${item.cp_loss} cp`
                        : ""}
                      {typeof item.material_change_in_line === "number"
                        ? ` · material in the line ${item.material_change_in_line}`
                        : ""}
                    </p>
                  </div>

                  <div>
                    <label className="text-sm font-medium" htmlFor="gap-lesson">
                      What is the lesson here?
                    </label>
                    <textarea
                      id="gap-lesson"
                      className="mt-1 w-full rounded border bg-background p-2 text-sm"
                      rows={4}
                      value={why}
                      onChange={(e) => setWhy(e.target.value)}
                      placeholder="e.g. The knight had no way back into the game from a4."
                    />
                    <p className="mt-1 text-[11px] text-muted-foreground">
                      Very easy English, short sentences. If there is no
                      lesson a player could use, say so with the button —
                      that is a real answer and it tells us a family will
                      never cover this card.
                    </p>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={saving || !why.trim()}
                      onClick={() => submitLesson("lesson")}
                      className="rounded bg-foreground px-3 py-1.5 text-sm text-background disabled:opacity-40"
                    >
                      Save the lesson
                    </button>
                    <button
                      type="button"
                      disabled={saving}
                      onClick={() => submitLesson("no_lesson")}
                      className="rounded border px-3 py-1.5 text-sm disabled:opacity-40"
                    >
                      No lesson here — just a worse position
                    </button>
                    {[
                      ["unsure", "Skip — unsure"],
                      ["card_looks_wrong", "Skip — card looks wrong"],
                      ["later", "Skip — later"],
                    ].map(([reasonKey, label]) => (
                      <button
                        key={reasonKey}
                        type="button"
                        disabled={saving}
                        onClick={() => submitLesson("skip", reasonKey)}
                        className="rounded border px-3 py-1.5 text-xs text-muted-foreground disabled:opacity-40"
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </>
              ) : mode === "why" ? (
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
                    {/* One "Skip" button was unreadable -- Mohit left 4 of
                        them and there is no way to tell "I don't know" from
                        "this card is broken". Only "later" comes back. */}
                    {[
                      ["unsure", "Not sure"],
                      ["card_looks_wrong", "Card looks wrong"],
                      ["later", "Later"],
                    ].map(([reasonKey, label]) => (
                      <Button
                        key={reasonKey}
                        variant="ghost"
                        onClick={() => submitWhy("skip", reasonKey)}
                        disabled={saving}
                      >
                        {label}
                      </Button>
                    ))}
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
