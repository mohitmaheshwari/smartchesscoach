/**
 * /coach2 — design preview for the Play-with-Coach redesign.
 *
 * NOT wired to the backend. No fetch, no session, no auth. It renders one
 * fixed position so the LOOK can be judged without a running API. The live
 * page stays /play-with-coach; nothing here changes it.
 *
 * What it is proposing, against the live screen:
 *   1. A thick warm frame around the board with the coordinates IN the frame.
 *      Today: 6-12px of #141618 (index.css .experience-board-stage) and the
 *      coordinates sit on the squares.
 *   2. Player strips at full board width, above and below.
 *   3. Our existing LIGHT tokens instead of the near-black page, so the
 *      shadows already in our CSS actually composite. A black shadow is
 *      ~12.5x more visible on the cream background than on #141618.
 *   4. Cards rather than pills for the decisions, all on one neutral
 *      surface. Deliberately NOT one colour family per card.
 *   5. Labelled icons in the rail and the bottom bar, never icon-only.
 *
 * The board is the REAL component (LichessBoard -> chessground, cburnett
 * pieces, #f0d9b5/#b58863 squares). The board is not what changed.
 *
 * Colours: every surface comes from existing tokens via `bg-background`,
 * `bg-card`, `border-border`, `text-muted-foreground`. The only two new
 * values are --c2-frame and --c2-coord, declared as HSL triplets in
 * index.css like every other token in that file. No new hex literal enters
 * src, so the design-system ratchet in .githooks/pre-commit stays at 209.
 */
import React, { useState } from "react";
import {
  BookOpen,
  MessageSquare,
  Flag,
  ChevronRight,
  ChevronLeft,
  Check,
  Settings as SettingsIcon,
} from "lucide-react";
import LichessBoard from "@/components/LichessBoard";
import C2Dialog, { initialDialog } from "@/components/coach2/C2Dialog";
import { C2Rail, C2MobileBar } from "@/components/coach2/C2Nav";

// Italian Game after 1.e4 e5 2.Nf3 Nc6 3.Bc4 — black to move.
// The coaching line below only claims what is true here: Bc4 is the ONE
// attacker on f7, and f7 is guarded ONLY by the king.
const FEN = "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b kq - 3 3";
const LAST_MOVE = ["f1", "c4"];
const ARROWS = [["c4", "f7", "green"]];

const FILES = ["a", "b", "c", "d", "e", "f", "g", "h"];
const RANKS = ["8", "7", "6", "5", "4", "3", "2", "1"];

const ACTIONS = [
  {
    id: "ask",
    title: "Ask the coach",
    sub: "Stuck? Get a hint before you move.",
    Icon: MessageSquare,
  },
  {
    id: "lessons",
    title: "Lesson library",
    sub: "18 traps and 10 endgames to play through.",
    Icon: BookOpen,
  },
  {
    id: "end",
    title: "End the game",
    sub: "Stop here and go straight to your review.",
    Icon: Flag,
  },
];

/** One player row: avatar, name, sub-line, clock. */
function PlayerStrip({ initial, name, sub, clock, active, accent }) {
  return (
    <div className="flex items-center gap-3 rounded-card border border-border bg-card px-4 py-2.5 shadow-e1">
      <span
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full font-heading text-body font-bold"
        style={
          accent
            ? { background: "var(--cg-accent)", color: "hsl(var(--experience-ink))" }
            : { background: "hsl(var(--experience-ink))", color: "hsl(var(--background))" }
        }
      >
        {initial}
      </span>
      <span className="min-w-0 flex-grow">
        <span className="block font-heading text-body font-semibold">{name}</span>
        <span className="block text-meta text-muted-foreground">{sub}</span>
      </span>
      <span
        className={`shrink-0 rounded-control px-3 py-1.5 font-mono text-lead ${
          active ? "text-foreground" : "text-muted-foreground"
        }`}
        style={{
          background: active
            ? "rgb(var(--cg-accent-rgb) / 0.18)"
            : "hsl(var(--muted))",
        }}
      >
        {clock}
      </span>
    </div>
  );
}

