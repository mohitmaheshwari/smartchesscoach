/**
 * First steps: a class for a child who has never played. docs/first_steps_scope.md.
 *
 * Reached by the child's class link, with no account. The page only shows
 * and sends taps: every answer is judged on the server by
 * services/first_steps.py, which also keeps it as evidence for the next class.
 */
import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { API } from "@/App";

const GLYPH = { k: "♚", q: "♛", r: "♜", b: "♝", n: "♞", p: "♟" };
const FILES = "abcdefgh";

export function parseFen(fen) {
  const pieces = {};
  const rows = String(fen || "").split(" ")[0].split("/");
  rows.forEach((row, i) => {
    let file = 0;
    for (const ch of row) {
      if (/\d/.test(ch)) { file += Number(ch); continue; }
      pieces[`${FILES[file]}${8 - i}`] = { type: ch.toLowerCase(), white: ch === ch.toUpperCase() };
      file += 1;
    }
  });
  return pieces;
}

async function call(path, body) {
  const res = await fetch(`${API}/academy/class/${path}`, body === undefined ? undefined : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Something went wrong. Try again.");
  return data;
}

function speak(text) {
  try {
    const u = new window.SpeechSynthesisUtterance(text);
    u.rate = 0.9;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
  } catch { /* the browser has no voice; the words are on the screen */ }
}

function Board({ fen, marks, stars, flip, onTap }) {
  const pieces = parseFen(fen);
  const squares = [];
  for (let row = 0; row < 8; row += 1) {
    for (let col = 0; col < 8; col += 1) {
      const rank = flip ? row + 1 : 8 - row;
      const file = flip ? 7 - col : col;
      const sq = `${FILES[file]}${rank}`;
      const p = pieces[sq];
      const light = (file + rank) % 2 === 1;
      const mark = marks[sq];
      const star = stars.includes(sq);
      const label = `${sq}${p ? ` ${p.white ? "white" : "black"} ${{ k: "king", q: "queen", r: "rook", b: "bishop", n: "knight", p: "pawn" }[p.type]}` : star ? " star" : ""}`;
      squares.push(
        <button key={sq} type="button" data-sq={sq} aria-label={label} onClick={() => onTap(sq)}
          className="relative grid place-items-center focus-visible:outline focus-visible:outline-4 focus-visible:-outline-offset-4 focus-visible:outline-primary"
          style={{ background: light ? "#efd9b4" : "#b58863", fontSize: "clamp(24px, 9vw, 40px)", lineHeight: 1,
                   fontFamily: '"Segoe UI Symbol","Noto Sans Symbols 2","DejaVu Sans",serif' }}>
          {p ? (
            <span style={p.white
              ? { color: "#fbfaf6", textShadow: "0 0 1px #2a2620,0 0 1px #2a2620,0 1px 1px #2a2620" }
              : { color: "#1d1b18" }}>{GLYPH[p.type]}</span>
          ) : star ? <span style={{ color: "#f2b632", textShadow: "0 0 2px #7a5208", fontSize: "0.8em" }}>{"★"}</span> : null}
          {mark && <span aria-hidden className="pointer-events-none absolute inset-0" style={MARK_STYLE[mark]} />}
          {row === 7 && <span className="absolute bottom-0 right-0.5 text-[9px] font-semibold text-[#3b2e20] opacity-70">{FILES[file]}</span>}
          {col === 0 && <span className="absolute left-0.5 top-0 text-[9px] font-semibold text-[#3b2e20] opacity-70">{rank}</span>}
        </button>,
      );
    }
  }
  return <div className="grid aspect-square w-full select-none grid-cols-8 overflow-hidden rounded-lg" style={{ touchAction: "manipulation" }}>{squares}</div>;
}

const MARK_STYLE = {
  found: { background: "radial-gradient(circle, rgba(47,125,67,.75) 22%, transparent 24%)" },
  answer: { background: "radial-gradient(circle, rgba(47,111,94,.5) 22%, transparent 24%)" },
  miss: { background: "radial-gradient(circle, rgba(181,69,47,.7) 18%, transparent 20%)" },
  pick: { boxShadow: "inset 0 0 0 4px rgba(47,111,94,.9)" },
  last: { boxShadow: "inset 0 0 0 4px rgba(232,163,61,.85)" },
  marked: { boxShadow: "inset 0 0 0 4px rgba(63,95,143,.85)" },
};

function Stars({ n }) {
  return (
    <span className="whitespace-nowrap text-xl tracking-widest" aria-label={`${n} stars`}>
      {[0, 1, 2, 3, 4].map((k) => <span key={k} style={{ color: k < n ? "#e8a33d" : "#d6d3c9" }}>{"★"}</span>)}
    </span>
  );
}

function Coach({ say, sub }) {
  return (
    <div className="flex items-start gap-3">
      <div className="grid h-11 w-11 flex-none place-items-center rounded-full bg-primary text-xl font-bold text-primary-foreground">C</div>
      <div className="min-w-0">
        <p className="text-xl font-semibold leading-snug">{say}</p>
        {sub && <p className="mt-0.5 text-[15px] text-muted-foreground">{sub}</p>}
      </div>
    </div>
  );
}

function Session({ token, view, setView, onDone }) {
  const cur = view.current;
  const [feedback, setFeedback] = useState(null);
  const [pick, setPick] = useState(null);
  const [miss, setMiss] = useState(null);
  const [reveal, setReveal] = useState(null);
  const [last, setLast] = useState([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => { setFeedback(null); setPick(null); setMiss(null); setReveal(null); setLast([]); }, [cur?.id]);

  const send = async (answer, tapped) => {
    if (busy) return;
    setBusy(true);
    try {
      const out = await call(`${token}/answer`, { session_id: view.session_id, item_id: cur.id, answer });
      const r = out.result;
      if (r.outcome !== "ignored") {
        let say = r.say;
        if (r.reveal?.choice) say = `${say} The answer is ${r.reveal.choice === "yes" ? "yes" : "no"}.`;
        if (r.reveal?.sans?.length) say = `${say} ${r.reveal.sans.length === 1 ? "The move is" : "Moves that work:"} ${r.reveal.sans.join(", ")}.`;
        setFeedback(say ? [r.outcome === "right" || r.outcome === "progress" ? "good" : "hint", say] : null);
        setMiss(r.outcome === "wrong" ? tapped : null);
        if (r.reveal) setReveal(r.reveal);
        if (r.played) setLast(r.played.length > 1 ? [r.played[1].slice(0, 2), r.played[1].slice(2, 4)] : []);
      }
      setView(out.session);
    } catch (e) {
      setFeedback(["hint", e.message]);
    } finally {
      setBusy(false);
    }
  };

  const movable = cur && (cur.kind === "move_goal" || cur.kind === "game");
  const pieces = cur ? parseFen(cur.fen) : {};
  const childWhite = (cur?.child || "w") === "w";

  const onTap = (sq) => {
    if (!cur || cur.finished) return;
    if (!movable) { send({ square: sq }, sq); return; }
    const p = pieces[sq];
    if (p && p.white === childWhite) { setPick(sq); return; }
    if (pick) { const from = pick; setPick(null); send({ move: from + sq }, sq); }
  };

  const next = async () => {
    try {
      const out = await call(`${token}/next`, { session_id: view.session_id });
      if (out.finished_at) onDone(out); else setView(out);
    } catch (e) { setFeedback(["hint", e.message]); }
  };
  const retry = async () => {
    try { setView(await call(`${token}/retry`, { session_id: view.session_id })); setFeedback(null); setLast([]); }
    catch (e) { setFeedback(["hint", e.message]); }
  };

  if (!cur) return null;
  const marks = {};
  (cur.marks || []).forEach((s) => { marks[s] = "marked"; });
  (cur.found || []).forEach((s) => { marks[s] = "found"; });
  if (reveal?.squares) reveal.squares.forEach((s) => { if (!marks[s]) marks[s] = "answer"; });
  last.forEach((s) => { marks[s] = "last"; });
  if (miss && !marks[miss]) marks[miss] = "miss";
  if (pick) marks[pick] = "pick";
  const count = cur.kind === "tap_reach" ? `${(cur.found || []).length} of ${cur.total} squares found`
    : cur.kind === "stars" ? `Moves: ${cur.moves} · Can you do it in ${cur.par}?` : null;

  return (
    <section className="grid gap-4 rounded-3xl border bg-card p-4 sm:p-5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-bold uppercase tracking-widest text-primary">{view.title} · {cur.part}</span>
        <Stars n={view.stars} />
      </div>
      <div className="flex gap-1.5" aria-hidden>
        {view.parts.map((_, k) => <span key={k} className={`h-1.5 flex-1 rounded ${k <= view.index ? "bg-primary" : "bg-muted"}`} />)}
      </div>
      <Coach say={cur.say} sub={cur.sub} />
      <Board fen={cur.fen} marks={marks} stars={cur.kind === "stars" ? cur.stars_left || [] : []} flip={!!cur.flip} onTap={onTap} />
      {count && <p className="text-sm font-semibold text-muted-foreground">{count}</p>}
      {feedback && (
        <p className={`rounded-xl px-4 py-2.5 font-semibold ${feedback[0] === "good" ? "bg-emerald-50 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200" : "bg-amber-50 text-amber-900 dark:bg-amber-950 dark:text-amber-200"}`}>
          {feedback[1]}
        </p>
      )}
      {cur.kind === "choose" && !cur.finished && (
        <div className="flex gap-3">
          {(cur.options || []).map((o) => (
            <button key={o.id} type="button" onClick={() => send({ choice: o.id })}
              className="flex-1 rounded-full border-2 border-primary px-5 py-2.5 text-lg font-bold">{o.label}</button>
          ))}
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => speak(`${cur.say} ${cur.sub || ""} ${feedback ? feedback[1] : ""}`)}
          className="rounded-full border px-4 py-2 text-sm font-semibold">Read aloud</button>
        {cur.can_skip && <button type="button" onClick={() => send({ skip: true })} className="rounded-full border px-4 py-2 text-sm font-semibold">I don&apos;t know yet</button>}
        {cur.can_reveal && <button type="button" onClick={() => send({ reveal: true })} className="rounded-full border px-4 py-2 text-sm font-semibold">Show me</button>}
        {cur.can_retry && <button type="button" onClick={retry} className="rounded-full border px-4 py-2 text-sm font-semibold">Try again</button>}
        {cur.finished && <button type="button" onClick={next} className="rounded-full bg-primary px-6 py-2.5 text-lg font-bold text-primary-foreground">Next</button>}
      </div>
    </section>
  );
}

function Finished({ view, onStart }) {
  const s = view.summary || {};
  return (
    <section className="grid gap-4 rounded-3xl border bg-card p-5">
      <div className="flex items-center justify-between"><span className="text-xs font-bold uppercase tracking-widest text-primary">{view.title}</span><Stars n={view.stars} /></div>
      <Coach say={s.say} sub={s.next ? `Next class: ${s.next.toLowerCase()}.` : s.all_done ? "You've finished every class. Time to play real games!" : null} />
      {s.parent && <p className="rounded-xl bg-muted px-4 py-2.5 text-[15px]"><b>For your parent:</b> {s.parent}</p>}
      {s.next && <button type="button" onClick={onStart} className="justify-self-start rounded-full bg-primary px-6 py-2.5 text-lg font-bold text-primary-foreground">Start the next class</button>}
    </section>
  );
}

export default function FirstStepsClass() {
  const { token } = useParams();
  const [home, setHome] = useState(null);
  const [view, setView] = useState(null);
  const [done, setDone] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const h = await call(token);
      setHome(h);
      setView(h.open);
    } catch (e) { setError(e.message); }
  }, [token]);
  useEffect(() => { load(); }, [load]);

  const start = async () => {
    try { setDone(null); setView(await call(`${token}/start`, {})); }
    catch (e) { setError(e.message); }
  };

  return (
    <div className="min-h-screen bg-background px-4 py-6 text-foreground">
      <div className="mx-auto grid w-full max-w-[460px] gap-4">
        <p className="text-sm font-semibold text-muted-foreground">ChessGuru · First steps</p>
        {error && <section className="rounded-2xl border bg-card p-5"><p className="font-semibold">{error}</p></section>}
        {!error && !home && <p className="text-muted-foreground">Getting your class ready…</p>}
        {done && <Finished view={done} onStart={start} />}
        {!done && view && <Session token={token} view={view} setView={setView} onDone={(v) => { setDone(v); setView(null); }} />}
        {!done && !view && home && (
          <section className="grid gap-4 rounded-3xl border bg-card p-5">
            <Coach say={`Hi ${home.child_name}!`}
              sub={!home.placed ? "Let's start with three quick questions, so your classes fit you."
                : home.all_done ? "You've finished every class. Time to play real games!"
                : `Your next class: ${home.next.title.toLowerCase()}.`} />
            {home.placed && (
              <ol className="grid gap-1.5">
                {home.classes.map((c) => (
                  <li key={c.id} className="flex items-center gap-2 text-[15px]">
                    <span aria-hidden style={{ color: c.passed || c.skipped ? "#2f7d43" : "#b9b5aa" }}>{c.passed || c.skipped ? "✔" : "○"}</span>
                    <span className={c.id === home.next?.id ? "font-bold" : ""}>{c.title}</span>
                    {c.skipped && <span className="text-xs text-muted-foreground">(you know this)</span>}
                  </li>
                ))}
              </ol>
            )}
            {!home.all_done && <button type="button" onClick={start} className="justify-self-start rounded-full bg-primary px-6 py-2.5 text-lg font-bold text-primary-foreground">{home.placed ? "Start the class" : "Let's go"}</button>}
          </section>
        )}
      </div>
    </div>
  );
}
