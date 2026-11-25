/**
 * /shell2 — a harness for judging the THEME, not a product screen.
 *
 * It renders the REAL Layout component with a stub user. Layout takes
 * `user` as a prop and every fetch inside it is already .catch()-guarded,
 * so it renders correctly with no backend. That matters: the theme is CSS
 * rules applied to real class names, and this page exercises the real
 * class names rather than a copy of them.
 *
 * It deliberately includes one of each surface the six light-selector
 * rules in index.css target, so a single screenshot shows whether the
 * theme is correct:
 *
 *   .experience-sidebar       from Layout itself
 *   .experience-mobile-nav    from Layout itself, under md
 *   .experience-board-stage   the board below
 *   .experience-coach-cta     the primary button
 *   .experience-primary       the primary button
 *   .experience-eyebrow       the kicker above the heading
 *
 * What it does NOT prove: that any individual product screen is right.
 * Those need a backend and a login. This proves the shell and the tokens.
 *
 * Unauthenticated and unlinked, exactly like /coach2.
 */
import React, { useState } from "react";
import Layout from "@/components/Layout";
import LichessBoard from "@/components/LichessBoard";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";

const FEN = "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b kq - 3 3";

// Shape-only. Layout reads user_id, name and email; nothing is fetched.
const STUB_USER = {
  user_id: "shell_preview",
  name: "Preview",
  email: "preview@example.com",
  rating: 1180,
};

const CARDS = [
  { label: "Games reviewed", value: "38", sub: "of 69 imported" },
  { label: "Clean games", value: "6", sub: "in a row, no blunder" },
  { label: "Working on", value: "Piece safety", sub: "down from 11 to 4" },
];

export default function ShellPreview() {
  // ?dialog=1 opens it on load, so a screenshot can land on the scrim.
  const [open, setOpen] = useState(
    typeof window !== "undefined" &&
      new URLSearchParams(window.location.search).get("dialog") === "1"
  );

  return (
    <Layout user={STUB_USER}>
      <div className="cg-page">
        <div className="experience-eyebrow mb-2">Theme harness</div>
        <h1 className="m-0 font-heading text-display font-bold">
          Every surface the theme touches
        </h1>
        <p className="mt-2 max-w-[60ch] text-body text-muted-foreground">
          One of each: the rail, the mobile bar, cards, a primary button and
          the board surround. If the theme is right, nothing on this page is
          near-black except the board frame.
        </p>

        <div className="mt-7 flex flex-wrap gap-3">
          <button type="button" className="experience-primary rounded-control px-5 py-2.5 font-heading text-note font-semibold">
            Primary action
          </button>
          <button type="button" className="rounded-control border border-border bg-card px-5 py-2.5 font-heading text-note font-semibold">
            Secondary action
          </button>
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="rounded-control border border-border bg-card px-5 py-2.5 font-heading text-note font-semibold"
          >
            Open a dialog
          </button>
        </div>

        <div className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {CARDS.map(({ label, value, sub }) => (
            <div key={label} className="rounded-card border border-border bg-card p-5 shadow-e1">
              <div className="text-meta font-bold uppercase text-muted-foreground">{label}</div>
              <div className="mt-1.5 font-heading text-title font-bold">{value}</div>
              <div className="mt-1 text-note text-muted-foreground">{sub}</div>
            </div>
          ))}
        </div>

        <div className="mt-8 max-w-[460px]">
          <div className="experience-board-stage">
            <div className="aspect-square w-full overflow-hidden">
              <LichessBoard fen={FEN} orientation="white" viewOnly interactive={false} />
            </div>
          </div>
        </div>

        <div className="mt-8 rounded-panel border border-border bg-card p-5 shadow-e2">
          <h2 className="m-0 font-heading text-lead font-bold">A panel of text</h2>
          <p className="mt-2 mb-0 text-body text-muted-foreground">
            Body copy on a card, to check that muted text still reads. This is
            the pair that breaks first when a palette is flipped without
            checking: foreground on card, and muted-foreground on card.
          </p>
        </div>
      </div>

      {/* The SHARED dialog from components/ui, not a copy. This is what
          verifies the scrim change for all 80+ screens that use it. */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>The shared dialog</DialogTitle>
            <DialogDescription>
              This is components/ui/dialog.jsx, unchanged except for the
              scrim. If the page behind is still readable, the change worked.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="rounded-control border border-border bg-background px-4 py-2 font-heading text-note font-semibold"
            >
              Close
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Layout>
  );
}
