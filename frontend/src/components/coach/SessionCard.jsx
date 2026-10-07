/**
 * Today's session — what the coach chose, and why.
 *
 * docs/home_session_scope.md
 *
 * Mohit's shape: appreciate · improve · challenge. The mode is a DECISION, not a
 * readout, and it is the thing that makes Home feel like a coach rather than a
 * dashboard. Measured across 70 players the steady state is challenge 41%,
 * improve 30%, appreciate 29%.
 *
 * THERE IS NO "START TODAY'S SESSION" BUTTON because there is no session runner.
 * Each block links to a destination that exists and has been supply-checked
 * server side; a block with nowhere to go is dropped before it is sent. This
 * codebase has a long history of buttons that lead to empty pages and this is
 * not going to be another one.
 *
 * No numbers except minutes, which are a promise about the next few minutes
 * rather than a score — argued for explicitly in the scope.
 */

import { useState, useEffect } from "react";
import { API } from "@/App";
import { Loader2, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";
import { Chessboard } from "react-chessboard";

const KIND_WORDS = {
  appreciate: "Appreciate",
  improve: "Improve",
  challenge: "Challenge",
};

const SIGNAL_WORDS = {
  improving: "Improving",
  working_on: "Working on",
  strength: "Strength",
};

const SIGNAL_ORDER = ["improving", "working_on", "strength"];

function Signals({ signals }) {
  if (!signals?.length) return null;
  const ordered = SIGNAL_ORDER
    .map((kind) => signals.find((s) => s.kind === kind))
    .filter(Boolean);
  if (!ordered.length) return null;
  return (
    <div
      className="mt-6 grid gap-4 border-t border-border/40 pt-5 sm:grid-cols-3"
      data-testid="session-signals"
    >
      {ordered.map((signal) => (
        <div key={signal.kind}>
          <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">
            {SIGNAL_WORDS[signal.kind]}
          </p>
          <p className="mt-1 text-[14px] text-foreground">{signal.label}</p>
        </div>
      ))}
    </div>
  );
}

function Block({ block }) {
  const body = (
    <>
      <span className="min-w-0 flex-1">
        <span className="block text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">
          {KIND_WORDS[block.kind] || block.kind}
        </span>
        <span className="mt-0.5 block text-[14.5px] text-foreground">
          {block.title}
        </span>
        {block.detail && (
          <span className="mt-0.5 block text-[12.5px] text-muted-foreground">
            {block.detail}
          </span>
        )}
        {/* Why this topic and not another. Mohit, 2026-10-07: the card gave no
            reason to care, and a coach that cannot say why it chose is a
            random topic generator with a nice voice. */}
        {block.why && (
          <span className="mt-1.5 block border-l-2 border-emerald-600/40 pl-3 text-[12.5px] leading-relaxed text-foreground">
            {block.why}
          </span>
        )}
      </span>
      <span className="flex shrink-0 items-center gap-2 text-[12px] text-muted-foreground">
        {block.minutes} min
        {block.href && (
          <ChevronRight
            className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5"
            aria-hidden="true"
          />
        )}
      </span>
    </>
  );

  const shared =
    "flex items-center gap-4 py-3 border-b border-border/40 last:border-0";
  if (!block.href) {
    return <div className={shared}>{body}</div>;
  }
  return (
    <Link
      to={block.href}
      data-testid={`session-block-${block.kind}`}
      className={`group -mx-3 rounded-xl px-3 transition-colors hover:bg-foreground/[0.03] dark:hover:bg-foreground/[0.05] ${shared}`}
    >
      {body}
    </Link>
  );
}

export default function SessionCard({ showFocusWhy = true }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API}/home/session`, { credentials: "include" });
        if (res.ok && !cancelled) setData(await res.json());
      } catch (e) {
        // Non-fatal: the card simply does not render.
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div className="cg-panel flex items-center justify-center p-10">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!data?.headline) return null;
  const blocks = data.blocks || [];

  return (
    <section className="cg-panel p-6 md:p-7" data-testid="session-card">
      <p className="cg-eyebrow">From your coach</p>
      <h3 className="mt-2 font-heading text-[22px] leading-[1.15] tracking-[-0.025em] text-foreground md:text-[26px]">
        {data.headline}
      </h3>
      {data.line && (
        <p className="mt-3 max-w-[620px] text-[14px] leading-relaxed text-foreground">
          {data.line}
        </p>
      )}
      {/* On an improve day the headline IS the focus, so the reason belongs
          directly under it rather than buried in a block. */}
      {/* Shown whatever the MODE is -- it explains the focus, and the focus
          exists on a challenge day too. Suppressed when the page already names
          the topic somewhere else: on the curriculum home the lesson card
          carries it directly under "Time management", and printing it again
          here put the same sentence on the screen twice. */}
      {showFocusWhy && data.focus_why && (
        <p className="mt-3 max-w-[620px] border-l-2 border-emerald-600/40 pl-3 text-[13.5px] leading-relaxed text-muted-foreground">
          {data.focus_why}
        </p>
      )}

      {/* The position itself, when the celebration has one. A chess product
          whose home page contains no chess is the thing this replaces. */}
      {data.fen && (
        <div className="mt-5 aspect-square w-full max-w-[280px]">
          <Chessboard
            position={data.fen}
            arePiecesDraggable={false}
            customBoardStyle={{ borderRadius: "8px" }}
          />
        </div>
      )}

      <Signals signals={data.signals} />

      {blocks.length > 0 && (
        <div className="mt-6" data-testid="session-blocks">
          <p className="mb-1 text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">
            Today with your coach
          </p>
          {blocks.map((block) => (
            <Block key={block.kind} block={block} />
          ))}
        </div>
      )}
    </section>
  );
}
