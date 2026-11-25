/**
 * /coach2/settings — design preview, companion to /coach2.
 *
 * Exists to show the DIALOG treatment on the surface dialogs actually
 * live on. Static: no fetch, no auth, no save. Nothing here writes.
 *
 * The identity shown is a placeholder on purpose. This page is served
 * publicly from chessguru.ai, so no real account, address or rating
 * goes into the markup.
 *
 * Structure follows the three-column settings pattern: rail, a section
 * index, then the sections themselves. The section index matters more
 * than it looks — it is what stops a settings page becoming one long
 * scroll in which "where do I turn the coach down" has no answer.
 */
import React, { useState } from "react";
import {
  User,
  Link2,
  Palette,
  Volume2,
  Swords,
  Brain,
  FileText,
  Pencil,
} from "lucide-react";
import LichessBoard from "@/components/LichessBoard";
import C2Dialog, { initialDialog } from "@/components/coach2/C2Dialog";
import { C2Rail, C2MobileBar } from "@/components/coach2/C2Nav";

const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

const SECTIONS = [
  { label: "Account", Icon: User },
  { label: "Connected accounts", Icon: Link2 },
  { label: "Appearance", Icon: Palette },
  { label: "Sound", Icon: Volume2 },
  { label: "Play", Icon: Swords },
  { label: "Coaching", Icon: Brain },
  { label: "Game review", Icon: FileText },
];

/** Section heading: icon tile, title, one line of what it controls. */
function SectionHead({ Icon, title, sub }) {
  return (
    <div className="mb-3 flex items-center gap-3">
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
      <span>
        <span className="block font-heading text-body font-semibold">{title}</span>
        <span className="block text-meta text-muted-foreground">{sub}</span>
      </span>
    </div>
  );
}

/** One row inside a section card. */
function Row({ title, sub, children, top }) {
  return (
    <div
      className={`flex flex-wrap items-center gap-3 px-4 py-3.5 ${
        top ? "" : "border-t border-border"
      }`}
    >
      <span className="min-w-0 flex-grow">
        <span className="block font-heading text-note font-semibold">{title}</span>
        <span className="block text-meta text-muted-foreground">{sub}</span>
      </span>
      {children}
    </div>
  );
}

function SmallButton({ children, onClick, solid }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="shrink-0 rounded-control border border-border px-3.5 py-1.5 font-heading text-meta font-semibold"
      style={
        solid
          ? {
              background: "hsl(var(--experience-ink))",
              color: "hsl(var(--background))",
              borderColor: "hsl(var(--experience-ink))",
            }
          : { background: "hsl(var(--background))" }
      }
    >
      {children}
    </button>
  );
}

