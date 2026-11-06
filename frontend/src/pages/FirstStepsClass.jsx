/**
 * First steps: a class for a child who has never played. docs/first_steps_scope.md.
 *
 * Reached by the child's class link, with no account. The page only shows
 * and sends taps: every answer is judged on the server by
 * services/first_steps.py, which also keeps it as evidence for the next class.
 * The look (journey map, Guru the owl, the wooden board, sound and sparkle)
 * lives in components/kids.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { API } from "@/App";
import "@/components/kids/kids.css";
import KidsBoard, { parseFen } from "@/components/kids/KidsBoard";
import JourneyMap from "@/components/kids/JourneyMap";
import { CLASS_ART, Medal, Owl, SpeakerIcon, Star, World } from "@/components/kids/KidsArt";
import { burst, centerOf, confetti, flyStar, isMuted, setMuted, sfx } from "@/components/kids/kidsFx";

export { parseFen };

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

/** Moves between two positions, by colour: [[from, to], ...]. */
function diffMoves(before, after) {
  const a = parseFen(before);
  const b = parseFen(after);
  const out = [];
  for (const white of [true, false]) {
    const gone = Object.keys(a).filter((s) => a[s].white === white && !(b[s] && b[s].white === white && b[s].type === a[s].type));
    const came = Object.keys(b).filter((s) => b[s].white === white && !(a[s] && a[s].white === white && a[s].type === b[s].type));
    if (gone.length === 1 && came.length === 1) out.push([gone[0], came[0]]);
  }
  return out;
}

function Words({ text }) {
  if (!text) return null;
  return text.split(/(\s+)/).map((w, i) => (
    <span key={`${i}-${w}`} className="w" style={{ animationDelay: `${Math.min(i, 40) * 22}ms` }}>{w}</span>
  ));
}

function Hud({ name, sub, stars }) {
  const [muted, setM] = useState(isMuted());
  return (
    <div className="kids-hud">
      <div className="kids-avatar" aria-hidden="true">{(name || "?")[0]}</div>
      <div className="kids-who">{name}<small>{sub}</small></div>
      <div className="kids-pill" id="kids-starpill" aria-label={`${stars} stars`}><Star /><span>{stars}</span></div>
      <button type="button" className="kids-icon-btn" aria-label={muted ? "Turn sound on" : "Turn sound off"}
        onClick={() => { setMuted(!muted); setM(!muted); if (muted) sfx.pop(); }}>
        <SpeakerIcon muted={muted} />
      </button>
    </div>
  );
}

function Coach({ mood, bump, say, sub, feedback }) {
  return (
    <div className="kids-coach">
      <Owl mood={mood} bump={bump} />
      <div className={`kids-bubble ${feedback ? feedback[0] : ""}`}>
        <div className="kids-say" key={say}><Words text={say} /></div>
        {sub && <div className="kids-sub">{sub}</div>}
        {feedback && <div className={`kids-feedback ${feedback[0]}`} key={feedback[1]}><Words text={feedback[1]} /></div>}
        <button type="button" className="kids-read" onClick={() => speak(`${say}. ${sub || ""} ${feedback ? feedback[1] : ""}`)}>
          <SpeakerIcon /> Read aloud
        </button>
      </div>
    </div>
  );
}

