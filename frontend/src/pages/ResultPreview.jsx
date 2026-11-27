/**
 * /result2 — the game-over pop-up, every state it has, no Lichess game.
 *
 * Same reason /lobby2 exists: the only way to see this screen in the real
 * product is to play a rated game to its end, which makes a visual bug
 * expensive to catch. On 2026-11-27 Mohit won a rated game on time and the
 * screen did not change at all, because the result only ever appeared as a
 * card in a side column.
 *
 * Renders the REAL ResultModal. Nothing is fetched.
 *
 * Unauthenticated and unlinked, like /shell2, /theme2 and /lobby2.
 */
import React, { useState } from "react";
import { ResultModal } from "@/components/coach/LiveGameSurfaces";

const OPPONENT = { username: "vanissimo1", rating: 1450 };

const BASE = {
  rated: true,
  opponent: OPPONENT,
  opponent_rating_after: 1444,
};

const STATES = [
  {
    key: "won",
    label: "Won on time, rating in",
    game: {
      ...BASE,
      status: "outoftime",
      winner: "white",
      our_rating: 1430,
      our_rating_diff: 6,
    },
    review: { ready: true, review_url: "/game/demo" },
  },
  {
    key: "lost",
    label: "Lost by resignation",
    game: {
      ...BASE,
      status: "resign",
      winner: "black",
      our_rating: 1417,
      our_rating_diff: -7,
    },
    review: { ready: true, review_url: "/game/demo" },
  },
  {
    key: "draw",
    label: "Draw by agreement",
    game: {
      ...BASE,
      status: "draw",
      winner: null,
      our_rating: 1424,
      our_rating_diff: 0,
    },
    review: { imported: true, ready: false },
  },
  {
    key: "pending",
    label: "Won, rating not in yet",
    // The real first second of every rated game: the server knows the game is
    // over before it knows what the game was worth.
    game: {
      ...BASE,
      status: "mate",
      winner: "white",
      our_rating: null,
      our_rating_diff: null,
    },
    review: null,
    ratingPending: true,
  },
  {
    key: "casual",
    label: "Casual game, no rating at all",
    game: {
      ...BASE,
      rated: false,
      status: "mate",
      winner: "white",
      our_rating: null,
      our_rating_diff: null,
    },
    review: { imported: true, ready: false },
    ratingPending: true,
  },
];

export default function ResultPreview() {
  const [key, setKey] = useState("won");
  const [open, setOpen] = useState(true);
  const state = STATES.find((s) => s.key === key) || STATES[0];

  return (
    <div className="min-h-screen bg-background px-4 py-8 text-foreground">
      <div className="mx-auto max-w-3xl">
        <h1 className="text-lg font-semibold">The game-over pop-up</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          The real component. Nothing is fetched. Pick a state; close it and it
          comes back with the button below.
        </p>

        <div className="mt-5 flex flex-wrap gap-2">
          {STATES.map((s) => (
            <button
              key={s.key}
              type="button"
              onClick={() => {
                setKey(s.key);
                setOpen(true);
              }}
              className={`flex min-h-[44px] items-center rounded-lg border px-3 text-sm ${
                s.key === key
                  ? "border-primary bg-primary/10 font-medium"
                  : "border-border text-muted-foreground"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>

        {!open && (
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="mt-5 flex min-h-[44px] items-center rounded-lg border border-border px-4 text-sm font-medium"
          >
            Show it again
          </button>
        )}

        <div className="mt-8 rounded-2xl border border-border p-6">
          <p className="text-sm text-muted-foreground">
            Behind the pop-up sits the finished board and its sidebar. Closing
            the pop-up leaves the same result standing there, so nothing is
            lost by dismissing it.
          </p>
        </div>
      </div>

      {open && (
        <ResultModal
          game={state.game}
          ourColor="white"
          review={state.review}
          ratingPending={state.ratingPending}
          onDismiss={() => setOpen(false)}
          onNewGame={() => setOpen(false)}
        />
      )}
    </div>
  );
}
