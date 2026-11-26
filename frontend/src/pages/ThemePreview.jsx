/**
 * /theme2 — judges the THEME against the real product, not a mood board.
 *
 * It rebuilds the two screens we have live screenshots of (home and learn,
 * captured 2026-11-12 in .playwright-mcp/) using the SHARED primitives the
 * real pages use: Layout, .cg-page, .cg-hero, .cg-panel, .cg-title,
 * .cg-lede, .cg-eyebrow, and the real board. Same classes, same copy, same
 * structure — so a screenshot of this page next to the old one is a fair
 * before/after of the theme and nothing else.
 *
 * It is NOT the real page: the data is fixed and nothing is fetched. It
 * cannot catch a bug inside HomePageNew. It can only show what the shared
 * surface, spacing and type rules do to a page of this shape.
 *
 * Unauthenticated and unlinked, like /coach2 and /shell2.
 */
import React from "react";
import Layout from "@/components/Layout";
import LichessBoard from "@/components/LichessBoard";

const STUB_USER = {
  user_id: "theme_preview",
  name: "Preview",
  email: "preview@example.com",
  rating: 1180,
};

// Copy lifted from the 2026-11-12 live screenshots so the comparison is
// like-for-like. Positions are ordinary openings, not anyone's game.
const LAST_GAME_FEN =
  "r1b1k2r/pp2qppp/2n5/3pp3/1b1P4/2NBPN2/PP3PPP/R1BQ1RK1 w kq - 0 10";
const KEPT_FEN =
  "rnbqkb1r/pppp1ppp/5n2/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3";

const SLIPS = [
  { tone: "flat", text: "The Vienna Game gave a level position." },
  {
    tone: "bad",
    text: "Rf1 nearly cost you a rook. After Nxb3, it would have had no safe square. They played f5 instead.",
  },
  {
    tone: "bad",
    text: "dxe5 gave them a big chance. Qb6 was strong for them, but they played fxe5.",
  },
];

function Dot({ tone }) {
  return (
    <span
      aria-hidden="true"
      className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full"
      style={{
        background:
          tone === "bad"
            ? "hsl(var(--experience-rose))"
            : "hsl(var(--muted-foreground))",
      }}
    />
  );
}

export default function ThemePreview() {
  return (
    <Layout user={STUB_USER}>
      <div className="cg-page">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <p className="m-0 text-note text-muted-foreground">Good evening, Coach.</p>
          <p className="m-0 text-meta uppercase text-muted-foreground">
            Thursday · 7:25 PM
          </p>
        </div>

        {/* ── Last game. The real home page's primary card. ───────────── */}
        <section className="cg-panel mt-5 p-5 md:p-6">
          <div className="flex flex-wrap gap-6">
            <div className="w-full max-w-[260px] shrink-0">
              <div className="experience-board-stage">
                <div className="aspect-square w-full overflow-hidden">
                  <LichessBoard
                    fen={LAST_GAME_FEN}
                    orientation="white"
                    viewOnly
                    interactive={false}
                    showCoordinates={false}
                  />
                </div>
              </div>
              <p className="m-0 mt-2 text-meta text-muted-foreground">
                You played <strong className="font-mono text-foreground">Rf1</strong> here.
              </p>
            </div>

            <div className="min-w-[280px] flex-1">
              <p className="cg-eyebrow m-0">Your last game</p>
              <h2 className="m-0 mt-1.5 font-heading text-title font-bold">
                A winning position slipped away
              </h2>
              <p className="m-0 mt-2 max-w-[54ch] text-note text-muted-foreground">
                You had chances to win, but you missed them, and your opponent
                punished some of your mistakes. Look for your opponent's best
                reply before you move.
              </p>

              <p className="cg-eyebrow m-0 mt-5">It slipped away</p>
              <ul className="m-0 mt-2 list-none space-y-2 p-0">
                {SLIPS.map((s) => (
                  <li key={s.text} className="flex gap-2.5 text-note">
                    <Dot tone={s.tone} />
                    <span>{s.text}</span>
                  </li>
                ))}
              </ul>

              <button
                type="button"
                className="experience-primary mt-5 rounded-control px-4 py-2.5 font-heading text-note font-semibold"
              >
                See the moment →
              </button>
            </div>
          </div>
        </section>

        {/* ── Two cards side by side: the old page stacked these full-width,
               one per band, which is where most of the empty space went. ── */}
        <div className="mt-5 grid gap-5 lg:grid-cols-2">
          <section className="cg-panel p-5">
            <div className="flex gap-4">
              <div className="w-[120px] shrink-0 overflow-hidden rounded-control">
                <div className="aspect-square w-full">
                  <LichessBoard
                    fen={KEPT_FEN}
                    orientation="white"
                    viewOnly
                    interactive={false}
                    showCoordinates={false}
                  />
                </div>
              </div>
              <div className="min-w-0">
                <h3 className="m-0 font-heading text-body font-semibold">
                  You found something here worth keeping.
                </h3>
                <p className="m-0 mt-1.5 text-note text-muted-foreground">
                  You gave up material and it was still the best move on the board.
                </p>
                <button
                  type="button"
                  className="mt-3 rounded-control border border-border bg-background px-3.5 py-2 font-heading text-note font-semibold"
                >
                  See the game
                </button>
              </div>
            </div>
          </section>

          <section className="cg-panel p-5">
            <p className="cg-eyebrow m-0">Learn next</p>
            <h3 className="m-0 mt-1.5 font-heading text-lead font-bold">
              Mate with King + Queen
            </h3>
            <p className="m-0 mt-1.5 text-note text-muted-foreground">
              Haven't seen you use this in a game yet — worth a quick check?
            </p>
            <p className="m-0 mt-1 text-meta text-muted-foreground">
              Fixes: missing an easy win
            </p>
            <button
              type="button"
              className="experience-primary mt-4 rounded-control px-4 py-2.5 font-heading text-note font-semibold"
            >
              Start this lesson →
            </button>
          </section>
        </div>

        {/* ── A strip of numbers. The old pages had nowhere to put these,
               so facts like these lived as sentences inside big cards. ── */}
        <div className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ["Games reviewed", "38", "of 69 imported"],
            ["Clean games", "6", "in a row, no blunder"],
            ["Working on", "Piece safety", "down from 11 to 4"],
            ["Skills studied", "0 of 77", "nothing opened yet"],
          ].map(([label, value, sub]) => (
            <div key={label} className="cg-panel p-4">
              <div className="text-meta font-bold uppercase text-muted-foreground">
                {label}
              </div>
              <div className="mt-1 font-heading text-lead font-bold">{value}</div>
              <div className="mt-0.5 text-meta text-muted-foreground">{sub}</div>
            </div>
          ))}
        </div>

        {/* ── Hero last, so the screenshot shows what it looks like now that
               it is not 165px of empty band. ─────────────────────────── */}
        <section className="cg-hero mt-5">
          <p className="cg-eyebrow m-0">Your coaching room</p>
          <h2 className="cg-title m-0">Let's choose what will help next.</h2>
          <p className="cg-lede m-0">
            Three things are worth your time today. Each one comes from a game
            you actually played, not from a list of topics.
          </p>
        </section>
      </div>
    </Layout>
  );
}