function Session({ token, view, setView, onDone }) {
  const cur = view.current;
  const [feedback, setFeedback] = useState(null);
  const [pick, setPick] = useState(null);
  const [reveal, setReveal] = useState(null);
  const [last, setLast] = useState([]);
  const [slides, setSlides] = useState([]);
  const [fx, setFx] = useState({ seq: 0 });
  const [mood, setMood] = useState(["", 0]);
  const busy = useRef(false);

  useEffect(() => {
    setFeedback(null); setPick(null); setReveal(null); setLast([]); setSlides([]); setFx({ seq: 0 }); setMood(["", 0]);
  }, [cur?.id]);

  const owl = (m) => setMood(([, n]) => [m, n + 1]);
  const effect = (e) => setFx((f) => ({ ...e, seq: f.seq + 1 }));

  const send = async (answer, tapped, el) => {
    if (busy.current) return;
    busy.current = true;
    const before = cur;
    try {
      const out = await call(`${token}/answer`, { session_id: view.session_id, item_id: cur.id, answer });
      const r = out.result;
      const next = out.session.current;
      if (r.outcome !== "ignored") {
        let say = r.say;
        if (r.reveal?.choice) say = `${say} The answer is ${r.reveal.choice === "yes" ? "yes" : "no"}.`;
        if (r.reveal?.sans?.length) say = `${say} ${r.reveal.sans.length === 1 ? "The move is" : "Moves that work:"} ${r.reveal.sans.join(", ")}.`;
        const good = r.outcome === "right" || r.outcome === "progress";
        setFeedback(say ? [good ? "good" : "hint", say] : null);
        if (r.reveal) setReveal(r.reveal);
        if (r.played) {
          setSlides(r.played.map((m) => [m.slice(0, 2), m.slice(2, 4)]));
          setLast(r.played.length > 1 ? [r.played[1].slice(0, 2), r.played[1].slice(2, 4)] : []);
        } else if (next && before.fen !== next.fen) {
          setSlides(diffMoves(before.fen, next.fen));
        }
        const [x, y] = el ? centerOf(el) : [window.innerWidth / 2, window.innerHeight / 2];
        if (r.outcome === "wrong") {
          sfx.wrong(); owl("think");
          const p = tapped && parseFen(before.fen)[tapped];
          effect({ flash: p ? null : tapped, wiggle: p ? tapped : null, shake: true });
        } else if (r.outcome === "progress") {
          if (before.kind === "tap_reach") { sfx.found((next?.found || []).length - 1); burst(x, y, 6); }
          else sfx.slide();
          const gotStar = before.kind === "stars" && (next?.stars_left || []).length < (before.stars_left || []).length;
          if (gotStar) { owl("happy"); setTimeout(() => { burst(x, y, 24); sfx.star(); }, 300); }
        } else if (r.outcome === "right") {
          sfx.right(); owl("cheer");
          if (before.kind === "stars" || before.kind === "game") sfx.fanfare();
          setTimeout(() => burst(x, y, 24), before.kind === "stars" ? 300 : 0);
          if (before.kind === "tap_reach" && before.from) effect({ beams: before.from, hop: before.from });
          else if (tapped && parseFen(before.fen)[tapped]) effect({ hop: tapped });
          if (!before.test) flyStar(el || document.querySelector(".kids-board"));
        } else if (r.outcome === "done") {
          owl("wow");
        } else if (r.outcome === "skipped" || r.outcome === "revealed") {
          owl("happy");
        }
      }
      setView(out.session);
    } catch (e) {
      setFeedback(["hint", e.message]);
    } finally {
      busy.current = false;
    }
  };

  const movable = cur && (cur.kind === "move_goal" || cur.kind === "game");
  const pieces = cur ? parseFen(cur.fen) : {};
  const childWhite = (cur?.child || "w") === "w";

  const onTap = (sq, el) => {
    if (!cur || cur.finished) return;
    if (!movable) { send({ square: sq }, sq, el); return; }
    const p = pieces[sq];
    if (p && p.white === childWhite) { sfx.pop(); setPick(sq); return; }
    if (pick) { const from = pick; setPick(null); send({ move: from + sq }, sq, el); }
  };

  const next = async () => {
    sfx.pop();
    try {
      const out = await call(`${token}/next`, { session_id: view.session_id });
      if (out.finished_at) onDone(out); else setView(out);
    } catch (e) { setFeedback(["hint", e.message]); }
  };
  const retry = async () => {
    sfx.pop();
    try { setView(await call(`${token}/retry`, { session_id: view.session_id })); setFeedback(null); setLast([]); setSlides([]); owl(""); }
    catch (e) { setFeedback(["hint", e.message]); }
  };

  if (!cur) return null;
  const marks = {};
  (cur.marks || []).forEach((s) => { marks[s] = "marked"; });
  last.forEach((s) => { marks[s] = "last"; });
  (cur.found || []).forEach((s) => { marks[s] = "found"; });
  if (reveal?.squares) reveal.squares.forEach((s) => { if (marks[s] !== "found") marks[s] = "show"; });
  const count = cur.kind === "tap_reach" ? `${(cur.found || []).length} of ${cur.total} squares found`
    : cur.kind === "stars" ? `Moves: ${cur.moves}` : null;

  return (
    <section className="kids-scene">
      <div className="kids-steps" aria-hidden="true">
        {view.parts.map((_, k) => <span key={k} className={k < view.index || (k === view.index && cur.finished) ? "on" : ""} />)}
      </div>
      <Coach mood={mood[0]} bump={mood[1]} say={cur.say} sub={cur.sub} feedback={feedback} />
      <KidsBoard fen={cur.fen} flip={!!cur.flip} marks={marks} stars={cur.kind === "stars" ? cur.stars_left || [] : []}
        picked={pick} slides={slides} effects={fx} onTap={onTap} />
      {cur.kind === "choose" && !cur.finished && (
        <div className="kids-choices">
          {(cur.options || []).map((o) => (
            <button key={o.id} type="button" className={`kids-btn ${o.id === "yes" ? "green" : ""}`}
              onClick={(e) => send({ choice: o.id }, null, e.currentTarget)}>{o.label}</button>
          ))}
        </div>
      )}
      <div className="kids-counter">
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {count && <span className="kids-chip">{count}</span>}
          {cur.kind === "stars" && <span className="kids-chip">Goal: {cur.par}</span>}
          {cur.test && <span className="kids-chip">No hints this time</span>}
        </div>
        <div className="kids-actions">
          {cur.can_skip && <button type="button" className="kids-btn ghost" onClick={() => send({ skip: true })}>I don&apos;t know yet</button>}
          {cur.can_reveal && <button type="button" className="kids-btn ghost" onClick={() => send({ reveal: true })}>Show me</button>}
          {cur.can_retry && <button type="button" className="kids-btn ghost" onClick={retry}>Try again</button>}
          {cur.finished && <button type="button" className="kids-btn green" onClick={next}>Next</button>}
        </div>
      </div>
    </section>
  );
}

