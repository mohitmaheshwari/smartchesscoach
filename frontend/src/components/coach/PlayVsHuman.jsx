/**
 * Play vs Human — a real Lichess opponent, on our board.
 *
 * Mohit, 2026-11-25: "a separate section inside play with coach, play vs human,
 * something and then shows lichess board".
 *
 * The one rule this component exists under: while the game is live, NOTHING
 * here may help the player choose a move. No evaluation, no arrow, no hint, no
 * "are you sure?", no opening name. Lichess forbids outside help during a
 * Board-API game, and the penalty is an engine mark on the player's own
 * account, not on us. The server enforces it structurally (live_play_guard.py
 * refuses every other /api path mid-game); this file must not try to be clever
 * around that.
 *
 * So the review is *sealed*: during the game the panel says only that it will
 * open, and it holds no data at all. The endpoint that resolves the review is
 * not even in the guard's allowlist, so it cannot answer until the game ends.
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import LichessBoard from "@/components/LichessBoard";

import LiveSearchBoard from "./LiveSearchBoard";
import {
  MoveList,
  MoveNav,
  PlayerCard,
  ResultCard,
  captured as capturedFrom,
  replay,
} from "./LiveGameSurfaces";

const API = process.env.REACT_APP_BACKEND_URL || "";
const POLL_MS = 1500;

const TIME_CONTROL_BLURB =
  "Lichess allows Rapid and slower for games played through other apps, so these are the three we offer.";

const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

/**
 * "10+5" -> "10 min + 5s a move". Arithmetic on the time control, not a speed
 * class: Lichess's Bullet/Blitz/Rapid thresholds are a table we have not
 * checked, and a wrong label on a screen about time would be its own bug.
 */
function describeTimeControl(tc) {
  const [base, inc] = String(tc).split("+");
  const minutes = `${base} min`;
  return Number(inc) > 0 ? `${minutes} + ${inc}s a move` : minutes;
}

