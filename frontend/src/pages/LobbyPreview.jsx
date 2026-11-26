/**
 * /lobby2 — the "finding an opponent" screen, both states, no Lichess seek.
 *
 * It exists because the only way to see that screen in the real product is to
 * queue a real rated game, which makes a visual bug expensive to catch. On
 * 2026-11-26 one shipped: the player plate sat on top of the Cancel button and
 * the board was washed out to near-invisibility.
 *
 * Renders the REAL LiveSearchBoard inside the REAL Shell width (max-w-xl),
 * searching on the left and paired on the right, so a screenshot at phone and
 * desktop width is a fair check of both.
 *
 * Unauthenticated and unlinked, like /shell2 and /theme2.
 */
import React from "react";
import LiveSearchBoard from "@/components/coach/LiveSearchBoard";
import PlayVsHuman from "@/components/coach/PlayVsHuman";

const ME = { username: "bhutramohit", rating: 1424 };

export default function LobbyPreview() {
  return (
    <div className="min-h-screen bg-background px-4 py-8 text-foreground">
      <div className="mx-auto max-w-5xl">
        <h1 className="text-lg font-semibold">Finding an opponent — both states</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          The real component at the real column width. Nothing is fetched.
        </p>

        <div className="mt-6 flex flex-wrap gap-8">
          <section className="w-full max-w-xl">
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Searching
            </h2>
            <LiveSearchBoard
              timeControl="10+5"
              rated
              waited={4}
              me={ME}
              opponent={null}
              onCancel={() => {}}
            />
          </section>

          <section className="w-full max-w-xl">
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Paired
            </h2>
            <LiveSearchBoard
              timeControl="10+5"
              rated
              waited={31}
              me={ME}
              opponent={{ username: "vornl49", rating: 1521 }}
              onCancel={() => {}}
            />
          </section>
        </div>

        {/* The step BEFORE the seek. PlayVsHuman falls to its lobby branch
            when nothing is playing, seeking or finished, and its fetches are
            caught — so it renders here with no backend at all. */}
        <section className="mt-10 w-full max-w-xl">
          <h2 className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Before the seek — choosing a game
          </h2>
          <p className="mb-3 text-xs text-muted-foreground">
            The real PlayVsHuman lobby. No backend, so it shows the state a
            signed-out visitor would reach.
          </p>
          <PlayVsHuman onExit={() => {}} />
        </section>
      </div>
    </div>
  );
}