function Finished({ view, name, onBack }) {
  const s = view.summary || {};
  const placement = view.kind === "placement";
  const art = CLASS_ART[view.class_id] || CLASS_ART.rook;
  useEffect(() => {
    if (placement || s.passed) {
      const t = setTimeout(() => { sfx.fanfare(); confetti(); }, 250);
      return () => clearTimeout(t);
    }
    return undefined;
  }, [placement, s.passed]);
  return (
    <section className="kids-scene">
      <div className="kids-card">
        {placement ? (
          <>
            <Owl mood="cheer" />
            <h2>Your journey is ready!</h2>
            <p>{s.say}</p>
          </>
        ) : s.passed ? (
          <>
            <Medal piece={art.piece} label={`${art.badge} badge`} />
            <h2>{art.badge}!</h2>
            <p>{s.say}</p>
            <div className="kids-earned">{[0, 1, 2].map((k) => <Star key={k} style={{ animationDelay: `${0.6 + k * 0.18}s` }} />)}</div>
          </>
        ) : (
          <>
            <Owl mood="happy" />
            <h2>Good try, {name}!</h2>
            <p>{s.say}</p>
          </>
        )}
        {s.parent && <div className="kids-parent"><b>For your parent:</b> {s.parent}</div>}
        <button type="button" className="kids-btn big" onClick={onBack}>{placement ? "See my journey" : "Back to the journey"}</button>
      </div>
    </section>
  );
}

export default function FirstStepsClass() {
  const { token } = useParams();
  const [home, setHome] = useState(null);
  const [view, setView] = useState(null);
  const [done, setDone] = useState(null);
  const [error, setError] = useState("");
  const [celebrate, setCelebrate] = useState(false);

  const load = useCallback(async () => {
    try {
      const h = await call(token);
      setHome(h);
      setView(h.open);
    } catch (e) { setError(e.message); }
  }, [token]);
  useEffect(() => { load(); }, [load]);

  const start = async () => {
    sfx.pop();
    try { setDone(null); setCelebrate(false); setView(await call(`${token}/start`, {})); }
    catch (e) { setError(e.message); }
  };
  const back = async () => {
    sfx.pop();
    const passed = done?.summary?.passed;
    setDone(null); setView(null);
    await load();
    setCelebrate(!!passed);
  };

  const name = home?.child_name || "";
  // home.stars counts finished classes; the class in hand adds its own.
  const stars = (home?.stars || 0) + (view ? view.stars : done ? done.stars : 0);
  const sub = done ? (done.kind === "placement" ? "All set" : "Class finished") : view ? `${view.title}` : "Chess Kingdom";

  return (
    <div className="kids">
      <World />
      <div className="kids-wrap">
        <main className="kids-app">
          {home && <Hud name={name} sub={sub} stars={stars} />}
          {error && (
            <section className="kids-card"><Owl mood="think" /><p style={{ color: "#1f2a44" }}>{error}</p></section>
          )}
          {!error && !home && <div className="kids-loading"><Owl mood="happy" />Getting your class ready…</div>}
          {done && <Finished view={done} name={name} onBack={back} />}
          {!done && view && (
            <Session token={token} view={view} setView={setView}
              onDone={(v) => { setDone(v); setView(null); }} />
          )}
          {!done && !view && home && !home.placed && (
            <section className="kids-scene">
              <div className="kids-card">
                <Owl mood="happy" />
                <h2>Hi {name}!</h2>
                <p>I&apos;m Guru, your chess coach. Let&apos;s start with three quick questions, so your classes fit you.</p>
                <button type="button" className="kids-btn big" onClick={start}>Let&apos;s go</button>
              </div>
            </section>
          )}
          {!done && !view && home && home.placed && (
            <section className="kids-scene">
              <JourneyMap classes={home.classes} nextId={home.next?.id} celebrate={celebrate} onPlay={start} />
              <div className="kids-panel">
                <Owl small mood={celebrate ? "cheer" : ""} />
                <p>
                  <b>{home.all_done ? "Every class done!" : home.next?.title}</b>
                  {home.all_done ? "You've finished every class. Time to play real games!"
                    : celebrate ? `Next class unlocked. Ready, ${name}?` : `Hi ${name}! Your next class is ready.`}
                </p>
                {!home.all_done && <button type="button" className="kids-btn" onClick={start}>Play</button>}
              </div>
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