async function call(path, options = {}) {
  const response = await fetch(`${API}/api/coach/play/live${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  let body = null;
  try {
    body = await response.json();
  } catch (_) {
    body = null;
  }
  if (!response.ok) {
    const detail = body && body.detail;
    const error = new Error(
      (detail && (detail.message || detail)) || "Something went wrong."
    );
    error.status = response.status;
    error.reason = detail && detail.reason;
    throw error;
  }
  return body;
}

export default function PlayVsHuman({ onExit }) {
  const [timeControls, setTimeControls] = useState(["10+0", "10+5", "15+10"]);
  const [chosen, setChosen] = useState("10+0");
  // Rated by default because the casual pool is a fraction of the size, and
  // casual-by-default reads as "nobody is here". It moves the player's real
  // Lichess rating, so the choice is on screen, not hidden in a default.
  const [rated, setRated] = useState(true);
  // The player's real Lichess handle and rating, shown on the search screen.
  const [me, setMe] = useState(null);
  // Which half-move the board is showing. Only meaningful once the game ends.
  const [ply, setPly] = useState(0);
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [reconnect, setReconnect] = useState(null);
  const [review, setReview] = useState(null);
  const pollRef = useRef(null);

  const game = state && state.game;
  const seeking = Boolean(state && state.seeking);
  const playing = Boolean(game && !game.finished);

  useEffect(() => {
    let alive = true;
    call("/time-controls")
      .then((data) => {
        if (alive && data && data.options) {
          setTimeControls(data.options);
          setChosen(data.default || data.options[0]);
          if (typeof data.default_rated === "boolean") setRated(data.default_rated);
          if (data.me) setMe(data.me);
        }
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  const poll = useCallback(async () => {
    try {
      const next = await call("/state");
      setState(next);
      setError(null);
    } catch (e) {
      if (e.status === 409) setReconnect(e.message);
      else setError(e.message);
    }
  }, []);

  // Poll while there is anything to watch. Stop once the game is over, so a
  // finished board does not keep a timer alive for the rest of the session.
  useEffect(() => {
    poll();
    pollRef.current = setInterval(poll, POLL_MS);
    return () => clearInterval(pollRef.current);
  }, [poll]);

  useEffect(() => {
    if (game && game.finished && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, [game]);

  // The game is over, so the seal is lifted and we may ask where the review is.
  useEffect(() => {
    if (!game || !game.finished) return;
    let alive = true;
    let tries = 0;
    const ask = async () => {
      tries += 1;
      try {
        const data = await call(`/review/${game.game_id}`);
        if (!alive) return;
        setReview(data);
        if (!data.ready && tries < 20) setTimeout(ask, 3000);
      } catch (_) {
        if (alive && tries < 20) setTimeout(ask, 3000);
      }
    };
    ask();
    return () => {
      alive = false;
    };
  }, [game]);

  // Seconds spent searching, so a quiet pool reads as "still looking" rather
  // than "this button does nothing".
  const [waited, setWaited] = useState(0);
  useEffect(() => {
    if (!seeking) {
      setWaited(0);
      return undefined;
    }
    const started = Date.now();
    const tick = setInterval(
      () => setWaited(Math.floor((Date.now() - started) / 1000)),
      1000
    );
    return () => clearInterval(tick);
  }, [seeking]);

  const act = async (path, body) => {
    setBusy(true);
    setError(null);
    try {
      await call(path, { method: "POST", body: JSON.stringify(body || {}) });
      await poll();
    } catch (e) {
      if (e.status === 409) setReconnect(e.message);
      else setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  // LichessBoard hands us {from, to, ...}; it already promotes to a queen
  // internally, so a promoting move needs the q suffix in the UCI we relay.
  const onBoardMove = (moveData) => {
    if (!moveData || !playing || !game.our_turn) return;
    const { from, to } = moveData;
    const promoting =
      (to[1] === "8" || to[1] === "1") &&
      String(moveData.piece || "").toLowerCase().includes("p");
    act("/move", { uci: `${from}${to}${promoting ? "q" : ""}` });
  };

  // ---------------------------------------------------------------- reconnect

  if (reconnect) {
    return (
      <Shell onExit={onExit} title="Play a human">
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-5 text-sm">
          <p className="font-medium mb-2">One-time Lichess permission needed</p>
          <p className="text-muted-foreground mb-4">{reconnect}</p>
          <a
            href={`${API}/api/oauth/lichess/connect`}
            className="inline-flex items-center rounded-md bg-amber-500 px-4 py-2 font-medium text-black"
          >
            Reconnect Lichess
          </a>
          <p className="mt-3 text-xs text-muted-foreground">
            You play on Lichess against a real person. We never suggest moves
            during the game — Lichess forbids it, and breaking that would put
            your account at risk.
          </p>
        </div>
      </Shell>
    );
  }

  // ------------------------------------------------------------------- lobby

  if (!playing && !seeking && !(game && game.finished)) {
    const choice = (selected) =>
      `rounded-xl border px-3 py-2.5 text-left transition-colors ${
        selected
          ? "border-emerald-500 bg-emerald-500/10 ring-1 ring-emerald-500/40"
          : "border-border hover:border-muted-foreground/40 hover:bg-muted/40"
      }`;

    return (
      <div className="mx-auto w-full max-w-5xl px-4 py-8">
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-2xl font-semibold leading-tight">Play a human</h2>
            <p className="mt-1.5 max-w-lg text-sm text-muted-foreground">
              A real opponent from the Lichess pool, on this board. Your coach
              stays quiet until the game ends — then your review is waiting.
            </p>
          </div>
          {onExit && (
            <button
              onClick={onExit}
              data-testid="live-exit"
              className="shrink-0 text-sm text-muted-foreground hover:text-foreground"
            >
              Close
            </button>
          )}
        </div>

        {/* The board is here before a single choice is made, because this is a
            chess screen and it should look like one the moment it opens. It is
            also literally the next thing the player sees: the search screen
            animates this same board, then the game takes it over. */}
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_23rem] lg:items-start">
          <div className="min-w-0">
            <div className="rounded-2xl border border-border bg-card p-3">
              <LichessBoard
                fen={START_FEN}
                orientation="white"
                interactive={false}
                viewOnly
                arrows={[]}
                circles={[]}
                highlights={[]}
                showCoordinates={false}
                edgeCoordinates
                disableArrows
              />
            </div>
            <p className="mt-2.5 text-center text-xs text-muted-foreground">
              Lichess decides your colour when it pairs you.
            </p>
          </div>

          <aside className="flex flex-col gap-3.5">
            {me && me.username ? (
              <div
                className="flex items-center gap-3 rounded-2xl border border-border bg-card px-4 py-3"
                data-testid="live-me"
              >
                <div
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-muted text-sm font-semibold"
                  aria-hidden
                >
                  {me.username.trim().charAt(0).toUpperCase()}
                </div>
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold leading-tight">
                    {me.username}
                    {me.rating ? (
                      <span className="ml-1 font-normal text-muted-foreground">
                        ({me.rating})
                      </span>
                    ) : null}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    Playing as you, on Lichess
                  </div>
                </div>
              </div>
            ) : null}

            <div className="rounded-2xl border border-border bg-card p-4">
              <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Time control
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2">
                {timeControls.map((tc) => (
                  <button
                    key={tc}
                    onClick={() => setChosen(tc)}
                    data-testid={`live-tc-${tc}`}
                    className={choice(chosen === tc)}
                  >
                    <div className="text-base font-semibold leading-none">{tc}</div>
                    <div className="mt-1 text-[11px] leading-tight text-muted-foreground">
                      {describeTimeControl(tc)}
                    </div>
                  </button>
                ))}
              </div>
              <p className="mt-3 text-xs text-muted-foreground">{TIME_CONTROL_BLURB}</p>
            </div>

            <div className="rounded-2xl border border-border bg-card p-4">
              <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Rating
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2">
                {[
                  { value: true, label: "Rated", sub: "Counts" },
                  { value: false, label: "Casual", sub: "Does not count" },
                ].map((option) => (
                  <button
                    key={option.label}
                    onClick={() => setRated(option.value)}
                    data-testid={`live-rated-${option.label.toLowerCase()}`}
                    className={choice(rated === option.value)}
                  >
                    <div className="text-base font-semibold leading-none">
                      {option.label}
                    </div>
                    <div className="mt-1 text-[11px] leading-tight text-muted-foreground">
                      {option.sub}
                    </div>
                  </button>
                ))}
              </div>
              <p className="mt-3 text-xs text-muted-foreground">
                {rated
                  ? "Rated counts on your Lichess rating, and far more people are waiting in the rated pool — you will be paired much faster."
                  : "Casual leaves your rating alone, but the casual pool is much quieter, so you may wait a while."}
              </p>
            </div>

            <button
              onClick={() => act("/seek", { time_control: chosen, rated })}
              disabled={busy}
              data-testid="live-find-opponent"
              className="w-full rounded-xl bg-emerald-600 px-5 py-3.5 text-base font-semibold text-white transition-colors hover:bg-emerald-500 disabled:opacity-50"
            >
              {busy ? "Starting…" : `Find an opponent · ${chosen}`}
            </button>

            <p className="text-center text-xs text-muted-foreground">
              We never suggest a move while the game is live. Lichess forbids
              outside help, and we are not putting your account at risk.
            </p>
            {error && <Problem text={error} />}
          </aside>
        </div>
      </div>
    );
  }

  // ----------------------------------------------------------------- seeking

  if (seeking && !playing) {
    const pool = state.seek || {};
    return (
      <Shell onExit={onExit} title="Looking for an opponent">
        <LiveSearchBoard
          timeControl={pool.time_control || chosen}
          rated={pool.rated === false ? false : true}
          waited={waited}
          me={me}
          opponent={null}
          onCancel={() => act("/seek/cancel")}
          busy={busy}
        />
        <p className="mt-3 text-center text-xs text-muted-foreground">
          Keep this tab open — a Lichess seek lives only as long as this
          connection. The board takes over the moment someone accepts.
        </p>
        {waited >= 45 && (
          <p className="mt-2 text-center text-xs text-amber-400" data-testid="live-slow-pool">
            {pool.rated === false
              ? "The casual pool is quiet. Cancel and try Rated — many more people are waiting there."
              : "Quiet right now. Cancel and try 10+0 if you picked a less common time control."}
          </p>
        )}
        {error && <Problem text={error} />}
      </Shell>
    );
  }

  // -------------------------------------------------------------- the board

  const finished = Boolean(game && game.finished);
  const opponent = (game && game.opponent) || {};
  const ourColor = (game && game.color) || "white";

  const { sans, fens } = replay(game.initial_fen, game.moves);
  const livePly = sans.length;
  // While the game is live the board always shows the live position. Browsing
  // only unlocks once it is over -- a board that can show some OTHER position
  // mid-game is one refactor away from showing an analysed one.
  const shownPly = finished ? Math.min(ply, livePly) : livePly;
  const shownFen = fens[shownPly] || game.fen;
  const atLive = shownPly === livePly;

  const taken = capturedFrom(shownFen);
  const ourTaken = ourColor === "white" ? taken.white : taken.black;
  const theirTaken = ourColor === "white" ? taken.black : taken.white;
  const edge = ourColor === "white" ? taken.advantage : -taken.advantage;

  const ourClock = ourColor === "white" ? game.white_time_ms : game.black_time_ms;
  const theirClock = ourColor === "white" ? game.black_time_ms : game.white_time_ms;
  // Whose clock is running is the server's call, not ours: it is the only side
  // that knows whether the stream is still alive and whose turn it is. While we
  // are browsing a finished game, neither clock runs.
  const theirColor = ourColor === "white" ? "black" : "white";
  const ourClockRunning = game.ticking === ourColor;
  const theirClockRunning = game.ticking === theirColor;
  const ourTurn = Boolean(!finished && game.our_turn);

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-5">
      {game.reconnecting && (
        <div className="mb-4 rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-xs">
          We lost our connection to this game. It is still live on{" "}
          <a className="underline" href={game.lichess_url} target="_blank" rel="noreferrer">
            lichess.org
          </a>{" "}
          — you can finish it there and your review will still arrive.
        </div>
      )}

      {/* Board left, game panel right: the shape every chess site uses,
          because the board wants the room and the move list wants height. */}
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-start">
        <div className="min-w-0">
          <PlayerCard
            name={opponent.username || "Opponent"}
            rating={opponent.rating}
            clockMs={theirClock}
            clockAgeMs={game.clock_age_ms}
            running={theirClockRunning}
            pieces={theirTaken}
            advantage={edge < 0 ? -edge : 0}
            active={!finished && !ourTurn}
            testId="live-opponent-card"
          />

          <div className="my-2.5" data-testid="live-board">
            <LichessBoard
              fen={shownFen}
              orientation={ourColor}
              onMove={onBoardMove}
              interactive={playing && ourTurn && atLive}
              viewOnly={!(playing && ourTurn && atLive)}
              movableColor={ourColor}
              arrows={[]}
              circles={[]}
              highlights={[]}
              showCoordinates={false}
              edgeCoordinates
              disableArrows={!finished}
            />
          </div>

          <PlayerCard
            name={(me && me.username) || "You"}
            rating={me && me.rating}
            clockMs={ourClock}
            clockAgeMs={game.clock_age_ms}
            running={ourClockRunning}
            pieces={ourTaken}
            advantage={edge > 0 ? edge : 0}
            active={ourTurn}
            testId="live-our-card"
          />

          {!finished && (
            <div className="mt-3 flex flex-wrap items-center justify-center gap-2">
              <span
                className={`mr-1 text-sm font-medium ${
                  ourTurn ? "text-emerald-400" : "text-muted-foreground"
                }`}
                data-testid="live-turn"
              >
                {ourTurn ? "Your move" : "Their move"}
              </span>
              <button
                onClick={() => act("/draw", { accept: true })}
                disabled={busy}
                className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-muted/40"
              >
                Offer draw
              </button>
              <button
                onClick={() => act("/resign")}
                disabled={busy}
                data-testid="live-resign"
                className="rounded-lg border border-rose-500/50 px-3 py-1.5 text-sm text-rose-400 hover:bg-rose-500/10"
              >
                Resign
              </button>
              <button
                onClick={() => act("/abort")}
                disabled={busy}
                className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-muted/40"
              >
                Abort
              </button>
            </div>
          )}

          {game.draw_offer_from && game.draw_offer_from !== ourColor && !finished && (
            <div className="mt-3 rounded-xl border border-border p-3 text-sm">
              Your opponent offers a draw.
              <div className="mt-2 flex gap-2">
                <button
                  onClick={() => act("/draw", { accept: true })}
                  className="rounded-lg bg-emerald-600 px-3 py-1.5 text-white"
                >
                  Accept
                </button>
                <button
                  onClick={() => act("/draw", { accept: false })}
                  className="rounded-lg border border-border px-3 py-1.5"
                >
                  Decline
                </button>
              </div>
            </div>
          )}
        </div>

        <aside className="flex min-w-0 flex-col gap-4">
          <div className="rounded-2xl border border-border bg-card">
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <div>
                <div className="text-base font-semibold leading-tight">Play a Human</div>
                <div className="text-xs text-muted-foreground">
                  {game.rated ? "Rated" : "Casual"} · {game.speed || "rapid"} · on Lichess
                </div>
              </div>
              {finished && (
                <button
                  onClick={onExit}
                  data-testid="live-exit"
                  className="text-sm text-muted-foreground hover:text-foreground"
                >
                  Close
                </button>
              )}
            </div>
            <MoveList sans={sans} ply={shownPly} onSeek={setPly} canSeek={finished} />
            {finished && (
              <div className="border-t border-border px-2 pb-2">
                <MoveNav ply={shownPly} total={livePly} onSeek={setPly} enabled />
              </div>
            )}
          </div>

          {finished ? (
            <ResultCard
              game={game}
              ourColor={ourColor}
              review={review}
              onNewGame={() => act("/finish")}
              busy={busy}
            />
          ) : (
            <div
              className="rounded-2xl border border-border p-4"
              data-testid="live-review-panel"
            >
              <p className="text-sm text-muted-foreground">
                🔒 Your review opens the moment this game ends. Nothing about
                this position is shown while you are playing — Lichess forbids
                outside help, and we are not going to put your account at risk.
              </p>
            </div>
          )}

          {error && <Problem text={error} />}
        </aside>
      </div>
    </div>
  );
}

function Problem({ text }) {
  return (
    <p className="mt-4 text-sm text-red-400" data-testid="live-error">
      {text}
    </p>
  );
}

function Shell({ title, children, onExit }) {
  return (
    <div className="mx-auto max-w-xl px-4 py-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">{title}</h2>
        {onExit && (
          <button
            onClick={onExit}
            data-testid="live-exit"
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            Close
          </button>
        )}
      </div>
      {children}
    </div>
  );
}
