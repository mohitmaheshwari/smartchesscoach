/**
 * Reply check — a sitting recorded move by move.
 *
 * Spec: docs/reply_check_page_scope.md
 *
 * He plays his move on the board; the page works out the notation. Nothing
 * about the position is shown until all six answers are recorded, and the
 * answer key is a separate request the server refuses until then — so it
 * cannot sit in the browser while he is deciding.
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Chess } from "chess.js";
import { Chessboard } from "react-chessboard";
import { toast } from "sonner";

import Layout from "@/components/Layout";
import { API } from "@/App";

const ASSESS = ["winning", "clearly better", "slightly better", "level", "worse", "losing"];

const REASONS = [
  ["followed_the_line", "I followed the forcing line to the end before choosing."],
  ["best_right_now", "I picked the move that looked strongest on this move."],
];

const REFLECT = [
  ["thought_piece_safe", "I thought my piece was safe"],
  ["thought_protected", "I thought it could not be taken"],
  ["chose_attack_over_safety", "I was trying to continue the attack"],
  ["missed_check", "I didn't see the check"],
  ["missed_capture", "I did not consider the full capture sequence"],
  ["ignored_forcing_sequence", "I stopped counting before the end"],
  ["played_fast", "I played it quickly"],
  ["none_of_these", "None of these"],
  ["not_sure", "Not sure"],
];

// Steps 0-5 are recorded before anything is revealed. 6 is the reveal.
const STEP = {
  RECOGNISE: 0, MOVE: 1, REPLY: 2, NOW: 3, AFTER: 4, REVISE: 5, REVEAL: 6,
};

function Pill({ tone = "muted", children }) {
  const tones = {
    good: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/40",
    bad: "bg-rose-500/15 text-rose-700 dark:text-rose-300 border-rose-500/40",
    pend: "bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/40",
    muted: "bg-slate-500/10 text-slate-600 dark:text-slate-300 border-slate-500/30",
  };
  return (
    <span className={`inline-block rounded-full border px-3 py-1 text-xs font-mono ${tones[tone]}`}>
      {children}
    </span>
  );
}

function Choices({ options, value, onPick, cols }) {
  return (
    <div className={`grid gap-2 ${cols || "grid-cols-2 sm:grid-cols-3"}`}>
      {options.map(([key, label]) => (
        <button
          key={key}
          type="button"
          onClick={() => onPick(key)}
          aria-pressed={value === key}
          className={`rounded-lg border px-3 py-2 text-left text-sm transition
            ${value === key
              ? "border-teal-500 bg-teal-500/10 font-medium"
              : "border-slate-300 dark:border-slate-700 hover:border-teal-500/60"}`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

export default function ReplyCheck({ user }) {
  const [packet, setPacket] = useState(null);
  const [done, setDone] = useState({});        // position_id -> derived
  const [idx, setIdx] = useState(0);
  const [step, setStep] = useState(STEP.RECOGNISE);
  const [ans, setAns] = useState({});
  const [evidence, setEvidence] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const item = packet?.items?.[idx] || null;

  // ---- load ----
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [p, r] = await Promise.all([
          fetch(`${API}/coach/reply-check/packet`, { credentials: "include" }),
          fetch(`${API}/coach/reply-check/responses`, { credentials: "include" }),
        ]);
        if (!p.ok) throw new Error((await p.json()).detail || "Could not load the positions.");
        const pj = await p.json();
        const rj = r.ok ? await r.json() : { responses: [] };
        if (!alive) return;
        const seen = {};
        (rj.responses || []).forEach((x) => { seen[x.position_id] = x.derived; });
        setPacket(pj);
        setDone(seen);
        const first = (pj.items || []).findIndex((it) => !seen[it.position_id]);
        setIdx(first < 0 ? (pj.items || []).length : first);
      } catch (e) {
        if (alive) setError(e.message);
      }
    })();
    return () => { alive = false; };
  }, []);

  // Reset per position.
  useEffect(() => {
    setStep(STEP.RECOGNISE);
    setAns({});
    setEvidence(null);
    setError("");
  }, [idx]);

  const orientation = item?.to_move === "black" ? "black" : "white";

  /** What the board shows. A move he has played stays on the board — it would
   *  be alarming to watch it snap back — so the position reflects whatever he
   *  has entered so far at this step. */
  const shownFen = useMemo(() => {
    if (!item) return "start";
    const play = (moves) => {
      try {
        const g = new Chess(item.fen);
        for (const m of moves) if (m && m !== "not sure") g.move(m);
        return g.fen();
      } catch { return item.fen; }
    };
    if (step === STEP.REVISE) return play([ans.revised_move]);
    if (step === STEP.REVEAL) return play([ans.revised_move || ans.intended_move]);
    if (step === STEP.MOVE) return play([ans.intended_move]);
    if (step >= STEP.REPLY) return play([ans.intended_move, ans.expected_reply]);
    return item.fen;
  }, [item, step, ans.intended_move, ans.expected_reply, ans.revised_move]);

  /** Draggable only while that step still needs a move. Once he has entered
   *  one, the board locks until he takes it back — otherwise a second drag
   *  would add a move rather than replace it. */
  const draggable =
    (step === STEP.MOVE && !ans.intended_move) ||
    (step === STEP.REPLY && !ans.expected_reply) ||
    (step === STEP.REVISE && !ans.revised_move);

  /** A drop is accepted only when it is legal. chess.js throws otherwise. */
  const onDrop = useCallback((from, to) => {
    if (!item) return false;
    const pickingReply = step === STEP.REPLY;
    const pickingMove = step === STEP.MOVE || step === STEP.REVISE;
    if (!pickingMove && !pickingReply) return false;
    let base;
    try {
      base = new Chess(item.fen);
      if (pickingReply) base.move(ans.intended_move);
    } catch { return false; }
    let mv;
    try {
      mv = base.move({ from, to, promotion: "q" });
    } catch { return false; }
    if (!mv) return false;
    if (pickingReply) setAns((a) => ({ ...a, expected_reply: mv.san }));
    else if (step === STEP.REVISE) setAns((a) => ({ ...a, revised_move: mv.san }));
    else setAns((a) => ({ ...a, intended_move: mv.san }));
    return true;
  }, [item, step, ans.intended_move]);

  async function record() {
    setBusy(true);
    setError("");
    try {
      const res = await fetch(`${API}/coach/reply-check/response`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ position_id: item.position_id, ...ans }),
      });
      const j = await res.json();
      if (!res.ok) throw new Error(j.detail || "Could not record that.");
      setDone((d) => ({ ...d, [item.position_id]: j.derived }));
      const ev = await fetch(
        `${API}/coach/reply-check/evidence/${encodeURIComponent(item.position_id)}`,
        { credentials: "include" });
      setEvidence(ev.ok ? await ev.json() : null);
      setStep(STEP.REVEAL);
    } catch (e) {
      setError(e.message);
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (error && !packet) {
    return <Layout user={user}><div className="mx-auto max-w-xl px-4 py-16 text-center">
      <p className="text-sm text-rose-600 dark:text-rose-400">{error}</p>
    </div></Layout>;
  }
  if (!packet) {
    return <Layout user={user}><div className="mx-auto max-w-xl px-4 py-16 text-center text-sm opacity-70">
      Loading the positions…
    </div></Layout>;
  }
  if (!item) {
    const rows = Object.values(done);
    const held = rows.filter((d) => d?.move_holds === true).length;
    const named = rows.filter((d) => d?.reply_names_the_capture === true).length;
    const pend = rows.filter((d) => d?.pending_verification).length;
    return <Layout user={user}>
      <div className="mx-auto max-w-xl px-4 py-16 text-center">
        <h1 className="text-2xl font-semibold">Recorded</h1>
        <p className="mt-2 text-sm opacity-70">
          All {rows.length} positions are saved. Nothing else is needed from this page.
        </p>
        <div className="mt-6 grid grid-cols-3 gap-3 text-sm">
          <div className="rounded-lg border border-slate-300 dark:border-slate-700 p-3">
            <div className="font-mono text-xl">{held}/{rows.length}</div>
            <div className="opacity-60 text-xs mt-1">move held</div>
          </div>
          <div className="rounded-lg border border-slate-300 dark:border-slate-700 p-3">
            <div className="font-mono text-xl">{named}/{rows.length}</div>
            <div className="opacity-60 text-xs mt-1">named the capture</div>
          </div>
          <div className="rounded-lg border border-slate-300 dark:border-slate-700 p-3">
            <div className="font-mono text-xl">{pend}</div>
            <div className="opacity-60 text-xs mt-1">pending check</div>
          </div>
        </div>
        <p className="mt-5 text-xs opacity-60 mx-auto max-w-md">
          Counts from fourteen positions chosen because of how they were played
          before. They describe this sitting and nothing wider.
        </p>
      </div>
    </Layout>;
  }

  const derived = done[item.position_id];
  const branch = evidence?.reply_evidence_by_candidate_move?.[ans.intended_move] || null;
  const punishing = branch?.punishing_replies || [];

  return (
    <Layout user={user}>
      <div className="mx-auto max-w-5xl px-4 py-6">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-300 dark:border-slate-700 pb-4">
          <div>
            <h1 className="text-xl font-semibold">Reply check</h1>
            <p className="mt-1 text-sm opacity-70">
              Play your move on the board. Nothing is shown until all the answers are in.
            </p>
          </div>
          <span className="rounded-full border border-slate-300 dark:border-slate-700 px-3 py-1 font-mono text-xs">
            {idx + 1} of {packet.count}
          </span>
        </div>

        <div className="mt-5 grid gap-6 md:grid-cols-[minmax(0,440px)_minmax(0,1fr)]">
          {/* ---------- board ---------- */}
          <div className="min-w-0">
            <div className="aspect-square w-full max-w-[440px]">
              <Chessboard
                id="reply-check-board"
                position={shownFen}
                boardOrientation={orientation}
                onPieceDrop={onDrop}
                arePiecesDraggable={draggable}
                customBoardStyle={{ borderRadius: "6px" }}
              />
            </div>
            <p className="mt-3 text-sm font-medium">
              {item.to_move === "white" ? "White" : "Black"} to move
              {item.side_to_move_in_check && (
                <span className="text-rose-600 dark:text-rose-400">
                  {" "}— in check from {(item.checking_squares || []).join(", ")}
                </span>
              )}
            </p>
            <dl className="mt-2 space-y-1 text-xs opacity-70">
              <div className="flex justify-between gap-3">
                <dt>legal moves</dt><dd className="font-mono">{item.n_legal}</dd>
              </div>
              {!!(item.preceding_moves || []).length && (
                <div className="flex justify-between gap-3">
                  <dt>before this</dt>
                  <dd className="font-mono text-right">{item.preceding_moves.join("  ")}</dd>
                </div>
              )}
            </dl>
          </div>

          {/* ---------- prompts ---------- */}
          <div className="min-w-0 space-y-3">
            {step === STEP.RECOGNISE && (
              <Card n={1} q="Do you recognise this position?">
                <Choices cols="grid-cols-2" options={[["no", "No"], ["yes", "Yes"]]}
                  value={ans.recognised}
                  onPick={(v) => { setAns((a) => ({ ...a, recognised: v })); setStep(STEP.MOVE); }} />
              </Card>
            )}

            {step === STEP.MOVE && (
              <Card n={2} q="It is your move. Take as long as you like."
                    note="Drag a piece on the board. You can change it until you lock it in.">
                <Locked label="Your move" value={ans.intended_move} />
                <div className="mt-3 flex gap-2">
                  <Primary disabled={!ans.intended_move} onClick={() => setStep(STEP.REPLY)}>
                    Lock it in
                  </Primary>
                  {ans.intended_move && (
                    <Ghost onClick={() => setAns((a) => ({ ...a, intended_move: undefined }))}>
                      Take it back
                    </Ghost>
                  )}
                </div>
              </Card>
            )}

            {step === STEP.REPLY && (
              <Card n={3} q="What do you expect them to reply?"
                    note="Your move is on the board. Play their reply the same way.">
                <Locked label="Their reply" value={ans.expected_reply} />
                <div className="mt-3 flex flex-wrap gap-2">
                  <Primary disabled={!ans.expected_reply} onClick={() => setStep(STEP.NOW)}>
                    Lock it in
                  </Primary>
                  <Ghost onClick={() => { setAns((a) => ({ ...a, expected_reply: "not sure" })); setStep(STEP.NOW); }}>
                    Not sure
                  </Ghost>
                  {ans.expected_reply && ans.expected_reply !== "not sure" && (
                    <Ghost onClick={() => setAns((a) => ({ ...a, expected_reply: undefined }))}>
                      Take it back
                    </Ghost>
                  )}
                </div>
              </Card>
            )}

            {step === STEP.NOW && (
              <Card n={4} q="How do you rate your position right now?">
                <Choices options={ASSESS.map((v) => [v, v])} value={ans.assessment_now}
                  onPick={(v) => { setAns((a) => ({ ...a, assessment_now: v })); setStep(STEP.AFTER); }} />
              </Card>
            )}

            {step === STEP.AFTER && (
              <Card n={5}
                q={ans.expected_reply === "not sure"
                  ? "And after their reply, whatever it turns out to be?"
                  : `And after ${ans.expected_reply}, how would you rate it then?`}>
                <Choices options={ASSESS.map((v) => [v, v])}
                  value={ans.assessment_after_predicted_reply}
                  onPick={(v) => { setAns((a) => ({ ...a, assessment_after_predicted_reply: v })); setStep(STEP.REVISE); }} />
              </Card>
            )}

            {step === STEP.REVISE && (
              <Card n={6} q="Having said that out loud, do you want to change your move?"
                    note="The board is back to the start. Play a different move, or keep the one you had.">
                <Locked label="You had" value={ans.intended_move} />
                {ans.revised_move && <Locked label="New move" value={ans.revised_move} />}
                <div className="mt-3 flex flex-wrap gap-2">
                  <Primary disabled={busy} onClick={record}>
                    {busy ? "Saving…" : ans.revised_move ? "Change it and record" : "Keep my move and record"}
                  </Primary>
                  {ans.revised_move && (
                    <Ghost onClick={() => setAns((a) => ({ ...a, revised_move: undefined }))}>
                      Undo the change
                    </Ghost>
                  )}
                </div>
                {error && <p className="mt-2 text-xs text-rose-600 dark:text-rose-400">{error}</p>}
              </Card>
            )}

            {step === STEP.REVEAL && derived && (
              <Reveal
                item={item} ans={ans} derived={derived} evidence={evidence}
                branch={branch} punishing={punishing}
                last={idx + 1 >= packet.count}
                onNext={() => setIdx((i) => i + 1)}
                onReason={(v) => setAns((a) => ({ ...a, reason_choice: v }))}
                onReflect={(v) => setAns((a) => ({ ...a, reflection_choice: v }))}
              />
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
}

function Card({ n, q, note, children }) {
  return (
    <div className="rounded-xl border border-slate-300 dark:border-slate-700 p-4">
      <p className="text-[0.95rem] font-medium">{n}. {q}</p>
      {note && <p className="mt-1 text-xs opacity-60">{note}</p>}
      <div className="mt-3">{children}</div>
    </div>
  );
}

function Locked({ label, value }) {
  return (
    <div className="flex items-baseline justify-between gap-3 text-sm">
      <span className="opacity-60">{label}</span>
      <span className="font-mono text-base">{value || "—"}</span>
    </div>
  );
}

function Primary({ children, ...p }) {
  return <button type="button" {...p}
    className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white
      disabled:opacity-40 hover:bg-teal-700 transition">{children}</button>;
}

function Ghost({ children, ...p }) {
  return <button type="button" {...p}
    className="rounded-lg border border-slate-300 dark:border-slate-700 px-4 py-2
      text-sm opacity-80 hover:opacity-100 transition">{children}</button>;
}

/** Shown only after the answers are recorded. Describes what happened; it does
 *  not tell him what it means about how he thinks. */
function Reveal({ item, ans, derived, evidence, branch, punishing, last, onNext, onReason, onReflect }) {
  const played = derived.move_graded;
  const pills = [];
  if (!derived.move_branch_prepared) pills.push(["pend", "move: pending check"]);
  else pills.push([derived.move_holds ? "good" : "bad",
    derived.move_holds
      ? (derived.move_holds_at_every_depth ? "move holds" : "move holds (depth-sensitive)")
      : "move gives ground"]);
  if (derived.reply_not_sure) pills.push(["pend", "reply: not sure"]);
  else if (derived.reply_names_the_capture === null) pills.push(["pend", "reply: pending check"]);
  else pills.push([derived.reply_names_the_capture ? "good" : derived.reply_as_damaging_as_best ? "good" : "bad",
    derived.reply_names_the_capture ? "reply: named the capture"
      : derived.reply_as_damaging_as_best ? "reply: as damaging as their best"
        : "reply: not the one they have"]);
  if (derived.revised) pills.push(["pend", "changed after step 6"]);

  let body;
  if (!derived.move_branch_prepared) {
    body = <>{played} is outside the frozen set, so it is <b>pending a check</b> rather than
      anything else. Record it and verify it afterwards.</>;
  } else if (derived.move_holds && derived.reply_names_the_capture) {
    body = <>{played} holds, and {ans.expected_reply} is the move that takes something.</>;
  } else if (derived.move_holds) {
    body = <>{played} holds. Their best is <b>{branch?.engine_top_replies?.[0]?.reply}</b>.</>;
  } else if (derived.reply_names_the_capture) {
    body = <>You named <b>{ans.expected_reply}</b>, which does win material, and played {played} anyway.
      Worth talking through: after {ans.expected_reply} you rated it
      “{ans.assessment_after_predicted_reply}”.</>;
  } else {
    body = <>{played} gives up material. {punishing.length
      ? <>They take with <b>{punishing[0]}</b>.</>
      : <>Their best is <b>{branch?.engine_top_replies?.[0]?.reply}</b>.</>}</>;
  }

  return (
    <div className="rounded-xl border border-slate-300 dark:border-slate-700 p-4">
      <div className="flex flex-wrap gap-2">
        {pills.map(([tone, label]) => <Pill key={label} tone={tone}>{label}</Pill>)}
      </div>
      <p className="mt-3 rounded-lg bg-slate-500/10 p-3 text-sm">{body}</p>

      {!!branch?.engine_top_replies?.length && (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="opacity-60">
                <th className="py-1 pr-3 text-left font-medium">their reply to {played}</th>
                <th className="py-1 pr-3 text-left font-medium">then it stands at</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {branch.engine_top_replies.map((r) => (
                <tr key={r.reply} className="border-t border-slate-300/50 dark:border-slate-700/50">
                  <td className="py-1 pr-3 font-mono">{r.reply}</td>
                  <td className="py-1 pr-3 font-mono tabular-nums">
                    {r.eval_after_reply_his_pov > 0 ? "+" : ""}{r.eval_after_reply_his_pov}
                  </td>
                  <td className="py-1 opacity-60">
                    {punishing.includes(r.reply) ? "takes material" : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {evidence && (
        <p className="mt-3 text-xs opacity-60">
          Moves that hold here ({evidence.n_moves_that_hold}):{" "}
          <span className="font-mono">{(evidence.accept_moves || []).join(", ")}</span>.
          {evidence.one_move_only_wording_permitted && " Only one move holds at every depth checked."}
        </p>
      )}

      <div className="mt-4 border-t border-slate-300 dark:border-slate-700 pt-3">
        <p className="text-sm font-medium">How did you pick it?</p>
        <div className="mt-2"><Choices cols="grid-cols-1" options={REASONS}
          value={ans.reason_choice} onPick={onReason} /></div>
      </div>
      <div className="mt-3">
        <p className="text-sm font-medium">What were you thinking before this move?</p>
        <div className="mt-2"><Choices options={REFLECT} value={ans.reflection_choice}
          onPick={onReflect} /></div>
      </div>

      <div className="mt-4">
        <Primary onClick={onNext}>{last ? "Finish" : "Next position"}</Primary>
      </div>
    </div>
  );
}