export default function Coach2Settings() {
  const [dialog, setDialog] = useState(initialDialog);
  const [username, setUsername] = useState("");

  const close = () => {
    setDialog(null);
    setUsername("");
  };

  return (
    <div className="experience-v1 coach2 flex min-h-screen flex-wrap bg-background text-foreground">
      <C2Rail active="Settings" />

      <div className="w-full min-w-0 px-5 pb-24 pt-6 md:w-auto md:flex-[999_1_560px] md:px-8 md:pb-10">
        <header className="mb-7">
          <h1 className="m-0 font-heading text-title font-bold">Settings</h1>
          <p className="m-0 mt-1.5 text-note text-muted-foreground">
            Your account, and how the coach behaves while you play, train and review.
          </p>
        </header>

        <div className="flex flex-wrap items-start gap-8">
          {/* Section index */}
          <nav
            aria-label="Settings sections"
            className="hidden w-[210px] shrink-0 flex-col gap-0.5 md:flex"
          >
            {SECTIONS.map(({ label, Icon }, i) => (
              <a
                key={label}
                href={`#${label.replace(/\s+/g, "-").toLowerCase()}`}
                className={`flex items-center gap-2.5 rounded-card px-3 py-2.5 text-note font-semibold no-underline ${
                  i === 0 ? "" : "text-muted-foreground"
                }`}
                style={i === 0 ? { background: "hsl(var(--muted))" } : undefined}
              >
                <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span>{label}</span>
              </a>
            ))}
          </nav>

          <div className="flex w-full min-w-0 flex-col gap-7 md:max-w-[620px] md:flex-[1_1_420px]">
            {/* Account */}
            <section id="account">
              <SectionHead Icon={User} title="Account" sub="Who you are on ChessGuru." />
              <div className="rounded-card border border-border bg-card shadow-e1">
                <div className="flex flex-wrap items-center gap-3.5 px-4 py-4">
                  <span
                    className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full font-heading text-lead font-bold"
                    style={{
                      background: "hsl(var(--experience-ink))",
                      color: "hsl(var(--background))",
                    }}
                  >
                    C
                  </span>
                  <span className="min-w-0 flex-grow">
                    <span className="block font-heading text-body font-semibold">
                      coach_test
                    </span>
                    <span className="block text-meta text-muted-foreground">
                      coach-test@example.com
                    </span>
                  </span>
                  <SmallButton>
                    <span className="inline-flex items-center gap-1.5">
                      <Pencil className="h-3.5 w-3.5" aria-hidden="true" />
                      Edit
                    </span>
                  </SmallButton>
                </div>
                <Row
                  title="Free plan"
                  sub="2 coached games a week. Reviews stay free and unlimited."
                >
                  <SmallButton solid>Upgrade</SmallButton>
                </Row>
              </div>
            </section>

            {/* Connected accounts */}
            <section id="connected-accounts">
              <SectionHead
                Icon={Link2}
                title="Connected accounts"
                sub="Where your games are imported from."
              />
              <div className="rounded-card border border-border bg-card shadow-e1">
                <Row top title="Lichess" sub="Connected. Last import 2 hours ago.">
                  <SmallButton onClick={() => setDialog("disconnect")}>
                    Disconnect
                  </SmallButton>
                </Row>
                <Row title="Chess.com" sub="Not connected.">
                  <SmallButton onClick={() => setDialog("connect")}>Connect</SmallButton>
                </Row>
              </div>
            </section>

            {/* Appearance */}
            <section id="appearance">
              <SectionHead Icon={Palette} title="Appearance" sub="Theme, board and pieces." />
              <div className="rounded-card border border-border bg-card p-4 shadow-e1">
                <div
                  className="mx-auto max-w-[260px] rounded-card p-3"
                  style={{
                    background: "var(--c2-frame)",
                    boxShadow: "0 14px 34px hsl(var(--experience-shadow) / 0.18)",
                  }}
                >
                  <div className="aspect-square w-full overflow-hidden rounded">
                    <LichessBoard
                      fen={START_FEN}
                      orientation="white"
                      viewOnly
                      interactive={false}
                      showCoordinates={false}
                    />
                  </div>
                </div>
                <p className="m-0 mt-3.5 text-center text-meta text-muted-foreground">
                  Brown board, cburnett pieces — the Lichess default, unchanged.
                </p>
              </div>
            </section>
          </div>
        </div>
      </div>

      <C2MobileBar active="Settings" />

      {/* The input dialog — the case the reference screenshot shows. */}
      <C2Dialog
        open={dialog === "connect"}
        onOpenChange={(v) => (v ? setDialog("connect") : close())}
        title="Connect Chess.com"
        description="Enter your Chess.com username. We import your games and read your rating — we never ask for your password."
        cancelLabel="Cancel"
        confirmLabel="Connect"
        confirmDisabled={username.trim().length === 0}
        onConfirm={close}
      >
        <label className="block">
          <span className="sr-only">Chess.com username</span>
          <input
            className="c2-input w-full rounded-control border border-border bg-background px-3.5 py-2.5 text-body text-foreground"
            placeholder="Chess.com username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </label>
      </C2Dialog>

      <C2Dialog
        open={dialog === "disconnect"}
        onOpenChange={(v) => (v ? setDialog("disconnect") : close())}
        title="Disconnect Lichess?"
        description="Your imported games and every review stay exactly where they are. New games just stop arriving."
        cancelLabel="Keep it connected"
        confirmLabel="Disconnect"
        onConfirm={close}
      />
    </div>
  );
}