export default function Coach2() {
  // Only here so the dialogs can be opened and judged. The preview still
  // makes no network call of any kind.
  const [dialog, setDialog] = useState(initialDialog);

  return (
    <div className="experience-v1 coach2 flex min-h-screen flex-wrap bg-background text-foreground">
      <C2Rail active="Play" />

      <div className="w-full min-w-0 px-5 pb-24 pt-6 md:w-auto md:flex-[999_1_560px] md:px-8 md:pb-10">
        {/* Mobile back row */}
        <div className="mb-4 flex items-center gap-2 md:hidden">
          <a
            href="/home"
            aria-label="Back"
            className="flex h-9 w-9 items-center justify-center rounded-control text-muted-foreground"
          >
            <ChevronLeft className="h-5 w-5" aria-hidden="true" />
          </a>
          <span className="flex-grow font-heading text-body font-semibold">
            Play with Coach
          </span>
          <a
            href="/coach2/settings"
            aria-label="Settings"
            className="flex h-9 w-9 items-center justify-center rounded-control text-muted-foreground"
          >
            <SettingsIcon className="h-5 w-5" aria-hidden="true" />
          </a>
        </div>

        <header className="mb-6 flex flex-wrap items-end justify-between gap-5">
          <div>
            <div
              className="mb-1.5 hidden text-meta font-bold uppercase md:block"
              style={{ color: "var(--c2-green)" }}
            >
              Play with Coach
            </div>
            <h1 className="m-0 font-heading text-title font-bold">Italian Game</h1>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="inline-flex items-center rounded-full border border-border bg-card px-3 py-1.5 text-meta font-semibold text-muted-foreground">
              10 + 0 rapid
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-meta font-semibold text-muted-foreground">
              <Check
                className="h-3.5 w-3.5"
                style={{ color: "var(--c2-green)" }}
                aria-hidden="true"
              />
              Guardian on
            </span>
          </div>
        </header>

        <div className="c2row flex flex-wrap items-start gap-8">
          {/* Board column */}
          <div className="c2col w-full min-w-0 md:max-w-[600px] md:flex-[1_1_440px]">
            <PlayerStrip
              initial="C"
              name="Coach"
              sub="Plays like 1200 · thinking…"
              clock="9:42"
              active
            />

            {/* The frame. This is the single biggest visual change. */}
            <div
              className="c2frame relative my-3 rounded-panel p-4 md:p-6"
              style={{
                background: "var(--c2-frame)",
                boxShadow:
                  "0 26px 70px hsl(var(--experience-shadow) / 0.20), 0 1px 0 rgb(255 255 255 / 0.16) inset",
              }}
            >
              <div className="aspect-square w-full overflow-hidden rounded">
                <LichessBoard
                  fen={FEN}
                  orientation="white"
                  viewOnly
                  interactive={false}
                  lastMove={LAST_MOVE}
                  arrows={ARROWS}
                  showCoordinates={false}
                />
              </div>
              {/* Coordinates live IN the frame, not on the squares */}
              <div
                aria-hidden="true"
                className="absolute bottom-4 left-0 top-4 flex w-4 flex-col items-center justify-around text-meta font-semibold md:bottom-6 md:top-6 md:w-6"
                style={{ color: "var(--c2-coord)" }}
              >
                {RANKS.map((r) => (
                  <span key={r}>{r}</span>
                ))}
              </div>
              <div
                aria-hidden="true"
                className="absolute bottom-0 left-4 right-4 flex h-4 items-center justify-around text-meta font-semibold md:left-6 md:right-6 md:h-6"
                style={{ color: "var(--c2-coord)" }}
              >
                {FILES.map((f) => (
                  <span key={f}>{f}</span>
                ))}
              </div>
            </div>

            <PlayerStrip
              initial="Y"
              name="You"
              sub="1180 · you played Bc4"
              clock="10:00"
              accent
            />
          </div>

          {/* Coach panel — cards, not pills */}
          <aside className="flex w-full min-w-0 flex-col gap-3.5 md:max-w-[400px] md:flex-[1_1_330px]">
            <div className="rounded-panel border border-border bg-card p-5 shadow-e2">
              <div className="mb-4 flex items-center gap-3">
                <span
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full font-heading text-note font-bold"
                  style={{
                    background: "hsl(var(--experience-ink))",
                    color: "hsl(var(--background))",
                  }}
                >
                  C
                </span>
                <span className="flex-grow font-heading text-body font-semibold">Coach</span>
                <span
                  className="rounded-full px-3 py-1 font-mono text-meta"
                  style={{
                    background: "rgb(var(--cg-accent-rgb) / 0.18)",
                    color: "var(--c2-green)",
                  }}
                >
                  on Bc4
                </span>
              </div>
              <p className="m-0 text-body">
                Your bishop on c4 is aimed straight at f7, and only his king guards that
                square. There is nothing to take yet — but keep that square in mind. Once
                you get a second attacker onto it, he has to deal with it.
              </p>
              <div className="mt-4 flex items-center gap-5 border-t border-border pt-4">
                <button
                  type="button"
                  className="cg-link inline-flex items-center gap-1.5 text-note font-semibold"
                >
                  Show me the squares
                  <ChevronRight className="h-4 w-4" aria-hidden="true" />
                </button>
                <button
                  type="button"
                  className="text-note font-semibold text-muted-foreground"
                >
                  Not useful
                </button>
              </div>
            </div>

            {ACTIONS.map(({ id, title, sub, Icon }) => (
              <button
                key={title}
                type="button"
                onClick={() => setDialog(id)}
                className="flex w-full items-center gap-3.5 rounded-card border border-border bg-card px-4 py-3.5 text-left shadow-e1"
              >
                <span
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-control"
                  style={{ background: "rgb(var(--cg-accent-rgb) / 0.16)" }}
                >
                  <Icon
                    className="h-4 w-4"
                    style={{ color: "var(--c2-green)" }}
                    aria-hidden="true"
                  />
                </span>
                <span className="min-w-0 flex-grow">
                  <span className="block font-heading text-body font-semibold">{title}</span>
                  <span className="block text-note text-muted-foreground">{sub}</span>
                </span>
                <ChevronRight
                  className="h-4 w-4 shrink-0 text-muted-foreground"
                  aria-hidden="true"
                />
              </button>
            ))}

            <div className="rounded-card border border-border bg-card px-4 py-4 shadow-e1">
              <div className="mb-3 text-meta font-bold uppercase text-muted-foreground">
                Moves
              </div>
              {/* 4rem columns, not 1fr: a 7-character SAN (Qxd8=Q+) measures
                  ~59px at the 14px `note` step in JetBrains Mono. */}
              <div className="grid grid-cols-[1.75rem_4rem_4rem] gap-x-2.5 gap-y-1 font-mono text-note">
                <span className="text-muted-foreground">1.</span>
                <span>e4</span>
                <span className="text-muted-foreground">e5</span>
                <span className="text-muted-foreground">2.</span>
                <span>Nf3</span>
                <span className="text-muted-foreground">Nc6</span>
                <span className="text-muted-foreground">3.</span>
                <span className="font-medium" style={{ color: "var(--c2-green)" }}>
                  Bc4
                </span>
                <span className="text-muted-foreground">…</span>
              </div>
            </div>
          </aside>
        </div>
      </div>

      <C2MobileBar active="Play" />

      <C2Dialog
        open={dialog === "end"}
        onOpenChange={(v) => setDialog(v ? "end" : null)}
        title="End the game here?"
        description="You are 3 moves in. The coach will still write your review, but a 3-move game does not give it much to go on."
        cancelLabel="Keep playing"
        confirmLabel="End and review"
        onConfirm={() => setDialog(null)}
      />

      <C2Dialog
        open={dialog === "ask"}
        onOpenChange={(v) => setDialog(v ? "ask" : null)}
        title="Ask for a hint?"
        description="The coach will point at the square that matters, not give you the move. This uses one of your 5 hints for this game."
        cancelLabel="Not yet"
        confirmLabel="Give me a hint"
        onConfirm={() => setDialog(null)}
      />

      <C2Dialog
        open={dialog === "lessons"}
        onOpenChange={(v) => setDialog(v ? "lessons" : null)}
        title="Leave this game for a lesson?"
        description="Your game is saved and you can come straight back to this position."
        cancelLabel="Stay here"
        confirmLabel="Open the library"
        onConfirm={() => setDialog(null)}
      />
    </div>
  );
}
