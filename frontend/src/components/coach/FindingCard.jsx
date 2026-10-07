/**
 * The one thing worth interrupting the player with.
 *
 * Mohit, 2026-10-07: "it's not the representation only, it's the data too that
 * is not giving me enough value on home page". He was right. The page had been
 * built out of weekly summaries -- "you have played on most days this month" --
 * which is something a player can work out without us, while the findings that
 * would stop them were measured and left in a terminal.
 *
 * This is the first thing on the page, above the lesson, and it shows exactly
 * ONE finding. Two findings is a report again.
 *
 * It carries a NUMBER on purpose, against the standing rule. "You have lost
 * games you were winning on the clock" is a shrug; "seventy-one games you were
 * winning, lost on the clock" is the entire point. Counts of games only --
 * rates, percentages and scores remain banned, because those are the ones that
 * mislead. See services/striking_finding.py.
 */
import { useState, useEffect } from "react";
import { API } from "@/App";

export default function FindingCard() {
  const [finding, setFinding] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/home/session`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (!cancelled) setFinding(d?.finding || null); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  if (!finding?.headline) return null;

  return (
    <section
      className="mb-8 overflow-hidden rounded-[28px] border border-amber-500/30 bg-gradient-to-br from-amber-500/[0.10] via-card to-rose-400/[0.05] p-6 shadow-[0_24px_70px_-42px_rgba(15,23,42,0.35)] md:p-8"
      data-testid="finding-card"
    >
      <p className="cg-eyebrow !text-[10px]">Something I want you to see</p>
      <h2 className="mt-3 max-w-[760px] font-heading text-[26px] leading-[1.1] tracking-[-0.03em] text-foreground md:text-[34px]">
        {finding.headline}
      </h2>
      {finding.line && (
        <p className="mt-4 max-w-[620px] text-[14.5px] leading-relaxed text-foreground">
          {finding.line}
        </p>
      )}
      {finding.next && (
        <p className="mt-4 max-w-[620px] border-l-2 border-amber-600/50 pl-4 text-[14px] leading-relaxed text-muted-foreground">
          {finding.next}
        </p>
      )}
    </section>
  );
}
