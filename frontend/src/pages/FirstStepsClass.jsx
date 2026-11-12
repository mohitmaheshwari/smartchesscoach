/**
 * First steps: the rules of chess, one lesson at a time. docs/first_steps_scope.md.
 *
 * Reached by the child's class link, with no account. The board is the app's
 * own LichessBoard in tap mode: the page sends each tap, and every answer is
 * judged on the server by services/first_steps.py, which also keeps it as
 * evidence for the next lesson.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { API } from "@/App";
import LichessBoard from "@/components/LichessBoard";
import "@/components/room/room.css";
import { setSoundOff, soundOff, woodClick } from "@/components/room/roomSound";

const PIECE_OF = { rook: "rook", bishop: "bishop", queen: "queen", knight: "knight", pawn: "pawn", king: "king", check: "king", checkmate: "queen" };
const PREVIEW = {
  rook: "8/8/8/8/3R4/8/8/8 w - - 0 1", bishop: "8/8/8/8/3B4/8/8/8 w - - 0 1", queen: "8/8/8/8/3Q4/8/8/8 w - - 0 1",
  knight: "8/8/8/8/3N4/8/8/8 w - - 0 1", pawn: "8/8/8/8/8/8/4P3/8 w - - 0 1", king: "8/8/8/8/4K3/8/8/8 w - - 0 1",
  check: "k3r3/8/8/8/8/8/8/4K3 w - - 0 1", checkmate: "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1",
};
const WHAT = {
  rook: "Straight lines", bishop: "Diagonals", queen: "Both together", knight: "The L-shape",
  pawn: "Forward, and captures", king: "One step, always safe", check: "Attacking the king", checkmate: "Winning the game",
};

async function call(path, body) {
  const res = await fetch(`${API}/academy/class/${path}`, body === undefined ? undefined : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Something went wrong. Try again.");
  return data;
}

function whitePieces(fen) {
  const out = {};
  String(fen || "").split(" ")[0].split("/").forEach((row, i) => {
    let file = 0;
    for (const ch of row) {
      if (/\d/.test(ch)) { file += Number(ch); continue; }
      out[`${"abcdefgh"[file]}${8 - i}`] = ch === ch.toUpperCase();
      file += 1;
    }
  });
  return out;
}

function Top({ where }) {
  const [off, setOff] = useState(soundOff());
  return (
    <div className="room-top">
      <span className="room-mark">ChessGuru</span>
      <span className="room-where">{where}</span>
      <button type="button" className="room-sound" onClick={() => { setSoundOff(!off); setOff(!off); }}>
        {off ? "Sound off" : "Sound on"}
      </button>
    </div>
  );
}

function Lesson({ token, view, setView, onDone }) {
  const cur = view.current;
  const [say, setSay] = useState(null);
  const [pick, setPick] = useState(null);
  const [reveal, setReveal] = useState(null);
  const [miss, setMiss] = useState(null);
  const [lastMove, setLastMove] = useState(null);
  const [after, setAfter] = useState(null);
  const box = useRef(null);
  const busy = useRef(false);
  const pending = useRef(null);
  const sendRef = useRef(null);

  useEffect(() => { setSay(null); setPick(null); setReveal(null); setMiss(null); setLastMove(null); setAfter(null); }, [cur?.id]);

  const nudge = () => {
    const el = box.current;
    if (!el) return;
    el.classList.remove("nudge");
    void el.offsetWidth;
    el.classList.add("nudge");
  };

  const send = async (answer, tapped) => {
    // A tap made while the last one is being checked is kept (only the latest).
    if (busy.current) { pending.current = [answer, tapped]; return; }
    busy.current = true;
    try {
      const out = await call(`${token}/answer`, { session_id: view.session_id, item_id: cur.id, answer });
      const r = out.result;
      if (r.outcome !== "ignored") {
        let text = r.say;
        if (r.reveal?.choice) text = `${text} The answer is ${r.reveal.choice}.`;
        if (r.reveal?.sans?.length) text = `${text} ${r.reveal.sans.length === 1 ? "The move is" : "Moves that work:"} ${r.reveal.sans.join(", ")}.`;
        const good = r.outcome === "right" || r.outcome === "progress" || r.outcome === "skipped";
        if (text) setSay([good ? "good" : r.outcome === "wrong" ? "bad" : "", text]);
        else if (r.outcome === "progress") setSay(null);
        if (r.reveal) setReveal(r.reveal);
        if (r.fen_after) setAfter(r.fen_after);
        if (r.played) {
          const m = r.played[r.played.length - 1];
          setLastMove([m.slice(0, 2), m.slice(2, 4)]);
        }
        if (r.outcome === "wrong") {
          nudge();
          setMiss(tapped || null);
          setTimeout(() => setMiss(null), 650);
        } else if (r.outcome === "right" || r.outcome === "progress") {
          woodClick(r.outcome === "right");
        }
      }
      setView(out.session);
    } catch (e) {
      setSay(["bad", e.message]);
      pending.current = null;
    } finally {
      busy.current = false;
    }
    if (pending.current) {
      const queued = pending.current;
      pending.current = null;
      setTimeout(() => sendRef.current(...queued), 0);  // after the new view is drawn
    }
  };
  sendRef.current = send;

  const moves = cur && (cur.kind === "move_goal" || cur.kind === "game");
  const white = cur ? whitePieces(cur.fen) : {};

  const onSquare = (sq) => {
    if (!cur || cur.finished) return;
    if (!moves) { send({ square: sq }, sq); return; }
    if (white[sq] === true) { woodClick(); setPick(sq); return; }
    if (pick) { const from = pick; setPick(null); send({ move: from + sq }, sq); return; }
    setSay(["", "Tap one of your pieces first."]);
  };

  const next = async () => {
    try {
      const out = await call(`${token}/next`, { session_id: view.session_id });
      if (out.finished_at) onDone(out); else setView(out);
    } catch (e) { setSay(["bad", e.message]); }
  };
  const retry = async () => {
    try { setView(await call(`${token}/retry`, { session_id: view.session_id })); setSay(null); setLastMove(null); }
    catch (e) { setSay(["bad", e.message]); }
  };

  if (!cur) return null;
  const marks = [
    ...(cur.marks || []).map((square) => ({ square, kind: "target" })),
    ...(cur.found || []).map((square) => ({ square, kind: "found" })),
    ...(reveal?.squares || []).filter((s) => !(cur.found || []).includes(s)).map((square) => ({ square, kind: "answer" })),
    ...(pick ? [{ square: pick, kind: "picked" }] : []),
    ...(miss ? [{ square: miss }] : []),
  ];
  // Every "find them all" task carries `total` from the server: squares for the
  // piece lessons, pieces for the thinking habits (captures, threats, loose pieces).
  const tally = cur.kind === "tap_reach" ? `${(cur.found || []).length} of ${cur.total} squares found`
    : cur.kind === "stars" ? `${cur.moves} moves · ${(cur.stars_left || []).length} left`
    : typeof cur.total === "number" ? `${(cur.found || []).length} of ${cur.total} found` : "";

  return (
    <div className="room-lesson">
      <div className="room-boardbox" ref={box}>
        <LichessBoard key={cur.id} fen={after || cur.fen} orientation={cur.flip ? "black" : "white"}
          selectionOnly showDests={false} onSquareClick={onSquare} highlights={marks} lastMove={lastMove} squareTags />
      </div>
      <aside className="room-side">
        <div className="room-progress" aria-hidden="true"><i style={{ width: `${(view.index / view.count) * 100}%` }} /></div>
        <span className="room-label">{cur.part}</span>
        <h1>{cur.say}</h1>
        <p className="room-task">{cur.sub}</p>
        <div className="room-say" aria-live="polite">
          <div className="room-who">Coach</div>
          {say && <p key={say[1]} className={say[0]}>{say[1]}</p>}
        </div>
        <div className="room-tally"><span>{tally}</span><span>Step {view.index + 1} of {view.count}</span></div>
        {cur.kind === "choose" && !cur.finished && (
          <div className="room-acts">
            {(cur.options || []).map((o) => (
              <button key={o.id} type="button" className="room-btn quiet" onClick={() => send({ choice: o.id })}>{o.label}</button>
            ))}
          </div>
        )}
        <div className="room-acts">
          {cur.can_skip && <button type="button" className="room-btn quiet" onClick={() => send({ skip: true })}>I don&apos;t know yet</button>}
          {cur.can_reveal && <button type="button" className="room-btn quiet" onClick={() => send({ reveal: true })}>Show the answer</button>}
          {cur.can_retry && <button type="button" className="room-btn quiet" onClick={retry}>Try again</button>}
          {cur.finished && <button type="button" className="room-btn" onClick={next}>Continue</button>}
        </div>
      </aside>
    </div>
  );
}

function Finished({ view, name, onBack }) {
  const s = view.summary || {};
  const placement = view.kind === "placement";
  return (
    <div className="room-done">
      <span className="room-label">{placement ? "Ready" : s.passed ? "Lesson complete" : "One more time"}</span>
      <h1>{placement ? `${name}, your path is ready.` : s.passed ? `${view.title}, complete.` : `${view.title}, once more.`}</h1>
      <p>{s.say}</p>
      {!placement && (
        <div className="room-facts">
          <div><b>{s.steps}</b><span>Steps</span></div>
          <div><b>{s.first_try}</b><span>Right first time</span></div>
        </div>
      )}
      {s.parent && <p className="room-parent">For a parent: {s.parent}</p>}
      <div className="room-acts">
        <button type="button" className="room-btn" onClick={onBack}>{placement ? "See your path" : "Back to your path"}</button>
      </div>
    </div>
  );
}

function PieceIcon({ type }) {
  return <span className="room-icon cg-wrap" aria-hidden="true"><piece className={`${type} white`} /></span>;
}

function Path({ home, onStart, onPractise }) {
  const next = home.next;
  return (
    <div className="room-path">
      <header>
        <h1>{home.child_name}&apos;s path</h1>
        <p className="room-note">One idea at a time, checked before moving on.</p>
      </header>
      {next ? (
        <section className="room-next">
          <div><LichessBoard fen={PREVIEW[next.id]} viewOnly interactive={false} showCoordinates={false} /></div>
          <div style={{ minWidth: 0 }}>
            <span className="room-label">Continue</span>
            <h2>{next.title}</h2>
            <p>{WHAT[next.id]}</p>
            <button type="button" className="room-btn" onClick={onStart}>Start lesson</button>
          </div>
        </section>
      ) : (
        <section className="room-next" style={{ gridTemplateColumns: "minmax(0, 1fr)" }}>
          <div>
            <span className="room-label">Complete</span>
            <h2>Every lesson is done</h2>
            <p>Your first real game comes next. Ask your coach or parent to set it up.</p>
            <p>Until then, tap any lesson below to practise it.</p>
          </div>
        </section>
      )}
      <section className="room-stage">
        <h3>Foundations</h3>
        <div className="room-rows">
          {home.classes.map((c) => {
            const state = c.passed ? "done" : c.skipped ? "done" : c.id === next?.id ? "cur" : "locked";
            const words = c.passed ? "Complete" : c.skipped ? "Known" : c.id === next?.id ? "Next" : "Locked";
            const body = (
              <>
                <PieceIcon type={PIECE_OF[c.id] || "pawn"} />
                <span><b>{c.title}</b><small>{WHAT[c.id]}</small></span>
                <span className="st">{words}</span>
              </>
            );
            if (state === "cur") {
              return <button key={c.id} type="button" className="room-row cur open" onClick={onStart}>{body}</button>;
            }
            if (state === "done") {
              return (
                <button key={c.id} type="button" className="room-row done open" onClick={() => onPractise(c.id)}
                  aria-label={`Practise ${c.title}`}>{body}</button>
              );
            }
            return <div key={c.id} className={`room-row ${state}`}>{body}</div>;
          })}
        </div>
      </section>
    </div>
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
  // The coach's weekly reflection rides on the class home payload
  // (`reflect: {available, all_done}`), so no second request on this page.
  const reflect = home?.reflect;
  useEffect(() => { load(); }, [load]);

  const start = async () => {
    try { setDone(null); setView(await call(`${token}/start`, {})); }
    catch (e) { setError(e.message); }
  };
  const practise = async (classId) => {
    try { setDone(null); setView(await call(`${token}/practise`, { class_id: classId })); }
    catch (e) { setError(e.message); }
  };
  const back = async () => { setDone(null); setView(null); await load(); };

  const name = home?.child_name || "";
  const where = done ? "Finished" : view ? (view.title || "") : "Your path";

  return (
    <div className="room">
      <Top where={where} />
      <div className="room-page">
        {error && <div className="room-done"><h1>This link needs attention</h1><p>{error}</p></div>}
        {!error && !home && <p className="room-note">Loading…</p>}
        {done && <Finished view={done} name={name} onBack={back} />}
        {!done && view && <Lesson token={token} view={view} setView={setView} onDone={(v) => { setDone(v); setView(null); }} />}
        {!done && !view && home && !home.placed && (
          <div className="room-done">
            <span className="room-label">Welcome</span>
            <h1>Hello {name}.</h1>
            <p>Three quick questions first, so your lessons start in the right place.</p>
            <div className="room-acts"><button type="button" className="room-btn" onClick={start}>Begin</button></div>
          </div>
        )}
        {!done && !view && home && reflect?.available && (
          <div className="room-next" style={{ maxWidth: 760, margin: "0 auto 28px", gridTemplateColumns: "minmax(0,1fr) auto" }}>
            <div>
              <span className="room-label">This week with your coach</span>
              <h2>Look back at your own moves</h2>
              <p>A few moments from your games. You answer on the board.</p>
            </div>
            <Link className="room-btn" to={`/class/${token}/reflect`}>
              {reflect.all_done ? "Go over them" : "Open"}
            </Link>
          </div>
        )}
        {!done && !view && home && home.placed && <Path home={home} onStart={start} onPractise={practise} />}
      </div>
    </div>
  );
}
