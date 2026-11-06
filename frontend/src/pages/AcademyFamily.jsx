/**
 * The links a family receives, with no account: consent, the weekly report,
 * Win it back homework and class games. docs/academy_pilot_scope.md.
 *
 * Each page is reached by a long random token and shows only that child's own
 * page. Words come from the server; no number is rendered. All four use the
 * kids look (components/kids): the chess kingdom, Guru the owl, the wooden board.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { API } from "@/App";
import "@/components/kids/kids.css";
import ParentReport from "@/components/academy/ParentReport";
import KidsBoard, { diffMoves, parseFen } from "@/components/kids/KidsBoard";
import { Owl, World } from "@/components/kids/KidsArt";
import { confetti, sfx } from "@/components/kids/kidsFx";

function Shell({ children }) {
  return (
    <div className="kids">
      <World />
      <div className="kids-wrap">
        <main className="kids-app">
          <div className="kids-hud" style={{ padding: "8px 14px" }}>
            <div className="kids-avatar" aria-hidden="true">C</div>
            <div className="kids-who">ChessGuru<small>Chess Kingdom</small></div>
          </div>
          {children}
        </main>
      </div>
    </div>
  );
}

function useFamilyPage(path) {
  const [state, setState] = useState({ loading: true });
  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API}${path}`);
      const body = await res.json().catch(() => ({}));
      if (!res.ok) setState({ error: body.detail || "This link is not valid." });
      else setState({ data: body });
    } catch {
      setState({ error: "We could not reach ChessGuru. Check your internet and try again." });
    }
  }, [path]);
  useEffect(() => { load(); }, [load]);
  return [state, load];
}

async function post(path, body) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Something went wrong. Try again.");
  return data;
}

function Message({ title, mood = "happy", children }) {
  return (
    <section className="kids-card kids-scene">
      <Owl mood={mood} />
      <h2>{title}</h2>
      {children}
    </section>
  );
}

function Loading() {
  return <Shell><div className="kids-loading"><Owl mood="happy" />Loading…</div></Shell>;
}

/** Pieces slide from where they were to where they are, whenever the position changes. */
function useSlides(fen) {
  const prev = useRef(fen);
  const [slides, setSlides] = useState([]);
  useEffect(() => {
    if (fen && prev.current && fen !== prev.current) setSlides(diffMoves(prev.current, fen));
    prev.current = fen;
  }, [fen]);
  return slides;
}

/** Tap a piece of your colour, then a square. Pawns reaching the end become queens. */
function useTapMove(fen, myColor, enabled, onMove) {
  const [pick, setPick] = useState(null);
  useEffect(() => { setPick(null); }, [fen]);
  const pieces = parseFen(fen || "");
  const white = myColor === "white";
  const onTap = (sq) => {
    if (!enabled) return;
    const p = pieces[sq];
    if (p && p.white === white) { sfx.pop(); setPick(sq); return; }
    if (!pick) return;
    const from = pick;
    const moving = pieces[from];
    const lastRank = white ? "8" : "1";
    const promotion = moving && moving.type === "p" && sq[1] === lastRank ? "q" : "";
    setPick(null);
    onMove(`${from}${sq}${promotion}`);
  };
  return [pick, onTap];
}

