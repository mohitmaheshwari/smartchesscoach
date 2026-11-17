/**
 * How a stronger player handled the same kind of moment, how the coach wants
 * you to think there, and the same mistake from the other side.
 * docs/similar_moments_scope.md (2026-11-17). Shown after a landing-square
 * drill is done. Every sentence comes from the backend's board facts.
 */
import React, { useEffect, useState } from "react";
import { Eye } from "lucide-react";
import { API } from "@/App";
import { Board, PLAYED, BETTER } from "@/components/coachfile/CoachFileBlocks";

const arrow = (uci, color) => (uci && uci.length >= 4 ? [uci.slice(0, 2), uci.slice(2, 4), color] : null);
const orient = (side) => (side === "Black" ? "black" : "white");

export default function SimilarMoment({ puzzleId }) {
  const [data, setData] = useState(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    let live = true;
    setData(null);
    setShown(false);
    if (!puzzleId) return undefined;
    fetch(`${API}/training/similar-moment`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ puzzle_id: puzzleId }),
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (live) setData(d); })
      .catch(() => {});
    return () => { live = false; };
  }, [puzzleId]);

  if (!data?.available) return null;
  const { stronger, thinking, other_side: other } = data;

  return (
    <section data-testid="similar-moment" className="mt-12 border-t border-border/60 pt-10">
      {stronger && (
        <div data-testid="similar-moment-stronger" className="grid gap-6 md:grid-cols-[240px_1fr] items-start">
          <Board
            fen={stronger.fen}
            orientation={orient(stronger.side)}
            arrows={[arrow(stronger.dangerous_uci, PLAYED), arrow(stronger.played_uci, BETTER)].filter(Boolean)}
            size={240}
          />
          <div>
            <p className="cg-eyebrow">A stronger player, the same kind of moment</p>
            <p className="mt-2 text-lead text-foreground max-w-[520px]">{stronger.words}</p>
            <p className="mt-2 text-meta text-muted-foreground">
              Orange is the move that would have lost the piece. Green is what they played.
            </p>
          </div>
        </div>
      )}

      {thinking && (
        <div data-testid="similar-moment-thinking" className="mt-8 max-w-[560px]">
          <p className="cg-eyebrow flex items-center gap-1.5">
            <Eye className="h-3 w-3" strokeWidth={1.75} />
            How I want you to think here
          </p>
          <p className="mt-2 text-note text-foreground">{thinking.lead}</p>
          <ul className="mt-2 space-y-1">
            {thinking.looks.map((look) => (
              <li key={look.label} className="flex items-baseline justify-between gap-4 text-note">
                <span className="text-muted-foreground">{look.label}</span>
                <span className={look.found === "nothing" ? "text-muted-foreground" : "font-medium text-foreground"}>
                  {look.found}
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-note text-foreground">{thinking.end}</p>
        </div>
      )}

      {other && (
        <div data-testid="similar-moment-other-side" className="mt-10 grid gap-6 md:grid-cols-[240px_1fr] items-start">
          <Board
            fen={other.fen}
            orientation={orient(other.side)}
            arrows={shown ? [arrow(other.solution_uci, BETTER)].filter(Boolean) : []}
            size={240}
          />
          <div>
            <p className="cg-eyebrow">From the other side</p>
            <p className="mt-2 text-note text-foreground max-w-[460px]">{other.words}</p>
            {shown ? (
              <p data-testid="similar-moment-solution" className="mt-3 text-note text-foreground">
                <span className="font-mono">{other.solution_san}</span> wins it. This is what your opponent sees when your piece lands on the wrong square.
              </p>
            ) : (
              <button
                type="button"
                onClick={() => setShown(true)}
                className="mt-3 text-meta text-muted-foreground hover:text-foreground transition-colors"
              >
                Show me
              </button>
            )}
            <p className="mt-3 text-meta text-muted-foreground">A real game position from Lichess.</p>
          </div>
        </div>
      )}
    </section>
  );
}
