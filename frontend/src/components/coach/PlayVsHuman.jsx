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
import { Chessboard } from "react-chessboard";

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

function clock(ms) {
  if (ms === null || ms === undefined) return "—";
  const total = Math.max(0, Math.floor(ms / 1000));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
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

  const onDrop = (from, to) => {
    if (!playing || !game.our_turn) return false;
    // Always promote to a queen. Anything else needs a picker, which is a
    // choice for V2, not a reason to block the move now.
    const promotion = to[1] === "8" || to[1] === "1" ? "q" : "";
    act("/move", { uci: `${from}${to}${promotion}` });
    return true; // optimistic; the Lichess stream is the source of truth
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
    return (
      <Shell onExit={onExit} title="Play a human">
        <p className="text-sm text-muted-foreground mb-5">
          A real opponent from the Lichess pool, on this board. Your coach stays
          quiet until the game ends — then your review is waiting.
        </p>
        <div className="flex flex-wrap gap-2 mb-4">
          {timeControls.map((tc) => (
            <button
              key={tc}
              onClick={() => setChosen(tc)}
              data-testid={`live-tc-${tc}`}
              className={`rounded-md border px-4 py-2 text-sm font-medium ${
                chosen === tc
                  ? "border-emerald-500 bg-emerald-500/15"
                  : "border-border hover:bg-muted/40"
              }`}
            >
              {tc}
            </button>
          ))}
        </div>
        <p className="text-xs text-muted-foreground mb-4">{TIME_CONTROL_BLURB}</p>

        <div className="mb-5 flex flex-wrap gap-2">
          {[
            { value: true, label: "Rated" },
            { value: false, label: "Casual" },
          ].map((option) => (
            <button
              key={option.label}
              onClick={() => setRated(option.value)}
              data-testid={`live-rated-${option.label.toLowerCase()}`}
              className={`rounded-md border px-4 py-2 text-sm font-medium ${
                rated === option.value
                  ? "border-emerald-500 bg-emerald-500/15"
                  : "border-border hover:bg-muted/40"
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
        <p className="text-xs text-muted-foreground mb-5">
          {rated
            ? "Rated counts on your Lichess rating, and far more people are waiting in the rated pool — you will be paired much faster."
            : "Casual leaves your rating alone, but the casual pool is much quieter, so you may wait a while."}
        </p>
        <button
          onClick={() => act("/seek", { time_control: chosen, rated })}
          disabled={busy}
          data-testid="live-find-opponent"
          className="rounded-md bg-emerald-600 px-5 py-2.5 font-medium text-white disabled:opacity-50"
        >
          {busy ? "Starting…" : "Find an opponent"}
        </button>
        {error && <Problem text={error} />}
      </Shell>
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

  return (
    <Shell onExit={finished ? onExit : null} title={finished ? "Game over" : "Playing"}>
      {game.reconnecting && (
        <div className="mb-3 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-xs">
          We lost our connection to this game. It is still live on{" "}
          <a className="underline" href={game.lichess_url} target="_blank" rel="noreferrer">
            lichess.org
          </a>{" "}
          — you can finish it there and your review will still arrive.
        </div>
      )}

      <PlayerCard
        name={opponent.username || "Opponent"}
        rating={opponent.rating}
        clockMs={theirClock}
        pieces={theirTaken}
        advantage={edge < 0 ? -edge : 0}
        active={!finished && !game.our_turn}
        testId="live-opponent-card"
      />

      <div className="my-2" data-testid="live-board">
        <Chessboard
          position={shownFen}
          boardOrientation={ourColor}
          onPieceDrop={onDrop}
          arePiecesDraggable={playing && game.our_turn && atLive}
          customBoardStyle={{ borderRadius: "6px" }}
        />
      </div>

      <PlayerCard
        name={(me && me.username) || "You"}
        rating={me && me.rating}
        clockMs={ourClock}
        pieces={ourTaken}
        advantage={edge > 0 ? edge : 0}
        active={!finished && game.our_turn}
        testId="live-our-card"
      />

      {!finished && (
        <p className="mt-2 text-center text-sm text-muted-foreground">
          {game.our_turn ? "Your move" : "Their move"}
        </p>
      )}

      {game.draw_offer_from && game.draw_offer_from !== ourColor && !finished && (
        <div className="mt-4 rounded-md border border-border p-3 text-sm">
          Your opponent offers a draw.
          <div className="mt-2 flex gap-2">
            <button
              onClick={() => act("/draw", { accept: true })}
              className="rounded-md bg-emerald-600 px-3 py-1.5 text-white"
            >
              Accept
            </button>
            <button
              onClick={() => act("/draw", { accept: false })}
              className="rounded-md border border-border px-3 py-1.5"
            >
              Decline
            </button>
          </div>
        </div>
      )}

      {!finished && (
        <div className="mt-4 flex flex-wrap justify-center gap-2">
          <button
            onClick={() => act("/draw", { accept: true })}
            disabled={busy}
            className="rounded-md border border-border px-3 py-1.5 text-sm"
          >
            Offer draw
          </button>
          <button
            onClick={() => act("/resign")}
            disabled={busy}
            data-testid="live-resign"
            className="rounded-md border border-red-500/50 px-3 py-1.5 text-sm text-red-400"
          >
            Resign
          </button>
          <button
            onClick={() => act("/abort")}
            disabled={busy}
            className="rounded-md border border-border px-3 py-1.5 text-sm"
          >
            Abort
          </button>
        </div>
      )}

      <div className="mt-5 rounded-xl border border-border">
        <div className="border-b border-border px-3 py-2 text-xs font-medium text-muted-foreground">
          Moves
        </div>
        <MoveList sans={sans} ply={shownPly} onSeek={setPly} canSeek={finished} />
      </div>
      {finished && (
        <MoveNav ply={shownPly} total={livePly} onSeek={setPly} enabled />
      )}

      {finished ? (
        <div className="mt-5">
          <ResultCard
            game={game}
            ourColor={ourColor}
            review={review}
            onNewGame={() => act("/finish")}
            busy={busy}
          />
        </div>
      ) : (
        /* The sealed panel. During the game it holds no data whatsoever --
           not a number, not a word about the position. That is the rule. */
        <div className="mt-5 rounded-lg border border-border p-4" data-testid="live-review-panel">
          <p className="text-sm text-muted-foreground">
            🔒 Your review opens the moment this game ends. Nothing about this
            position is shown while you are playing — Lichess forbids outside
            help, and we are not going to put your account at risk.
          </p>
        </div>
      )}

      {error && <Problem text={error} />}
    </Shell>
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