// ---------------------------------------------------------------------------
// consent
// ---------------------------------------------------------------------------
export function FamilyConsent() {
  const { token } = useParams();
  const [state, reload] = useFamilyPage(`/academy/consent/${token}`);
  const [name, setName] = useState("");
  const [agree, setAgree] = useState(false);
  const [isParent, setIsParent] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmStop, setConfirmStop] = useState(false);

  if (state.loading) return <Loading />;
  if (state.error) return <Shell><Message title="This link does not work" mood="think"><p>{state.error}</p></Message></Shell>;
  const page = state.data;

  if (page.status === "deleted") {
    return (
      <Shell>
        <Message title="Stopped">
          <p>Everything about {page.child_name} has been deleted from ChessGuru. Nothing more will be read.</p>
        </Message>
      </Shell>
    );
  }

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await post(`/academy/consent/${token}`, { parent_name: name, agree, is_parent: isParent });
      confetti();
      reload();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const stop = async () => {
    setBusy(true);
    try {
      await post(`/academy/consent/${token}/withdraw`);
      reload();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const given = page.status === "given";
  return (
    <Shell>
      <section className="kids-card kids-scene">
        <Owl mood={given ? "cheer" : "happy"} />
        <p className="kids-eyebrow">{page.academy}</p>
        <h2>{given ? `${page.child_name} is set up` : `Add ${page.child_name} to ChessGuru`}</h2>
        <ul className="kids-points">
          {page.points.map((p) => <li key={p}>{p}</li>)}
        </ul>
        {page.accounts?.length > 0 && (
          <p style={{ fontSize: 14 }}>Chess account: {page.accounts.join(", ")}</p>
        )}
      </section>

      {given ? (
        <section className="kids-card">
          <p style={{ color: "#1f2a44" }}>Thank you. Your first weekly report comes from the coach.</p>
          {!confirmStop ? (
            <button type="button" className="kids-link" onClick={() => setConfirmStop(true)}>
              Stop and delete {page.child_name}&apos;s data
            </button>
          ) : (
            <div className="kids-danger">
              <p style={{ color: "#1f2a44" }}>This deletes everything we hold about {page.child_name}. It cannot be undone.</p>
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                <button type="button" disabled={busy} onClick={stop} className="kids-btn red">Yes, stop and delete</button>
                <button type="button" onClick={() => setConfirmStop(false)} className="kids-btn ghost">Keep it</button>
              </div>
            </div>
          )}
        </section>
      ) : (
        <form onSubmit={submit} className="kids-card" style={{ justifyItems: "stretch" }}>
          <label htmlFor="consent-name" className="kids-field">
            <span>Your name</span>
            <input id="consent-name" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
          </label>
          <label htmlFor="consent-parent" className="kids-check">
            <input id="consent-parent" type="checkbox" checked={isParent} onChange={(e) => setIsParent(e.target.checked)} />
            <span>I am {page.child_name}&apos;s parent or guardian.</span>
          </label>
          <label htmlFor="consent-agree" className="kids-check">
            <input id="consent-agree" type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
            <span>I agree to the points above.</span>
          </label>
          {error && <p className="kids-error">{error}</p>}
          <button type="submit" disabled={busy} className="kids-btn green big" style={{ justifySelf: "start" }}>I agree</button>
        </form>
      )}
    </Shell>
  );
}

// ---------------------------------------------------------------------------
// report
// ---------------------------------------------------------------------------
export function FamilyReport() {
  const { token } = useParams();
  const [state] = useFamilyPage(`/academy/report/${token}`);
  if (state.loading) return <Loading />;
  if (state.error) return <Shell><Message title="This link does not work" mood="think"><p>{state.error}</p></Message></Shell>;
  const page = state.data;
  if (page.status === "deleted") {
    return <Shell><Message title="Stopped"><p>This report has been stopped and deleted.</p></Message></Shell>;
  }
  if (page.status === "none") {
    return (
      <Shell>
        <Message title={`${page.child_name}'s report is on its way`}>
          <p>The coach sends the first report after a week of games.</p>
        </Message>
      </Shell>
    );
  }
  return (
    <Shell>
      <ParentReport report={page.report} homeworkLink={page.homework_link} />
      <a href={page.stop_link} className="kids-link" style={{ justifySelf: "center" }}>
        Stop the reports and delete the data
      </a>
    </Shell>
  );
}

// ---------------------------------------------------------------------------
// class game: two children of one batch
// ---------------------------------------------------------------------------
const POLL_MS = 2500;

export function FamilyClassGame() {
  const { token } = useParams();
  const [game, setGame] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmResign, setConfirmResign] = useState(false);
  const [fx, setFx] = useState({ seq: 0 });

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API}/academy/play/${token}`);
      const body = await res.json().catch(() => ({}));
      if (!res.ok) { setError(body.detail || "This link is not valid."); return; }
      setGame(body);
    } catch {
      setError("We could not reach ChessGuru. Check your internet.");
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  // Wait for the other side: poll only while it is their turn.
  const waiting = game && game.status === "playing" && game.turn !== game.my_color;
  useEffect(() => {
    if (!waiting) return undefined;
    const id = setInterval(load, POLL_MS);
    return () => clearInterval(id);
  }, [waiting, load]);

  const finished = game && game.status !== "playing";
  const won = finished && /won/i.test(game.result_words || "");
  useEffect(() => { if (won) { sfx.fanfare(); confetti(); } }, [won]);

  const myTurn = !!game && game.status === "playing" && game.turn === game.my_color;
  const slides = useSlides(game?.fen);

  const onMove = async (uci) => {
    if (!myTurn || busy) return;
    setBusy(true);
    setError("");
    try {
      setGame(await post(`/academy/play/${token}/move`, { uci, ply: game.ply }));
      sfx.slide();
    } catch (err) {
      setError(err.message);
      sfx.wrong();
      setFx((f) => ({ shake: true, seq: f.seq + 1 }));
      load();
    } finally {
      setBusy(false);
    }
  };
  const [pick, onTap] = useTapMove(game?.fen, game?.my_color, myTurn && !busy, onMove);

  if (!game) {
    return error ? <Shell><Message title="This link does not work" mood="think"><p>{error}</p></Message></Shell> : <Loading />;
  }

  const resign = async () => {
    try { setGame(await post(`/academy/play/${token}/resign`)); } catch (err) { setError(err.message); }
    setConfirmResign(false);
  };
  const last = game.last_move ? { [game.last_move.slice(0, 2)]: "last", [game.last_move.slice(2, 4)]: "last" } : {};

  return (
    <Shell>
      <section className="kids-scene">
        <div className="kids-coach">
          <Owl mood={finished ? (won ? "cheer" : "happy") : myTurn ? "" : "think"} />
          <div className="kids-bubble">
            <p className="kids-eyebrow" style={{ margin: 0 }}>Class game</p>
            <div className="kids-say">You are playing {game.opponent_name}</div>
            <div className="kids-sub">You play {game.my_color}.</div>
            <div className="kids-feedback good">
              {game.status === "playing" ? (myTurn ? "Your move." : `Waiting for ${game.opponent_name}…`) : (game.result_words || game.status_words)}
            </div>
          </div>
        </div>
        <KidsBoard fen={game.fen} flip={game.my_color === "black"} marks={last} picked={pick} slides={slides} effects={fx} onTap={onTap} />
        {error && <p className="kids-error">{error}</p>}
        {game.status === "playing" && (
          !confirmResign ? (
            <button type="button" className="kids-link" style={{ justifySelf: "start" }} onClick={() => setConfirmResign(true)}>Resign</button>
          ) : (
            <div className="kids-danger">
              <span style={{ color: "#1f2a44" }}>Give up this game?</span>
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                <button type="button" className="kids-btn red" onClick={resign}>Yes, resign</button>
                <button type="button" className="kids-btn ghost" onClick={() => setConfirmResign(false)}>Keep playing</button>
              </div>
            </div>
          )
        )}
      </section>
    </Shell>
  );
}

// ---------------------------------------------------------------------------
// homework
// ---------------------------------------------------------------------------
export function FamilyHomework() {
  const { token } = useParams();
  const [state, reload] = useFamilyPage(`/academy/homework/${token}`);
  const [attempt, setAttempt] = useState(null);
  const [error, setError] = useState("");
  const [thinking, setThinking] = useState(false);
  const [fx, setFx] = useState({ seq: 0 });

  useEffect(() => {
    if (state.data?.attempt) setAttempt(state.data.attempt);
  }, [state.data]);

  const page = state.data;
  const playing = attempt?.status === "playing";
  const fen = page ? (playing ? attempt.fen : (attempt?.fen || page.fen)) : null;
  const slides = useSlides(fen);
  const kept = attempt && !playing && attempt.status === "kept";
  useEffect(() => { if (kept) { sfx.fanfare(); confetti(); } }, [kept]);

  const onMove = async (uci) => {
    if (!playing || thinking) return;
    setThinking(true);
    setError("");
    try {
      setAttempt(await post(`/academy/homework/${token}/move`, { attempt_id: attempt.attempt_id, uci }));
      sfx.slide();
    } catch (err) {
      setError(err.message);
      sfx.wrong();
      setFx((f) => ({ shake: true, seq: f.seq + 1 }));
      reload();
    } finally {
      setThinking(false);
    }
  };
  const [pick, onTap] = useTapMove(fen, page?.color, playing && !thinking, onMove);

  if (state.loading) return <Loading />;
  if (state.error) return <Shell><Message title="This link does not work" mood="think"><p>{state.error}</p></Message></Shell>;
  if (page.status === "none") {
    return (
      <Shell>
        <Message title="No homework yet">
          <p>Homework comes from a game where {page.child_name} was winning and it slipped away.</p>
        </Message>
      </Shell>
    );
  }

  const start = async () => {
    setError("");
    sfx.pop();
    try {
      setAttempt(await post(`/academy/homework/${token}/start`));
    } catch (err) {
      setError(err.message);
    }
  };

  const stop = async () => {
    try {
      setAttempt(await post(`/academy/homework/${token}/stop`, { attempt_id: attempt.attempt_id }));
    } catch (err) {
      setError(err.message);
    }
  };

  const status = thinking ? "The other side is thinking…"
    : attempt && !playing && attempt.result_words ? attempt.result_words
      : playing ? `You play ${page.color}. Tap a piece, then a square.` : null;

  return (
    <Shell>
      <section className="kids-scene">
        <div className="kids-coach">
          <Owl mood={kept ? "cheer" : thinking ? "think" : "happy"} />
          <div className="kids-bubble">
            <p className="kids-eyebrow" style={{ margin: 0 }}>Homework</p>
            <div className="kids-say">Win it back</div>
            {page.lines.map((l) => <div className="kids-sub" key={l}>{l}</div>)}
            {status && <div className={`kids-feedback ${kept ? "good" : ""}`}>{status}</div>}
          </div>
        </div>
        <KidsBoard fen={fen} flip={page.color === "black"} picked={pick} slides={slides} effects={fx} onTap={onTap} />
        {error && <p className="kids-error">{error}</p>}
        <div className="kids-actions">
          {!playing && <button type="button" onClick={start} className="kids-btn green big">{attempt ? "Try again" : "Start"}</button>}
          {playing && <button type="button" onClick={stop} className="kids-btn ghost">Stop here</button>}
        </div>
      </section>
    </Shell>
  );
}
