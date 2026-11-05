/**
 * The three links a family receives, with no account: consent, the weekly
 * report and Win it back homework. docs/academy_pilot_scope.md.
 *
 * Each page is reached by a long random token and shows only that child's own
 * page. Words come from the server; no number is rendered.
 */
import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { API } from "@/App";
import LichessBoard from "@/components/LichessBoard";
import ParentReport from "@/components/academy/ParentReport";

function Shell({ children }) {
  return (
    <div className="min-h-screen bg-background px-4 py-6 text-foreground">
      <div className="mx-auto grid w-full max-w-[460px] gap-4">
        <p className="text-sm font-semibold text-muted-foreground">ChessGuru</p>
        {children}
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

function Message({ title, children }) {
  return (
    <section className="grid gap-2 rounded-2xl border bg-card p-5">
      <h1 className="text-2xl font-bold">{title}</h1>
      {children}
    </section>
  );
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

  if (state.loading) return <Shell><p>Loading…</p></Shell>;
  if (state.error) return <Shell><Message title="This link does not work">{state.error}</Message></Shell>;
  const page = state.data;

  if (page.status === "deleted") {
    return (
      <Shell>
        <Message title="Stopped">
          <p>{page.child_name}'s games have been deleted from ChessGuru. Nothing more will be read.</p>
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

  return (
    <Shell>
      <section className="grid gap-3 rounded-2xl border bg-card p-5">
        <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">{page.academy}</p>
        <h1 className="text-2xl font-bold">
          {page.status === "given" ? `${page.child_name} is set up` : `Add ${page.child_name} to ChessGuru`}
        </h1>
        <ul className="grid list-disc gap-1.5 pl-5">
          {page.points.map((p) => <li key={p}>{p}</li>)}
        </ul>
        {page.accounts?.length > 0 && (
          <p className="text-sm text-muted-foreground">Chess account: {page.accounts.join(", ")}</p>
        )}
      </section>

      {page.status === "given" ? (
        <section className="grid gap-3 rounded-2xl border bg-card p-5">
          <p>Thank you. Your first weekly report comes from the coach.</p>
          {!confirmStop ? (
            <button type="button" className="w-fit text-sm underline" onClick={() => setConfirmStop(true)}>
              Stop and delete {page.child_name}'s games
            </button>
          ) : (
            <div className="grid gap-2 rounded-xl border border-red-300 p-3">
              <p>This deletes {page.child_name}'s games and reports. It cannot be undone.</p>
              <div className="flex flex-wrap gap-2">
                <button type="button" disabled={busy} onClick={stop}
                  className="rounded-full bg-red-600 px-4 py-2 font-semibold text-white">
                  Yes, stop and delete
                </button>
                <button type="button" onClick={() => setConfirmStop(false)}
                  className="rounded-full border px-4 py-2">Keep it</button>
              </div>
            </div>
          )}
        </section>
      ) : (
        <form onSubmit={submit} className="grid gap-3 rounded-2xl border bg-card p-5">
          <label htmlFor="consent-name" className="grid gap-1">
            <span className="font-semibold">Your name</span>
            <input id="consent-name" value={name} onChange={(e) => setName(e.target.value)}
              className="rounded-lg border bg-background px-3 py-2" autoComplete="name" />
          </label>
          <label htmlFor="consent-parent" className="flex items-start gap-2">
            <input id="consent-parent" type="checkbox" checked={isParent}
              onChange={(e) => setIsParent(e.target.checked)} className="mt-1" />
            <span>I am {page.child_name}'s parent or guardian.</span>
          </label>
          <label htmlFor="consent-agree" className="flex items-start gap-2">
            <input id="consent-agree" type="checkbox" checked={agree}
              onChange={(e) => setAgree(e.target.checked)} className="mt-1" />
            <span>I agree to the points above.</span>
          </label>
          {error && <p className="text-red-600">{error}</p>}
          <button type="submit" disabled={busy}
            className="w-fit rounded-full bg-foreground px-5 py-2.5 font-semibold text-background disabled:opacity-60">
            I agree
          </button>
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
  if (state.loading) return <Shell><p>Loading…</p></Shell>;
  if (state.error) return <Shell><Message title="This link does not work">{state.error}</Message></Shell>;
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
      <a href={page.stop_link} className="text-sm text-muted-foreground underline">
        Stop the reports and delete the games
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

  if (!game) {
    return <Shell>{error ? <Message title="This link does not work">{error}</Message> : <p>Loading…</p>}</Shell>;
  }

  const myTurn = game.status === "playing" && game.turn === game.my_color;

  const onMove = async (move) => {
    if (!myTurn || busy) return;
    setBusy(true);
    setError("");
    const promotion = move.san && move.san.includes("=") ? "q" : "";
    try {
      setGame(await post(`/academy/play/${token}/move`, { uci: `${move.from}${move.to}${promotion}`, ply: game.ply }));
    } catch (err) {
      setError(err.message);
      load();
    } finally {
      setBusy(false);
    }
  };

  const resign = async () => {
    try { setGame(await post(`/academy/play/${token}/resign`)); } catch (err) { setError(err.message); }
    setConfirmResign(false);
  };

  return (
    <Shell>
      <section className="grid gap-3 rounded-2xl border bg-card p-5">
        <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Class game</p>
        <h1 className="text-2xl font-bold">You are playing {game.opponent_name}</h1>
        <p className="text-muted-foreground">You play {game.my_color}.</p>
        <div className="w-full max-w-[400px]">
          <LichessBoard
            key={`${game.ply}-${game.status}`}
            fen={game.fen}
            orientation={game.my_color}
            interactive={myTurn && !busy}
            viewOnly={!myTurn}
            movableColor={game.my_color}
            lastMove={game.last_move ? [game.last_move.slice(0, 2), game.last_move.slice(2, 4)] : null}
            onMove={onMove}
          />
        </div>
        {game.status === "playing" ? (
          <p className="text-lg font-semibold">{myTurn ? "Your move." : `Waiting for ${game.opponent_name}…`}</p>
        ) : (
          <p className="text-lg font-semibold">{game.result_words || game.status_words}</p>
        )}
        {error && <p className="text-red-600">{error}</p>}
        {game.status === "playing" && (
          !confirmResign ? (
            <button type="button" className="w-fit text-sm underline" onClick={() => setConfirmResign(true)}>Resign</button>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <span>Give up this game?</span>
              <button type="button" className="rounded-full bg-red-600 px-4 py-2 font-semibold text-white" onClick={resign}>Yes, resign</button>
              <button type="button" className="rounded-full border px-4 py-2" onClick={() => setConfirmResign(false)}>Keep playing</button>
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

  useEffect(() => {
    if (state.data?.attempt) setAttempt(state.data.attempt);
  }, [state.data]);

  if (state.loading) return <Shell><p>Loading…</p></Shell>;
  if (state.error) return <Shell><Message title="This link does not work">{state.error}</Message></Shell>;
  const page = state.data;
  if (page.status === "none") {
    return (
      <Shell>
        <Message title="No homework yet">
          <p>Homework comes from a game where {page.child_name} was winning and it slipped away.</p>
        </Message>
      </Shell>
    );
  }

  const playing = attempt?.status === "playing";
  const fen = playing ? attempt.fen : (attempt?.fen || page.fen);

  const start = async () => {
    setError("");
    try {
      setAttempt(await post(`/academy/homework/${token}/start`));
    } catch (err) {
      setError(err.message);
    }
  };

  const onMove = async (move) => {
    if (!playing || thinking) return;
    setThinking(true);
    setError("");
    const promotion = move.san && move.san.includes("=") ? "q" : "";
    try {
      setAttempt(await post(`/academy/homework/${token}/move`, {
        attempt_id: attempt.attempt_id, uci: `${move.from}${move.to}${promotion}`,
      }));
    } catch (err) {
      setError(err.message);
      reload();
    } finally {
      setThinking(false);
    }
  };

  const stop = async () => {
    try {
      setAttempt(await post(`/academy/homework/${token}/stop`, { attempt_id: attempt.attempt_id }));
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <Shell>
      <section className="grid gap-3 rounded-2xl border bg-card p-5">
        <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Homework</p>
        <h1 className="text-2xl font-bold">Win it back</h1>
        {page.lines.map((l) => <p key={l}>{l}</p>)}
        <div className="w-full max-w-[400px]">
          <LichessBoard
            key={`${attempt?.attempt_id || "start"}-${fen}`}
            fen={fen}
            orientation={page.color}
            interactive={playing && !thinking}
            viewOnly={!playing}
            movableColor={page.color}
            onMove={onMove}
          />
        </div>
        {thinking && <p className="text-muted-foreground">The other side is thinking…</p>}
        {attempt && !playing && attempt.result_words && (
          <p className="text-lg font-semibold">{attempt.result_words}</p>
        )}
        {error && <p className="text-red-600">{error}</p>}
        <div className="flex flex-wrap gap-2">
          {!playing && (
            <button type="button" onClick={start}
              className="rounded-full bg-foreground px-5 py-2.5 font-semibold text-background">
              {attempt ? "Try again" : "Start"}
            </button>
          )}
          {playing && (
            <button type="button" onClick={stop} className="rounded-full border px-5 py-2.5">
              Stop here
            </button>
          )}
        </div>
        {playing && <p className="text-sm text-muted-foreground">You play {page.color}. Move a piece to play.</p>}
      </section>
    </Shell>
  );
}
